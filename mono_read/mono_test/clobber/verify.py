#!/usr/bin/env python3
"""Audit the supplied clobbers, embedded bytes, control flow and resource notes."""
import argparse
import json
import re
import struct
import subprocess

from pathlib import Path
from generate import extract

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--stage", type=Path, required=True)
p.add_argument("--contract", type=Path, required=True)
p.add_argument("--module", type=Path, required=True)
p.add_argument("--llvm-bin", type=Path, required=True)
p.add_argument("--report", type=Path, required=True)
args = p.parse_args()
body = extract(args.stage, json.loads(args.contract.read_text()), args.llvm_bin)
words = []
for line in body.splitlines():
    words.extend(re.findall(r"0x([0-9A-Fa-f]{8})", line.split("//")[0]))
blob = b"".join(struct.pack("<I", int(w, 16)) for w in words)
assert args.module.read_bytes().count(blob) == 6, "expected two exact body copies per variant"
note = subprocess.check_output([str(args.llvm_bin / "llvm-readelf"), "-n", str(args.module)], text=True)
resources = {}
for block in note.split("  - .args:")[1:]:
    name = re.search(r"\.name:\s+(\w+)", block)[1]
    resources[name] = {key: int(re.search(r"\." + key + r":\s+(\d+)", block)[1])
                       for key in ["private_segment_fixed_size", "group_segment_fixed_size", "vgpr_count", "sgpr_count"]}
for mode in ["unsafe", "preserve", "phase"]:
    name = "mono_" + mode
    expected = (0, 544) if mode == "phase" else (64, 512)
    r = resources[name]
    assert (r["private_segment_fixed_size"], r["group_segment_fixed_size"]) == expected
    disasm = subprocess.check_output([str(args.llvm_bin / "llvm-objdump"), "--mcpu=gfx1100",
                                     f"--disassemble-symbols={name}", str(args.module)], text=True)
    assert f"<{name}>:" in disasm
    assert not re.search(r"\bs_(?:getpc|setpc|swappc)_b64\b", disasm)
    assert len(re.findall(r"^\s*s_endpgm\b", disasm, re.M)) == 1
    print(f"PASS {name}: one final endpgm, no PC call/return, private={expected[0]} B/lane, LDS={expected[1]} B/CTA")
report = {"target": "gfx1100", "body_bytes_per_stage": len(blob), "unchanged_body_copies": 6,
          "resource_metadata": resources, "performance_timed": False}
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(f"PASS: six exact body copies; report: {args.report}")
