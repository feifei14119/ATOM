# SPDX-License-Identifier: MIT
# Copyright (C) 2026, Advanced Micro Devices, Inc. All rights reserved.
# ruff: noqa
# fmt: off
"""The whole decode step as one persistent FlyDSL kernel (4-GPU TP, one build per rank and target width).

  target entry   the input ids' embedding -> block state (R = 4 copies, pre (1,0,0,0)) -> layer 0's attention front
  40 target layers  attention body (attention: A, kv, C, [indexer: iq / iw / compressor GEMM, iquant / compressor rows,
                 scorer + top-512 selection], D, E, F + wo_b cluster), TP1 all-reduce -> y1; then the two fronts with one
                 copy of the code (front.front_any: FFN front -> router ids -> routed + shared MoE (moe) -> combine
                 -> TP2 -> y2; attention front of the next layer); the draft context taps on the tap layers
  target tail    head -> 4-rank sampling -> verify (tail); the draft context KV (draft_ctx) inside the sampling
                 exchanges
  draft entry    the draft block's metadata from the verify, block state (anchor embedding / noise rows) -> draft stage
                 0's attention front
  3 draft layers the same layer code traced with the draft shape (TRD rows, 128-expert top-3 router, kmeta_d / kvw_d /
                 rpos_d metadata)
  draft tail     draft head -> Markov block drafts; the step epoch's end

Pointers: kernel args (attention), the device table `fp` (FPTRS, then ATAB, then the per-layer rows LKEYS) and the
step-tail table `tp`. Handoffs are fence-free with device-scope exchange stores. The receive buffers are double-buffered
by step parity (tp_epoch_begin / tp_epoch_end). Every handoff counter, the fixed LDS regions and the layer-table
rows are named in layout.py; the indexer's and the MoE's per-step arithmetic is in index_plan.py / moe_plan.py.
"""
from __future__ import annotations


import flydsl.compiler as flyc
import flydsl.expr as fx
from flydsl._mlir.dialects import llvm
from flydsl.compiler.ast_rewriter import ASTRewriter
from flydsl.expr import gpu, range_constexpr
from flydsl.expr.typing import Int64

from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx
from atom.models.deepseek_v41.mono.gfx1250.kernels import dims as D
from atom.models.deepseek_v41.mono.gfx1250.kernels import layout as LY
from atom.models.deepseek_v41.mono.gfx1250.kernels import front as FS
from atom.models.deepseek_v41.mono.gfx1250.kernels import moe as MS
from atom.models.deepseek_v41.mono.gfx1250.kernels import tail as ST
from atom.models.deepseek_v41.mono.gfx1250.kernels import attention as AS
from atom.models.deepseek_v41.mono.gfx1250.kernels import index_query as IS
from atom.models.deepseek_v41.mono.gfx1250.kernels import compressor as CS
from atom.models.deepseek_v41.mono.gfx1250.kernels import draft_ctx as CX
from atom.models.deepseek_v41.mono.gfx1250.kernels import index_score as SC
from atom.models.deepseek_v41.mono.gfx1250.kernels import topk as TK
from atom.models.deepseek_v41.mono.gfx1250.kernels import engram as ES
from atom.models.deepseek_v41.mono.gfx1250.kernels.attention import (CL, CTAS, KWOA, NWOA, QL, THREADS, i64, pf_rows, smem_layout, stage_A,
                         stage_C, stage_D, stage_E, stage_F_cluster, stage_kv, tp_allreduce)
from atom.models.deepseek_v41.mono.gfx1250.kernels.attention import handoff as _handoff
from flydsl._mlir import ir

DRAFT_NE, DRAFT_TOPK = D.DRAFT_EXPERTS, D.DRAFT_TOPK
DSPARK_W = D.DSPARK_W          # the DSpark block width: a build's draft requests = its draft rows // 5
TENTRY_ROW = LY.TARGET_ENTRY_ROW       # the layer-table row of the target entry's attention front (tables.StepTables: after 40 + 3 layers and the draft entry)

FRONT_LDS_OFF = LY.FRONT_LDS                # keep the TP payload ([TR][20] f32 at LDS 0) intact
FPTRS = ['R', 'y', 'pre', 'post', 'comb', 'fnh', 'fnl', 'hsc', 'hbs', 'nw', 'gate', 'gbias', 'Rout', 'xn', 'fx8', 'fxs', 'part', 'plog', 'cand', 'cands', 'npre', 'npost', 'ncomb', 'ids', 'wts', 'mout', 'mid8', 'midc', 'afnh', 'afnl', 'ahsc', 'ahbs', 'anw', 'aRout', 'axn', 'anpre', 'anpost', 'ancomb', 'tp2out', 'cyc', 'y1', 'y2', 'shplane', 'kmeta', 'knsel', 'ksel', 'kvw', 'rpos', 'iq', 'iwp', 'iq_out', 'iqs_out', 'iw_out', 'xh', 'cpart', 'ilvl', 'aux8', 'auxs', 'tpep', 'kmeta_d', 'kvw_d', 'rpos_d', 'dR', 'dy', 'dpre', 'dpost', 'dcomb', 'emb', 'noise', 'x8', 'xs', 'ctxtab', 'dgeom', 'tids', 'eng8', 'engs', 'engkv', 'engpart']   # the step's pointers, in a device table (kernel arg `fp`):
# as ~30 more kernel args they pushed SGPRs into spills and a 64-bit VGPR spill whose ~45 scratch reloads each waited,
# by the in-order loadcnt, for every outstanding load of the stage they sat in
ATAB = ("x8 xs wqkv wqkv_s qnw kvnw wqb wqb_s kv sel sink rcos rsin woa woa_s wob wob_s qkv_part qkv ss qr8 qrs kvn q "
        "apart aml o8 os_ y8 ys ypart out opart tpout recv0 recv1 recv2 recv3").split()   # attention pointers (after FPTRS in fp)
