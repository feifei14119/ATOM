# SPDX-License-Identifier: MIT
"""Cost of the step kernel's synchronization primitives on this GPU (256 CTAs x 256 threads, clusters of 16, as the
step kernel launches): workgroup barrier, cluster barrier (+ fences: attention.cluster_sync), device-wide handoff."""
import sys

import torch
import flydsl.compiler as flyc
import flydsl.expr as fx
from flydsl.expr import gpu
from flydsl.expr.typing import Int64, Int32

from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx
from atom.models.deepseek_v41.mono.gfx1250.kernels.attention import cluster_sync

N = 64


def bench(kind):
    @flyc.kernel(known_block_size=[256, 1, 1])
    def body(out: Int64, cnt: Int64):
        t = hx.opaque_v(fx.thread_idx.x)
        b = hx.opaque_s(fx.block_idx.x)
        t0 = hx.clock()
        for i in range(hx.opaque_s(Int32(N))):
            if fx.const_expr(kind == "wg"):
                gpu.barrier()
            if fx.const_expr(kind == "cluster"):
                hx.cluster_barrier()
            if fx.const_expr(kind == "cluster_sync"):
                cluster_sync()
            if fx.const_expr(kind == "handoff"):
                hx.handoff(cnt + Int64(i) * 4, t, True)
            if fx.const_expr(kind == "atomic_same"):   # every CTA's thread 0: one atomic add on a shared counter
                if t == 0:
                    hx.atomic_add(cnt + Int64(i) * 4, 1)
                gpu.barrier()
            if fx.const_expr(kind == "atomic_own"):    # every CTA's thread 0: one atomic add on its own word
                if t == 0:
                    hx.atomic_add(cnt + Int64(N + 16) * 4 + Int64(b) * 4, 1)
                gpu.barrier()
            if fx.const_expr(kind == "load_agent"):    # one agent-scope load of a counter
                if t == 0:
                    v = hx.gload(cnt + Int64(i) * 4, Int32, scope="agent")
                    if v == Int32(-12345):
                        hx.gstore(out + Int64(b) * 8, Int64(0))
                gpu.barrier()
            if fx.const_expr(kind in ("load_plain", "load_nt")):
                if t == 0:
                    v = hx.gload(cnt + Int64(i) * 4, Int32, nt=kind == "load_nt")
                    if v == Int32(-12345):
                        hx.gstore(out + Int64(b) * 8, Int64(0))
                gpu.barrier()
            if fx.const_expr(kind == "sleep1"):
                hx.s_sleep(1)
        t1 = hx.clock()
        if t == 0:
            hx.gstore(out + Int64(b) * 8, t1 - t0)

    @flyc.jit
    def launch(out: Int64, cnt: Int64, stream: fx.Stream = fx.Stream(None)):
        body(out, cnt).launch(grid=(256,), block=(256,), smem=0, cluster=(16, 1, 1), stream=stream)

    out = torch.zeros(256, dtype=torch.int64, device="cuda")
    cnt = torch.zeros(N + 16 + 256, dtype=torch.int32, device="cuda")
    res = []
    for _ in range(3):
        cnt.zero_()
        launch(out.data_ptr(), cnt.data_ptr(), stream=torch.cuda.current_stream())
        torch.cuda.synchronize()
        res.append(float(out.max()) / 100.0 / N)  # 100 MHz ticks -> us, per iteration
    print(f"{kind:13s} {min(res):9.2f} us / iteration (max over CTAs)", flush=True)


if __name__ == "__main__":
    torch.cuda.set_device(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    for k in sys.argv[2].split(",") if len(sys.argv) > 2 else (
            "wg", "cluster", "cluster_sync", "sleep1", "load_agent", "atomic_own", "atomic_same", "handoff"):
        bench(k)
