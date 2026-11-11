"""Compile-time adapter: c -> scalar arguments -> fixed-register ASM call.

No tensor payload is read here. wqkv.contract.json owns the parameter mapping.
"""
from pathlib import Path
import flydsl.expr as fx
from compiler import AsmFFI
from mono1250.device.sync import _noted
from mono1250.device.ops import uniform


def lds_offset(pointer):
    return fx.Int32(fx.ptrtoint(pointer))


class WqkvStage:
    def __init__(self, manifest):
        self.asm = AsmFFI(Path(manifest))

    def __call__(self, c, task, t0=0, n=1):
        if not isinstance(t0,int) or t0 != 0 or not isinstance(n,int) or n != 1:
            raise ValueError("this assembly object is specialized for t0=0, n=1")
        if c["threads"] != 256:
            raise ValueError("this object requires exactly 256 threads")
        # _noted records plan effects while Python builds IR; it does not poll.
        qkv = _noted(c["qkv"], "put")
        x8 = _noted(c["x8"], "poll")
        x8s = _noted(c["x8s"], "poll")
        self.asm(
            qkv,                         # s[2:3]
            uniform(c["mailbox_tag"]),   # s0; one immutable layer value/launch
            lds_offset(c["xl"]),         # s1: workspace, not prepared input
            lds_offset(c["red"]),        # s4
            task,                        # s5
            t0,                          # v4 (each lane gets 0)
            n,                           # s6
            c["args"]["wqkv"],          # s[8:9]
            c["args"]["wqkv_s"],        # s[10:11]
            x8s,                         # s[12:13]
            x8,                          # s[14:15]
            c["tid"],                    # v0
            c["diag_base"],              # s[16:17], reserved diagnostic context
            c["failure_base"],           # s[18:19], checked by ASM polling
            c["bid"],                    # s7
            1_000_000,                   # s22, bounded polling iterations
        )
