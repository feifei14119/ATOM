#!/usr/bin/env python3
"""Build the opaque-ASM standard-ABI device wrapper as real LLVM bitcode.

No llc/MIR pipeline, external ELF linking, or Mono compiler monkeypatch is used.
This script compiles files but never launches a GPU kernel.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from asm.audit import audit_source, load_fragment
from wrapper_audit import WRAPPER, audit_wrapper_source, audit_wrapper_ir

ROOT = Path(__file__).resolve().parent


def build(llvm):
    llvm = llvm.resolve()
    for name in ('clang++', 'opt', 'llvm-dis', 'llvm-objdump'):
        if not (llvm/name).is_file():
            raise RuntimeError(f'Missing {llvm/name}; select a gfx1250-capable ROCm LLVM')
    report = {'commands': [], 'gpu_execution': 'NOT RUN by this builder',
              'abi': 'standard AMDGPU device C ABI; no custom regmask',
              'source': audit_source(), 'wrapper_source': audit_wrapper_source()}
    out = ROOT/'build/wrapper'
    out.mkdir(parents=True, exist_ok=True)

    def run(args):
        args = [str(a) for a in args]
        report['commands'].append(args)
        print('[wrapper/build] '+str(args), flush=True)
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f'{args}\n{p.stdout}\n{p.stderr}')
        if p.stderr:
            print(p.stderr, file=sys.stderr)
        return p.stdout

    report['clang_version'] = run([llvm/'clang++', '--version'])
    report['opt_version'] = run([llvm/'opt', '--version'])
    try:
        run([sys.executable, ROOT/'asm/prepare.py', '--llvm-bin', llvm])
        _, _, fragment, _ = load_fragment(ROOT/'build/asm')
        raw, bc, ll = out/'dq_wrapper.raw.bc', out/'dq_wrapper.bc', out/'dq_wrapper.ll'
        run([llvm/'clang++', '-x', 'hip', '-std=c++17', '-O2', '-Wall', '-Wextra',
             '--offload-arch=gfx1250', '--offload-device-only', '-fgpu-rdc',
             '-emit-llvm', '-c', '-I'+str(ROOT/'build/asm'),
             ROOT/'asm/dq_wrapper.cpp', '-o', raw])
        # Remove unused HIP assert/printf helpers. Retain a real externally
        # linkable IR definition, including noinline/convergent.
        run([llvm/'opt', '-passes=internalize,globaldce',
             '-internalize-public-api-list='+WRAPPER, raw, '-o', bc])
        if not bc.read_bytes().startswith(b'BC\xc0\xde'):
            raise RuntimeError('Clang/opt did not produce raw LLVM bitcode')
        run([llvm/'llvm-dis', bc, '-o', ll])
        report['ir'] = audit_wrapper_ir(ll.read_text(), ROOT/'build/asm')
        # Offline inspection of this same wrapper, not a second GPU test.
        # Final Mono codegen still belongs entirely to FlyDSL's built-in LLVM.
        assembly = out/'dq_wrapper.codegen.s'
        run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-nogpulib',
             '-x', 'ir', '-O2', '-S', bc, '-o', assembly])
        from wrapper_audit import audit_codegen_envelope
        report['offline_codegen'] = audit_codegen_envelope(assembly.read_text())
        report.update(status='BUILT', bitcode=str(bc),
                      bitcode_sha256=hashlib.sha256(bc.read_bytes()).hexdigest(),
                      fragment_sha256=hashlib.sha256(fragment).hexdigest())
    except Exception:
        report['status'] = 'FAIL'
        raise
    finally:
        (out/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    print('[wrapper/build] BUILT '+str(bc)+'; no GPU execution', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-bin', type=Path, default=Path('/opt/rocm/llvm/bin'))
    a = parser.parse_args()
    build(a.llvm_bin)