LKEYS = ("wqkv wqkv_s wqb wqb_s woa woa_s wob wob_s qnw kvnw sink fnh fnl hsc hbs nw gate gbias "
         "afnh afnl ahsc ahbs anw mw13 ms13 mw2 ms2 rcos rsin shplane ksel knsel kring lflags iqw iqws iww cwkv cnw cape cwk cknw cplan wplan ccap wcap cmain crpp cprow cplane ckv cscore cstate btab bstride slots ibat ibound iplane irpp ilog ilw isel irow imain ibmax icand engw engws enggw engemb").split()   # ksel/knsel: the layer's topk owner's selection; kring: ring start row   # rcos/rsin: this layer's RoPE row table (window or global, by the layer's ratio)   # a*: the attention front at the END of layer Ly = layer Ly+1's weights (host fills)
RECV_HALF = 16 * 40960 * 16 + (2 << 20)   # bytes a parity half of a receive buffer (TP regions + tail)
RKOFF = LY.RKEEP        # LDS: the residual streams kept between the fronts
LCB = LY.LAYER_BYTES             # (+ 128..255: the TP1 / TP2 column-group counters, gpub / gwait)  # bytes of handoff counters a layer (16: the indexer layers' extra phases use 4, 44.., 60)
IDX_LEVELS = 2        # selection-tree levels (1: bound <= 8192 index rows; 2: <= 8192 x 16 -- the 64K-token ILW)
IPF_KB = 32           # instruction prefetch (KB) before the fronts / the MoE
FPF_SPLIT = True      # (front prefetch layout; the step build does not prefetch the front weights)


def opaque_s64(x):
    """asm volatile("" : "+s"(x)) on an i64."""
    return fx.Int64(llvm.inline_asm(ir.IntegerType.get_signless(64), [hx._v(fx.Int64(x))], "", "=s,0",
                                    has_side_effects=True))


_EPOCH = [0]
_BASES = {}


def fresh_t():   # a thread id copy per use: computed from v0 where it is used (never live across a stage's asm)
    return hx.opaque_v(fx.thread_idx.x)


def next_epoch():
    """A new table-read interval (handoffs, gpub / gwait, the front's sub-stages): see tbase."""
    _EPOCH[0] += 1


KARG = dict(recv0=0, recv1=8, recv2=16, recv3=24, cnt=32, st=40, scale=48, fp=56, tp=64)   # body's kernarg offsets


def kseg():
    """The kernarg segment pointer, opaque once per interval and block (see tbase)."""
    k = (_EPOCH[0], ir.InsertionPoint.current.block, "kseg")
    if k not in _BASES:
        p = llvm.call_intrinsic(ir.Type.parse("!llvm.ptr<4>"), "llvm.amdgcn.kernarg.segment.ptr", [], [], [])
        _BASES[k] = opaque_s64(fx.Int64(llvm.PtrToIntOp(ir.IntegerType.get_signless(64), p).result))
    return _BASES[k]


def karg(name):
    """Kernel argument `name` re-read from the kernarg segment (a scalar load) where it is used: the arguments the
    layer loop uses (fp, cnt, st, scale) otherwise stay in SGPRs through the whole loop."""
    k = (_EPOCH[0], ir.InsertionPoint.current.block, "karg", name)
    if k not in _BASES:
        a = kseg() + i64(KARG[name])
        if name == "scale":
            q = llvm.IntToPtrOp(ir.Type.parse("!llvm.ptr<4>"), hx._v(a)).result
            _BASES[k] = fx.Float32(llvm.LoadOp(fx.Float32.ir_type, q, alignment=4).result)
        else:
            _BASES[k] = hx.sload64(a)
    return _BASES[k]


def oly(Ly):
    """The layer index as i64, opaque once per interval and block: what is derived from it (the layer's table row
    offset, its handoff counters) is invariant in the inner loops and LICM hoisted it above them, live through the
    layer."""
    k = (_EPOCH[0], ir.InsertionPoint.current.block, "ly", id(Ly))
    if k not in _BASES:
        _BASES[k] = opaque_s64(i64(Ly))
    return _BASES[k]


def tbase(fp):
    """The table base, read once per interval and block (from the kernarg segment: karg). The table is addrspace(4)
    (invariant to LLVM): with the plain base, GVN / EarlyCSE merge every read of a slot into one and LICM hoists it
    out of the layer loop, and each pointer stays in an SGPR through the whole loop (SGPR spills). Reads of one
    interval still merge."""
    return karg("fp")


def handoff(cnt, t, hdev, *a):
    """attention.handoff in a new table-read interval, on a fresh t (its t == 0 mask not kept across the layer)."""
    next_epoch()
    _handoff(cnt, t, hdev, *a)
    next_epoch()


def fptr(fp, name):
    """Pointer `name` from the table (wave-uniform: a scalar load, scalar cache)."""
    return hx.sload64(tbase(fp) + i64(FPTRS.index(name) * 8))


