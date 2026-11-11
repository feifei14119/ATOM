#!/usr/bin/env python3
"""Negative tests: each broken contract must be rejected with a precise message.

Pack-time cases run the packer only. Compile-time cases pack a deliberately
wrong (but self-consistent) manifest and compile the whole Mono kernel with it
in a child process; no GPU kernel is launched.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build/negative"
BASE = yaml.safe_load((ROOT / "asm/dq_convert.contract.yaml").read_text())
BASE["source"] = str(ROOT / "asm" / BASE["source"])
FULL = ["s[2:23]", "s[25:29]", "s[40:48]", "v[4:45]", "scc"]

PACK_CASES = {
    "clobber_missing_s5": (dict(clobbers=["s[2:4]", "s[6:23]", "s[25:29]", "s[40:48]", "v[4:45]", "scc"]),
                           "fragment writes s5, which is not in clobbers"),
    "mode_not_preserved": (dict(preserves=["exec"]),
                           "fragment changes mode"),
    "input_is_written": (dict(params=[dict(BASE["params"][0]), dict(name="lane", reg="v4", type="uint32"),
                                      dict(BASE["params"][2])]),
                         "fragment writes input register(s) v4"),
}

COMPILE_CASES = {
    # Footprint above the 512 VGPRs a 256-thread CTA may use (256 CTAs resident).
    "footprint_over_budget": (dict(clobbers=FULL[:3] + ["v[4:600]", "scc"]),
                              "may use at most 512 VGPRs"),
    # Leaves the caller only v0 (the input): its live v1 must be spilled.
    "footprint_forces_spill": (dict(clobbers=FULL[:3] + ["v[1:3]", "v[4:511]", "scc"]),
                               "violates amdgpu-spill-policy=error"),
}

CHILD = r'''
import os, sys
sys.path.insert(0, os.environ["MONO_ROOT"])
from flydsl.compiler.kernel_function import CompilationContext
from flydsl.compiler.asm_contract import spill_hints
from mono1250.runtime.compile import compile_only
from mono1250.kernels.projection_asm import build_projection_asm
import flydsl.expr as fx, torch
torch.cuda.set_device(0)
stream = fx.Stream(torch.cuda.current_stream())
with CompilationContext.compile_hints({"llvm_options": spill_hints("error")}):
    with compile_only():
        build_projection_asm()(*([0] * 15), stream=stream)
print("COMPILED")
'''


def pack_case(name, override, llvm_dir):
    from flydsl.compiler.asm_contract import ContractError, Manifest, pack
    try:
        manifest = Manifest.from_dict(dict(BASE, **override), base=ROOT / "asm")
        info = pack(manifest, OUT / name, llvm_dir=llvm_dir)
    except ContractError as exc:
        return str(exc), None
    return None, info


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--llvm-dir", default="/app/llvm-upstream/build")
    a = ap.parse_args()
    results, failed = {}, False

    for name, (override, expected) in PACK_CASES.items():
        error, _ = pack_case(name, override, a.llvm_dir)
        ok = error is not None and expected in error
        results[name] = {"stage": "pack", "ok": ok, "message": error}
        print(f"[{'PASS' if ok else 'FAIL'}] pack/{name}: {error}", flush=True)
        failed |= not ok

    env = dict(os.environ, MONO_ROOT=str(ROOT), ARCH="gfx1250", GPU_ARCHS="gfx1250",
               FLYDSL_RUNTIME_ENABLE_CACHE="0", FLYDSL_COMPILE_LLVM_DIR=str(Path(a.llvm_dir).resolve()),
               FLYDSL_COMPILE_LLVM_HANDOFF="llvm", PYTHONDONTWRITEBYTECODE="1",
               AITER_JIT_DIR=str(ROOT / "build/cache/aiter"))
    for name, (override, expected) in COMPILE_CASES.items():
        error, info = pack_case(name, override, a.llvm_dir)
        if error is not None:
            results[name] = {"stage": "pack", "ok": False, "message": error}
            print(f"[FAIL] compile/{name}: rejected at pack time: {error}", flush=True)
            failed = True
            continue
        sidecar = OUT / name / "dq_convert.contract.json"
        proc = subprocess.run([sys.executable, "-c", CHILD], cwd=ROOT, capture_output=True, text=True,
                              env=dict(env, MONO_CONTRACT_SIDECAR=str(sidecar)), timeout=900)
        output = proc.stdout + proc.stderr
        lines = [l for l in output.splitlines() if "error:" in l or l.startswith("  ")]
        message = "\n".join(l for l in lines if "amdgpu" in l or "contract" in l or "VGPR" in l or "spill" in l)
        ok = proc.returncode != 0 and expected in output and "COMPILED" not in output
        results[name] = {"stage": "compile", "ok": ok, "pack_warnings": info["warnings"], "message": message}
        print(f"[{'PASS' if ok else 'FAIL'}] compile/{name}:\n{message or output[-2000:]}", flush=True)
        failed |= not ok

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"[{'FAIL' if failed else 'PASS'}] {len(results)} negative cases; {OUT / 'result.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
