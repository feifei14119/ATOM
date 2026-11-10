# SPDX-License-Identifier: MIT
# Copyright (C) 2026, Advanced Micro Devices, Inc. All rights reserved.
"""The same three-stage Mono as reference_projection, with ASM BF16 rounding.

Only the WQKV epilogue changes: WMMA -> FP32 sums -> vendor conversion -> QKV
mailbox. One independent 64x64 input/output tile and 240-byte argument record
per WQKV task. The 16 live outputs occupy logical tile row 0, columns 0..15.
"""
from functools import lru_cache

import flydsl.compiler as flyc
import flydsl.expr as fx
from aiter.ops.flydsl.kernels import buffer_ops as bo
from flydsl.expr import gpu, range_constexpr
from flydsl.expr.typing import Int64, T

from mono1250.device.ops import CM_DEV, kernel_symbol, launcher, load_ptr64, rsrc, traced
from mono1250.device.sync import sreg
from mono1250.kernels.attn_helpers import HIDDEN, QKV_ROWS, X8_WORDS, lds_row
from mono1250.kernels.dq_ffi import drain_global, invoke_dq_convert
from mono1250.kernels.reference_k1 import stage_slice_c1
from mono1250.kernels.reference_norm import stage_norm_c1
from mono1250.kernels.reference_plan import BLOCKS, WAVES, C1ReferencePlan
from mono1250.kernels.reference_projection import (
    reference_fp8_loads, reference_load_x8_c1, reference_fp8_matrices_c1,
)
from mono1250.kernels.reference_sync import reference_mailbox

THREADS = 256
ARGS_BYTES = 240


@traced
def stage_wqkv_asm(c, task, ops, dq_args):
    # Identical WMMA and eight-way FP32 reduction to stage_wqkv_c1.
    reference_fp8_matrices_c1(c, HIDDEN, ops)
    record = dq_args + fx.Int64(task) * ARGS_BYTES
    src = load_ptr64(record, 0)  # ptr_dq_acc at byte 0x00
    dst = load_ptr64(record, 2)  # ptr_dq at byte 0x10
    if c['tid'] < 16:
        total = fx.Float32(0.0)
        for w in range_constexpr(WAVES):
            total = total + fx.ptr_load(c['red'] + w * 16 + c['tid'])
        # For row=0 and col<16, supplier packed index == col. All other
        # positions are initialized by the host and checked after conversion.
        bo.buffer_store(total, rsrc(src), c['tid'], cache_modifier=CM_DEV)
    drain_global()
    gpu.barrier()
    # Every one of the CTA's eight wave32s reaches the boundary. The wrapped .s skips
    # wave>=4 itself. Never move this invocation inside the tid<16 branch.
    invoke_dq_convert(record, c['tid'])
    drain_global()
    gpu.barrier()
    # Live c['tid'], task, dst and the mailbox context cross the standard device ABI boundary.
    # LLVM owns their placement/spills. There is no second bf16_round here.
    if c['tid'] < 16:
        rounded = fx.Float32(fx.BFloat16(bo.buffer_load(
            rsrc(dst), c['tid'], vec_width=1, dtype=T.bf16, cache_modifier=CM_DEV)))
        c['put'](c['qkv'], task * 16 + c['tid'], rounded)
    gpu.barrier()


def asm_symbol():
    return kernel_symbol('gfx1250_ffi_bc_dq_k1_projection', front=1, fold=0, ix=1,
                         b=BLOCKS, t=THREADS)


@lru_cache(None)
def build_projection_asm():
    plan = C1ReferencePlan(feeds_index=True)
    layout = plan.k1_scratch_layout()
    name = asm_symbol()

    @fx.struct
    class Smem:
        red: fx.Array[fx.Float32, 512, 16]

    @fx.struct
    class SliceLds:
        rl: fx.Array[fx.Float32, 128, 16]
        fl: fx.Array[fx.Float32, 24 * 128, 16]

    @fx.struct
    class WqkvLds:
        xl: fx.Array[fx.Int32, lds_row(X8_WORDS), 16]
        xsl: fx.Array[fx.Int32, lds_row(HIDDEN // 32), 16]

    @fx.union
    class StageLds:
        slice: SliceLds
        wqkv: WqkvLds

    @flyc.kernel(name=name, known_block_size=[THREADS, 1, 1])
    def projection(res_in: Int64, pend: Int64, post_in: Int64, comb_in: Int64,
                   pre_in: Int64, hc_fn: Int64, res_out: Int64, scratch: Int64,
                   diag: Int64, layer: Int64, attn_w: Int64, normed: Int64,
                   weight: Int64, scale: Int64, dq_args: Int64):
        tid, bid = fx.thread_idx.x, fx.block_idx.x
        alloc = fx.SharedAllocator(); lds = alloc.allocate(Smem).peek()
        stages = alloc.allocate(StageLds)
        sl, wl = stages.slice.peek(), stages.wqkv.peek()
        pointer = fx.PointerType.get(fx.Int32.ir_type, fx.AddressSpace.Global, 4)
        failure = fx.inttoptr(pointer, diag + fx.Int64(BLOCKS * 8 * 4))
        mb = reference_mailbox(fx.ptr_load(fx.inttoptr(pointer, layer)), diag,
            {'lin': 1, 'pmix': 2, 'x8': 3, 'x8s': 4, 'nb': 5, 'qkv': 6}, failure, diagnostic=True)
        args = dict(res_in=res_in, pend=pend, post_in=post_in, comb_in=comb_in,
                    pre_in=pre_in, hc_fn=hc_fn, res_out=res_out, attn_w=attn_w, normed=normed)
        c = dict(S=1, tid=tid, bid=bid, lane=tid % 64, wave=tid // 64, threads=THREADS,
                 rl=sl.rl.ptr, fl=sl.fl.ptr, red=lds.red.ptr, xl=wl.xl.ptr, xsl=wl.xsl.ptr,
                 args=args, fold=False, aux=False, index=True,
                 put=mb.put, put_words=mb.put_words, put_bf=mb.put_bf, poll=mb.poll)
        for region in ('lin', 'pmix', 'x8', 'x8s', 'nb', 'qkv'):
            c[region] = sreg(scratch, layout[region][0], region)
        for task in range(plan.stages['k1.slice'].first(bid), 160, BLOCKS):
            stage_slice_c1(c, task)
        for task in range(plan.stages['k1.norm'].first(bid), 1, BLOCKS):
            stage_norm_c1(c)
        task = plan.stages['k1.wqkv_a'].first(bid)
        if task < QKV_ROWS // 16:
            matrix = dict(c, lane=tid % (THREADS // WAVES), wave=tid // (THREADS // WAVES))
            ops = reference_fp8_loads(matrix, weight, scale, HIDDEN, task)
            reference_load_x8_c1(matrix)
            stage_wqkv_asm(matrix, task, ops, dq_args)

    @launcher(name)
    def launch(res_in: Int64, pend: Int64, post_in: Int64, comb_in: Int64,
               pre_in: Int64, hc_fn: Int64, res_out: Int64, scratch: Int64,
               diag: Int64, layer: Int64, attn_w: Int64, normed: Int64,
               weight: Int64, scale: Int64, dq_args: Int64, stream: fx.Stream):
        projection(res_in, pend, post_in, comb_in, pre_in, hc_fn, res_out,
                   scratch, diag, layer, attn_w, normed, weight, scale, dq_args).launch(
                       grid=(BLOCKS,), block=(THREADS,), stream=stream)
    return launch
