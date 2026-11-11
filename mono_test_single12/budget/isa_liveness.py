# SPDX-License-Identifier: MIT
"""Post-RA liveness of the physical s0-s105 / v0-v511 at the `; probe: <stage>#<k>:in|out` marks of a final gfx1250 ISA
(FlyDSL's 22_final_isa.s): the registers the compiled kernel really holds across each stage.

Conservative where the ISA is: a partial write (v_writelane, true16 .l/.h, fma_mixlo/hi, d16 loads, a masked DPP) is a
use and a def (permlane / full-mask bound_ctrl DPP write every lane); an unknown instruction is a def of its first operand. VCC / EXEC / SCC / M0 are not counted.
Usage: python3 isa_liveness.py 22_final_isa.s [--json out.json]
"""
import json
import re
import sys
from collections import defaultdict

REG = re.compile(r'\b([vs])(?:\[(\d+):(\d+)\]|(\d+))(\.[lh])?(?![\w])')
HI = re.compile(r'\b(v\d+|v\[\d+:\d+\])\s*/\*(v\d+|v\[\d+:\d+\])\*/')
LABEL = re.compile(r'^(\.LBB\d+_\d+|[A-Za-z_][\w.$]*):')
NO_DEF = ("global_store", "buffer_store", "scratch_store", "flat_store", "ds_store", "ds_write", "s_cmp", "s_bitcmp",
          "s_cbranch", "s_branch", "s_wait", "s_nop", "v_nop", "s_barrier", "s_sendmsg", "s_setprio", "s_sleep",
          "s_dcache", "s_prefetch", "s_endpgm", "s_delay_alu", "s_clause", "s_setreg", "s_set_vgpr_msb", "s_cluster",
          "tensor_", "global_load_lds", "global_load_async", "global_store_async", "s_monitor", "s_trap", "s_icache",
          "s_code_end", "s_inst_prefetch", "s_singleuse", "s_version", "v_cmpx", "s_ttrace", "s_alloc", "global_inv",
          "global_wb", "buffer_inv", "buffer_wbl2", "s_wakeup", "s_sethalt", "s_waitcnt", "s_denorm", "s_round",
          "global_prefetch", "s_buffer_prefetch", "s_atomic", "ds_gws", "s_sendmsghalt")
PARTIAL = ("v_writelane", "v_fma_mixlo", "v_fma_mixhi", "_d16")
SECOND_DEF = ("v_div_scale", "v_add_co_u32", "v_sub_co_u32", "v_subrev_co_u32", "v_add_co_ci", "v_sub_co_ci",
              "v_subrev_co_ci", "v_mad_u64_u32", "v_mad_i64_i32", "v_mad_co_u64_u32", "v_mad_co_i64_i32", "v_swap")


def regs(op):
    out, partial = set(), False
    for m in REG.finditer(op):
        k = m[1]
        rng = range(int(m[2]), int(m[3]) + 1) if m[4] is None else [int(m[4])]
        out.update((k, i) for i in rng)
        partial |= m[5] is not None
    return out, partial


def split_ops(ops):
    """operands up to the first modifier (offset:, op_sel:, quad_perm:, ...): commas outside brackets."""
    parts, depth, cur = [], 0, ""
    for ch in ops:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def decode(mn, ops, line):
    parts = split_ops(ops)
    defs, uses = set(), set()
    if not parts:
        return defs, uses
    if mn.startswith(NO_DEF) or (mn.startswith(("global_atomic", "buffer_atomic", "flat_atomic"))
                                 and "RETURN" not in line) or (mn.startswith("ds_") and "rtn" not in mn
                                                               and not mn.startswith(("ds_read", "ds_load", "ds_bpermute",
                                                                                      "ds_permute", "ds_swizzle", "ds_consume",
                                                                                      "ds_append"))):
        for p in parts:
            uses |= regs(p)[0]
        return defs, uses
    d, part = regs(parts[0])
    defs |= d
    first_src = 1
    if mn.startswith(SECOND_DEF) and len(parts) > 1:
        d2, _ = regs(parts[1])
        defs |= d2
        first_src = 2
        if mn.startswith("v_swap"):
            uses |= d | d2
    for p in parts[first_src:]:
        uses |= regs(p)[0]
    # a DPP / permlane old value matters only with masked rows / banks or no bound_ctrl (LLVM passes undef otherwise)
    dpp_old = ("_dpp" in mn or mn.startswith("v_permlane")) and (
        "row_mask:0xf" not in line or "bank_mask:0xf" not in line or "bound_ctrl:1" not in line) and "quad_perm" in line
    if part or mn.startswith(PARTIAL) or dpp_old or mn.startswith("s_cmov"):
        uses |= d
    return defs, uses


