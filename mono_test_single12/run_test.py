# SPDX-License-Identifier: MIT
# Copyright (C) 2026, Advanced Micro Devices, Inc. All rights reserved.
"""Single-GPU test of the gfx1250 DeepSeek-V4.1 step kernel's layer loop (atom/models/deepseek_v41/mono/gfx1250).

The kernel is built unmodified as ``step.build(TR, rank=0, NL=n, ndr=0, part="all")``: the target entry and n target
layers, no head / sampling / draft (those exchange with the peers in layouts a pointer alias cannot fold). The TP4
all-reduce is folded onto this GPU by aliasing the receive bases: rank 0 pushes "peer o"'s words to
``recv[o] + src 0 slot`` and polls ``recv[0] + src o slot``; with ``recv[o] = recv[0] + o * TP_TG * 16`` both are the same
address. The network computed is therefore TP4 with all four ranks holding the same (synthetic) shard.

Checks: no cross-rank poll / handoff timeout, finite, bounded and non-degenerate outputs (head input ``xh``, the last
residual streams ``aRout``, this step's KV ring rows), run-to-run agreement over repeated launches (both receive epochs)
and optionally against a saved golden, within a relative L2 bound: the kernel is not bitwise repeatable (stage_A's
atomic f32 sums of squares; the FP8 quantizations and the top-6 routing amplify their order noise).

stage_C (wq_b, q_norm rstd, RoPE) is swapped at build time (step.stage_C, no ATOM source edit) per --stagec:
  native  the kernel as is
  asm     kernels/stage_c_asm.stage_C_asm: the whole stage_C is the inline sp3 fragment (sp3/stage_c_full.sp3)
  dual    native stage_C as is (q, read by stage_D: the rest of the kernel unchanged), then per layer Ly the native one
          again into H[2 Ly] and the asm one into H[2 Ly + 1] (H: behind q in its buffer); same launch, same inputs, so
          the two must be bit-identical for every layer
"""

import argparse
import hashlib
import importlib
import json
import math
import sys
import time
from pathlib import Path

import torch

PKG = "atom.models.deepseek_v41.mono.gfx1250"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
H = 5120
REQ, ROWS_PER_REQ = 8, 6
TP_TG = 40960  # attention.tp_allreduce: 16-byte words a (region, source) slot
V_EMB = 4096  # rows of the synthetic embedding table (the step's ids are drawn below it)
ROPE_POS = 8192


def log(*a):
    print(*a, flush=True)


def kernels():
    names = ("step", "attention", "front", "moe", "head", "tail", "draft_ctx", "layout")
    return {n: importlib.import_module(f"{PKG}.kernels.{n}") for n in names}


