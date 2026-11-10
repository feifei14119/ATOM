"""Compiler-visible .long boundary for the fixed gfx1250 dq_convert fragment.

This is the FlyDSL/MLIR equivalent of callee_test10's C++ asm volatile. The
clobbers are declared BEFORE register allocation. No MIR/regmask/count patch.
The caller executes this on a whole CTA, between CTA barriers, in a uniform
task branch. Inputs describe one complete packed 64x64 tile.
"""
from pathlib import Path

import flydsl.expr as fx
from flydsl._mlir.dialects import llvm
from flydsl.expr import rocdl
from flydsl.expr.typing import T

from asm.audit import load_fragment

FRAGMENT_DIR = Path(__file__).resolve().parents[2]/'build/asm'
ASM_TEXT, CONSTRAINTS, FRAGMENT_BYTES, CONTRACT = load_fragment(FRAGMENT_DIR)


def drain_global():
    # All waves drain their stores before joining the CTA barrier. The tile
    # buffers are uncached, and the producer also uses device-scope stores.
    llvm.inline_asm(None, [], 's_wait_storecnt 0\ns_wait_loadcnt 0\n', '~{memory}',
                    has_side_effects=True, is_align_stack=False,
                    asm_dialect=llvm.AsmDialect.AD_ATT)


def invoke_dq_convert(args_address, tid):
    args = fx.Int64(rocdl.readfirstlane(T.i64, fx.Int64(args_address).ir_value()))
    lane = fx.Int32(tid) & 31
    wave = fx.Int32(rocdl.readfirstlane(T.i32, fx.Int32(tid).ir_value())) >> 5
    # The v0 input also makes the low VGPR bank visible to AMDGPU's encoding
    # pass. The fragment restores EXEC/MODE and never touches s30:s39 or TTMP.
    llvm.inline_asm(None, [args.ir_value(), lane.ir_value(), wave.ir_value()],
                    ASM_TEXT, CONSTRAINTS, has_side_effects=True,
                    is_align_stack=False, asm_dialect=llvm.AsmDialect.AD_ATT)
