# SPDX-License-Identifier: MIT
"""SP3 -> inline fragment: compile with sp3 (MI450 = gfx1250), drop the s_version sp3 puts first, disassemble the words
back with llvm-mc, audit the registers against the contract, and write build/asm/<name>.{inc,disasm.txt,contract.json}.

Usage: python3 asm/build_fragment.py [stage_c_gemm ...]   (default: every fragment in FRAGMENTS)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SP3_DIR = HERE / "sp3"
OUT = HERE / "build" / "asm"
SP3 = Path(os.environ.get("SP3_DIR", "/app/sp3cvt"))
LLVM_MC = os.environ.get("LLVM_MC", "/opt/rocm/llvm/bin/llvm-mc")
S_VERSION = 0xB0804009
S_CODE_END = 0xBF9F0000


def vrange(a, b):
    return [f"v{i}" for i in range(a, b + 1)]


# inputs: read only; outputs: written and returned; clobbers: everything else the fragment may write
FRAGMENTS = {
    "stage_c_gemm": dict(
        inputs={"v0": "lane", "s[0:1]": "qr8 tile", "s[2:3]": "wqb tile", "s[4:5]": "qrs tile", "s[6:7]": "wqb_s tile"},
        outputs={"v[8:15]": "acc (vector<8xf32>)"},
        clobbers=vrange(1, 4) + vrange(16, 151),
        special=[],
    ),
}


def regs_of(spec):
    """'v[8:15]' / 's[0:1]' / 'v3' -> the single registers."""
    m = re.fullmatch(r"([vs])\[(\d+):(\d+)\]", spec)
    if m:
        return [f"{m[1]}{i}" for i in range(int(m[2]), int(m[3]) + 1)]
    return [spec]


def sp3_compile(name):
    src = SP3_DIR / f"{name}.sp3"
    env = dict(os.environ, LD_LIBRARY_PATH=str(SP3))
    for flag, ext in (("-text", "text"), ("-hex", "hex")):
        subprocess.run([str(SP3 / "sp3"), "compile:", "-allow-raw-bits", "asic=MI450", "type=CS", str(src), "write:",
                        flag, str(OUT / f"{name}.sp3.{ext}")], check=True, env=env, stdout=subprocess.DEVNULL)
    words = [int(w, 16) for w in re.findall(r"0x[0-9a-fA-F]{8}", (OUT / f"{name}.sp3.{ext}").read_text())]
    assert words[0] == S_VERSION, f"expected s_version first, got {words[0]:#x}"
    while words[-1] in (S_CODE_END, 0):   # sp3 pads the shader with s_code_end and zero words
        words.pop()
    return src, words[1:]


def disassemble(words):
    data = b"".join(w.to_bytes(4, "little") for w in words)
    text = " ".join(f"0x{b:02x}" for b in data)
    r = subprocess.run([LLVM_MC, "-disassemble", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1250", "-show-encoding"],
                       input=text, capture_output=True, text=True, check=True)
    if "invalid" in r.stderr or "warning" in r.stderr:
        raise SystemExit(f"llvm-mc could not decode the fragment:\n{r.stderr}")
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and not ln.strip().startswith(".")]


REG = re.compile(r"\b([vs])(?:\[(\d+):(\d+)\]|(\d+)(?!\w))")
NO_DEST = ("global_store", "s_wait", "s_nop", "v_nop", "s_cmp", "s_cbranch", "s_branch", "s_delay_alu")
FORBIDDEN = ("s_endpgm", "s_code_end", "v_illegal", "s_setpc", "s_swappc", "s_set_vgpr_msb", "s_setreg", "s_sendmsg", "s_barrier", "exec", "m0",
             "ttmp", "s_getpc")


def operand_regs(op):
    out = []
    for m in REG.finditer(op):
        if m[4] is not None:
            out.append(f"{m[1]}{m[4]}")
        else:
            out += [f"{m[1]}{i}" for i in range(int(m[2]), int(m[3]) + 1)]
    return out


def audit(name, lines, spec):
    inputs = {r for k in spec["inputs"] for r in regs_of(k)}
    outputs = {r for k in spec["outputs"] for r in regs_of(k)}
    clobbers = set(spec["clobbers"])
    allowed_write = outputs | clobbers
    used, written = set(), set()
    for ln in lines:
        ins = ln.split(";")[0].strip()
        mn, _, ops = ins.partition(" ")
        for bad in FORBIDDEN:
            assert not re.search(rf"\b{bad}", ins), f"{name}: forbidden {bad!r} in {ins!r}"
        parts = [p.strip() for p in ops.split(",")] if ops else []
        regs = operand_regs(ops)
        used |= set(regs)
        if parts and not mn.startswith(NO_DEST):
            written |= set(operand_regs(parts[0]))
        for r in regs:
            if r[0] == "v":
                assert int(r[1:]) < 256, f"{name}: {r} >= v256 needs the VGPR MSB / clobber fix"
            else:
                assert not (30 <= int(r[1:]) <= 39), f"{name}: {r} is reserved (s30-s39)"
    bad_w = written - allowed_write
    assert not bad_w, f"{name}: writes registers outside outputs + clobbers: {sorted(bad_w)}"
    assert not (written & inputs), f"{name}: writes its inputs: {sorted(written & inputs)}"
    unknown = used - inputs - allowed_write
    assert not unknown, f"{name}: reads registers that are neither inputs nor its own: {sorted(unknown)}"
    return sorted(written, key=lambda r: (r[0], int(r[1:])))


def constraints(spec):
    outs = [f"={{{k}}}" for k in spec["outputs"]]
    ins = [f"{{{k}}}" for k in spec["inputs"]]
    clob = [f"~{{{r}}}" for r in spec["clobbers"]] + [f"~{{{r}}}" for r in spec["special"]] + ["~{memory}"]
    return ",".join(outs + ins + clob)


def build(name):
    spec = FRAGMENTS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    src, words = sp3_compile(name)
    lines = disassemble(words)
    written = audit(name, lines, spec)
    (OUT / f"{name}.disasm.txt").write_text("\n".join(lines) + "\n")
    body = b"".join(w.to_bytes(4, "little") for w in words)
    asm_text = "\n".join(".long " + ", ".join(f"0x{w:08x}" for w in words[i:i + 8]) for i in range(0, len(words), 8))
    (OUT / f"{name}.inc").write_text(asm_text + "\n")
    contract = dict(
        target="gfx1250", wave_size=32, name=name, source=str(src),
        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        fragment_bytes=len(body), fragment_sha256=hashlib.sha256(body).hexdigest(), instructions=len(lines),
        inputs=spec["inputs"], outputs=spec["outputs"], written=written, clobbers=spec["clobbers"],
        special_clobbers=spec["special"], constraints=constraints(spec),
    )
    (OUT / f"{name}.contract.json").write_text(json.dumps(contract, indent=1) + "\n")
    print(f"{name}: {len(lines)} instructions, {len(body)} bytes, writes {len(written)} registers -> {OUT}")
    return contract


if __name__ == "__main__":
    for n in sys.argv[1:] or FRAGMENTS:
        build(n)
