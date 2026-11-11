"""Same C1 slice/norm/WQKV schedule as mono_test00/01/10; whole WQKV in ASM."""
import flydsl.compiler as flyc
import flydsl.expr as fx
from flydsl._mlir import ir
from flydsl._mlir.dialects import llvm
from flydsl.expr.typing import Int64
from mono1250.kernels.attn_helpers import HIDDEN, X8_WORDS, lds_row
from mono1250.kernels.reference_k1 import stage_slice_c1
from mono1250.kernels.reference_norm import stage_norm_c1
from mono1250.kernels.reference_sync import reference_mailbox
from mono1250.kernels.reference_plan import C1ReferencePlan, BLOCKS
from mono1250.device.sync import sreg
from mono1250.plan.trace import enter_stage
from stage_api import WqkvStage

SYMBOL = "mono_contract_projection"
THREADS = 256


def _global(address):
    return llvm.inttoptr(ir.Type.parse("!llvm.ptr<1>"), fx.Int64(address).ir_value())


def snapshot(address):
    # Volatile old data must survive the opaque call; reloading is not equivalent.
    return fx.Int32(llvm.load(fx.Int32.ir_type, _global(address), alignment=4, volatile_=True))


def record(value, address):
    llvm.store(fx.Int32(value).ir_value(), _global(address), alignment=4)


def build_mono(manifest_path):
    plan = C1ReferencePlan(feeds_index=True)
    layout = plan.k1_scratch_layout()
    stage_wqkv_asm = WqkvStage(manifest_path)

    # Keep the exact original allocation/union, including its unused xsl field.
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

    @flyc.kernel(name=SYMBOL, known_block_size=[THREADS, 1, 1])
    def projection(res_in: Int64, pend: Int64, post_in: Int64, comb_in: Int64,
                   pre_in: Int64, hc_fn: Int64, res_out: Int64, scratch: Int64,
                   diag: Int64, layer: Int64, attn_w: Int64, normed: Int64,
                   weight: Int64, scale: Int64, live_state: Int64):
        tid, bid = fx.thread_idx.x, fx.block_idx.x
        alloc = fx.SharedAllocator()
        lds = alloc.allocate(Smem).peek()
        stages = alloc.allocate(StageLds)
        sl, wl = stages.slice.peek(), stages.wqkv.peek()
        pointer = fx.PointerType.get(fx.Int32.ir_type, fx.AddressSpace.Global, 4)
        failure_base = diag + fx.Int64(BLOCKS * 8 * 4)
        failure = fx.inttoptr(pointer, failure_base)
        mb = reference_mailbox(fx.ptr_load(fx.inttoptr(pointer, layer)), diag,
            {"lin":1,"pmix":2,"x8":3,"x8s":4,"nb":5,"qkv":6}, failure, diagnostic=True)
        args = dict(res_in=res_in, pend=pend, post_in=post_in, comb_in=comb_in,
                    pre_in=pre_in, hc_fn=hc_fn, res_out=res_out, attn_w=attn_w,
                    normed=normed, wqkv=weight, wqkv_s=scale)
        c = dict(S=1, tid=tid, bid=bid, lane=tid%64, wave=tid//64, threads=THREADS,
                 rl=sl.rl.ptr, fl=sl.fl.ptr, red=lds.red.ptr, xl=wl.xl.ptr, xsl=wl.xsl.ptr,
                 args=args, fold=False, aux=False, index=True,
                 put=mb.put, put_words=mb.put_words, put_bf=mb.put_bf, poll=mb.poll,
                 mailbox_tag=mb.tag, diag_base=diag, failure_base=failure_base)
        for region in ("lin","pmix","x8","x8s","nb","qkv"):
            c[region] = sreg(scratch, layout[region][0], region)

        enter_stage("k1.slice")
        for task in range(plan.stages["k1.slice"].first(bid), 160, BLOCKS):
            stage_slice_c1(c, task)
        enter_stage("k1.norm")
        for task in range(plan.stages["k1.norm"].first(bid), 1, BLOCKS):
            stage_norm_c1(c)

        enter_stage("k1.wqkv_a")
        task = plan.stages["k1.wqkv_a"].first(bid)
        if task < 112:
            # An extra observation buffer demonstrates real live-through values.
            # It is not a WQKV input or a context spill area.
            at = live_state + fx.Int64(bid * THREADS + tid) * 16
            before = snapshot(at)
            old_tag = c["mailbox_tag"]

            # The entire replacement boundary: no weight/X/scale preload here.
            stage_wqkv_asm(c, task, 0, 1)

            # These old values are kept by LLVM according to the call regmask.
            record(before ^ fx.Int32(0x2468ace0), at + 4)
            record(old_tag, at + 8)
            record(fx.Int32(tid), at + 12)

    @flyc.jit
    def launch(res_in: Int64, pend: Int64, post_in: Int64, comb_in: Int64,
               pre_in: Int64, hc_fn: Int64, res_out: Int64, scratch: Int64,
               diag: Int64, layer: Int64, attn_w: Int64, normed: Int64,
               weight: Int64, scale: Int64, live_state: Int64, stream: fx.Stream):
        projection(res_in,pend,post_in,comb_in,pre_in,hc_fn,res_out,scratch,
                   diag,layer,attn_w,normed,weight,scale,live_state).launch(
                       grid=(BLOCKS,),block=(THREADS,),stream=stream)
    return launch
