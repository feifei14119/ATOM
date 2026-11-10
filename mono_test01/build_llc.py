#!/usr/bin/env python3
"""Provide an llc built from the selected ROCm LLVM when that LLVM ships without one.

The vendored llvm/tools/llc sources are compiled against the same installation's
headers and static libraries; all other tools stay the installed binaries. The
llc is rejected unless headers, clang++ and the vendored sources name one commit.
Nothing is downloaded or installed.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT/'tools/llc'
OUT = ROOT/'build/llvm-bin'
COMPONENTS = ['all-targets', 'analysis', 'asmprinter', 'codegen', 'codegentypes', 'core', 'ipo',
              'irprinter', 'irreader', 'mc', 'mirparser', 'passes', 'plugins', 'remarks',
              'scalaropts', 'selectiondag', 'support', 'target', 'targetparser',
              'transformutils', 'vectorize']


def run(argv):
    result = subprocess.run([str(a) for a in argv], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{argv}\n{result.stdout}\n{result.stderr}')
    return result.stdout.strip()


def find_llvm_config(llvm):
    candidates = [llvm/'llvm-config']
    try:
        import _rocm_sdk_devel
        candidates.append(Path(_rocm_sdk_devel.__file__).parent/'lib/llvm/bin/llvm-config')
    except ImportError:
        pass
    for path in candidates:
        # The runtime package also ships llvm-config, but without headers or libraries.
        if (path.is_file() and (Path(run([path, '--includedir']))/'llvm/Support/VCSRevision.h').is_file()
                and (Path(run([path, '--libdir']))/'libLLVMCodeGen.a').is_file()):
            return path
    raise RuntimeError(f'No llc in {llvm} and no llvm-config with headers and static libraries '
                       'to build one; install the ROCm devel LLVM')


def system_libraries(config, libdir):
    # ROCm names bundled zlib/zstd as -lrocm_sysdeps_z.so.1; GNU ld needs the file path.
    search = [libdir, libdir.parent.parent/'rocm_sysdeps/lib']
    flags, rpaths = [], set()
    for flag in run([config, '--link-static', '--system-libs']).split():
        name = flag[2:] if flag.startswith('-l') else None
        if name and '.so' in name:
            path = next((d/('lib'+name) for d in search if (d/('lib'+name)).exists()), None)
            if path is None:
                raise RuntimeError(f'Cannot locate system library {flag}')
            flags.append(path)
            rpaths.add(path.parent.resolve())
        else:
            flags.append(flag)
    return flags + [f'-Wl,-rpath,{p}' for p in sorted(rpaths)]


def ensure_llc(llvm):
    llvm = Path(llvm).resolve()
    if (llvm/'llc').is_file():
        return llvm
    source = json.loads((SOURCES/'SOURCE.json').read_text())
    for name, digest in source['sha256'].items():
        assert hashlib.sha256((SOURCES/name).read_bytes()).hexdigest() == digest, f'Changed {name}'
    config = find_llvm_config(llvm)
    include = Path(run([config, '--includedir']))
    libdir = Path(run([config, '--libdir']))
    header = re.search(r'LLVM_REVISION R"\((\w+)\)"', (include/'llvm/Support/VCSRevision.h').read_text())
    clang = run([llvm/'clang++', '--version'])
    commit = source['commit']
    if not header or header[1] != commit or commit not in clang:
        raise RuntimeError(f'llc sources are {commit}; headers are {header and header[1]}; clang is\n{clang}')
    stamp = json.dumps({'commit': commit, 'llvm_config': str(config), 'llvm_bin': str(llvm),
                        'sources': source['sha256']}, sort_keys=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if not ((OUT/'llc').is_file() and (OUT/'stamp.json').is_file()
            and (OUT/'stamp.json').read_text() == stamp):
        print(f'[llc] building {commit[:12]} against {libdir}', flush=True)
        run(['c++', '-O2', *run([config, '--cxxflags']).split(),
             SOURCES/'llc.cpp', SOURCES/'NewPMDriver.cpp', '-o', OUT/'llc.tmp', '-L'+str(libdir),
             '-Wl,--start-group', *run([config, '--link-static', '--libs', *COMPONENTS]).split(),
             '-Wl,--end-group', *system_libraries(config, libdir)])
        (OUT/'llc.tmp').replace(OUT/'llc')
        (OUT/'stamp.json').write_text(stamp)
    for tool in llvm.iterdir():
        link = OUT/tool.name
        if tool.name in ('llc', 'stamp.json') or not tool.is_file():
            continue
        if link.is_symlink() or link.exists():
            if link.resolve() == tool.resolve():
                continue
            link.unlink()
        link.symlink_to(tool)
    if commit not in run([OUT/'clang++', '--version']):
        raise RuntimeError('Assembled tool directory does not run the selected clang++')
    return OUT


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-bin', type=Path, default=Path('/opt/rocm/llvm/bin'))
    print(ensure_llc(parser.parse_args().llvm_bin))
