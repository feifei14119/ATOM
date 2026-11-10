"""gfx1250 port of callee_test01's pre-RA SI_CALL preservation-mask prototype.

Only the named call's mask changes. Baseline and untouched MIR round-trip
instruction bytes must match before the custom caller is linked or launched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from regmask_tables import Elf, run, native_mask, low_mask
from asm.prepare import SYMBOL

LLVM_COMMIT = 'd177931e65e6057dca59f1c5b95e643d29876db3'


def preflight(llvm):
    for name in ('clang++', 'llc', 'opt', 'llvm-dis', 'ld.lld', 'llvm-objdump'):
        if not (llvm/name).is_file():
            raise RuntimeError(f'Missing LLVM tool {llvm/name}')
    version = run([llvm/'clang++', '--version'])
    if LLVM_COMMIT not in version:
        raise RuntimeError('This MIR prototype requires the callee_test01 LLVM build '
                           + LLVM_COMMIT + '; revalidate the MIR round trip and ABI for another build.\n'+version)
    # llc itself, not clang, supplies the physical register names and aliases.
    llc_version = run([llvm/'llc', '--version'])
    names, sha = native_mask(llvm/'llc')
    kept, removed = low_mask(names)
    return dict(clang_version=version, llc_version=llc_version, llc_sha256=sha,
                native_mask_names=names, kept_mask_names=kept, removed_mask_names=removed)


def body(text, symbol):
    m = re.search(r'^'+re.escape(symbol)+r':[^\n]*\n.*?^\.Lfunc_end\d+:', text, re.M | re.S)
    if not m:
        raise RuntimeError('Cannot locate exactly delimited caller assembly body')
    return m[0]


def compile_caller(bitcode, stage, symbol, out, llvm, llvm_options=None):
    out.mkdir(parents=True, exist_ok=True)
    report = preflight(llvm)
    from asm.audit import audit_object
    report['stage'] = audit_object(stage, llvm)
    clean = out/'caller.codegen.ll'
    run([llvm/'opt', '-S', '-passes=internalize,globaldce',
         '-internalize-public-api-list='+symbol+','+SYMBOL, bitcode, '-o', clean])
    ir = clean.read_text()
    assert 'amdgpu-num-vgpr' not in ir and 'amdgpu-num-sgpr' not in ir
    definitions = re.findall(r'^define\b[^\n]*@([^ (]+)\(', ir, re.M)
    assert definitions == [symbol], f'Unexpected non-inlined device functions: {definitions}'
    assert len(re.findall(r'\bcall\b[^\n]*@'+SYMBOL+r'\(', ir)) == 1
    assert re.search(r'^declare\b[^\n]*void @'+SYMBOL+r'\(ptr(?: [^,]+)?, i32', ir, re.M), \
        'Device signature must be generic pointer + i32, with no inreg/byval'
    declaration = next(l for l in ir.splitlines() if l.startswith('declare ') and '@'+SYMBOL+'(' in l)
    assert not any(word in declaration for word in ('inreg', 'byval', 'sret', 'amdgpu_kernel'))
    attr_match = re.search(r'#(\d+)', declaration)
    attrs = declaration
    if attr_match:
        attrs += re.search(r'^attributes #'+attr_match[1]+r' = \{([^\n]*)\}', ir, re.M)[1]
    assert all(word in attrs for word in ('convergent', 'noduplicate', 'noinline', 'nounwind'))
    assert not re.search(r'\b(?:readnone|readonly|speculatable)\b|memory\(none\)', attrs)
    flags = [llvm/'llc', '-mtriple=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-O2',
             '-verify-machineinstrs', '-amdgpu-assume-external-call-stack-size=0']
    for key, value in (llvm_options or {}).items():
        if any(s in key for s in ('regalloc', 'stop-', 'start-', 'verify-machine', 'assume-external')):
            raise RuntimeError(f'Unsupported codegen override {key}')
        flags.append('--'+key+'='+str(value).lower() if isinstance(value, bool) else '--'+key+'='+str(value))
    baseline_path, raw_mir = out/'caller.default_abi.s', out/'caller.before_regmask.mir'
    run(flags+[clean, '-o', baseline_path])
    run(flags+['-stop-after=finalize-isel', clean, '-o', raw_mir])
    baseline, mir = baseline_path.read_text(), raw_mir.read_text()
    assert re.findall(r'^name:\s+(\S+)', mir, re.M) == [symbol]
    target_calls = [line for line in mir.splitlines() if 'SI_CALL' in line]
    assert len(target_calls) == 1 and '@'+SYMBOL in target_calls[0]
    # Ordinary pointer + i32 parameters must actually reach v0:v1 + v2.
    # LLVM may print a 64-bit argument as a tuple or two legalized i32 uses.
    implicit_vgprs = set()
    for operand in re.findall(r'\bimplicit(?: killed)? \$(vgpr\d+(?:_vgpr\d+)*)', target_calls[0]):
        implicit_vgprs.update(int(n) for n in re.findall(r'vgpr(\d+)', operand))
    assert {0, 1, 2} <= implicit_vgprs, target_calls[0]
    # The wave32 MIR printer writes $vcc_lo, but the parser requires the
    # descriptor's implicit $vcc on these opcodes.
    mir, normalized = re.subn(
        r'^(\s*(?:S_CBRANCH_VCC(?:NZ|Z) |[^\n]*\bV_DIV_FMAS_F(?:32|64)_e64 )[^\n]*?implicit (?:killed )?\$vcc_lo)\b',
        r'\1, implicit undef $vcc', mir, flags=re.M)
    roundtrip_mir = out/'caller.roundtrip.mir'
    roundtrip_mir.write_text(mir)
    roundtrip_s = out/'caller.roundtrip.raw.s'
    run(flags+['-start-after=finalize-isel', roundtrip_mir, '-o', roundtrip_s])
    assert body(roundtrip_s.read_text(), symbol) == body(baseline, symbol), \
        'Untouched MIR round trip changed instructions; do not use this pipeline/toolchain'

    # The pinned MIR serializer loses the entry preload count. Recover only
    # this ABI field; resource allocation counts remain the custom pipeline's.
    user_counts = re.findall(r'\.amdhsa_user_sgpr_count (\d+)', baseline)
    assert len(user_counts) == 1
    def finish(text):
        text, n = re.subn(r'(\.amdhsa_user_sgpr_count )\d+',
                          lambda m: m[1]+user_counts[0], text)
        assert n == 1
        text = re.sub(r'(; COMPUTE_PGM_RSRC2:USER_SGPR: )\d+', lambda m: m[1]+user_counts[0], text)
        if not re.search(r'\.set\s+amdgpu.max_num_named_barrier,', text):
            text += '\n.set amdgpu.max_num_named_barrier, 0\n'
        return text

    kept = report['kept_mask_names']
    custom = 'CustomRegMask('+','.join('$'+n.lower() for n in kept)+')'
    changed_mir, count = re.subn(r'(^.*SI_CALL[^\n]*@'+SYMBOL+r', )csr_amdgpu\b',
                                lambda m: m[1]+custom, mir, flags=re.M)
    assert count == 1 and changed_mir.replace(custom, 'csr_amdgpu') == mir
    custom_path = out/'caller.lowctx.mir'
    custom_path.write_text(changed_mir)
    custom_raw = out/'caller.lowctx.raw.s'
    run(flags+['-start-after=finalize-isel', custom_path, '-o', custom_raw])
    run(flags+['-start-after=finalize-isel', '-stop-after=amdgpu-resource-usage',
               custom_path, '-o', out/'caller.allocated.mir'])
    allocated = (out/'caller.allocated.mir').read_text()
    final_calls = [l for l in allocated.splitlines() if 'SI_CALL' in l and '@'+SYMBOL in l]
    assert len(final_calls) == 1 and 'CustomRegMask(' in final_calls[0]
    final_mask = re.search(r'CustomRegMask\(([^)]*)\)', final_calls[0])[1]
    assert {x.strip().lower() for x in final_mask.split(',')} == {'$'+n.lower() for n in kept}

    # Assemble both unmodified paths and compare actual bytes and relocations.
    for name, source in [('default', baseline), ('roundtrip', roundtrip_s.read_text()),
                         ('lowctx', custom_raw.read_text())]:
        path = out/f'caller.{name}.s'
        path.write_text(finish(source))
        run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250',
             '-x', 'assembler', '-c', path, '-o', out/f'caller.{name}.o'])
    a, b = Elf(out/'caller.default.o'), Elf(out/'caller.roundtrip.o')
    assert a.blob(symbol) == b.blob(symbol)
    def relocations(obj):
        return [(s[1], obj.data[s[4]:s[4]+s[5]]) for s in obj.sections if s[1] in (4, 9)]
    assert relocations(a) == relocations(b), 'MIR round trip changed relocation records'
    assert a.blob(symbol+'.kd') == b.blob(symbol+'.kd'), 'Round trip changed kernel descriptor'
    run([llvm/'ld.lld', '-shared', '--no-undefined', out/'caller.lowctx.o', stage, '-o', out/'kernel.co'])
    report.update(caller=symbol, callee=SYMBOL, calls_changed=count,
                  point='after finalize-isel, before ALL register allocators',
                  preserved_vgprs=list(range(40, 48))+list(range(56, 64)),
                  preserved_sgprs=list(range(30, 40)), function_register_limits=None,
                  untouched_roundtrip_bytes_descriptor_relocations_identical=True,
                  mir_vcc_operands_normalized=normalized, restored_user_sgpr_count=int(user_counts[0]),
                  custom_mask_survives_allocation=True,
                  live_register_audit='LLVM machine verifier + ABI mask; no single-block liveness heuristic on Mono CFG',
                  compiled_gpu_execution='NOT RUN by this builder')
    (out/'callsite_regmask.json').write_text(json.dumps(report, indent=2)+'\n')
    return (out/'kernel.co').read_bytes(), report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bitcode', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--llvm-bin', type=Path, default=Path('/opt/rocm/llvm/bin'))
    a = parser.parse_args()
    compile_caller(a.bitcode, a.stage, a.symbol, a.output_dir, a.llvm_bin)
