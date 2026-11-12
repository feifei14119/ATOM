# SPDX-License-Identifier: MIT
"""gfx1250 register names <-> 32-bit units, register sets, range formatting."""
import re
import subprocess
import tempfile
from pathlib import Path

LLVM = Path("/app/llvm-upstream/build")   # the LLVM with the gfx1250 v256+ inline asm clobber fix
VGPR_HW = 1024                            # addressable VGPRs (v0..v1023, four 256-register MSB banks)
SGPR_HW = 106                             # s0..s105 (+ vcc_lo / vcc_hi)

_TUPLE = re.compile(r"(vgpr|sgpr|ttmp)(\d+)")


def units(name, mask=None):
    """MIR physical register (no '$') -> its 32-bit units ('v12', 's5', 'vcc_lo', 'scc', ...), lane mask applied
    (AMDGPU lane masks: 2 bits a 32-bit unit). A lo16 / hi16 half maps to its unit (partial=True)."""
    partial = False
    base = name
    if base.endswith("_lo16") or base.endswith("_hi16"):
        partial, base = True, base[:-5]
    parts = _TUPLE.findall(base)
    if parts and base.replace("_", "").replace("vgpr", "").replace("sgpr", "").replace("ttmp", "").isdigit():
        us = [{"vgpr": "v", "sgpr": "s", "ttmp": "t"}[k] + i for k, i in parts]
    elif base in ("vcc", "exec"):
        us = [base + "_lo", base + "_hi"]
    elif base == "sgpr_null" or base.startswith("src_") or base in ("mode", "private_rsrc_reg", "sp_reg", "fp_reg"):
        us = []
    else:
        us = [base]
    if mask is not None:
        us = [u for i, u in enumerate(us) if (mask >> (2 * i)) & 3]
    return us, partial


def vnum(u):
    return int(u[1:]) if u[0] == "v" and u[1:].isdigit() else None


def snum(u):
    return int(u[1:]) if u[0] == "s" and u[1:].isdigit() else None


def split(us):
    """(sorted VGPR numbers, sorted SGPR numbers, other units) of a unit set."""
    v = sorted(n for n in (vnum(u) for u in us) if n is not None)
    s = sorted(n for n in (snum(u) for u in us) if n is not None)
    o = sorted(u for u in us if vnum(u) is None and snum(u) is None)
    return v, s, o


def ranges(nums, pfx):
    """[0, 1, 2, 5] -> 'v[0:2] v5'."""
    out, i, nums = [], 0, sorted(nums)
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"{pfx}{nums[i]}" if i == j else f"{pfx}[{nums[i]}:{nums[j]}]")
        i = j + 1
    return " ".join(out) if out else "—"


def reserved_sgprs(llvm=LLVM):
    """The SGPRs LLVM reserves for gfx1250 kernels (it warns about them on a clobber list): s32 / s105 today."""
    cl = ",".join(f"~{{s{i}}}" for i in range(SGPR_HW))
    ll = ('target triple = "amdgcn-amd-amdhsa"\ndefine amdgpu_kernel void @k() {\n'
          f'  call void asm sideeffect "", "{cl}"()\n  ret void\n}}\n')
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r.ll"
        p.write_text(ll)
        r = subprocess.run([str(llvm / "bin/llc"), "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1250", str(p), "-o",
                            "/dev/null"], capture_output=True, text=True)
    m = re.search(r"clobber list contains reserved registers: ([^\n]*)", r.stderr)
    return sorted(int(x[1:]) for x in (m.group(1).replace(" ", "").split(",") if m else []) if re.fullmatch(r"s\d+", x))


def usable_sgprs(llvm=LLVM):
    res = set(reserved_sgprs(llvm))
    return [i for i in range(SGPR_HW) if i not in res]
