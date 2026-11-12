# SPDX-License-Identifier: MIT
"""--patch: the step kernel with no SGPR spill. Loads patches/step.py (the changed copy of kernels/step.py: its diff
is the source change) in place of kernels/step.py, and opens a new table-read interval (step.next_epoch) at each
front sub-stage (front.front_any's calls: the change front.py needs)."""
import importlib.util
import sys
from pathlib import Path

import atom.models.deepseek_v41.mono.gfx1250.kernels as K
from atom.models.deepseek_v41.mono.gfx1250.kernels import front as FS

NAME = "atom.models.deepseek_v41.mono.gfx1250.kernels.step"
spec = importlib.util.spec_from_file_location(NAME, Path(__file__).resolve().with_name("step.py"))
M = importlib.util.module_from_spec(spec)
sys.modules[NAME] = M
spec.loader.exec_module(M)
K.step = M


def interval(f):
    def g(*a, **k):
        M.next_epoch()
        r = f(*a, **k)
        M.next_epoch()
        return r
    return g


for n in ("front_A", "front_B", "front_C", "front_D", "front_E1", "front_E2"):
    setattr(FS, n, interval(getattr(FS, n)))


from flydsl.compiler.ast_rewriter import ASTRewriter  # noqa: E402
import flydsl.expr as fx  # noqa: E402
from atom.models.deepseek_v41.mono.gfx1250.kernels import device as hx  # noqa: E402


@ASTRewriter.transform
def note_timeout(t0, site):
    """device.note_timeout with TOFLAG[0] a thunk (step.py: the counter pointer read only where a poll times out)."""
    if fx.const_expr(hx.TOFLAG[0] is not None):
        if hx.clock() - t0 >= fx.Int64(hx.POLL_TICKS):
            f = hx.TOFLAG[0]() if callable(hx.TOFLAG[0]) else hx.TOFLAG[0]
            hx.atomic_add(f, 1)
            hx.gstore(f + fx.Int64(4), fx.Int32(site))


hx.note_timeout = note_timeout
