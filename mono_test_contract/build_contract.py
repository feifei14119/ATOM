#!/usr/bin/env python3
"""Pack asm/dq_convert.inline.s as a register-contract function (.bc + .contract.json).

Assembles the fragment, takes its write set from the machine code, checks it
against the manifest and writes build/contract/. Never launches a GPU kernel.
"""
import argparse
import json
from pathlib import Path

from flydsl.compiler.asm_contract import pack

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build/contract"
MANIFEST = ROOT / "asm/dq_convert.contract.yaml"
SIDECAR = OUT / "dq_convert.contract.json"


def build(llvm_dir):
    info = pack(MANIFEST, OUT, llvm_dir=str(llvm_dir))
    if info["warnings"]:
        raise RuntimeError("contract warnings: " + "; ".join(info["warnings"]))
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--llvm-dir", default="/app/llvm-upstream/build")
    a = ap.parse_args()
    print(json.dumps(build(Path(a.llvm_dir)), indent=2))
