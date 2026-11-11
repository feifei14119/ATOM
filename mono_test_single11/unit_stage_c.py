# SPDX-License-Identifier: MIT
"""stage_C alone, native vs the inline-asm replacement, bitwise.

One launch of 256 CTAs x 256 threads (the step kernel's shape): every CTA runs the native stage_C into qn and the asm one
into qa from the same synthetic inputs (qr8 / qrs, wq_b / wq_b_s, ss, rpos, rcos / rsin); the two bf16 outputs must be
bit-identical. Usage: PYTHONPATH=/app/ATOM:<this dir> python3 unit_stage_c.py [--rows 48] [--phase 1] [--mode both]
"""
import argparse
import sys
from pathlib import Path

import torch
import flydsl.compiler as flyc
import flydsl.expr as fx
from flydsl.expr.typing import Int64

from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx
from atom.models.deepseek_v41.mono.gfx1250.kernels import attention as AT
from atom.models.deepseek_v41.mono.gfx1250.kernels import dims as D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kernels import stage_c_asm as SC  # noqa: E402

T, QL, NQ, HD = D.T_MAX, AT.QL, AT.NQ, AT.HD
RPOS_MAX = 8192


def build(TR, phase, mode):
    MT = (TR + 15) // 16
    frag = SC.FRAGMENT_TAG if mode != "native" else ""

    @flyc.kernel(known_block_size=[256, 1, 1])
    def body(qr8: Int64, qrs: Int64, wqb: Int64, wqb_s: Int64, ss: Int64, rpos: Int64, rcos: Int64, rsin: Int64,
             qn: Int64, qa: Int64):
        t = hx.opaque_v(fx.thread_idx.x)
        b = hx.opaque_s(fx.block_idx.x)
        c = dict(t=t, b=b, w=t // 32, l=t % 32, MT=MT, TR=TR, stx=hx.stx_dev, qr8=qr8, qrs=qrs, wqb=wqb, wqb_s=wqb_s,
                 ss=ss, rpos=rpos, rcos=rcos, rsin=rsin)
        if fx.const_expr(mode in ("native", "both")):
            AT.stage_C(dict(c, q=qn))
        if fx.const_expr(mode in ("asm", "both") and frag != ""):
            SC.stage_C_asm(dict(c, q=qa), phase)

    @flyc.jit
    def launch(qr8: Int64, qrs: Int64, wqb: Int64, wqb_s: Int64, ss: Int64, rpos: Int64, rcos: Int64, rsin: Int64,
               qn: Int64, qa: Int64, stream: fx.Stream = fx.Stream(None)):
        body(qr8, qrs, wqb, wqb_s, ss, rpos, rcos, rsin, qn, qa).launch(grid=(256,), block=(256,), smem=0,
                                                                       cluster=(16, 1, 1), stream=stream)
    return launch


def fp8_codes(g, shape, dev):
    x = torch.randint(0, 256, shape, generator=g, dtype=torch.int32).to(torch.uint8)
    x = torch.where((x & 0x7f) == 0x7f, x ^ 1, x)   # e4m3fn: 0x7f / 0xff are NaN
    return x.to(dev)


def inputs(TR, seed, dev, specials=False):
    g = torch.Generator().manual_seed(seed)
    q = {}
    q["qr8"] = fp8_codes(g, (T, QL), dev)
    q["qrs"] = torch.randint(118, 125, (T, QL // 32), generator=g, dtype=torch.int32).to(torch.uint8).to(dev)
    q["wqb"] = fp8_codes(g, (NQ, QL), dev)
    q["wqb_s"] = torch.randint(118, 125, (NQ // 32, QL // 32), generator=g, dtype=torch.int32).to(torch.uint8).to(dev)
    q["ss"] = (torch.rand(T, generator=g) * 2000.0 + 1.0).to(dev)
    if specials:
        q["qr8"][2, 5] = 0x7F                  # a NaN in row 2 (NaN row)
        q["wqb"][100, 700] = 0xFF              # a NaN in column 100 (NaN column)
        q["qrs"][3, 7] = 254                   # row 3 scaled by 2^127 (overflow to inf)
        q["wqb_s"][200 // 32, 3] = 0           # E8M0 0 = 2^-127 (underflow to zero / denormal)
        q["ss"][0], q["ss"][1] = 0.0, 3.0e38   # rsq of eps, a huge sum of squares
    q["rpos"] = torch.randint(0, RPOS_MAX, (T,), generator=g, dtype=torch.int64).to(dev)
    q["rcos"] = torch.randn(RPOS_MAX, 32, generator=g).to(torch.bfloat16).to(dev)
    q["rsin"] = torch.randn(RPOS_MAX, 32, generator=g).to(torch.bfloat16).to(dev)
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, nargs="+", default=[48, 16, 6])
    ap.add_argument("--phase", type=int, default=1)
    ap.add_argument("--mode", default="both", choices=("native", "asm", "both"))
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--device", type=int, default=0)
    args = ap.parse_args()
    torch.cuda.set_device(args.device)
    dev = torch.device("cuda", args.device)
    ok = True
    for TR in args.rows:
        launch = build(TR, args.phase, args.mode)
        MT = (TR + 15) // 16
        for seed in args.seeds:
            for specials in (False, True):
                q = inputs(TR, seed, dev, specials)
                qn = torch.full((T, NQ), -1, dtype=torch.int16, device=dev)
                qa = torch.full((T, NQ), -1, dtype=torch.int16, device=dev)
                launch(*(q[k].data_ptr() for k in ("qr8", "qrs", "wqb", "wqb_s", "ss", "rpos", "rcos", "rsin")),
                       qn.data_ptr(), qa.data_ptr(), stream=torch.cuda.current_stream())
                torch.cuda.synchronize()
                rows = MT * 16
                if args.mode != "both":
                    out = qn if args.mode == "native" else qa
                    print(f"rows={TR} seed={seed} specials={specials}: written {(out[:rows] != -1).sum().item()}"
                          f" / {rows * NQ}", flush=True)
                    continue
                diff = (qn[:rows] != qa[:rows])
                untouched = (qa[:rows] == -1) & (qn[:rows] != -1)
                nan_n = torch.isnan(qn[:rows].view(torch.bfloat16)).sum().item()
                good = diff.sum().item() == 0 and (qn[:rows] != -1).all().item()
                ok &= good
                print(f"rows={TR} (MT={MT}) seed={seed} specials={specials}: {rows * NQ} elements, "
                      f"mismatches {diff.sum().item()}, asm-unwritten {untouched.sum().item()}, nan {nan_n} -> "
                      f"{'OK' if good else 'FAIL'}", flush=True)
                if not good:
                    idx = diff.nonzero()[:8].tolist()
                    for r, col in idx:
                        print(f"   q[{r}][{col}] native {qn[r, col].item() & 0xffff:#06x} asm {qa[r, col].item() & 0xffff:#06x}")
    if args.mode == "both":
        print("PASS" if ok else "FAIL", flush=True)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
