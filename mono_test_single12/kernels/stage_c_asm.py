# SPDX-License-Identifier: MIT
"""The whole attention.stage_C as one inline sp3 fragment (P2).

stage_C_asm(c) is a drop-in for attention.stage_C(c): it only turns the stage_C dict into the fragment's register
arguments (sp3/stage_c_full.sp3, built by asm/build_fragment.py) and emits the inline asm. The guard, the tile
coordinates, the wq_b GEMM, the q_norm rstd, the RoPE and the bf16 store are all inside the fragment.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

import flydsl.expr as fx
from flydsl._mlir.dialects import llvm
from flydsl.expr import rocdl
from flydsl.expr.typing import T

from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx
from atom.models.deepseek_v41.mono.gfx1250.kernels.attention import CTAS, HD, NORM_EPS, NQ, QL

ASM_DIR = Path(__file__).resolve().parents[1] / "build" / "asm"

# the constants sp3/stage_c_full.sp3 hard-codes
assert (QL, NQ, HD, CTAS) == (1280, 8192, 512, 256), (QL, NQ, HD, CTAS)
assert int(np.float32(NORM_EPS).view(np.uint32)) == 0x1E3CE508, NORM_EPS


def _load(name):
    contract = json.loads((ASM_DIR / f"{name}.contract.json").read_text())
    text = (ASM_DIR / f"{name}.inc").read_text()
    words = [int(w, 16) for w in text.replace(".long", "").replace(",", " ").split()]
    body = b"".join(w.to_bytes(4, "little") for w in words)
    assert hashlib.sha256(body).hexdigest() == contract["fragment_sha256"], f"{name}: .inc does not match its contract"
    return text, contract


FULL_TEXT, FULL_CONTRACT = _load("stage_c_full")
# FlyDSL's JIT cache key covers sources and closure scalars, not this module's fragment text: launchers fold this in
FRAGMENT_TAG = FULL_CONTRACT["fragment_sha256"][:16]


def _sgpr64(x):
    return rocdl.readfirstlane(T.i64, fx.Int64(x).ir_value())


def _sgpr32(x):
    return rocdl.readfirstlane(T.i32, fx.Int32(x).ir_value())


def wave_mask(MT):
    """bit w <=> stage_C's guard (w < 6) & (w % 3 < MT) admits wave w."""
    return sum(1 << w for w in range(6) if w % 3 < MT)


def stage_C_asm(c):
    """attention.stage_C(c), as the fragment. Its arguments, in the order of the contract's inputs:
    v0 = lane, s[0:17] = qr8 wqb qrs wqb_s ss q rpos rcos rsin (raw bases), s18 = b, s19 = w, s20 = wave mask."""
    assert isinstance(c["MT"], int), "MT must be a trace-time constant"
    assert c["stx"] is hx.stx_dev, "the fragment stores with global_store_b16 scope:SCOPE_DEV (stx_dev)"
    args = [fx.Int32(c["l"]).ir_value()]
    args += [_sgpr64(c[k]) for k in ("qr8", "wqb", "qrs", "wqb_s", "ss", "q", "rpos", "rcos", "rsin")]
    args += [_sgpr32(c["b"]), _sgpr32(c["w"]), fx.Int32(wave_mask(c["MT"])).ir_value()]
    llvm.inline_asm(None, args, FULL_TEXT, FULL_CONTRACT["constraints"], has_side_effects=True, is_align_stack=False,
                    asm_dialect=llvm.AsmDialect.AD_ATT)