class Synth:
    """Synthetic weights in the layouts the kernel reads (weights/layer.py, weights/planes.py, tables.py)."""

    def __init__(self, dev, seed):
        self.dev = dev
        self.g = torch.Generator(device=dev)
        self.g.manual_seed(seed)

    def randn(self, *shape, std=1.0, dtype=torch.float32):
        return (torch.randn(*shape, generator=self.g, device=self.dev) * std).to(dtype)

    def fp8(self, rows, k, code):
        """FP8 e4m3 [rows][k] (checkpoint row order) and its 32 x 32 block E8M0 codes, all `code` (2^(code-127))."""
        w = self.randn(rows, k).clamp(-8, 8).to(torch.float8_e4m3fn).view(torch.uint8).contiguous()
        s = torch.full((rows // 32, k // 32), code, dtype=torch.uint8, device=self.dev)
        return w, s

    def bytes_(self, *shape):
        return torch.randint(0, 256, shape, dtype=torch.uint8, generator=self.g, device=self.dev)


def hi_lo(fn, rows=128):
    f = fn.float().reshape(-1)
    hi = torch.zeros(rows * H, dtype=torch.bfloat16, device=f.device)
    lo = torch.zeros_like(hi)
    hi[: f.numel()] = f.to(torch.bfloat16)
    lo[: f.numel()] = (f - hi[: f.numel()].float()).to(torch.bfloat16)
    return hi, lo


def attention_weights(S):
    out = {}
    # codes ~ 1 / sqrt(K): keeps every GEMM's output O(1)
    for name, (rows, k, code) in {"wqkv": (1792, 5120, 121), "wqb": (8192, 1280, 122), "woa": (2048, 4096, 121),
                                  "wob": (5120, 2048, 121)}.items():
        out[name], out[name + "_s"] = S.fp8(rows, k, code)
    out["qnw"] = (1.0 + S.randn(1792, std=0.05)).contiguous()
    out["kvnw"] = (1.0 + S.randn(512, std=0.05)).contiguous()
    out["sink"] = S.randn(16, std=0.5).contiguous()
    return out


def hc(S, prefix):
    fnh, fnl = hi_lo(S.randn(24, 4 * H, std=0.02))
    return {f"{prefix}fnh": fnh, f"{prefix}fnl": fnl,
            f"{prefix}hsc": (1.0 + S.randn(3, std=0.1)).contiguous(), f"{prefix}hbs": S.randn(24, std=0.1).contiguous()}


def ffn_front(S, gate_std):
    out = hc(S, "")
    out["nw"] = (1.0 + S.randn(H, std=0.05)).to(torch.bfloat16).contiguous()
    out["gate"] = S.randn(384, H, std=gate_std, dtype=torch.bfloat16).contiguous()
    out["gbias"] = S.randn(384, std=0.01).contiguous()
    return out


def attention_front(S, last):
    if last:  # the final collapse: only the norm weight is read
        z = torch.zeros(128 * H, dtype=torch.bfloat16, device=S.dev)
        return {"afnh": z, "afnl": z, "ahsc": torch.zeros(3, device=S.dev), "ahbs": torch.zeros(24, device=S.dev),
                "anw": (1.0 + S.randn(H, std=0.05)).to(torch.bfloat16).contiguous()}
    out = hc(S, "a")
    out["anw"] = (1.0 + S.randn(H, std=0.05)).to(torch.bfloat16).contiguous()
    return out


def routed_experts(S):
    pad = 640
    return {
        "mw13": S.bytes_(384, 2 * pad, H // 2),  # MXFP4 (every byte a valid e2m1 pair)
        "ms13": torch.full((384, 2 * pad // 32, H // 32 * 32), 119, dtype=torch.uint8, device=S.dev),
        "mw2": S.bytes_(384, H, pad // 2),
        "ms2": torch.full((384, H // 32, pad // 32 * 32), 120, dtype=torch.uint8, device=S.dev),
    }


def shared_expert(S):
    from atom.models.deepseek_v41.mono.gfx1250.weights.planes import pack_shared_local
    gu, gus = S.fp8(2 * 576, H, 121)
    w2, w2s = S.fp8(H, 576, 123)
    return pack_shared_local(gu, gus, w2, w2s)


def rope_tables(dev, base):
    inv = 1.0 / (base ** (torch.arange(0, 64, 2, dtype=torch.float64, device=dev) / 64))
    ang = torch.arange(ROPE_POS, dtype=torch.float64, device=dev)[:, None] * inv[None, :]
    return torch.cos(ang).to(torch.bfloat16).contiguous(), torch.sin(ang).to(torch.bfloat16).contiguous()


def window_meta(TR, ctx_lens, ring):
    """Per row (request q = r // 6, verify row j = r % 6, position p = ctx + j): kmeta [first, count, 0, base] of its
    causal window (<= 128 keys, oldest first in the ring), the ring row it writes (kvw), its position."""
    kmeta, kvw, pos = [], [], []
    for r in range(TR):
        q, j = divmod(r, ROWS_PER_REQ)
        p = ctx_lens[q] + j
        count = min(128, p + 1)
        first = (p - count + 1) % ring
        base = q * ring
        kmeta += [first, count, 0, base]
        kvw.append(base + p % ring)
        pos.append(p)
    return kmeta, kvw, pos


def q_bytes(K):
    return K["attention"].T * K["attention"].NQ * 2


def install_stage_c(K, mode):
    """step.stage_C <- the --stagec variant (step.build looks the name up at trace time)."""
    M, AS = K["step"], K["attention"]
    from kernels import stage_c_asm as SC
    native = AS.stage_C
    if mode == "native":
        M.stage_C = native
        return ""
    if mode == "asm":
        M.stage_C = SC.stage_C_asm
    else:
        ring_rows = REQ * AS.KG_RING
        qb = q_bytes(K)

        def stage_C_dual(c):
            native(c)
            ly = AS.i64(c["kring_off"] // ring_rows)   # the layer: this test's kring is Ly * REQ * ring
            hist = lambda k: c["q"] + (ly * 2 + 1 + k) * qb
            native(M.cwith(c, q=hist(0)))
            SC.stage_C_asm(M.cwith(c, q=hist(1)))
        M.stage_C = stage_C_dual
    return f"+stagec={mode}:{SC.FRAGMENT_TAG}"


def build_state(K, args, dev):
    M, AS, LY = K["step"], K["attention"], K["layout"]
    from atom.models.deepseek_v41.mono.gfx1250 import buffers
    T, NL = buffers.T_MAX, args.layers
    S = Synth(dev, args.seed)
    keep = []
    t0 = time.time()
    sizes = buffers.scratch_bytes(K, NL + 3)
    if args.stagec == "dual":   # q, then the history H[2 NL]: native / asm per layer
        assert sizes["q"] == q_bytes(K), sizes["q"]
        sizes["q"] = q_bytes(K) * (1 + 2 * NL)
    scratch = {n: torch.zeros(b, dtype=torch.uint8, device=dev) for n, b in sizes.items()}
    dummy = torch.zeros(1 << 20, dtype=torch.uint8, device=dev)
    keep.append(dummy)

    # weights: per layer attention / fronts; one routed-expert set and one shared plane for every layer (memory)
    mpl = routed_experts(S)
    shp = shared_expert(S)
    rows = []
    for Ly in range(NL):
        rows.append({**attention_weights(S), **ffn_front(S, args.gate_std), **attention_front(S, last=Ly == NL - 1)})
    entry = attention_front(S, last=False)  # layer 0's attention front (target entry row)
    rope = [rope_tables(dev, 10000.0)]
    engram = {}
    eng_rows = [k - 1 for k in (1, 14) if k < NL] if args.engram else []
    for Ly in eng_rows:
        w, s = S.fp8(25600, 6144, 120)
        engram[Ly] = {"engw": w, "engws": s, "enggw": S.randn(4, H, std=0.02).contiguous(),
                      "engemb": S.randn(T, 6144, dtype=torch.bfloat16).contiguous()}
    keep += [mpl, shp, rows, entry, rope, engram]
    log(f"weights: {NL} layers, {len(eng_rows)} Engram rows, {time.time() - t0:.1f} s")

    # the step's inputs: the window geometry of every request, its KV ring rows prefilled (the cache)
    ring = AS.KG_RING
    ctx_lens = [args.ctx + 41 * q for q in range(REQ)]
    z32 = lambda n, fill=0: torch.full((n,), fill, dtype=torch.int32, device=dev)
    step = {"kmeta": z32(T * 4), "knsel": z32(T), "ksel": z32(T * 512), "kvw": z32(T, -1),
            "rpos": torch.zeros(T, dtype=torch.int64, device=dev), "kmeta_d": z32(T * 4), "kvw_d": z32(T, -1),
            "rpos_d": torch.zeros(T, dtype=torch.int64, device=dev), "tids": z32(T), "dgeom": z32(64)}
    kmeta, kvw, pos = window_meta(args.rows, ctx_lens, ring)
    step["kmeta"][: len(kmeta)].copy_(torch.tensor(kmeta, dtype=torch.int32))
    step["kvw"][: len(kvw)].copy_(torch.tensor(kvw, dtype=torch.int32))
    step["rpos"][: len(pos)].copy_(torch.tensor(pos, dtype=torch.int64))
    step["tids"][: args.rows].copy_(torch.randint(0, V_EMB, (args.rows,), generator=S.g, device=dev))
    layer_rows = REQ * ring
    pool0 = S.randn(NL * layer_rows, AS.KG_ROW, std=1.0, dtype=torch.bfloat16)
    pool = pool0.clone()
    keep += [step, pool0, pool]
    emb = S.randn(V_EMB, H, std=1.0, dtype=torch.bfloat16)
    noise = S.randn(H, dtype=torch.bfloat16)
    keep += [emb, noise]

    # the receive buffer: one rank's, the three "peers" aliased into its own source slots
    recv_half = M.RECV_HALF
    recv_buf = torch.zeros(2 * recv_half + 4 * TP_TG * 16, dtype=torch.uint8, device=dev)
    keep.append(recv_buf)
    recv = [recv_buf.data_ptr() + o * TP_TG * 16 for o in range(4)]

    # fp: FPTRS, ATAB, the layer rows (row TARGET_ENTRY_ROW: the target entry's attention front)
    src = dict(scratch)
    src["tpep"] = torch.zeros(16, dtype=torch.uint8, device=dev)
    src["ctxtab"] = torch.zeros(64, dtype=torch.int64, device=dev)
    keep += [src["tpep"], src["ctxtab"]]
    src.update(rows[0])
    src.update(shplane=shp, emb=emb, noise=noise, **step)
    src.update(rcos=rope[0][0], rsin=rope[0][1])
    src.update(pre=scratch["anpre"], post=scratch["anpost"], comb=scratch["ancomb"], R=scratch["aRout"])
    miss = [k for k in M.FPTRS if k not in src] + [k for k in M.ATAB if k not in src and not k.startswith("recv")
                                                  and k != "kv"]
    if miss:
        raise SystemExit(f"no buffer for {miss}")
    zero_keys = {"engw", "engws", "enggw", "engemb", "ibat", "kring", "ccap", "wcap", "cmain", "crpp", "cprow",
                 "bstride", "irpp", "ilw", "imain", "lflags", "cstate"}

    def row(w, Ly, kring, lflags, extra=None):
        p = {k: v.data_ptr() for k, v in w.items()}
        p.update({k: v.data_ptr() for k, v in mpl.items()})
        rc, rs = rope[0]
        p.update(shplane=shp.data_ptr(), rcos=rc.data_ptr(), rsin=rs.data_ptr(), ksel=step["ksel"].data_ptr(),
                 knsel=step["knsel"].data_ptr(), kring=kring, lflags=lflags)
        p.update(extra or {})
        return [p.get(k, 0 if k in zero_keys else dummy.data_ptr()) for k in M.LKEYS]

    tap0 = NL - 4
    nrows = max(NL, LY.TARGET_ENTRY_ROW + 1)
    table_rows = [[0 if k in zero_keys else dummy.data_ptr() for k in M.LKEYS] for _ in range(nrows)]
    lflags_used = []
    for Ly in range(NL):
        fl = 16 if tap0 <= Ly <= tap0 + 2 else 0
        extra = {}
        if Ly in engram:
            fl |= 128
            extra = {k: v.data_ptr() for k, v in engram[Ly].items()}
        lflags_used.append(fl)
        table_rows[Ly] = row(rows[Ly], Ly, Ly * layer_rows, fl, extra)
    table_rows[LY.TARGET_ENTRY_ROW] = row({**rows[0], **entry}, 0, 0, 0)
    head = [src[k].data_ptr() for k in M.FPTRS]
    rv = dict(zip(("recv0", "recv1", "recv2", "recv3"), recv))
    head += [rv[k] if k in rv else (pool if k == "kv" else src[k]).data_ptr() for k in M.ATAB]
    fptab = torch.tensor(head + [v for r in table_rows for v in r], dtype=torch.int64, device=dev)
    tp = torch.zeros(64, dtype=torch.int64, device=dev)  # (the tail's table: not read without the tail)
    keep += [fptab, tp]
    return dict(keep=keep, scratch=scratch, fptab=fptab, tp=tp, recv=recv, pool=pool, pool0=pool0, step=step,
                kvw=kvw, layer_rows=layer_rows, lflags=lflags_used, ctx_lens=ctx_lens, tpep=src["tpep"])


def outputs(st, args):
    sc, TR = st["scratch"], args.rows
    xh = sc["xh"].view(torch.bfloat16)[: TR * H].view(TR, H).clone()
    rout = sc["aRout"].view(torch.bfloat16)[: TR * 4 * H].view(TR, 4, H).clone()
    kvw = torch.tensor(st["kvw"], dtype=torch.int64, device=xh.device)
    rows = torch.cat([kvw + Ly * st["layer_rows"] for Ly in range(args.layers)])
    kv = st["pool"][rows].clone()
    return {"xh": xh, "aRout": rout, "kv_rows": kv}


def compare_history(K, st, args):
    """H[2 Ly] (native) vs H[2 Ly + 1] (asm) for every layer, over the rows stage_C computes (MT tiles of 16)."""
    AS = K["attention"]
    rows = (args.rows + 15) // 16 * 16
    h = st["scratch"]["q"].view(torch.int16).view(1 + 2 * args.layers, AS.T, AS.NQ)[1:, :rows]
    nat, asm = h[0::2], h[1::2]
    diff = nat != asm
    per_layer = diff.flatten(1).sum(1).tolist()
    unwritten = int(((asm == -1) & (nat != -1)).sum() + ((nat == -1) & (asm != -1)).sum())
    first = None
    if diff.any():
        ly, r, col = diff.nonzero()[0].tolist()
        first = {"layer": ly, "row": r, "col": col, "native": int(nat[ly, r, col]) & 0xFFFF, "asm": int(asm[ly, r, col]) & 0xFFFF}
    return {"elements": int(diff.numel()), "mismatches": int(diff.sum()), "per_layer": per_layer,
            "layers_equal": sum(1 for v in per_layer if v == 0), "unwritten": unwritten, "first": first,
            "nan": int(torch.isnan(nat.view(torch.bfloat16)).sum())}


def stats(t):
    f = t.float()
    return {"finite": bool(torch.isfinite(f).all()), "absmax": float(f.abs().max()), "rms": float(f.pow(2).mean().sqrt()),
            "row_std_min": float(f.reshape(f.shape[0], -1).std(dim=1).min())}


def digest(t):
    return hashlib.sha256(t.contiguous().view(torch.uint8).cpu().numpy().tobytes()).hexdigest()[:16]


def rel_l2(a, b):
    return float((a.float() - b.float()).norm() / b.float().norm().clamp_min(1e-30))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=48, help="target rows (6 a request, <= 48)")
    ap.add_argument("--layers", type=int, default=4, help="target layers of the build (1..40)")
    ap.add_argument("--repeat", type=int, default=3, help="launches (each a fresh step on the same inputs)")
    ap.add_argument("--ctx", type=int, default=60, help="context length of request 0 (request q: + 41 q)")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--gate-std", type=float, default=0.02, help="router weight std")
    ap.add_argument("--no-engram", dest="engram", action="store_false", help="no Engram rows (layers 1 / 14)")
    ap.add_argument("--device", type=int, default=0)
    ap.add_argument("--rtol", type=float, default=None,
                    help="relative L2 bound of run-to-run and golden differences (default none, reported only: the "
                         "kernel is not bitwise repeatable and its kv_rows noise is heavy-tailed, the native kernel "
                         "measured 0.08 .. 0.27 at 4 layers; --stagec dual is the asm check)")
    ap.add_argument("--absmax", type=float, default=1e4, help="bound on |output| (a blow-up)")
    ap.add_argument("--stagec", default="dual", choices=("native", "asm", "dual"),
                    help="stage_C variant (see the module doc); dual: per-layer bitwise native vs asm")
    ap.add_argument("--golden", type=Path, help="compare the outputs with / write them to this .pt file")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "build" / "result.json")
    args = ap.parse_args()
    if args.rows % ROWS_PER_REQ or not 0 < args.rows <= 48 or not 1 <= args.layers <= 40:
        raise SystemExit("--rows: a multiple of 6 up to 48; --layers: 1..40")
    rtol = args.rtol if args.rtol is not None else math.inf

    torch.cuda.set_device(args.device)
    dev = torch.device("cuda", args.device)
    name = torch.cuda.get_device_properties(dev).gcnArchName
    log(f"device {args.device}: {name}, {torch.cuda.get_device_properties(dev).multi_processor_count} CUs")
    K = kernels()
    M = K["step"]
    from atom.mono.plan.build_key import source_digest
    sources = source_digest("models/deepseek_v41/mono/gfx1250/kernels") + install_stage_c(K, args.stagec)
    log(f"stage_C: {args.stagec}  (build key sources {sources})")

    st = build_state(K, args, dev)
    t0 = time.time()
    launch, _ = M.build(args.rows, 0, NL=args.layers, ndr=0, part="all", sources=sources)
    scale = 512 ** -0.5
    cnt, stamps, cyc = st["scratch"]["cnt"], st["scratch"]["st"], st["scratch"]["cyc"]
    largs = (*st["recv"], cnt.data_ptr(), stamps.data_ptr(), scale, st["fptab"].data_ptr(), st["tp"].data_ptr())

    runs, times, dual = [], [], []
    for i in range(args.repeat):
        if args.stagec == "dual":
            st["scratch"]["q"].fill_(0xFF)   # a skipped history write shows as a mismatch / an unwritten count
        st["pool"].copy_(st["pool0"])  # the same cache every launch (the step rewrites its own ring rows)
        cnt.zero_()
        st["scratch"]["ss"].zero_()
        torch.cuda.synchronize()
        ta = time.time()
        launch(*largs, stream=torch.cuda.current_stream())
        torch.cuda.synchronize()
        dt = time.time() - ta
        if i == 0:
            log(f"build + first launch: {time.time() - t0:.1f} s")
        to = cyc.view(torch.int32)[:2].tolist()
        stp = stamps.view(torch.int64).view(256, 32)
        t_layers = float(stp[:, 18].max() - stp[:, 0].min()) / 1e5  # 100 MHz steady counter -> ms
        times.append(t_layers)
        out = outputs(st, args)
        runs.append(out)
        ep = int(st["tpep"].view(torch.int32)[0])
        log(f"launch {i}: {dt * 1e3:.1f} ms host, {t_layers:.2f} ms layers (device stamps), timeouts {to[0]}, "
            f"epoch -> {ep}, rel L2 vs launch 0: " + ", ".join(f"{k} {rel_l2(v, runs[0][k]):.3g}" for k, v in out.items()))
        if args.stagec == "dual":
            dual.append(compare_history(K, st, args))
            d = dual[-1]
            log(f"   dual: {d['layers_equal']}/{args.layers} layers bit-identical, {d['mismatches']} mismatching of "
                f"{d['elements']} q elements" + (f", first {d['first']}" if d["first"] else ""))

    report = {"device": name, "rows": args.rows, "layers": args.layers, "repeat": args.repeat, "seed": args.seed,
              "rtol": rtol if math.isfinite(rtol) else None, "lflags": st["lflags"], "ctx_lens": st["ctx_lens"][: args.rows // 6], "sources": sources,
              "layers_ms": times}
    fails = []
    to = cyc.view(torch.int32)[:2].tolist()
    report["timeouts"] = to[0]
    if to[0]:
        fails.append(f"{to[0]} poll timeouts (last site {to[1]})")
    report["stats"] = {k: stats(v) for k, v in runs[0].items()}
    for k, s in report["stats"].items():
        if not s["finite"]:
            fails.append(f"{k}: non-finite values")
        elif s["absmax"] > args.absmax:
            fails.append(f"{k}: |x| up to {s['absmax']:.3g} > {args.absmax}")
        if s["rms"] == 0 or s["row_std_min"] == 0:
            fails.append(f"{k}: degenerate (zero rms or a constant row)")
    agree = {}
    for k in runs[0]:
        worst = max([rel_l2(r[k], runs[0][k]) for r in runs[1:]], default=0.0)
        bitwise = all(torch.equal(r[k].view(torch.uint8), runs[0][k].view(torch.uint8)) for r in runs[1:])
        agree[k] = {"bitwise": bitwise, "max_rel_l2": worst}
        if not worst <= rtol:
            fails.append(f"{k}: run-to-run rel L2 {worst:.3g} > {rtol:.3g}")
    report["run_to_run"] = agree
    report["stagec"] = args.stagec
    if dual:
        report["dual"] = dual
        for i, d in enumerate(dual):
            if d["mismatches"] or d["unwritten"]:
                fails.append(f"launch {i}: native vs asm stage_C differ in {d['mismatches']} q elements "
                             f"({d['unwritten']} unwritten)")
    report["digests"] = {k: digest(v) for k, v in runs[0].items()}
    if args.golden:
        cfg = {"rows": args.rows, "layers": args.layers, "seed": args.seed, "ctx": args.ctx, "engram": args.engram,
               "gate_std": args.gate_std}
        if args.golden.exists():
            gold = torch.load(args.golden, map_location=dev)
            if gold["config"] != cfg:
                fails.append(f"golden {args.golden} is of another configuration: {gold['config']}")
            else:
                g = {k: rel_l2(runs[0][k], gold["outputs"][k]) for k in runs[0]}
                report["golden"] = {"path": str(args.golden), "rel_l2": g}
                fails += [f"{k}: rel L2 {v:.3g} vs golden > {rtol:.3g}" for k, v in g.items() if not v <= rtol]
        else:
            args.golden.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"config": cfg, "sources": sources, "outputs": {k: v.cpu() for k, v in runs[0].items()}},
                       args.golden)
            report["golden"] = {"path": str(args.golden), "written": True}
    report["pass"] = not fails
    report["failures"] = fails
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))
    log(json.dumps({k: report[k] for k in ("stats", "run_to_run")}, indent=1))
    log(("PASS" if not fails else "FAIL: " + "; ".join(fails)) + f"  ({args.out})")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
