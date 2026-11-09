#!/usr/bin/env python3
"""Compile SSA -> constrained machine code -> binary-stage adapter -> .co."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

from adapter import Bank, boundary
from audit import BudgetError, boundary_liveness, require_no_spills, resources

HERE = Path(__file__).resolve().parent
# Reuse the existing strict extractor; consuming a .co never reads stage.s.
sys.path.insert(0, str(HERE.parent / "clobber"))
spec = importlib.util.spec_from_file_location("clobber_extract", HERE.parent / "clobber/generate.py")
supplier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supplier)


def run(argv, log=None):
    p = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    if log:
        log.write_text(p.stdout + p.stderr)
    if p.returncode or p.stderr.strip():
        raise RuntimeError(f"command failed or emitted diagnostics: {argv}\n{p.stdout}{p.stderr}")
    return p.stdout


def compile_caller(llvm, dest, bank):
    dest.mkdir(parents=True, exist_ok=True)
    template = (HERE / "caller.ll.in").read_text()
    if template.count("@CLOBBERS@") != 2:
        raise ValueError("expected two compiler-visible boundary contracts")
    (dest / "caller.ll").write_text(template.replace("@CLOBBERS@", bank.clobbers))
    run([llvm / "opt", "-passes=verify", "-disable-output", dest / "caller.ll"])
    args = [llvm / "llc", "-O2", "-mcpu=gfx1100", dest / "caller.ll"]
    run(args + ["-o", dest / "caller.s"], dest / "compile.log")
    # This pass is after allocation, post-RA scheduling, hazards and relaxation.
    run(args + ["-stop-after=amdgpu-resource-usage", "-o", dest / "caller.mir"])
    return (dest / "caller.s").read_text()


def build(llvm, dest, bank, blob):
    asm = compile_caller(llvm, dest, bank)
    before = require_no_spills(asm)
    live = boundary_liveness((dest / "caller.mir").read_text(), bank)
    for i in range(2):
        marker = re.compile(rf"^\s*; MONO_BOUNDARY_{i}\s*$", re.M)
        if len(marker.findall(asm)) != 1:
            raise ValueError("missing/duplicated boundary marker")
        asm = marker.sub(lambda _: "\n" + boundary(bank, blob, i), asm)
    # Compiler only saw net effects. Final resources cover the whole binary.
    for pattern, value in [
        (r"(\.amdhsa_group_segment_fixed_size )\d+", bank.lds_bytes),
        (r"(\.group_segment_fixed_size:\s*)\d+", bank.lds_bytes),
        (r"(\.amdhsa_next_free_sgpr )\d+", 106),
        (r"(\.sgpr_count:\s*)\d+", 108),
        (r"(\.set mono_boundary.numbered_sgpr, )\d+", 106),
    ]:
        asm, count = re.subn(pattern, lambda m: m[1] + str(value), asm)
        if count != 1:
            raise ValueError(f"metadata format changed: {pattern}")
    # Remove obsolete compiler-only estimates, retaining originals in caller.s.
    asm = re.sub(r"; Kernel info:.*?(?=\n\s*\.text)",
                 "; Final resources are in the descriptor/metadata; see report.json.", asm, flags=re.S)
    (dest / "mono.s").write_text(asm)
    run([llvm / "clang++", "--target=amdgcn-amd-amdhsa", "-mcpu=gfx1100", "-x", "assembler",
         "-c", dest / "mono.s", "-o", dest / "mono.o"])
    run([llvm / "ld.lld", "-shared", "--no-undefined", dest / "mono.o", "-o", dest / "mono.co"])
    note = run([llvm / "llvm-readelf", "-n", "-r", dest / "mono.co"])
    (dest / "metadata.txt").write_text(note)
    if "There are no relocations" not in note:
        raise ValueError("unexpected final relocation")
    final = require_no_spills(note)
    if (final["vgpr_count"], final["sgpr_count"], final["group_segment_fixed_size"]) != (256, 108, bank.lds_bytes):
        raise ValueError("incorrect resource metadata")
    dis = run([llvm / "llvm-objdump", "--mcpu=gfx1100", "--disassemble-symbols=mono_boundary", dest / "mono.co"])
    (dest / "mono.disasm.s").write_text(dis)
    if re.search(r"\bs_(?:getpc|setpc|swappc)_b64\b", dis):
        raise ValueError("unexpected indirect control flow")
    if len(re.findall(r"^\s*s_branch\b", dis, re.M)) != 4 or len(re.findall(r"^\s*s_endpgm\b", dis, re.M)) != 1:
        raise ValueError("expected four direct branches and one final endpgm")
    words = [w for line in blob.splitlines() for w in re.findall(r"0x([0-9A-Fa-f]{8})", line.split("//")[0])]
    raw = b"".join(struct.pack("<I", int(w, 16)) for w in words)
    if (dest / "mono.co").read_bytes().count(raw) != 2:
        raise ValueError("supplier bytes changed")
    report = {"bank": bank.names, "bytes_per_logical_thread": bank.stride,
              "compiler_resources": before, "final_resources": final,
              "boundary_liveness": live, "unchanged_body_copies": 2,
              "body_bytes_per_stage": len(raw), "direct_branches": 4,
              "performance_timed": False}
    (dest / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {dest.name}: {bank.vgprs} VGPR + {bank.sgprs}+2 SGPR saved; "
          f"LDS={bank.lds_bytes}, scratch/spills=0; two unchanged binary bodies; direct branches only")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llvm-bin", type=Path, required=True)
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    blob = supplier.extract(args.stage, json.loads(args.contract.read_text()), args.llvm_bin)
    for sgprs in [16, 8]:
        build(args.llvm_bin, args.output / f"s{sgprs}_v8", Bank(sgprs, 8), blob)
    dest = args.output / "rejected_s8_v4"
    asm = compile_caller(args.llvm_bin, dest, Bank(8, 4))
    try:
        require_no_spills(asm)
    except BudgetError as e:
        (dest / "rejection.json").write_text(json.dumps({"reason": str(e), "resources": resources(asm)}, indent=2) + "\n")
        print(f"PASS negative budget test: {e}")
    else:
        raise ValueError("negative budget test stopped exceeding the budget; update the experiment")
    (args.output / "toolchain.txt").write_text(run([args.llvm_bin / "llc", "--version"]))


if __name__ == "__main__":
    main()
