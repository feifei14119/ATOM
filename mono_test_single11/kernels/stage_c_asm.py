# SPDX-License-Identifier: MIT
"""stage_C with its wq_b GEMM main loop as an inline sp3 fragment (P1).

The guard, the tile coordinates and the epilogue (q_norm rstd, RoPE, bf16 store) are attention.stage_C's, verbatim; the
fragment (sp3/stage_c_gemm.sp3, built by asm/build_fragment.py) replaces mx_loop: v0 = lane, s[0:7] = the qr8 / wqb /
qrs / wqb_s tile bases, v[8:15] = the 16x16 fp32 accumulator in the wmma_mx layout.
"""
import hashlib
import json
from pathlib import Path

import flydsl.expr as fx
from flydsl._mlir.dialects import llvm
from flydsl.compiler.ast_rewriter import ASTRewriter
from flydsl.expr import range_constexpr, rocdl
from flydsl.expr.typing import T

from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx
from atom.models.deepseek_v41.mono.gfx1250.kernels.attention import (BF16, CTAS, F32, HD, I32, NORM_EPS, NQ, QL, i64,
                                                                     rope_cs, rsq)

ASM_DIR = Path(__file__).resolve().parents[1] / "build" / "asm"


def _load(name):
    contract = json.loads((ASM_DIR / f"{name}.contract.json").read_text())
    text = (ASM_DIR / f"{name}.inc").read_text()
    words = [int(w, 16) for w in text.replace(".long", "").replace(",", " ").split()]
    body = b"".join(w.to_bytes(4, "little") for w in words)
    assert hashlib.sha256(body).hexdigest() == contract["fragment_sha256"], f"{name}: .inc does not match its contract"
    return text, contract


GEMM_TEXT, GEMM_CONTRACT = _load("stage_c_gemm")
# FlyDSL's JIT cache key covers sources and closure scalars, not this module's fragment text: launchers fold this in
FRAGMENT_TAG = GEMM_CONTRACT["fragment_sha256"][:16]


def _rfl64(x):
    return fx.Int64(rocdl.readfirstlane(T.i64, fx.Int64(x).ir_value()))


def _rfl32(x):
    return fx.Int32(rocdl.readfirstlane(T.i32, fx.Int32(x).ir_value()))


def gemm_tile(l, a, b, sa, sb):
    """acc[16x16] = qr8 tile . wqb tile^T over K = 1280 (the fragment); every argument but l wave-uniform."""
    r = llvm.inline_asm(hx.vty(8, T.f32), [fx.Int32(l).ir_value(), _rfl64(a).ir_value(), _rfl64(b).ir_value(),
                                           _rfl64(sa).ir_value(), _rfl64(sb).ir_value()],
                        GEMM_TEXT, GEMM_CONTRACT["constraints"], has_side_effects=True, is_align_stack=False,
                        asm_dialect=llvm.AsmDialect.AD_ATT)
    return fx.Vector(r, (8,), fx.Float32)


@ASTRewriter.transform
def stage_C_asm(c, phase=1):
    t, b, w, l, MT = c["t"], c["b"], c["w"], c["l"], c["MT"]
    if (w < 6) & (w % 3 < MT):
        wu = _rfl32(w)
        j = wu // 3
        mi = wu % 3
        n0 = (b + j * CTAS) * 16
        acc = gemm_tile(l, c["qr8"] + i64(mi * 16) * QL, c["wqb"] + i64(n0) * QL, c["qrs"] + i64(mi * 16 * (QL // 32)),
                        c["wqb_s"] + i64((n0 // 32) * (QL // 32)))
        # attention.stage_C's epilogue, verbatim
        cv = [acc[i] * rsq(hx.gload(c["ss"] + i64(mi * 16 + (l // 16) * 8 + i) * 4, F32) / F32(QL) + F32(NORM_EPS)) for i in range(8)]
        is_rope = n0 % HD >= HD - 64
        fi = fx.max((n0 % HD + l % 16 - (HD - 64)) // 2, I32(0))
        odd = (l & 1) == 1
        res = []
        for i in range_constexpr(8):
            r = mi * 16 + (l // 16) * 8 + i
            x = cv[i].to(BF16).to(F32)
            y = cv[i].shuffle_xor(1, 32).to(BF16).to(F32)
            cs, sn = rope_cs(c, r, fi)
            res.append(is_rope.select(odd.select(y * sn + x * cs, x * cs - y * sn), cv[i]))
        for i in range_constexpr(8):
            c["stx"](c["q"] + i64((mi * 16 + (l // 16) * 8 + i) * NQ + n0 + l % 16) * 2, res[i].to(BF16))

