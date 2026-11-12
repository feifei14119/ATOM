# SPDX-License-Identifier: MIT
"""FlyDSL build hook: inline asm at every stage insertion point of the mono step kernel, per a plan (GPRTOOL_PLAN).

mode "wrap":    `; gpr: <stage>#<k>:in` before and `:out` after each call of the TARGETS (the stage itself runs).
mode "replace": each call of a stage in plan["replace"] becomes one asm `; gpr: <stage>#<k>` (the stage does not run):
                the stage's runtime inputs (the c[...] keys it reads, its runtime positional arguments) are the asm's
                inputs, bound to fixed registers (v0 = t, read-only: t lives through the whole kernel; SGPRs from s0:
                the 64-bit pointers in aligned pairs, then the 32-bit scalars, tied to outputs of the same registers:
                the asm may overwrite them); other calls are wrapped as in "wrap".
A wrap marker has no operand (the native allocation unchanged). LLVM resets the VGPR MSB mode before an inline asm
only when it reads a VGPR and otherwise assumes the asm keeps it: an asm that switches banks saves MODE[19:12] at
entry and restores it at exit (poison_text).
plan["contracts"][tag]: clobber_v / clobber_s (register numbers), clobber_x (vcc, scc, ...): the clobber list;
                        poison_v / poison_s: registers the asm overwrites with 0xDEAD0000 + n (runtime check).
The bindings are written to GPRTOOL_BIND (json). Run: GPRTOOL_PLAN=plan.json python3 probe.py [run_test.py args]
"""
import collections
import functools
import importlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "budget"))

from flydsl._mlir import ir  # noqa: E402
from flydsl._mlir.dialects import arith, llvm  # noqa: E402
import flydsl.expr as fx  # noqa: E402
from flydsl.expr import rocdl  # noqa: E402
from flydsl.expr.typing import T  # noqa: E402

import run_test  # noqa: E402
import stage_inputs as SI  # noqa: E402

PKG = "atom.models.deepseek_v41.mono.gfx1250.kernels."
TARGETS = [
    ("step", "stage_A"), ("step", "stage_kv"), ("attention", "stage_C"), ("step", "stage_D"), ("step", "stage_E"),
    ("step", "stage_F_cluster"), ("step", "tp_allreduce"),
    ("index_query", "stage_iq"), ("index_query", "stage_iw"), ("index_query", "stage_iquant"),
    ("compressor", "stage_cgemm"), ("compressor", "stage_crow"), ("compressor", "stage_cring"),
    ("index_score", "stage_score_any"), ("topk", "stage_select_any"),
    ("engram", "stage_engq"), ("engram", "stage_engkv"),
    ("front", "front_any"), ("front", "front_A"), ("front", "front_B"), ("front", "front_C"), ("front", "front_D"),
    ("front", "front_E1"), ("front", "front_E2"),
    ("moe", "ug_shared_early"), ("moe", "moe_union"), ("moe", "moe_ug"), ("moe", "moe_dn_stage"), ("moe", "moe_dn"),
    ("moe", "moe_dn_shared"), ("moe", "moe_combine"),
    ("draft_ctx", "stage_block_state"), ("draft_ctx", "stage_tap1"),
]
MODULE_OF = {n: m for m, n in TARGETS}
CONST = set("MT SMEM TR QV RPC o NP topk ne nexp_max rms_eps hc_eps norm_eps hdev stx rank xcpol sm rk dn8_bi dn8_nct "
            "w l".split())
PLAN = json.loads(Path(os.environ["GPRTOOL_PLAN"]).read_text()) if os.environ.get("GPRTOOL_PLAN") else {}
MODE = PLAN.get("mode", "wrap")
REPLACE = set(PLAN.get("replace", []))
CONTRACTS = PLAN.get("contracts", {})
RESERVED_S = set(PLAN.get("reserved_s", [32, 102, 103, 105]))
CALLS = collections.Counter()
BINDINGS = {}


def poison_text(pv, ps):
    """Overwrite VGPRs pv / SGPRs ps with 0xDEAD0000 + n (SGPRs + 0x8000), VGPRs through s_set_vgpr_msb (imm[7:0]
    the new mode, [7:6] the destination's bank; imm[15:8] the previous mode). The VGPR MSB mode at the asm
    (MODE[19:12]) is whatever the compiler last set (an asm with no VGPR operand gets no reset: `v5` may mean v261),
    and the compiler assumes it unchanged after the asm: it is saved in a poisoned SGPR first, set explicitly, and
    restored at the end (s_setreg, then s_nop: an S_SET_VGPR_MSB right after a MODE setreg is dropped)."""
    out, ps = [], sorted(ps)
    if pv:
        assert ps, "writing VGPRs needs a free SGPR to save the MSB mode in"
        tmp = ps[0]
        out.append(f"s_getreg_b32 s{tmp}, hwreg(HW_REG_WAVE_MODE, 12, 8)")
        mode = None
        for n in sorted(pv):
            bank = n >> 8
            if bank != mode:
                out.append(f"s_set_vgpr_msb 0x{bank << 6:x}")
                mode = bank
            out.append(f"v_mov_b32 v{n & 255}, 0x{0xDEAD0000 + n:x}")
        out += [f"s_setreg_b32 hwreg(HW_REG_WAVE_MODE, 12, 8), s{tmp}", "s_nop 0"]
    out += [f"s_mov_b32 s{n}, 0x{0xDEAD0000 + 0x8000 + n:x}" for n in ps]
    return out


def clobbers(con, taken=()):
    taken = set(taken)
    cl = [f"~{{v{n}}}" for n in con.get("clobber_v", []) if f"v{n}" not in taken]
    cl += [f"~{{s{n}}}" for n in con.get("clobber_s", []) if f"s{n}" not in taken]
    cl += [f"~{{{x}}}" for x in con.get("clobber_x", [])]
    return cl


