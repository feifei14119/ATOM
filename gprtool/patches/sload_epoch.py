# SPDX-License-Identifier: MIT
"""step.py's pointer-table reads (fptr / ltab / atab / lsel) from a table base made opaque once per interval (between
handoffs / front sub-stages, and per block: an SSA value is reused only where it dominates). addrspace(4) loads are
invariant to LLVM, so GVN / EarlyCSE merge the reads of one table slot across the whole layer and LICM hoists them out
of the layer loop: the pointers stay live in SGPRs everywhere. With an opaque base the reads of one interval still
merge, the reads of different intervals cannot (nor leave the loop).

GPRTOOL_LAZY_FRONT=1 (default): the layer loop's front (front_any) reads its ~28 pointers at their uses (a LazyC, as
the attention stages do) instead of all at its entry. GPRTOOL_FRESH_B=1 (default): see fresh_b."""
import os

import flydsl.expr as fx
from flydsl._mlir import ir
from flydsl._mlir.dialects import llvm

from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx
from atom.models.deepseek_v41.mono.gfx1250.kernels import front as FS
from atom.models.deepseek_v41.mono.gfx1250.kernels import step as M

EPOCH = [0]
BASES = {}
LOOP = {}   # (fp, Ly) of the layer loop's front, seen at its lsel reads


def base(fp):
    k = (EPOCH[0], ir.InsertionPoint.current.block, hx._v(fx.Int64(fp)))
    if k not in BASES:
        BASES[k] = fx.Int64(llvm.inline_asm(ir.IntegerType.get_signless(64), [hx._v(fx.Int64(fp))], "", "=s,0",
                                            has_side_effects=True))
    return BASES[k]


def fptr(fp, name):
    return hx.sload64(base(fp) + M.i64(M.FPTRS.index(name) * 8))


def ltab(fp, Ly, name):
    def f():
        return hx.sload64(base(fp) + (M.i64(len(M.FPTRS) + len(M.ATAB)) + M.i64(Ly) * len(M.LKEYS)
                                      + M.i64(M.LKEYS.index(name))) * 8)
    return f


def lsel(fp, Ly, isf, n0, n1):
    LOOP.update(fp=fp, Ly=Ly)
    ix = isf.select(fx.Int32(M.LKEYS.index(n0)), fx.Int32(M.LKEYS.index(n1)))
    return hx.sload64(base(fp) + (M.i64(len(M.FPTRS) + len(M.ATAB)) + M.i64(Ly) * len(M.LKEYS) + M.i64(ix)) * 8)


def atab(fp, name, off=None):
    def f():
        v = hx.sload64(base(fp) + M.i64((len(M.FPTRS) + M.ATAB.index(name)) * 8))
        return v if off is None else v + off
    return f


def epoch(f):
    def g(*a, **k):
        EPOCH[0] += 1
        r = f(*a, **k)
        EPOCH[0] += 1
        return r
    return g


FSEL = dict(R=("R", "Rout"), y=("y1", "y2"), pre=("pre", "npre"), post=("post", "npost"), comb=("comb", "ncomb"),
            Rout=("Rout", "aRout"), npre=("npre", "anpre"), npost=("npost", "anpost"), ncomb=("ncomb", "ancomb"))
LSEL = dict(fnh=("fnh", "afnh"), fnl=("fnl", "afnl"), hsc=("hsc", "ahsc"), hbs=("hbs", "ahbs"), nw=("nw", "anw"))
FPTR = dict(part="part", plog="plog", cand="cand", cands="cands", ids="ids", wts="wts", engkv="engkv",
            engpart="engpart")
LTAB = dict(gate="gate", gbias="gbias", enggw="enggw")


def lazy_front(c):
    """The layer loop's front context with its table pointers as thunks (step.py's cu: fsel / lsel / ltab / fptr)."""
    fp, Ly, isf = LOOP["fp"], LOOP["Ly"], c["isffn"]
    th = {}
    for k, (n0, n1) in FSEL.items():
        th[k] = lambda n0=n0, n1=n1: isf.select(fptr(fp, n0), fptr(fp, n1))
    for k, (n0, n1) in LSEL.items():
        th[k] = lambda n0=n0, n1=n1: lsel(fp, Ly, isf, n0, n1)
    for k, n in FPTR.items():
        th[k] = lambda n=n: fptr(fp, n)
    for k, n in LTAB.items():
        th[k] = lambda n=n: ltab(fp, Ly, n)()
    th["x8"] = lambda: isf.select(fptr(fp, "fx8"), atab(fp, "x8")())
    th["xs"] = lambda: isf.select(fptr(fp, "fxs"), atab(fp, "xs")())
    th = {k: v for k, v in th.items() if k in c}
    return M.LazyC(th, **{k: v for k, v in c.items() if k not in th})


_front_any = FS.front_any


def front_any(c, stf):
    if LOOP and os.environ.get("GPRTOOL_LAZY_FRONT", "1") == "1":
        c = lazy_front(c)
        LOOP.clear()
    return _front_any(c, stf)


M.fptr, M.ltab, M.lsel, M.atab = fptr, ltab, lsel, atab
M.handoff, M.gpub, M.gwait = epoch(M.handoff), epoch(M.gpub), epoch(M.gwait)
def fresh_b(f):
    """f(c) with c["b"] re-made opaque at its entry: b-derived arithmetic stays in the sub-stage (not hoisted out of
    the two-pass front loop, live across both fronts and the MoE)."""
    def g(c, *a, **k):
        return f(M.cwith(c, b=hx.opaque_s(c["b"])), *a, **k)
    return g


FRESH_B = os.environ.get("GPRTOOL_FRESH_B", "1") == "1"
FS.front_any = front_any
for n in ("front_A", "front_B", "front_C", "front_D", "front_E1", "front_E2"):
    f = epoch(getattr(FS, n))
    setattr(FS, n, fresh_b(f) if FRESH_B else f)
