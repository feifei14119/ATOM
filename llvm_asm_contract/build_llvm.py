#!/usr/bin/env python3
"""Fetch the pinned ROCm LLVM, apply the local patch, and build AMDGPU tools.

Does not modify an installed ROCm/FlyDSL or reset an existing checkout.
The current development checkout already contains the patch and is accepted.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = json.loads((ROOT / "SOURCE.json").read_text())
DEFAULT_SOURCE = ROOT.parent.parent / "llvm-project-asm-contract"
TOOLS = ["llc", "opt", "llvm-as", "llvm-dis", "llvm-mc", "llvm-objdump",
         "llvm-readobj", "llvm-nm", "llvm-objcopy", "FileCheck", "not",
         "split-file", "count", "llvm-link", "llvm-config", "yaml2obj",
         "obj2yaml", "lld"]


def run(argv, *, cwd=None, capture=False):
    argv = [str(arg) for arg in argv]
    if not capture:
        print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def find_tool(name, candidates=()):
    for candidate in candidates:
        if Path(candidate).is_file():
            return str(Path(candidate).resolve())
    found = shutil.which(name)
    if found:
        return found
    raise RuntimeError(f"Missing {name}; install it or provide an explicit path")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--jobs", type=int, default=5)
    parser.add_argument("--cc")
    parser.add_argument("--cxx")
    parser.add_argument("--ninja")
    parser.add_argument("--configure-only", action="store_true")
    parser.add_argument("--skip-patch", action="store_true",
                        help="Use an explicitly edited development checkout")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    source = args.source.resolve()
    build = args.build.resolve() if args.build else source / "build-contract"
    if not source.exists():
        source.mkdir(parents=True)
        run(["git", "init", source])
        run(["git", "remote", "add", "origin", SOURCE["repository"]], cwd=source)
        run(["git", "fetch", "--depth=1", "origin", SOURCE["base_commit"]], cwd=source)
        run(["git", "switch", "-c", SOURCE["development_branch"], "FETCH_HEAD"], cwd=source)
    head = run(["git", "rev-parse", "HEAD"], cwd=source, capture=True).strip()
    if head != SOURCE["base_commit"]:
        raise RuntimeError(f"Expected pinned base {SOURCE['base_commit']}; found {head}. "
                           "This script will not reset an existing checkout.")
    patch = ROOT / "llvm.patch"
    if not args.skip_patch:
        if not patch.is_file():
            raise RuntimeError("llvm.patch is absent; use --skip-patch for the development checkout")
        check = subprocess.run(["git", "apply", "--reverse", "--check", str(patch)],
                               cwd=source, capture_output=True)
        if check.returncode:
            run(["git", "apply", "--check", patch], cwd=source)
            run(["git", "apply", patch], cwd=source)
        else:
            print("Patch already applied", flush=True)

    tool_env = source.parent / "llvm-project-asm-contract-tools" / "bin"
    ninja = args.ninja or find_tool("ninja", [tool_env / "ninja"])
    cc = args.cc or os.environ.get("CC") or find_tool("clang", ["/opt/rocm/llvm/bin/clang"])
    cxx = args.cxx or os.environ.get("CXX") or find_tool("clang++", ["/opt/rocm/llvm/bin/clang++"])
    config = [
        "cmake", "-S", source / "llvm", "-B", build, "-G", "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={ninja}", "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_COMPILER={cc}", f"-DCMAKE_CXX_COMPILER={cxx}",
        "-DLLVM_TARGETS_TO_BUILD=AMDGPU", "-DLLVM_ENABLE_PROJECTS=lld",
        "-DLLVM_ENABLE_ASSERTIONS=ON", "-DLLVM_ENABLE_BINDINGS=OFF",
        "-DLLVM_INCLUDE_EXAMPLES=OFF", "-DLLVM_INCLUDE_BENCHMARKS=OFF",
        "-DLLVM_INCLUDE_TESTS=ON", "-DLLVM_BUILD_TOOLS=ON",
        "-DLLVM_ENABLE_ZSTD=OFF", "-DLLVM_ENABLE_ZLIB=OFF",
        "-DLLVM_PARALLEL_LINK_JOBS=1", f"-DLLVM_PARALLEL_COMPILE_JOBS={args.jobs}",
    ]
    linker = Path(cxx).parent / "ld.lld"
    if linker.is_file():
        config.append(f"-DLLVM_USE_LINKER={linker}")
    lit = tool_env / "lit"
    if lit.is_file():
        config.append(f"-DLLVM_EXTERNAL_LIT={lit}")
    run(config)
    if not args.configure_only:
        run([ninja, "-C", build, "-j", args.jobs, *TOOLS])
        run([build / "bin/llc", "--version"])
    print(f"LLVM tools: {build / 'bin'}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
