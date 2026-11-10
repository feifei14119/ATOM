# SPDX-License-Identifier: MIT
# Copyright (C) 2026, Advanced Micro Devices, Inc. All rights reserved.
# Selected verbatim definitions from pinned attn_pre.py; see SOURCE_MANIFEST.json.
import flydsl.expr as fx
from vendor_aiter import buffer_ops as bo
from flydsl.expr import const_expr, range_constexpr
from flydsl.expr import math as fmath
from flydsl.expr.typing import T
from mono1250.kernels.dims import HC, HIDDEN, KV_DIM, Q_RANK
from mono1250.device.ops import batched_rounds, bf16_round, first_rounds, fresh, rsrc, traced
from mono1250.device.sync import POLL_MAX
from mono1250.plan.execution import THREADS


K_MIX = HC * HIDDEN


MIX = HC * (HC + 2)  # 24 projections: pre 4 | post 4 | comb 16


QKV_ROWS = Q_RANK + KV_DIM  # 1792


EPS = 1e-20


COLS = 32  # hidden columns a slice task


SLICES = HIDDEN // COLS  # 160


KT = HC * COLS  # projection columns a slice task


PART = MIX + 1  # a slice's partials a token: the mixes, then the sum of squares


X8_WORDS = HIDDEN // 4  # fp8 words of a normed row


def fma(a, b, c):
    return fx.Float32(fmath.fma(a, b, c))


def ld_f32(ptr, i):
    return fx.Float32(bo.buffer_load(rsrc(ptr), i, vec_width=1, dtype=T.f32))


def ld_bf(ptr, i):
    return fx.Float32(
        fx.BFloat16(bo.buffer_load(rsrc(ptr), i, vec_width=1, dtype=T.bf16))
    )


LDS_PAD = 4


def lds_row(words):
    return words + LDS_PAD


def lds_at(u, row):
    """Element u of a span of rows ``row`` wide, at the ``lds_row`` stride."""
    return u + u // row * LDS_PAD


def pend_value(c, t, col, cc):
    """The owed post's sublayer output at (token t, column col): read from
    ``pend``, or where a caller staged it (``pend_lds``, [token][32] of this
    task's columns: a reduction it did first)."""
    if const_expr(c.get("pend_lds") is None):
        return ld_bf(c["args"]["pend"], t * HIDDEN + col)
    return fx.ptr_load(c["pend_lds"] + (t * COLS + cc))