def tp_epoch_begin(recv, fp, rank):
    """(this step's receive bases, its epoch). Step e uses half e & 1 of every rank's receive buffer; this rank zeroes its
    own other half (the next step's) now: a peer writes there only in step e + 1, which it reaches after this rank's step-e
    pushes (issued after these stores drained at the first handoff), and every step-e word for this rank lands before this
    rank leaves step e (it polls them all)."""
    ep = hx.gload(fptr(fp, "tpep"), fx.Int32)
    half = i64(ep & 1) * RECV_HALF
    other = recv[rank] + i64((ep + 1) & 1) * RECV_HALF
    t = hx.opaque_v(fx.thread_idx.x)
    b = hx.opaque_s(fx.block_idx.x)
    zv = fx.Vector.from_elements([fx.Int32(0)] * 4, fx.Int32)
    n16 = RECV_HALF // 16
    for k in range_constexpr((n16 + CTAS * THREADS - 1) // (CTAS * THREADS)):   # (the last pass clamped: repeated zeros)
        hx.gstore(other + i64(fx.min(b * THREADS + t + k * (CTAS * THREADS), fx.Int32(n16 - 1))) * 16, zv, nt=True)
    hx.wait_storecnt0()
    return [r + half for r in recv], ep


@ASTRewriter.transform
def tp_epoch_end(fp, ep):
    """The next step's epoch (CTA 0 thread 0, after the last handoff: every CTA read this step's at its start)."""
    t = hx.opaque_v(fx.thread_idx.x)
    b = hx.opaque_s(fx.block_idx.x)
    if (b == 0) & (t == 0):
        hx.gstore(fptr(fp, "tpep"), hx.gload(fptr(fp, "tpep"), fx.Int32) + 1)   # (re-read: only this thread writes it)


class LazyC(dict):
    """Stage context whose pointer entries are emitted at each access: key -> thunk (a scalar table load, + offset)."""
    def __init__(self, thunks, **kw):
        super().__init__(**kw)
        self._th = dict(thunks)
        for k in thunks:
            dict.__setitem__(self, k, None)

    def __getitem__(self, k):
        if k in self._th:
            return self._th[k]()
        return dict.__getitem__(self, k)

    def get(self, k, d=None):
        return self[k] if k in self else d

    def with_(self, **kw):
        n = LazyC({k: v for k, v in self._th.items() if k not in kw},
                  **{k: dict.__getitem__(self, k) for k in self if k not in self._th and k not in kw})
        n.update(kw)
        return n


def cwith(c, **kw):
    return c.with_(**kw) if isinstance(c, LazyC) else dict(c, **kw)


def lazy(c, **th):
    """c plus entries emitted at each access (key -> thunk): a stage's table pointers are read where it uses them,
    not all at its entry (live through the stage: SGPR spills)."""
    n = c.with_() if isinstance(c, LazyC) else LazyC({}, **c)
    for k, f in th.items():
        n._th[k] = f
        dict.__setitem__(n, k, None)
    return n


def entry_front(fp, sm, b, row, ne, topk):
    """A segment entry's attention front (front CTAs): the block state (dR / dy / dpre / dpost / dcomb) through the
    attention front of layer-table row `row` (its a* weights) -> axn / x8 / xs / the gates; R kept in LDS (first)."""
    nof = fx.Int32(0) != fx.Int32(0)
    cu = LazyC(dict(t=fresh_t, w=lambda: fresh_t() // 32, l=lambda: fresh_t() % 32), b=b, sm=sm + FRONT_LDS_OFF, rms_eps=D.RMS_EPS, hc_eps=1e-6, norm_eps=D.RMS_EPS,
              R=fptr(fp, "dR"), y=fptr(fp, "dy"), pre=fptr(fp, "dpre"), post=fptr(fp, "dpost"), comb=fptr(fp, "dcomb"),
              fnh=ltab(fp, row, "afnh")(), fnl=ltab(fp, row, "afnl")(), hsc=ltab(fp, row, "ahsc")(),
              hbs=ltab(fp, row, "ahbs")(), nw=ltab(fp, row, "anw")(), gate=ltab(fp, row, "gate")(),
              gbias=ltab(fp, row, "gbias")(), Rout=fptr(fp, "aRout"), xn=fptr(fp, "axn"), x8=fptr(fp, "x8"),
              xs=fptr(fp, "xs"), part=fptr(fp, "part"), plog=fptr(fp, "plog"), cand=fptr(fp, "cand"),
              cands=fptr(fp, "cands"), npre=fptr(fp, "anpre"), npost=fptr(fp, "anpost"), ncomb=fptr(fp, "ancomb"),
              ids=fptr(fp, "ids"), wts=fptr(fp, "wts"), isffn=nof, xs32=fx.Int32(1) != fx.Int32(0), merge=nof,
              rk=sm + RKOFF, first=fx.Int32(1) != fx.Int32(0), last=nof, hdev=True, ne=ne, topk=topk)
    FS.front_any(cu, lambda k: None)


@ASTRewriter.transform
def gpub(base, b, t):
    """A TP CTA's y (device-scope stores) is out: count it in its column group b // 16 (16 CTAs a group)."""
    next_epoch()
    hx.wait_storecnt0()
    gpu.barrier()
    if t == 0:
        hx.atomic_add(base + i64(b // 16) * 4, 1)


@ASTRewriter.transform
def gwait(base, b, t):
    """A front CTA (g, p = b % 16): wait for the 16 TP CTAs of its column group."""
    next_epoch()
    if t == 0:
        hx.wait_count(lambda: base + i64(b % 16) * 4, 16, 7)
    gpu.barrier()


def _ctxtab(fp, ndr):   # (plain python) the draft context table when the step has draft layers
    return fptr(fp, "ctxtab") if ndr else None


def ltab(fp, Ly, name):
    """Thunk: per-layer pointer `name` of layer Ly (row Ly of the layer table)."""
    def f():
        return hx.sload64(tbase(fp) + (i64(len(FPTRS) + len(ATAB)) + oly(Ly) * len(LKEYS) + i64(LKEYS.index(name))) * 8)
    return f


def lsel(fp, Ly, isf, n0, n1):
    """Per-layer pointer n0 (isf) or n1, one scalar load."""
    ix = isf.select(fx.Int32(LKEYS.index(n0)), fx.Int32(LKEYS.index(n1)))
    return hx.sload64(tbase(fp) + (i64(len(FPTRS) + len(ATAB)) + oly(Ly) * len(LKEYS) + i64(ix)) * 8)


def atab(fp, name, off=None):
    """Thunk: pointer `name` of the attention table (after FPTRS in fp) [+ off]."""
    def f():
        v = hx.sload64(tbase(fp) + i64((len(FPTRS) + ATAB.index(name)) * 8))
        return v if off is None else v + off
    return f


def iprefetch(kb):
    """Instruction prefetch of the next `kb` KB of code (s_prefetch_inst_pc_rel, 4 KB a request), issued before a
    handoff so the stage after it starts warm (the layer loop is larger than the instruction cache)."""
    for off in range(0, kb * 1024, 4096):
        llvm.inline_asm(None, [], f"s_prefetch_inst_pc_rel {off}, null, 31", "", has_side_effects=True)


def build(TR, rank, NL=D.LAYERS, ndr=D.DRAFT_LAYERS, trd=None, part="all", sources=""):
    """The step kernel for TR target rows (TR // 6 requests) and trd draft rows (5 a request); NL target layers (NL < 40
    and ndr 0: a bring-up / shadow build of the first layers only). part: "all" (one launch), or the step as two launches
    on one stream: "target" (entry, target layers, head, sampling, verification) then "draft" (draft context, metadata,
    draft layers, draft head, Markov) -- the host reads the verdict after the first while the second runs.
    sources: the kernel sources' digest (the runner's atom.mono.plan.build_key.source_digest of this directory). Every
    parameter is in `keyed`, which the kernel and the launcher reference: all of them reach FlyDSL's JIT cache key (an edit to a helper
    the cache walk does not reach still rebuilds)."""
    assert part in ("all", "target", "draft")
    keyed = (("TR", TR), ("rank", rank), ("NL", NL), ("ndr", ndr), ("trd", trd), ("part", part), ("sources", sources))
    L = smem_layout(TR)
    TPG = TR * 10 // 3
    stx = hx.stx_dev
    SEGS = ([(0, NL, 1)] if part != "draft" else []) + ([(NL, NL + ndr, 4)] if ndr and part != "target" else [])
    NDR = ndr
    TRD = TR if trd is None else trd
    LD = smem_layout(TRD)

    @flyc.kernel(known_block_size=[THREADS, 1, 1])
    def body(recv0: Int64, recv1: Int64, recv2: Int64, recv3: Int64, cnt: Int64, st: Int64, scale: fx.Float32, fp: Int64,
             tp: Int64):
        recv = [recv0, recv1, recv2, recv3]
        hx.TOFLAG[0] = lambda: fptr(fp, "cyc")   # (poll-timeout counter: hx.note_timeout; read where a poll times out)
        recv, tep = tp_epoch_begin(recv, fp, rank)
        for si in range_constexpr(len(SEGS)):   # layer segments, each its own loop and body (kind 1: target, 4: draft)
            seg_lo, seg_hi, seg_kind = SEGS[si]
            DRS = (seg_kind & 4) != 0
            FIRST_LY = -1
            if fx.const_expr(si == 0 and part != "draft"):
                # the target entry: SinglePassHCState.from_embeddings (R = 4 copies of the token's embedding, pre = (1, 0, 0, 0),
                # y = 0, post = 0, comb = I: stage_block_state with W = 1), then layer 0's attention front (its a*: layer-table
                # row TENTRY_ROW): x8 / xs / the attention gates, R kept in LDS (layer 0's FFN front: first = 0)
                b = hx.opaque_s(fx.block_idx.x)
                sm = hx.lds_base()
                TCNT = cnt + i64((NL + NDR) * LCB)
                CX.stage_block_state(dict(t=fresh_t(), b=b, aid=fptr(fp, "tids"), emb=fptr(fp, "emb"), noise=fptr(fp, "noise"),
                                          R=fptr(fp, "dR"), y=fptr(fp, "dy"), pre=fptr(fp, "dpre"), post=fptr(fp, "dpost"),
                                          comb=fptr(fp, "dcomb")), TR, 1)
                handoff(TCNT + i64(LY.TARGET_STATE), fresh_t(), False)
                if b < FS.FRONT_CTAS:
                    entry_front(fp, sm, b, TENTRY_ROW, FS.NE, FS.TOPK)
                handoff(TCNT + i64(LY.TARGET_FRONT), fresh_t(), False)
            TRx = TRD if DRS else TR
            Lx = LD if DRS else L
            DSUF = "_d" if DRS else ""
            RNE, RTOPK = (DRAFT_NE, DRAFT_TOPK) if DRS else (FS.NE, FS.TOPK)   # the segment's router shape
            if fx.const_expr(DRS):
                b = hx.opaque_s(fx.block_idx.x)
                sm = hx.lds_base()
                TCNT = cnt + i64((NL + NDR) * LCB)
                if fx.const_expr(part == "all"):
                    if fresh_t() == 0:
                        hx.gstore(st + i64(b) * (32 * 8) + i64(25 * 8), hx.clock())
                    ST.target(tp, fresh_t(), b, sm, st, TCNT, recv, rank, head_d=4, ctx=fptr(fp, "ctxtab"), T=TR)
                # the draft context KV (main_proj .. ring) from the target loop's taps
                # (the draft context KV runs inside the target sampling's exchanges: ST.target(ctx=...))
                # the draft entry: the draft block's metadata from this step's verify, its block state, then draft stage 0's
                # attention front (layer-table row NL + NDR)
                if b == 0:
                    CX.draft_meta(dict(t=fresh_t(), verdict=ST.tptr(tp, "verdict"), rpos=fptr(fp, "rpos"), dgeom=fptr(fp, "dgeom"),
                                       kmeta_d=fptr(fp, "kmeta_d"), kvw_d=fptr(fp, "kvw_d"), rpos_d=fptr(fp, "rpos_d")),
                                  TRD // DSPARK_W, DSPARK_W)
                CX.stage_block_state(dict(t=fresh_t(), b=b, aid=ST.tptr(tp, "anc"), emb=fptr(fp, "emb"), noise=fptr(fp, "noise"),
                                          R=fptr(fp, "dR"), y=fptr(fp, "dy"), pre=fptr(fp, "dpre"), post=fptr(fp, "dpost"),
                                          comb=fptr(fp, "dcomb")), TRD // DSPARK_W, DSPARK_W)
                handoff(TCNT + i64(LY.DRAFT_STATE), fresh_t(), False)
                if b < FS.FRONT_CTAS:
                    entry_front(fp, sm, b, NL + NDR, DRAFT_NE, DRAFT_TOPK)
                handoff(TCNT + i64(LY.DRAFT_FRONT), fresh_t(), False)
            for Ly in range(seg_lo, seg_hi):
                kind = seg_kind
                b = hx.opaque_s(fx.block_idx.x)
                sm = hx.lds_base()
                def LC():   # this layer's handoff counters (cnt re-read: karg)
                    return karg("cnt") + oly(Ly) * LCB

                # the attention pointers: re-read from the table at each use (scalar loads; as kernel args they pushed SGPRs
                # into spills), the per-layer ones from the layer row
                lz = {k: atab(fp, k) for k in ("tpout x8 xs kv sel qkv_part qkv qr8 qrs kvn q apart aml o8 y8 ys ypart out "
                                               "opart").split()}
                lz.update(os=atab(fp, "os_"), ss=atab(fp, "ss", i64(Ly) * (AS.SS_LAYER_F32 * 4)),
                          recv=(lambda: [atab(fp, f"recv{o}")() + i64(tep & 1) * RECV_HALF for o in range(4)]))
                lz.update({k: ltab(fp, Ly, k) for k in ("wqkv wqkv_s wqb wqb_s woa woa_s wob wob_s qnw kvnw sink rcos "
                                                        "rsin").split()})
                # t / w / l per access (a fresh thread id): computed once here they lived through the whole layer
                # (VGPR scratch)
                lz.update(t=fresh_t, w=lambda: fresh_t() // 32, l=lambda: fresh_t() % 32)
                c = LazyC(lz, **dict(Lx, b=b, sm=sm, stx=stx, rank=rank, xcpol=0))
                c = lazy(c, scale=lambda: karg("scale"), rpos=lambda: fptr(fp, "rpos" + DSUF))   # each row's RoPE position (int64 [T]), the product's cache.rope_positions
                # the key geometry: step metadata, the layer's selection owner tables and ring start (a WINDOW layer: n_sel 0 table)
                c._th.update(kmeta=lambda: fptr(fp, "kmeta" + DSUF), knsel=lambda: fptr(fp, "knsel"), ksel=lambda: fptr(fp, "ksel"),
                             kvw=lambda: fptr(fp, "kvw" + DSUF))
                for k_ in ("kmeta", "knsel", "ksel", "kvw"):
                    dict.__setitem__(c, k_, None)
                c._th.update(ksel=ltab(fp, Ly, "ksel"), knsel=ltab(fp, Ly, "knsel"))
                c = lazy(c, kring_off=lambda: fx.Int32(ltab(fp, Ly, "kring")()))

                # inside the inner loops (select passes, the two fronts) b and the counters only through ob() / olc(): what is
                # derived from them is loop-invariant there, and LICM hoisted it all above the loop (the two-pass one:
                # ~45 SGPRs), live through every pass
                def ob():
                    return hx.opaque_s(b)

                def olc():
                    return LC()

                def stamp(k):   # the layer-time stamps only: 0 (layer 0 start), 12 (layer 1 start), 18 (a layer's end)
                    if fx.const_expr(k not in (0, 12, 18)):
                        return
                    if fresh_t() == 0:
                        hx.gstore(karg("st") + i64(b) * (32 * 8) + i64(k * 8), hx.clock())

                if Ly == 0:
                    stamp(0)
                if Ly == 1:
                    stamp(12)
                if fx.const_expr((kind & 1) != 0):   # the row before an Engram layer (lflags bit 7): its embeddings -> MXFP8
                    if (ltab(fp, Ly, "lflags")() & fx.Int64(128)) != fx.Int64(0):
                        ES.stage_engq(cwith(c, engemb=ltab(fp, Ly, "engemb")(), eng8=fptr(fp, "eng8"), engs=fptr(fp, "engs")))
                stage_A(c)
                pf_rows(c["wqb"] + i64(b) * (16 * QL), QL, 16, QL, fresh_t())
                pf_rows(c["wqb"] + i64(b + CTAS) * (16 * QL), QL, 16, QL, fresh_t())
                handoff(LC(), fresh_t(), True)   # LY.ATTN_A (offset 0)
                if fx.const_expr((kind & 1) != 0):   # the next layer's Engram kv = emb . wkv^T (read by this layer's attention front)
                    if (ltab(fp, Ly, "lflags")() & fx.Int64(128)) != fx.Int64(0):
                        ES.stage_engkv(cwith(c, eng8=fptr(fp, "eng8"), engs=fptr(fp, "engs"), engw=ltab(fp, Ly, "engw")(),
                                             engws=ltab(fp, Ly, "engws")(), engkv=fptr(fp, "engkv")))
                stage_kv(c)
                stage_C(c)
                if fx.const_expr((kind & 1) != 0):   # an indexer layer: iq / iw beside kv / C (their inputs: A's q latent and ss, the front's axn)
                    isidx = (ltab(fp, Ly, "lflags")() & fx.Int64(8)) != fx.Int64(0)   # lflags: bit0 special body, 1 compressor, 2 ratio 1, 3 indexer, 4 ctx tap, 5 candidate producer, 6 REINDEX, 7 next layer has Engram
                    if isidx:
                        ci = lazy(c, **{n: (lambda n=n: ltab(fp, Ly, n)()) for n in ("iqw", "iqws", "iww")},
                                  **{n: (lambda n=n: fptr(fp, n)) for n in ("iq", "iwp", "axn")})
                        IS.stage_iq(ci)
                        IS.stage_iw(ci)
                        lfl = ltab(fp, Ly, "lflags")()
                        hascomp = (lfl & fx.Int64(2)) != fx.Int64(0)
                        r1 = (lfl & fx.Int64(4)) != fx.Int64(0)
                        if hascomp:   # the compressor's wkv_gate GEMM (compressor)
                            CS.stage_cgemm(lazy(c, cwkv=lambda: ltab(fp, Ly, "cwkv")(), axn=lambda: fptr(fp, "axn"),
                                                cpart=lambda: fptr(fp, "cpart")), r1)
                handoff(LC() + i64(LY.KV_C), fresh_t(), True)
                if fx.const_expr((kind & 1) != 0):   # iquant, then its own handoff (the scorer reads iq_out / iw_out; lc + 4 is free)
                    if isidx:
                        IS.stage_iquant(lazy(c, **{n: (lambda n=n: fptr(fp, n)) for n in ("iq", "iwp", "iq_out", "iqs_out", "iw_out")}))
                        lfl2 = ltab(fp, Ly, "lflags")()
                        if (lfl2 & fx.Int64(2)) != fx.Int64(0):   # the compressor's rows: main KV row + index row, and the ring
                            r1b = (lfl2 & fx.Int64(4)) != fx.Int64(0)
                            cc = lazy(c, cpart=lambda: fptr(fp, "cpart"),
                                      **{n: (lambda n=n: ltab(fp, Ly, n)()) for n in ("cnw cape cwk cknw cplan wplan cplane ckv "
                                                                                      "cscore cstate btab slots").split()},
                                      **{n: (lambda n=n: fx.Int32(ltab(fp, Ly, n)())) for n in ("ccap wcap cmain crpp cprow "
                                                                                                "bstride").split()})
                            CS.stage_crow(cc, r1b)
                            CS.stage_cring(cc, r1b)
                        handoff(LC() + i64(LY.INDEX_QUANT), fresh_t(), True)
                        if ltab(fp, Ly, "ibat")() != fx.Int64(0):   # a layer whose table has no scorer inputs skips it
                            # FULL: the scores of every visible index row, then the top-512 -> isel / irow (the attention's ksel)
                            cs_ = lazy(c, **{n: (lambda n=n: ltab(fp, Ly, n)()) for n in ("ibat ibound iplane btab ilog isel irow "
                                                                                          "ibmax icand").split()},
                                       **{n: (lambda n=n: fx.Int32(ltab(fp, Ly, n)())) for n in "irpp bstride ilw cprow imain".split()},
                                       iq_out=lambda: fptr(fp, "iq_out"), iw_out=lambda: fptr(fp, "iw_out"), lvl=lambda: fptr(fp, "ilvl"),
                                       iprod=lambda: (ltab(fp, Ly, "lflags")() & fx.Int64(32)) != fx.Int64(0))   # bit 5: produces the candidate blocks (layer 20)
                            cs_ = cwith(cs_, ts=None)
                            lfl3 = ltab(fp, Ly, "lflags")()
                            isrx = (lfl3 & fx.Int64(64)) != fx.Int64(0)      # bit 6: REINDEX (layer 20's candidates)
                            # one instance of the scorer (FULL and REINDEX, isrx traced) and of the selection code for every pass (I-cache)
                            SC.stage_score_any(cs_, isrx)
                            handoff(LC() + i64(LY.SCORE), fresh_t(), True)
                            npass = isrx.select(fx.Int32(IDX_LEVELS), cs_["iprod"].select(fx.Int32(2 * IDX_LEVELS), fx.Int32(IDX_LEVELS)))
                            for pi in range(npass):   # sel or rx levels, then (layer 20) the blk levels
                                pmode = isrx.select(fx.Int32(TK.MODE_RX), (pi < IDX_LEVELS).select(fx.Int32(TK.MODE_SEL), fx.Int32(TK.MODE_BLK)))
                                plev = pi % IDX_LEVELS
                                TK.stage_select_any(lazy(cs_, b=ob), plev, IDX_LEVELS, pmode)
                                handoff(olc() + i64(LY.SELECT0) + i64(pi) * 4, fresh_t(), True)
                stage_D(c)
                pf_rows(c["woa"] + i64(b // 4) * (32 * KWOA) + i64((b % 4) * 1024), KWOA, 32, 1024, fresh_t())
                handoff(LC() + i64(LY.ATTN_D), fresh_t(), True)
                stage_E(c)
                pf_rows(c["wob"] + i64(b // 4) * (80 * NWOA) + i64((b % 4) * 512), NWOA, 80, 512, fresh_t())
                handoff(LC() + i64(LY.ATTN_E), fresh_t(), True)
                stage_F_cluster(c)
                gpu.barrier()
                par = Ly % 2
                tp_allreduce(cwith(c, ytgt=fptr(fp, 'y1')), par * 2, 2 * Ly + 1)
                gpub(LC() + i64(LY.TP1_GROUPS), b, fresh_t())
                # the two fronts with one copy of the code: pass 0 = FFN front, MoE, TP2; pass 1 = attention front
                for hf in range(hx.opaque_s(fx.Int32(2))):
                    if hf == 0:
                        iprefetch(28)   # the front (the attention-front pass reuses it warm)
                    # a front CTA (g, p) reads y (TP1 / TP2's output) only in its cols 320p.. -- the 16 TP CTAs 16p..16p+15:
                    # it waits for their column-group count, not a device-wide handoff (the idle CTAs do not wait at all)
                    if ob() < FS.FRONT_CTAS:
                        gwait(olc() + (hf == 0).select(i64(LY.TP1_GROUPS), i64(LY.TP2_GROUPS)), ob(), fresh_t())
                    if ob() < FS.FRONT_CTAS:
                        isf = hf == 0

                        def fsel(n0, n1):
                            ix = isf.select(fx.Int32(FPTRS.index(n0) * 8), fx.Int32(FPTRS.index(n1) * 8))
                            return hx.sload64(tbase(fp) + i64(ix))
                        # the front's pointers and thread id are read at their uses (lazy): all read here they lived through
                        # the whole front
                        cu = lazy(dict(sm=sm + FRONT_LDS_OFF, rms_eps=D.RMS_EPS, hc_eps=1e-6, norm_eps=D.RMS_EPS,
                                       isffn=isf, xs32=hf != 0, merge=isf, hdev=True, ne=RNE, topk=RTOPK),
                                  **{k: (lambda n0=n0, n1=n1: fsel(n0, n1)) for k, (n0, n1) in dict(
                                      R=("R", "Rout"), y=("y1", "y2"), pre=("pre", "npre"), post=("post", "npost"), comb=("comb", "ncomb"),
                                      Rout=("Rout", "aRout"), npre=("npre", "anpre"), npost=("npost", "anpost"),
                                      ncomb=("ncomb", "ancomb")).items()},
                                  **{k: (lambda n0=n0, n1=n1: lsel(fp, Ly, isf, n0, n1)) for k, (n0, n1) in dict(
                                      fnh=("fnh", "afnh"), fnl=("fnl", "afnl"), hsc=("hsc", "ahsc"), hbs=("hbs", "ahbs"),
                                      nw=("nw", "anw")).items()},
                                  **{k: (lambda k=k: fptr(fp, k)) for k in "part plog cand cands ids wts".split()},
                                  t=fresh_t, w=lambda: fresh_t() // 32, l=lambda: fresh_t() % 32,
                                  b=ob, gate=lambda: ltab(fp, Ly, "gate")(), gbias=lambda: ltab(fp, Ly, "gbias")(),
                                  # the last layer of each segment writes the head input: target -> xh, draft -> dh
                                  xn=lambda: ((hf != 0) & (Ly == (NL + NDR - 1 if DRS else NL - 1))).select(ST.tptr(tp, "dh") if DRS else fptr(fp, "xh"), fsel("xn", "axn")),
                                  x8=lambda: isf.select(fptr(fp, "fx8"), c["x8"]), xs=lambda: isf.select(fptr(fp, "fxs"), c["xs"]))
                        # the residual streams kept in LDS between the fronts; also to global (last) after the last layer and
                        # for the tap layers' inputs (the attention fronts of layers TAP0..TAP0+2)
                        tap0 = NL - 4
                        cu.update(rk=sm + RKOFF, first=isf & (Ly == FIRST_LY), last=(hf != 0) & ((Ly == NL - 1) | ((Ly >= tap0) & (Ly <= tap0 + 2))))
                        # the attention front before an Engram layer gates its value in (lflags bit 7; target body only)
                        if fx.const_expr((kind & 1) != 0):
                            cu = lazy(cu, engkv=lambda: fptr(fp, "engkv"), enggw=lambda: ltab(fp, Ly, "enggw")(),
                                      engpart=lambda: fptr(fp, "engpart"))
                            cu.update(eng=(hf != 0) & ((ltab(fp, Ly, "lflags")() & fx.Int64(128)) != fx.Int64(0)), TR=TRx)
                        def x8pub(k):   # the FFN front's x8 / xs are out (front_C): count it (the early shared UG waits on it)
                            if fx.const_expr(k == 5 and MS.sh_early((TRx + MS.MAXTOK - 1) // MS.MAXTOK)):
                                if isf:
                                    hx.wait_storecnt0()
                                    gpu.barrier()
                                    if fresh_t() == 0:
                                        hx.atomic_add(olc() + i64(LY.X8_PUB), 1)
                        FS.front_any(cu, x8pub)
                    if fx.const_expr(MS.sh_early((TRx + MS.MAXTOK - 1) // MS.MAXTOK)):
                        # the FFN front's idle CTAs: the shared expert's UG, K split over SHE_CTAS CTAs a unit, once every front
                        # CTA's x8 is out (the front leaves most CTAs idle)
                        if (hf == 0) & (ob() >= FS.FRONT_CTAS) & (ob() < FS.FRONT_CTAS + ((TRx + MS.MAXTOK - 1) // MS.MAXTOK) * MS.NUG * MS.SHE_CTAS):
                            if fresh_t() == 0:
                                hx.wait_count(lambda: olc() + i64(LY.X8_PUB), FS.FRONT_CTAS, 6)
                            gpu.barrier()
                            ce = lazy(dict(sm=sm + FRONT_LDS_OFF, NP=TRx * RTOPK, topk=RTOPK),
                                      t=fresh_t, w=lambda: fresh_t() // 32, l=lambda: fresh_t() % 32, b=ob, x8=lambda: fptr(fp, "fx8"), xs=lambda: fptr(fp, "fxs"), shplane=lambda: ltab(fp, Ly, "shplane")(),
                                      mid8=lambda: fptr(fp, "mid8"), midc=lambda: fptr(fp, "midc"), out=lambda: fptr(fp, "mout"))
                            MS.ug_shared_early(ce, ob() - FS.FRONT_CTAS)
                    if hf == 0:
                        iprefetch(16)   # the routed MoE
                        handoff(olc() + i64(LY.FRONT), fresh_t(), True)
                        cm = LazyC({'t': fresh_t, 'w': lambda: fresh_t() // 32, 'l': lambda: fresh_t() % 32,'shplane': (lambda Ly=Ly: ltab(fp, Ly, 'shplane')()),   # (re-read at its uses: not live across the layer)
                                    'b': ob, 'shcnt': (lambda: olc() + i64(LY.SHARED_DOWN)),
                                    **{k: (lambda n=n: ltab(fp, Ly, n)()) for k, n in dict(w13="mw13", s13="ms13", w2="mw2", s2="ms2").items()},
                                    **{k: (lambda n=n: fptr(fp, n)) for k, n in dict(x8="fx8", xs="fxs", ids="ids", wts="wts", out="mout",
                                                                                      mid8="mid8", midc="midc").items()}},
                                   sm=sm + FRONT_LDS_OFF, NP=TRx * RTOPK, topk=RTOPK, nexp_max=96)
                        MS.moe(cm, olc() + i64(LY.MOE_UG))
                        gpu.barrier()
                        handoff(olc() + i64(LY.MOE_DONE), fresh_t(), True)
                        # TP2 payload = the MoE output rows, result -> y2 (the attention front's y)
                        MS.moe_combine(dict(t=fresh_t(), b=ob(), out=fptr(fp, "mout"), topk=RTOPK), TRx, sm)
                        tp_allreduce(lazy(c, b=ob, tpout=lambda: fptr(fp, "tp2out"), ytgt=lambda: fptr(fp, "y2")), par * 2 + 1, 2 * Ly + 2)
                        gpub(olc() + i64(LY.TP2_GROUPS), ob(), fresh_t())
                handoff(LC() + i64(LY.LAYER_END), fresh_t(), True)
                if fx.const_expr((kind & 1) != 0):   # the target body: the draft context taps (read before the next front rewrites aRout)
                    if (ltab(fp, Ly, "lflags")() & fx.Int64(16)) != fx.Int64(0):
                        tap0 = NL - 4
                        CX.stage_tap1(dict(t=fresh_t(), b=b, aux8=fptr(fp, "aux8"), auxs=fptr(fp, "auxs")),
                                      TRx, Ly - tap0, fptr(fp, "aRout"))
                stamp(18)
        if fx.const_expr(part == "target"):   # the step's first launch ends with the head, sampling and verification
            b = hx.opaque_s(fx.block_idx.x)
            sm = hx.lds_base()
            if fresh_t() == 0:
                hx.gstore(st + i64(b) * (32 * 8) + i64(25 * 8), hx.clock())
            ST.target(tp, fresh_t(), b, sm, st, cnt + i64((NL + NDR) * LCB), recv, rank, head_d=4,
                     ctx=_ctxtab(fp, NDR), T=TR)
        if fx.const_expr(NDR > 0 and part != "target"):
            b = hx.opaque_s(fx.block_idx.x)
            sm = hx.lds_base()
            if fresh_t() == 0:
                hx.gstore(st + i64(b) * (32 * 8) + i64(26 * 8), hx.clock())
            ST.draft(tp, fresh_t(), b, sm, st, cnt + i64((NL + NDR) * LCB), recv, rank, head_d=4)
        tp_epoch_end(fp, tep)
        hx.TOFLAG[0] = None   # (the counter pointer belongs to this kernel's trace only)
        _BASES.clear()   # (this trace's values: FlyDSL checks the globals launch reaches are unchanged between calls)
        _EPOCH[0] = 0
        _ = keyed

    @flyc.jit
    def launch(recv0: Int64, recv1: Int64, recv2: Int64, recv3: Int64, cnt: Int64, st: Int64, scale: fx.Float32, fp: Int64,
               tp: Int64, stream: fx.Stream = fx.Stream(None)):
        """recv0..3: the 4 ranks' receive buffers; cnt: the step's zeroed handoff counters; st: stamps; scale: the
        attention softmax scale; fp: the pointer table (FPTRS, ATAB, layer rows); tp: the step tail's table."""
        _ = keyed
        body(recv0, recv1, recv2, recv3, cnt, st, scale, fp, tp).launch(
            grid=(CTAS,), block=(THREADS,), smem=max(L["LDS"], ST.HEAD_LDS if ndr else 0, FRONT_LDS_OFF + max(FS.FRONT_LDS, MS.MOE_LDS), RKOFF + FS.RK_BYTES), cluster=(CL, 1, 1), stream=stream)

    return launch, dict(L, TPG=TPG)