def asm_text(tag, con):
    return "\n".join([f"; gpr: {tag}"] + poison_text(con.get("poison_v", []), con.get("poison_s", [])))


def mark(tag):
    """A wrap marker: no operand (the native allocation unchanged); its contract's clobbers / poison, if any."""
    con = CONTRACTS.get(tag, {})
    llvm.inline_asm(None, [], asm_text(tag, con), ",".join(clobbers(con)), has_side_effects=True,
                    is_align_stack=False, asm_dialect=llvm.AsmDialect.AD_ATT)


def to_ir(v):
    """A runtime scalar of the stage's inputs as an ir.Value (i64 / i32 / i1 / f32), else None (trace-time)."""
    if v is None or isinstance(v, (bool, int, float, str, dict)):
        return None
    if hasattr(v, "ir_value"):
        try:
            v = v.ir_value()
        except Exception:
            return None
    if not isinstance(v, ir.Value):
        return None
    return v if str(v.type) in ("i64", "i32", "i1", "f32", "i16", "i8") else None


def uniform(v):
    ty = str(v.type)
    if ty == "i64":
        return rocdl.readfirstlane(T.i64, v), "i64"
    if ty == "f32":
        v = arith.bitcast(T.i32, v)
    elif ty in ("i1", "i16", "i8"):
        v = arith.extui(T.i32, v)
    return rocdl.readfirstlane(T.i32, v), "i32"


def stage_operands(name, args, kwargs):
    """[(label, value, kind)] of a replaced stage's runtime inputs; kind: 'v' (t) / 'i64' / 'i32'."""
    c = args[0]
    table = SI.funcs(MODULE_OF[name])
    keys, _ = SI.keys_of(table[name], table, set())
    ops = [("t", fx.Int32(c["t"]).ir_value(), "v")] if "t" in c else []
    for k in sorted(keys):
        if k in CONST or k == "t" or k not in c:
            continue
        val = c[k]
        vals = list(val) if isinstance(val, (list, tuple)) else [val]
        for i, x in enumerate(vals):
            iv = to_ir(x)
            if iv is not None:
                u, kind = uniform(iv)
                ops.append((k if len(vals) == 1 else f"{k}{i}", u, kind))
    params = [p for p in table[name].args.args[1:]]
    for p, x in zip(params, args[1:]):
        iv = to_ir(x)
        if iv is not None:
            u, kind = uniform(iv)
            ops.append((p.arg, u, kind))
    for p, x in kwargs.items():
        iv = to_ir(x)
        if iv is not None:
            u, kind = uniform(iv)
            ops.append((p, u, kind))
    return ops


def bind(ops):
    """Fixed registers: v0 = t; SGPRs ascending from s0 (reserved ones skipped), 64-bit values first, aligned."""
    free = [n for n in range(106) if n not in RESERVED_S]
    out, used = [], set()
    for label, val, kind in [o for o in ops if o[2] == "v"]:
        out.append((label, val, kind, "v" if PLAN.get("t_free") else "v0", [] if PLAN.get("t_free") else ["v0"]))
    for label, val, kind in [o for o in ops if o[2] == "i64"] + [o for o in ops if o[2] == "i32"]:
        if kind == "i64":
            n = next(n for n in free if n % 2 == 0 and n not in used and n + 1 not in used and n + 1 in free)
            used |= {n, n + 1}
            out.append((label, val, kind, f"s[{n}:{n + 1}]", [f"s{n}", f"s{n + 1}"]))
        else:
            n = next(n for n in free if n not in used)
            used.add(n)
            out.append((label, val, kind, f"s{n}", [f"s{n}"]))
    return out


def replaced(name, tag, args, kwargs):
    con = CONTRACTS.get(tag, {})
    b = bind(stage_operands(name, args, kwargs))
    taken = [u for x in b for u in x[4]]
    tied = [x for x in b if x[2] != "v"]
    b = tied + [x for x in b if x[2] == "v"]
    tys = [T.i64 if x[2] == "i64" else T.i32 for x in tied]
    res = None if not tied else (tys[0] if len(tied) == 1 else llvm.StructType.get_literal(tys))
    cons = [f"={{{x[3]}}}" for x in tied] + [x[3] if x[3] == "v" else f"{{{x[3]}}}" for x in b] + clobbers(con, taken)
    llvm.inline_asm(res, [x[1] for x in b], asm_text(tag, con), ",".join(cons), has_side_effects=True,
                    is_align_stack=False, asm_dialect=llvm.AsmDialect.AD_ATT)
    BINDINGS[tag] = [dict(name=x[0], kind=x[2], reg=x[3], writable=x[2] != "v") for x in b]


def wrap(mod, name):
    orig = getattr(mod, name)

    @functools.wraps(orig)
    def probed(*a, **k):
        tag = f"{name}#{CALLS[name]}"
        CALLS[name] += 1
        if MODE == "replace" and name in REPLACE:
            replaced(name, tag, a, k)
            return None
        mark(f"{tag}:in")
        r = orig(*a, **k)
        mark(f"{tag}:out")
        return r
    setattr(mod, name, probed)


def main():
    for m, n in TARGETS:
        wrap(importlib.import_module(PKG + m), n)
    sys.argv = [sys.argv[0], "--stagec", "native"] + sys.argv[1:]
    try:
        rc = run_test.main()
    finally:
        print("PROBES", dict(CALLS), flush=True)
        if os.environ.get("GPRTOOL_BIND"):
            Path(os.environ["GPRTOOL_BIND"]).write_text(json.dumps(dict(calls=dict(CALLS), bindings=BINDINGS),
                                                                   indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