@traced
def slice_input(c, task, idx):
    """Thread ``idx``'s pair of the layer input (token idx / 16, columns
    32 task + 2 (idx % 16) ..) and the drafter's tap."""
    s, rl = c["S"], c["rl"]
    a = c["args"]
    c0 = task * COLS
    if idx < s * COLS // 2:
        t = idx // (COLS // 2)
        cc = 2 * (idx % (COLS // 2))
        outs = []
        for d in range_constexpr(2):
            acc = fx.Float32(0.0)
            for h in range_constexpr(HC):
                rb = fx.ptr_load(rl + (t * KT + h * COLS + cc + d))
                acc = acc + ld_f32(a["pre_in"], t * HC + h) * rb
            outs.append(acc)
        c["put_bf"](c["lin"], t * HIDDEN + c0 + cc, outs)
        if const_expr(c["aux"]):
            # the drafter's tap: torch mean over the bf16 streams (sum in order, / 4)
            for d in range_constexpr(2):
                acc = fx.Float32(0.0)
                for h in range_constexpr(HC):
                    acc = acc + fx.ptr_load(rl + (t * KT + h * COLS + cc + d))
                bo.buffer_store(
                    (acc * fx.Float32(1.0 / HC)).to(fx.BFloat16),
                    rsrc(a["aux"]),
                    t * HIDDEN + c0 + cc + d,
                )


def slice_at(c0, e):
    """Element e of a slice task at column c0: (token, stream, hidden column)."""
    return e // KT, (e % KT) // COLS, c0 + e % COLS


def slice_loads(c, c0, e):
    """Element e's loads of ``stage_slice`` (e clamped into the step's)."""
    a = c["args"]
    t, o, col = slice_at(c0, e)
    if const_expr(not c["fold"]):
        # a settled residual: read as it is, and left where it is
        return ld_bf(a["res_in"], (t * HC + o) * HIDDEN + col)
    r = [ld_bf(a["res_in"], (t * HC + h) * HIDDEN + col) for h in range(HC)]
    cm = [ld_f32(a["comb_in"], (t * HC + h) * HC + o) for h in range(HC)]
    return r, cm, ld_f32(a["post_in"], t * HC + o)


def slice_row(c, c0, e, got):
    """Element e of ``stage_slice``'s R_new from ``slice_loads``' values."""
    a = c["args"]
    t, o, col = slice_at(c0, e)
    if const_expr(c["fold"]):
        r, cm, post = got
        # aiter's mhc_fused_post_pre_delayed_rmsnorm: ((post x + c0 r0)
        # + c1 r1) + c2 r2, each product rounded, then fma(c3, r3, ..)
        v = post * pend_value(c, t, col, e % COLS) + (r[0] * cm[0])
        for h in range_constexpr(1, HC - 1):
            v = v + cm[h] * r[h]
        # bf16 R_new is what the collapse, the sums of squares and the
        # mix projection all read
        v = bf16_round(fma(cm[HC - 1], r[HC - 1], v))
        bo.buffer_store(
            v.to(fx.BFloat16), rsrc(a["res_out"]), (t * HC + o) * HIDDEN + col
        )
    else:
        v = got
    fx.ptr_store(v, c["rl"] + (t * KT + o * COLS + e % COLS))


def slice_fn_loads(c, task):
    """``task``'s columns of the mix projection's weights, a thread's
    ``MIX KT / THREADS``: no wait decides them, so they go out first."""
    a = c["args"]
    c0 = task * COLS
    fns = []
    for i in range_constexpr(MIX * KT // THREADS):
        e = c["tid"] + THREADS * i
        j = e // KT
        o = (e % KT) // COLS
        fns.append(ld_f32(a["hc_fn"], j * K_MIX + o * HIDDEN + c0 + e % COLS))
    return fns


def slice_issued(c, task, pre):
    """``stage_slice``'s (weights, first rows' loads) issued ahead of its rows:
    what the caller issued (``pre``; weights None: loaded after the rows), or
    else the weights now."""
    return (slice_fn_loads(c, task), None) if pre is None else pre


@traced
def poll_copy(c, idx, width, spans, live=None):
    """Mailbox spans [(region, pair_of, n, dst, row)] into LDS: element u (pair
    ``pair_of(u)``) to dst + u, or ``lds_at(u, row)`` for a span of rows
    ``row`` words wide. Thread ``idx`` of ``width`` takes u = idx, idx +
    width, ..., POLL_MAX a round trip, each batch stored before the next is
    polled (holding them all spills past S = 16); a thread past a span's end
    re-reads its last element and stores nothing.

    ``live``: a span's elements the reader needs (traced, <= n), a span each;
    a batch past them is not polled and an element past them neither polled
    nor written (one past a step's rows is never written)."""
    idx = fresh(idx)  # its elements' indices not hoisted out of a task loop
    if const_expr(live is None):
        _poll_store_batches(c, [
            (region, pair_of, n, (dst, row), idx + width * i)
            for region, pair_of, n, dst, row in spans
            for i in range((n + width - 1) // width)
        ])  # fmt: skip
        return
    for (region, pair_of, n, dst, row), need in zip(spans, live):
        chunks = [
            (region, pair_of, need, (dst, row), idx + width * i)
            for i in range((n + width - 1) // width)
        ]
        for b0 in range_constexpr(0, len(chunks), POLL_MAX):
            if chunks[b0][4] < need:
                _poll_store_batches(c, chunks[b0 : b0 + POLL_MAX])


@traced
def _poll_store_batches(c, chunks):
    """``poll_copy``'s chunks [(region, pair_of, n, (dst, row), u)], POLL_MAX a
    round trip, each batch stored before the next is polled."""
    for b0 in range_constexpr(0, len(chunks), POLL_MAX):
        batch = chunks[b0 : b0 + POLL_MAX]
        got = c["poll"]([(r, p(fx.min(u, n - 1)), 1) for r, p, n, _, u in batch])
        for (_, _, n, (dst, row), u), v in zip(batch, got):
            at = u if row is None else lds_at(u, row)
            if u < n:
                fx.ptr_store(v[0], dst + at)

