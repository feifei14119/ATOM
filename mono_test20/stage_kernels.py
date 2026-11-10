"""FlyDSL computation bodies; the hand-written ASM owns all task scheduling.

The gpu.kernel form is a tracing container only. export_stages converts it to
a C-ABI LLVM function BEFORE LLVM optimization/codegen, substitutes explicit
IDs, and rejects any leftover dispatch/kernarg implicit dependencies.
"""
from functools import lru_cache
import flydsl.compiler as flyc
import flydsl.expr as fx
from flydsl.expr import const_expr
from flydsl.expr.typing import Int32, Int64, T

from mono1250.device.ops import load_ptr64
from mono1250.device.sync import sreg
from mono1250.kernels.reference_plan import C1ReferencePlan
from mono1250.kernels.reference_sync import reference_mailbox
from mono1250.kernels.reference_k1 import stage_slice_c1
from mono1250.kernels.reference_norm import stage_norm_c1
from mono1250.kernels.reference_projection import reference_fp8_loads, reference_load_x8_c1
from mono1250.kernels.projection_asm import stage_wqkv_asm
from mono1250.kernels.attn_helpers import HIDDEN, X8_WORDS, lds_row

KINDS = ('slice', 'norm', 'wqkv')
LDS_BYTES = 14848
ARGUMENTS = ('res_in', 'pend', 'post_in', 'comb_in', 'pre_in', 'hc_fn',
             'res_out', 'scratch', 'diag', 'layer', 'attn_w', 'normed',
             'weight', 'scale', 'dq_args')


def shared(dtype, byte_offset):
    return fx.inttoptr(fx.PointerType.get(dtype.ir_type, fx.AddressSpace.Shared, 16),
                      fx.Int32(byte_offset))


@lru_cache(None)
def build_stage(kind):
    if kind not in KINDS:
        raise ValueError(kind)
    layout = C1ReferencePlan(feeds_index=True).k1_scratch_layout()
    symbol = 'mono_stage_' + kind

    @flyc.kernel(name=symbol, known_block_size=[256, 1, 1])
    def stage(record: Int64, task: Int32, explicit_bid: Int32, explicit_tid: Int32):
        # These builtins (including the ones inside mailbox helpers) are
        # replaced by explicit_bid/tid in lowered MLIR, before LLVM optimizes.
        tid, bid = fx.thread_idx.x, fx.block_idx.x
        record = fx.Int64(fx.rocdl.readfirstlane(T.i64, record.ir_value()))
        task = fx.Int32(fx.rocdl.readfirstlane(T.i32, task.ir_value()))
        bid = fx.Int32(fx.rocdl.readfirstlane(T.i32, fx.Int32(bid).ir_value()))
        values = {key: load_ptr64(record, i) for i, key in enumerate(ARGUMENTS)}
        pointer = fx.PointerType.get(fx.Int32.ir_type, fx.AddressSpace.Global, 4)
        failure = fx.inttoptr(pointer, values['diag'] + fx.Int64(256 * 8 * 4))
        mb = reference_mailbox(fx.ptr_load(fx.inttoptr(pointer, values['layer'])), values['diag'],
            {'lin': 1, 'pmix': 2, 'x8': 3, 'x8s': 4, 'nb': 5, 'qkv': 6}, failure, diagnostic=True)
        # Same union layout as test10: red[512] then union(slice,wqkv).
        # The caller descriptor allocates it once; no callee-owned LDS globals.
        c = dict(S=1, tid=tid, bid=bid, lane=tid % 64, wave=tid // 64, threads=256,
                 red=shared(fx.Float32, 0), rl=shared(fx.Float32, 2048),
                 fl=shared(fx.Float32, 2560), xl=shared(fx.Int32, 2048),
                 xsl=shared(fx.Int32, 2048 + lds_row(X8_WORDS) * 4),
                 args=values, fold=False, aux=False, index=True,
                 put=mb.put, put_words=mb.put_words, put_bf=mb.put_bf, poll=mb.poll)
        for region in ('lin', 'pmix', 'x8', 'x8s', 'nb', 'qkv'):
            c[region] = sreg(values['scratch'], layout[region][0], region)
        if const_expr(kind == 'slice'):
            stage_slice_c1(c, task)
        elif const_expr(kind == 'norm'):
            stage_norm_c1(c)
        else:
            matrix = dict(c, lane=tid % 32, wave=tid // 32)
            ops = reference_fp8_loads(matrix, values['weight'], values['scale'], HIDDEN, task)
            reference_load_x8_c1(matrix)
            stage_wqkv_asm(matrix, task, ops, values['dq_args'])

    @flyc.jit
    def trace(record: Int64, task: Int32, bid: Int32, tid: Int32, stream: fx.Stream):
        stage(record, task, bid, tid).launch(grid=(256,), block=(256,), stream=stream)
    return trace
