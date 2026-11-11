# SPDX-License-Identifier: MIT
"""Build the mono step kernel (run_test.py, --stagec native) with a `; probe: <stage>#<k>:in` / `:out` empty inline asm
around every call of the candidate stages, and dump its IR (FLYDSL_DUMP_IR) for the liveness analysis (liveness.py).

Usage: FLYDSL_RUNTIME_ENABLE_CACHE=0 FLYDSL_DUMP_IR=1 FLYDSL_DUMP_DIR=<dir> PYTHONPATH=/app/ATOM \
       python3 budget/probe_build.py [run_test.py args]
"""
import collections
import json
import functools
import importlib
import os
import sys
from pathlib import Path

from flydsl._mlir.dialects import llvm

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import run_test  # noqa: E402

PKG = "atom.models.deepseek_v41.mono.gfx1250.kernels."
# (module, function name): the module whose global the callers look the name up in
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
CALLS = collections.Counter()
# PROBE_CLOBBER=v: every :in mark also clobbers v0-v255 (what an asm owning the low VGPR window costs); vs: and every
# SGPR but s30-s39 (s0-s29, s40-s105)
CLOBBER = os.environ.get("PROBE_CLOBBER", "")
VMAX = int(os.environ.get("PROBE_VMAX", "256"))   # PROBE_CLOBBER=v clobbers v0..v(VMAX-1)
CLOB = ([f"~{{v{i}}}" for i in range(VMAX)] if "v" in CLOBBER else []) + \
       ([f"~{{s{i}}}" for i in list(range(30)) + list(range(40, 106))] if "s" in CLOBBER else [])
# PROBE_SGPRS=a-b: clobber s[a:b] only (an SGPR budget), with PROBE_CLOBBER=v
if os.environ.get("PROBE_SGPRS"):
    lo, hi = map(int, os.environ["PROBE_SGPRS"].split("-"))
    CLOB += [f"~{{s{i}}}" for i in range(lo, hi + 1)]


# PROBE_SGPR_MAP=file.json: {stage: n} -- that stage's :in mark clobbers its first n SGPRs (s0.., skipping s30-s39)
SMAP = json.load(open(os.environ["PROBE_SGPR_MAP"])) if os.environ.get("PROBE_SGPR_MAP") else {}
SORDER = list(range(30)) + list(range(40, 106))


# PROBE_VGPR_MAP=file.json: {stage: n} -- that stage's :in mark clobbers v0..v(n-1) (needs the v256+ clobber LLVM fix)
VMAP = json.load(open(os.environ["PROBE_VGPR_MAP"])) if os.environ.get("PROBE_VGPR_MAP") else {}


def mark(text):
    cons = ",".join(CLOB) if text.endswith(":in") else ""
    stg = text.split("#")[0]
    if text.endswith(":in") and stg in VMAP:
        cons = ",".join(([cons] if cons else []) + [f"~{{v{i}}}" for i in range(VMAP[stg])])
    if text.endswith(":in") and stg in SMAP:
        cons = ",".join(([cons] if cons else []) + [f"~{{s{i}}}" for i in SORDER[:SMAP[stg]]])
    llvm.inline_asm(None, [], f"; probe: {text}", cons, has_side_effects=True, is_align_stack=False,
                    asm_dialect=llvm.AsmDialect.AD_ATT)


def wrap(mod, name):
    orig = getattr(mod, name)

    @functools.wraps(orig)
    def probed(*a, **k):
        tag = f"{name}#{CALLS[name]}"
        CALLS[name] += 1
        mark(f"{tag}:in")
        r = orig(*a, **k)
        mark(f"{tag}:out")
        return r
    setattr(mod, name, probed)


def main():
    for m, n in TARGETS:
        wrap(importlib.import_module(PKG + m), n)
    # stage_C reaches step through install_stage_c(native) = attention.stage_C (the wrapped one)
    sys.argv = [sys.argv[0], "--stagec", "native"] + sys.argv[1:]
    try:
        run_test.main()
    finally:
        print("PROBES", dict(CALLS), flush=True)


if __name__ == "__main__":
    main()
