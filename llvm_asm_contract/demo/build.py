#!/usr/bin/env python3
"""Build/link the external-ASM contract test; this script never launches a GPU."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

if __package__:
    from .contract import Elf, audit_object, llvm_attributes, pack_stage, run, verify_identity
else:
    from contract import Elf, audit_object, llvm_attributes, pack_stage, run, verify_identity

ROOT = Path(__file__).resolve().parent
DEFAULT_LLVM = Path("/home/feifei/repo/llvm-project-asm-contract/build-contract/bin")


def begin_build(output):
    """A failed rebuild must not leave an old success report/executable current."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output/"kernel.co").unlink(missing_ok=True)
    (output/"result.json").write_text(json.dumps({
        "status": "INCOMPLETE", "gpu_execution": "NOT_RUN",
        "reason": "build started; success is published only after all checks pass"}, indent=2)+"\n")


def require_backend(llvm, output):
    """Fail closed when an older LLVM would silently ignore target attrs."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source = output/"unsupported-version.ll"
    source.write_text('''target triple = "amdgcn-amd-amdhsa"
declare void @unsupported_contract() #0
define amdgpu_kernel void @probe() {
  call void @unsupported_contract()
  ret void
}
attributes #0 = { convergent nounwind norecurse "amdgpu-asm-contract"="999" }
''')
    command = [str(Path(llvm)/"llc"), "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
               "-mattr=+wavefrontsize32", "-global-isel=0", str(source), "-o", str(output/"probe.s")]
    result = subprocess.run(command, capture_output=True, text=True)
    (output/"backend-probe.stderr").write_text(result.stderr)
    if result.returncode == 0 or "unsupported contract version (expected 1)" not in result.stderr:
        raise RuntimeError("selected llc does not implement the external-ASM contract; "
                           "refusing a silent default-ABI fallback\n"+result.stderr)
    return {"unsupported_version_rejected": True, "llc_version": run([Path(llvm)/"llc", "--version"])[0]}


def metadata(llvm, path):
    notes, _ = run([Path(llvm)/"llvm-readobj", "--notes", path])
    result = {}
    for name in ("vgpr_count", "sgpr_count", "private_segment_fixed_size", "group_segment_fixed_size"):
        values = re.findall(r"\."+name+r":\s*(\d+)", notes)
        if len(values) != 1:
            raise RuntimeError(f"expected one kernel metadata field {name}: {values}")
        result[name] = int(values[0])
    return result, notes


def compile_and_link(ir, manifest, llvm, output, symbol="contract_caller"):
    llvm, output = Path(llvm).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    verify_identity(manifest)
    # No assume-external-call-stack-size escape hatch: the backend must use
    # the callee's explicit zero-private contract.
    flags = [llvm/"llc", "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
             "-mattr=+wavefrontsize32", "-global-isel=0", "-O2", "-verify-machineinstrs"]
    obj, assembly = output/"caller.o", output/"caller.s"
    backend_report_path = output/"backend.resources.json"
    _, object_stderr = run([*flags, "-amdgpu-asm-contract-report="+str(backend_report_path),
                            "-filetype=obj", ir, "-o", obj])
    _, assembly_stderr = run([*flags, "-filetype=asm", ir, "-o", assembly])
    (output/"codegen.stderr").write_text(object_stderr+assembly_stderr)
    verify_identity(manifest)
    binary = output/"kernel.pending.co"
    run([llvm/"ld.lld", "-shared", "--no-undefined", obj, manifest["object_path"], "-o", binary])
    final = Elf(binary)
    source = Elf(manifest["object_path"])
    if final.symbol_bytes(manifest["symbol"]) != source.symbol_bytes(manifest["symbol"]):
        raise RuntimeError("linked callee bytes changed")
    final_meta, notes = metadata(llvm, binary)
    (output/"kernel.notes.txt").write_text(notes)
    if final_meta["private_segment_fixed_size"] != 0:
        raise RuntimeError("strict backend produced a nonzero final private segment")
    if final_meta["vgpr_count"] < manifest["resources"]["vgpr_count"]:
        raise RuntimeError("final VGPR descriptor omits callee registers")
    if final_meta["sgpr_count"] < manifest["resources"]["sgpr_count"]:
        raise RuntimeError("final SGPR metadata omits callee registers")
    if final_meta["group_segment_fixed_size"] != 0:
        raise RuntimeError("unexpected LDS allocation in this demo")
    disassembly, _ = run([llvm/"llvm-objdump", "--mcpu=gfx1250", "-d", binary])
    (output/"kernel.dis.s").write_text(disassembly)
    # Supplemental readability checks; the backend enforces the policy.
    if re.search(r"\bscratch_(?:load|store)\w*\b", disassembly):
        raise RuntimeError("unexpected scratch instruction in final disassembly")
    calls = re.findall(r"\bs_(?:swappc_b64|swap_pc_i64)\b", disassembly)
    if len(calls) != 2:
        raise RuntimeError(f"expected two real device calls, found {len(calls)}")
    backend_report = json.loads(backend_report_path.read_text())
    if backend_report.get("schema") != "amdgpu.asm_contract_report.v1" or backend_report.get("strict_policy_status") != "checked":
        raise RuntimeError("the backend did not certify the requested strict policy")
    entries = [fn for fn in backend_report["functions"] if fn.get("name", fn.get("function")) == symbol]
    if len(entries) != 1:
        raise RuntimeError("backend report omits the compiled caller")
    stage_calls = [call for call in entries[0]["calls"] if call["callee"] == manifest["symbol"]]
    if len(stage_calls) != 2:
        raise RuntimeError("backend report omits the two contract calls")
    published = output/"kernel.co"
    binary.replace(published)
    return {"status": "OFFLINE_PASS", "kernel": str(published), "symbol": symbol,
            "metadata": final_meta, "device_calls": len(calls),
            "callee_bytes_preserved": True, "object_hash_verified": True,
            "gpu_execution": "NOT_RUN", "backend_diagnostics": str(output/"codegen.stderr"),
            "backend_resource_report": str(backend_report_path),
            "strict_policy_status": backend_report["strict_policy_status"],
            "backend_scope": backend_report["scope"], "calls": stage_calls,
            "full_wave_entry": "caller_asserted; this test has no divergent control flow"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-bin", type=Path, default=DEFAULT_LLVM)
    parser.add_argument("--output", type=Path, default=ROOT.parent/"build/demo")
    args = parser.parse_args()
    out = args.output.resolve()
    llvm = args.llvm_bin.resolve()
    begin_build(out)
    preflight = require_backend(llvm, out)
    manifest, audit = pack_stage(ROOT, out/"stage", llvm)
    # Assert the reviewable hand-written IR agrees with the manifest; it is
    # never rewritten or patched by this builder.
    source = (ROOT/"caller.ll").read_text()
    for name, value in llvm_attributes(manifest).items():
        if f'"{name}"="{value}"' not in source:
            raise RuntimeError(f"caller.ll and manifest disagree on {name}")
    report = compile_and_link(ROOT/"caller.ll", manifest, llvm, out)
    report.update(backend=preflight, stage=audit)
    (out/"result.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "kernel", "metadata", "device_calls", "strict_policy_status", "gpu_execution")}, indent=2))
    print("Detailed report:", out/"result.json")


if __name__ == "__main__":
    main()