def parse(path):
    blocks, order, cur, nxt = {}, [], None, 0
    in_fn = False

    def new_block(name):
        nonlocal cur
        blocks[name] = dict(ins=[], succ=[], term=False)
        order.append(name)
        cur = name

    pending_mark = False
    for raw in open(path):
        line = raw.rstrip("\n")
        s = line.strip()
        if not in_fn:
            if re.match(r'^body_0:|^[\w$]+:\s*(;.*)?$', s) and not s.startswith("."):
                in_fn = True
                new_block(s.split(":")[0])
            continue
        if s.startswith(".Lfunc_end") or s.startswith(".section"):
            break
        m = LABEL.match(s)
        if m:
            prev = cur
            new_block(m[1])
            if not blocks[prev]["term"]:
                blocks[prev]["succ"].append(cur)
            continue
        if "probe: " in s:
            blocks[cur]["ins"].append(("mark", s.split("probe: ", 1)[1].strip()))
            continue
        if not s or s.startswith((";", ".", "//")):
            continue
        # VGPRs >= 256 print as their low name with the real one in a comment (s_set_vgpr_msb): v19 /*v275*/
        s = HI.sub(lambda m: m[2], s)
        code = s.split(";")[0].strip()
        mn, _, ops = code.partition(" ")
        if blocks[cur]["term"]:          # an instruction after an unconditional branch: a new (unreachable) block
            nxt += 1
            new_block(f".Lafter{nxt}")
        if mn.startswith("s_cbranch") or mn == "s_branch":
            tgt = ops.strip().split()[0].rstrip(",")
            blocks[cur]["succ"].append(tgt)
            blocks[cur]["ins"].append(("op",) + decode(mn, ops, code))
            if mn == "s_branch":
                blocks[cur]["term"] = True
            else:
                prev = cur
                nxt += 1
                new_block(f".Lft{nxt}")
                blocks[prev]["succ"].append(cur)
            continue
        if mn in ("s_endpgm", "s_setpc_b64", "s_code_end"):
            blocks[cur]["ins"].append(("op", set(), set()))
            blocks[cur]["term"] = True
            continue
        if "::" in code:                 # VOPD: two instructions read their sources together, then write
            d_all, u_all = set(), set()
            for half in code.split("::"):
                hm, _, hops = half.strip().partition(" ")
                d, u = decode(hm, hops, half)
                d_all |= d
                u_all |= u
            blocks[cur]["ins"].append(("op", d_all, u_all))
            continue
        blocks[cur]["ins"].append(("op",) + decode(mn, ops, code))
    return blocks, order


def analyse(path):
    blocks, order = parse(path)
    gen, kill = {}, {}
    for b, blk in blocks.items():
        g, k = set(), set()
        for ins in reversed(blk["ins"]):
            if ins[0] == "op":
                _, d, u = ins
                g -= d
                k |= d
                g |= u
        gen[b], kill[b] = g, k
    live_in = defaultdict(set)
    changed = True
    while changed:
        changed = False
        for b in reversed(order):
            out = set().union(*(live_in[s] for s in blocks[b]["succ"] if s in blocks))
            new = gen[b] | (out - kill[b])
            if new != live_in[b]:
                live_in[b] = new
                changed = True
    # may-defined (forward): a conservative use of a register no path has written yet (a partial write's merge, a DPP
    # old value) is not a live value; at entry only v0 (thread id) and the SGPRs the dispatch preloads hold one
    entry = order[0]
    preds = defaultdict(list)
    for b in order:
        for s in blocks[b]["succ"]:
            if s in blocks:
                preds[s].append(b)
    init = {r for r in live_in[entry] if r[0] == "s"} | {("v", 0)}
    def_out = defaultdict(set)
    changed = True
    while changed:
        changed = False
        for b in order:
            din = set(init) if b == entry else set()
            for p in preds[b]:
                din |= def_out[p]
            new = din | kill[b]
            if new != def_out[b]:
                def_out[b] = new
                changed = True
    def_at = {}
    for b in order:
        dset = set(init) if b == entry else set()
        for p in preds[b]:
            dset |= def_out[p]
        for ins in blocks[b]["ins"]:
            if ins[0] == "mark":
                def_at[ins[1]] = frozenset(dset)
            else:
                dset |= ins[1]
    at, peak = {}, (0, 0)
    for b in order:
        live = set().union(*(live_in[s] for s in blocks[b]["succ"] if s in blocks))
        for ins in reversed(blocks[b]["ins"]):
            if ins[0] == "mark":
                at[ins[1]] = frozenset(live) & def_at[ins[1]]
            else:
                _, d, u = ins
                live = (live - d) | u
    return at, peak


def fmt_regs(units, k):
    idx = sorted(i for kk, i in units if kk == k)
    out, i = [], 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        out.append(f"{k}{idx[i]}" if i == j else f"{k}[{idx[i]}:{idx[j]}]")
        i = j + 1
    return " ".join(out)


def main(path, out_json=None):
    at, peak = analyse(path)
    print(f"peak live: {peak[0]} SGPR, {peak[1]} VGPR")
    names = []
    for m in at:
        s = m.rsplit(":", 1)[0]
        if s not in names:
            names.append(s)
    rows = {}
    print(f'{"stage":22s} | {"keep S":>6s} {"keep V":>6s} {"keep V>=256":>11s} | {"in S":>5s} {"in V":>5s} | {"out S":>5s} {"out V":>5s}')
    for s in names:
        li, lo = at.get(f"{s}:in"), at.get(f"{s}:out")
        if li is None or lo is None:
            continue
        keep, inp, outp = li & lo, li - lo, lo - li
        n = lambda u, k: sum(1 for r in u if r[0] == k)
        hi = sum(1 for r in keep if r[0] == "v" and r[1] >= 256)
        rows[s] = dict(keep_s=n(keep, "s"), keep_v=n(keep, "v"), keep_v_hi=hi, in_s=n(inp, "s"), in_v=n(inp, "v"),
                       out_s=n(outp, "s"), out_v=n(outp, "v"), keep_s_regs=fmt_regs(keep, "s"),
                       keep_v_regs=fmt_regs(keep, "v"), in_s_regs=fmt_regs(inp, "s"), in_v_regs=fmt_regs(inp, "v"))
        print(f'{s:22s} | {n(keep, "s"):6d} {n(keep, "v"):6d} {hi:11d} | {n(inp, "s"):5d} {n(inp, "v"):5d} | '
              f'{n(outp, "s"):5d} {n(outp, "v"):5d}')
    if out_json:
        json.dump(rows, open(out_json, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
