#!/usr/bin/env python3
"""Run the LLVM regressions, object audit, and both external-ASM integrations.

The default is offline. --run-gpu additionally executes the kernels on gfx1250.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT.parent.parent / "llvm-project-asm-contract"
EXISTING_TESTS = [
    "call-preserved-registers.ll", "call-argument-types.ll", "call-return-types.ll",
    "callee-special-input-vgprs.ll", "callee-special-input-vgprs-packed.ll",
    "function-resource-usage.ll", "call-alias-register-usage0.ll", "nested-calls.ll",
    "multi-call-resource-usage-mcexpr.ll", "call-waitcnt.ll",
    "hsa-metadata-resource-usage-function-ordering.ll",
    "resource-usage-dead-function.ll", "tail-call-inreg-arguments.ll",
]


def execute(argv, logfile):
    argv = [str(arg) for arg in argv]
    print("+", " ".join(argv), flush=True)
    with logfile.open("w") as log:
        result = subprocess.run(argv, cwd=ROOT, text=True, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print("\n".join(logfile.read_text(errors="replace").splitlines()[-75:]), file=sys.stderr)
        raise RuntimeError(f"command exited {result.returncode}; full log: {logfile}")
    print(f"PASS: {logfile.name}", flush=True)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--llvm-bin", type=Path)
    parser.add_argument("--python", type=Path,
                        help="Python with FlyDSL 0.4.1 and its dependencies")
    parser.add_argument("--output", type=Path, default=ROOT / "build")
    parser.add_argument("--build-llvm", action="store_true")
    parser.add_argument("--jobs", type=int, default=5)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-gpu", action="store_true")
    mode.add_argument("--build-only", action="store_true", help="Default: no GPU execution")
    args = parser.parse_args()
    source = args.source.resolve()
    llvm = args.llvm_bin.resolve() if args.llvm_bin else source / "build-contract/bin"
    out = args.output.resolve()
    validation = out / "validation"
    validation.mkdir(parents=True, exist_ok=True)
    summary_path = validation / "result.json"
    # Never leave an earlier PASS where a failed new run looks successful.
    summary = {"status": "RUNNING", "started_unix": time.time(),
               "gpu_execution": "NOT_RUN", "llvm_bin": str(llvm),
               "source": str(source)}
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    try:
        if args.build_llvm:
            execute([sys.executable, ROOT / "build_llvm.py", "--source", source,
                     "--build", llvm.parent,
                     "--jobs", args.jobs], validation / "build-llvm.log")
        if not (llvm / "llc").is_file():
            raise RuntimeError("Patched llc is missing; first run build_llvm.py")
        default_python = ROOT.parent / "mono_test20/build/venv/bin/python"
        python = (args.python or (default_python if default_python.is_file()
                                 else Path(sys.executable))).absolute()
        execute([python, "-c", "import flydsl; print(flydsl.__version__)"],
                validation / "flydsl-version.log")

        test_root = source / "llvm/test/CodeGen/AMDGPU"
        new_tests = sorted(set(test_root.glob("asm-call-contract*.ll")) |
                           set(test_root.glob("asm-contract-no-spill*.ll")))
        if len(new_tests) < 3:
            raise RuntimeError("LLVM checkout does not contain all contract regression tests")
        all_tests = new_tests + [test_root / name for name in EXISTING_TESTS]
        execute([llvm / "llvm-lit", "-sv", "-o", validation / "llvm-tests.json",
                 *all_tests], validation / "llvm-tests.log")
        lit = json.loads((validation / "llvm-tests.json").read_text())
        if any(test["code"] != "PASS" for test in lit["tests"]):
            raise RuntimeError("All selected LLVM tests must pass, including no skipped tests")
        summary["llvm_regression_files_passed"] = len(lit["tests"])
        execute([sys.executable, ROOT / "demo/test_audit.py", "--llvm-bin", llvm],
                validation / "object-audit-tests.log")
        execute([sys.executable, ROOT / "demo/build.py", "--llvm-bin", llvm,
                 "--output", out / "demo"], validation / "ir-demo.log")
        execute([python, ROOT / "test_flydsl.py", "--llvm-bin", llvm,
                 "--output", out / "flydsl"], validation / "flydsl-demo.log")
        for name in ("demo", "flydsl"):
            report = json.loads((out / name / "result.json").read_text())
            if report["status"] != "OFFLINE_PASS":
                raise RuntimeError(f"{name}: offline validation did not pass")
            summary[name] = {key: report[key] for key in
                             ("metadata", "device_calls", "strict_policy_status", "kernel")}
            summary[name]["kernel_sha256"] = sha256(Path(report["kernel"]))

        rocm = Path(os.environ.get("ROCM_PATH", "/opt/rocm"))
        if (rocm / "include/hip/hip_runtime_api.h").is_file():
            cxx = shutil.which(os.environ.get("CXX", "c++"))
            if not cxx:
                raise RuntimeError("C++ compiler is required for the HIP host launcher")
            execute([cxx, "-std=c++17", "-O2", "-D__HIP_PLATFORM_AMD__",
                     "-I" + str(rocm / "include"), ROOT / "demo/test.cpp",
                     "-L" + str(rocm / "lib"), "-Wl,-rpath," + str(rocm / "lib"),
                     "-lamdhip64", "-o", out / "host"], validation / "host-build.log")
            summary["host_launcher"] = "BUILT"
        else:
            summary["host_launcher"] = "NO_ROCM_HEADERS"

        if args.run_gpu:
            if summary["host_launcher"] != "BUILT":
                raise RuntimeError("--run-gpu requires ROCm headers and runtime")
            for name, symbol in (("demo", "contract_caller"), ("flydsl", "contract_flydsl")):
                execute([out / "host", out / name / "kernel.co", symbol],
                        validation / f"{name}-gpu.log")
            summary["gpu_execution"] = "PASS_BOTH_KERNELS"
        summary["llc_sha256"] = sha256(llvm / "llc")
        summary["llvm_base"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        summary["status"] = "GPU_PASS" if args.run_gpu else "OFFLINE_PASS"
    except Exception as exc:
        summary["status"] = "FAILED"
        summary["error"] = str(exc)
        raise
    finally:
        summary["completed_unix"] = time.time()
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print("Validation report:", summary_path)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
