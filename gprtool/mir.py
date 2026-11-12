# SPDX-License-Identifier: MIT
"""Physical-register liveness at inline asm markers, from post-register-allocation MIR.

The MIR is `llc -stop-before=prolog-epilog` of the bitcode FlyDSL hands to the external llc (the same llc, flags
and input: its code is identical to the kernel's). Block live-ins there are the register allocator's own (from its
live intervals), so a register is live at a marker exactly when the allocator keeps a value in it; within a block
the walk is backward from the union of the successors' live-ins. Function-wide reserved registers (stack pointer,
the WWM registers holding SGPR spill lanes, the long-branch pair, the EXEC copy) are reported apart: always kept.
"""
import re
import subprocess
from pathlib import Path

from regs import LLVM, split, units

FLAGS = {"implicit-def", "implicit", "def", "killed", "dead", "undef", "renamable", "early-clobber", "internal",
         "debug-use"}
REG = re.compile(r"((?:(?:implicit-def|implicit|def|killed|dead|undef|renamable|early-clobber|internal|debug-use)\s+)*)"
                 r"\$([a-z][a-z0-9_]*)(?::(0x[0-9a-fA-F]+))?")
ASMTEXT = re.compile(r'INLINEASM &"((?:[^"\\]|\\.)*)"')


def post_ra_mir(bc, out, llvm=LLVM, opt="-O2"):
    subprocess.run([str(llvm / "bin/llc"), str(bc), "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1250", opt,
                    "-stop-before=prolog-epilog", "-o", str(out)], check=True)
    return out


class Instr:
    __slots__ = ("text", "op", "defs", "uses", "pdefs", "asm")

    def __init__(self, line):
        self.text = line
        body = line.split(" :: ")[0]
        body = re.sub(r",\s*debug-(location|instr-number) [^,]*", "", body)
        lhs, rhs = (body.split(" = ", 1) if re.match(r"^[^\"]*? = ", body) else ("", body))
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", rhs)
        self.op = m.group(1) if m else ""
        a = ASMTEXT.search(rhs)
        self.asm = a.group(1).encode().decode("unicode_escape") if a else None
        self.defs, self.uses, self.pdefs = set(), set(), set()
        for part, is_lhs in ((lhs, True), (rhs, False)):
            for fl, name, mask in REG.findall(part):
                if name == "noreg":
                    continue
                fl = set(fl.split())
                us, partial = units(name, int(mask, 16) if mask else None)
                if is_lhs or "implicit-def" in fl or "def" in fl:
                    (self.pdefs if partial else self.defs).update(us)
                    if partial:
                        self.uses.update(us)   # a 16-bit write keeps the other half
                elif "undef" not in fl:
                    self.uses.update(us)


def parse(path):
    """-> blocks {id: dict(succs, liveins, instrs)}, block order, reserved units, machineFunctionInfo extras."""
    text = Path(path).read_text()
    text = text[text.index("\n---\nname:"):]   # the machine function (after the embedded IR module)
    body = text[re.search(r"^body:", text, re.M).start():]
    blocks, order, cur = {}, [], None
    for line in body.splitlines()[1:]:
        if line.startswith("...") or line.startswith("---"):
            break
        m = re.match(r"^  bb\.(\d+)", line)
        if m:
            cur = int(m.group(1))
            blocks[cur] = dict(succs=[], liveins=set(), instrs=[])
            order.append(cur)
            continue
        s = line.strip()
        if cur is None or not s or s.startswith(";"):
            continue
        if s.startswith("successors:"):
            blocks[cur]["succs"] = [int(x) for x in re.findall(r"%bb\.(\d+)", s)]
        elif s.startswith("liveins:"):
            for name, mask in re.findall(r"\$([a-z][a-z0-9_]*)(?::(0x[0-9a-fA-F]+))?", s):
                blocks[cur]["liveins"].update(units(name, int(mask, 16) if mask else None)[0])
        elif s in ("{", "}") or s.startswith("BUNDLE"):
            continue
        else:
            blocks[cur]["instrs"].append(Instr(s))
    # fall-through successors are listed explicitly in MIR ("successors:"); a block without the line has none
    head = text[:re.search(r"^body:", text, re.M).start()]
    reserved = set()
    for key in ("stackPtrOffsetReg", "sgprForEXECCopy", "longBranchReservedReg", "frameOffsetReg"):
        m = re.search(rf"^\s+{key}:\s+'\$([a-z0-9_]+)'", head, re.M)
        if m:
            reserved.update(units(m.group(1))[0])
    m = re.search(r"^\s+wwmReservedRegs:\n((?:\s+- '\$[a-z0-9_]+'\n)+)", head, re.M)
    if m:
        for name in re.findall(r"\$([a-z0-9_]+)", m.group(1)):
            reserved.update(units(name)[0])
    return blocks, order, reserved


def marker_liveness(blocks, order, match):
    """{tag: [dict(block, index, before, after, defs, uses)]} for every INLINEASM whose text `match` maps to a tag
    (None: not a marker). before / after: units live just before / after the instruction."""
    out = {}
    for b in order:
        blk = blocks[b]
        live = set()
        for s in blk["succs"]:
            live |= blocks[s]["liveins"]
        for i in range(len(blk["instrs"]) - 1, -1, -1):
            ins = blk["instrs"][i]
            after = set(live)
            live = (live - ins.defs) | ins.uses
            if ins.asm is not None:
                tag = match(ins.asm)
                if tag is not None:
                    out.setdefault(tag, []).append(dict(block=b, index=i, before=set(live), after=after,
                                                        defs=set(ins.defs) | ins.pdefs, uses=set(ins.uses)))
    return out


def region_defs(blocks, start, stop):
    """Units defined on some path from instruction start=(block, index) (exclusive) to stop=(block, index)
    (exclusive), not passing stop."""
    work = [(start[0], start[1] + 1)]
    seen_blocks = set()
    defs = set()
    while work:
        b, i0 = work.pop()
        ins = blocks[b]["instrs"]
        hit_stop = False
        for i in range(i0, len(ins)):
            if (b, i) == stop:
                hit_stop = True
                break
            defs |= ins[i].defs | ins[i].pdefs
        if hit_stop:
            continue
        for s in blocks[b]["succs"]:
            if s not in seen_blocks:
                seen_blocks.add(s)
                work.append((s, 0))
    return defs


SPILL_KINDS = ("sgpr_to_vgpr_lane", "sgpr_from_vgpr_lane", "sgpr_scratch_save", "sgpr_scratch_restore",
               "vgpr_scratch_save", "vgpr_scratch_restore")


def spill_kind(op):
    if op.startswith("SI_SPILL_S") and "TO_VGPR" in op:
        return "sgpr_to_vgpr_lane"
    if op.startswith("SI_RESTORE_S"):
        return "sgpr_from_vgpr_lane"
    if op.startswith("SI_SPILL_S"):
        return "sgpr_scratch_save" if op.endswith("_SAVE") else "sgpr_scratch_restore"
    if op.startswith("SI_SPILL_V") or op.startswith("SI_SPILL_AV"):
        return "vgpr_scratch_save" if op.endswith("_SAVE") else "vgpr_scratch_restore"
    return None


def spill_counts(blocks):
    c = dict.fromkeys(SPILL_KINDS, 0)
    for blk in blocks.values():
        for ins in blk["instrs"]:
            k = spill_kind(ins.op)
            if k:
                c[k] += 1
    c["sgpr"] = sum(v for k, v in c.items() if k.startswith("sgpr_"))
    c["vgpr"] = c["vgpr_scratch_save"] + c["vgpr_scratch_restore"]
    return c


def spill_sites(blocks, order, match):
    """Every spill / restore instruction: dict(kind, block, region = the last marker before it in layout order,
    text, def = for an SGPR spill, the instruction (same block) that last defined the spilled register)."""
    out, region = [], None
    for b in order:
        ins = blocks[b]["instrs"]
        for i, x in enumerate(ins):
            if x.asm is not None and match(x.asm) is not None:
                region = match(x.asm)
                continue
            kind = spill_kind(x.op)
            if kind is None:
                continue
            d = None
            if kind in ("sgpr_to_vgpr_lane", "sgpr_scratch_save"):
                src = x.uses - x.defs
                for k in range(i - 1, -1, -1):
                    if (ins[k].defs | ins[k].pdefs) & src and not ins[k].op.startswith("SI_"):
                        d = ins[k].text.split(" :: ")[0][:160]
                        break
            out.append(dict(kind=kind, block=b, region=region, text=x.text.split(" :: ")[0][:120], defn=d))
    return out


def remat_units(blocks, at, us):
    """Units of `us` live at instruction at=(block, index) whose every reaching definition is an immediate move
    (the allocator can rematerialize them instead of keeping them)."""
    preds = {}
    for b, blk in blocks.items():
        for s in blk["succs"]:
            preds.setdefault(s, set()).add(b)
    IMM = re.compile(r"^(S_MOV_B32|S_MOV_B64|V_MOV_B32_e32|V_MOV_B32_e64|V_MOV_B64_e32|S_MOV_B64_IMM_PSEUDO|"
                     r"V_MOV_B64_PSEUDO|S_MOVK_I32)$")

    def is_imm(ins):
        if not IMM.match(ins.op):
            return False
        src = ins.text.split(" = ", 1)[1] if " = " in ins.text else ""
        return "$" not in src.split(",", 1)[0].replace(ins.op, "") and not re.search(r"\$(?!exec|mode)", src)

    res = set()
    for u in us:
        ok, work, seen = True, [at], set()
        while work and ok:
            b, i = work.pop()
            ins = blocks[b]["instrs"]
            found = False
            for k in range(i - 1, -1, -1):
                if u in ins[k].defs or u in ins[k].pdefs:
                    found = True
                    if not is_imm(ins[k]):
                        ok = False
                    break
            if not found:
                ps = preds.get(b, set())
                if not ps:
                    ok = False
                for p in ps:
                    if p not in seen:
                        seen.add(p)
                        work.append((p, len(blocks[p]["instrs"])))
        if ok:
            res.add(u)
    return res


def summarize(us):
    v, s, o = split(us)
    return dict(v=len(v), s=len(s), v_regs=v, s_regs=s, other=o)
