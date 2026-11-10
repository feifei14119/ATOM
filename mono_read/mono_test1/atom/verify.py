"""Audit the adaptation and compile/link the real inline header; no GPU run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from prepare import (ROOT, SYMBOL, SOURCE_SHA, SGPRS, VGPRS, PATCHES, Elf,
                     original_records, rename_sgprs, disassembly_rows, run)

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--llvm-bin', default='/opt/rocm/llvm/bin', type=Path)
llvm = ap.parse_args().llvm_bin
build = ROOT/'build'
build.mkdir(exist_ok=True)
records = original_records()
contract = json.loads((ROOT/'inline_contract.json').read_text())
assert contract['source_sha256'] == SOURCE_SHA
original_bytes = b''.join(struct.pack('<I', int(w, 16)) for _, _, ws in records for w in ws)
run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-x', 'assembler',
     '-c', ROOT/'dq_convert.original.s', '-o', build/'original.o'])
assert Elf(build/'original.o').body('_ZN5aiter29fmha_bwd_hd64_dq_convert_bf16E') == original_bytes

assembly = (ROOT/'dq_convert.inline.s').read_text()
prefix, rest = assembly.split('.Linline_payload:\n')
payload, suffix = rest.split('.Linline_payload_end:\n')


def instructions(text):
    result = []
    for line in text.splitlines():
        line = line.split('//')[0].strip()
        if line and not line.startswith('.') and not line.endswith(':'):
            result.append(line)
    return result


expected = []
for offset, inst, _ in records[:-1]:
    expected.extend(PATCHES[offset][1] if offset in PATCHES else [rename_sgprs(inst)])
assert instructions(payload) == expected, 'Unreviewed payload change'
# The mapping is bijective and its destination range was unused by the supplier.
assert not re.search(r'\bs(?:4\d|\[4\d:)', '\n'.join(i for _, i, _ in records))


def regs(operand):
    m = re.fullmatch(r'([sv])\[(\d+):(\d+)\]', operand)
    if m:
        return {m[1]+str(i) for i in range(int(m[2]), int(m[3])+1)}
    return {operand} if re.fullmatch(r'[sv]\d+', operand) else set()


written = set()
for inst in instructions(assembly):
    opcode, *operands = inst.split(None, 1)
    # Store's first operand is a source; the others have no numbered GPR dest.
    if opcode.startswith(('buffer_store', 's_wait', 's_version', 's_cmp',
                          's_cbranch', 's_setreg', 's_nop')):
        continue
    if operands:
        written |= regs(operands[0].split(',')[0].strip())
assert written == {f's{i}' for i in SGPRS} | {f'v{i}' for i in VGPRS}
assert not written & {'s0', 's1', 's24', 'v0', *[f's{i}' for i in range(30, 40)]}
code = '\n'.join(instructions(assembly))
assert not re.search(r'\b(?:ttmp\d+|vcc(?:_lo|_hi)?|m0|scratch_\w+|ds_\w+|s_barrier\w*)\b', code)
assert not re.search(r'\bs_(?:endpgm|getpc|setpc|swappc|swap_pc)\w*\b', code)
exec_writes = [i for i in instructions(payload) if 'exec_lo' in i]
assert len(exec_writes) == 32
assert all(exec_writes[i] in ('s_mov_b32 exec_lo, s40', 's_mov_b32 exec_lo, s41')
           and exec_writes[i+1] == 's_mov_b32 exec_lo, -1' for i in range(0, 32, 2))
assert 's_getreg_b32 s5, hwreg(HW_REG_MODE, 0, 8)' in prefix
assert 's_setreg_imm32_b32 hwreg(HW_REG_MODE, 0, 8), 0xc0' in prefix
assert 's_setreg_b32 hwreg(HW_REG_MODE, 0, 8), s5' in suffix
assert not any('s5' in regs(i.split(None, 1)[1].split(',')[0])
               for i in instructions(payload) if len(i.split(None, 1)) == 2)
assert prefix.index('s_cbranch_scc1 .Linline_end') < prefix.index('s_getreg_b32')
assert suffix.index('s_setreg_b32') < suffix.index('.Linline_end:')

stage = Elf(ROOT/'dq_convert.inline.co')
assert (stage.kind, stage.machine) == (1, 224)
assert not any(s[1] in (4, 9) and s[5] for s in stage.sections)
body = stage.body(SYMBOL)
assert hashlib.sha256(body).hexdigest() == contract['fragment_sha256']
# Byte identity: unchanged instructions retain their original encoding; renamed
# instructions are intentionally re-encoded by the assembler, never bit-patched.
payload_at = body.index(original_bytes[:4])
assert body.count(original_bytes[:4]) == 1
unchanged_bytes = 0
for offset, inst, words in records[:-1]:
    if offset not in PATCHES and rename_sgprs(inst) == inst:
        old = b''.join(struct.pack('<I', int(w, 16)) for w in words)
        assert body[payload_at+offset:payload_at+offset+len(old)] == old
        unchanged_bytes += len(old)
inc = (ROOT/'dq_convert.inline.words.inc').read_text()
words = [int(w, 16) for line in inc.splitlines() if line.startswith('"')
         for w in re.findall(r'0x([0-9a-f]{8})', line.split(' // ')[0])]
assert b''.join(struct.pack('<I', w) for w in words) == body

# Independent tile-address equations vs. the documented input permutation.
seen_in, seen_out = set(), set()
for wave in range(4):
    for lane in range(32):
        load_base = wave*16*256 + (lane >> 4)*8*256 + (lane & 15)*16
        store_base = wave*16*128 + (lane & 4)*2*128 + ((lane & 15) >> 3)*64 + (lane >> 4)*32 + (lane & 3)*8
        for j in range(8):
            for component in range(4):
                src = (load_base+j*256+component*4)//4
                dst = (store_base+j*128+component*2)//2
                r, c = divmod(dst, 64)
                packed = (16*(r//16)+8*((c//16)%2)+r%8)*64 + 32*(c//32)+16*((r//8)%2)+c%16
                assert packed == src and src not in seen_in and dst not in seen_out
                seen_in.add(src)
                seen_out.add(dst)
assert seen_in == seen_out == set(range(4096))

# Compile unmodified C++ -> LLVM -> object. IR is saved for inspection only.
run([llvm/'clang++', '-x', 'hip', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
     '--offload-arch=gfx1250', '--offload-device-only', '-fgpu-rdc',
     '-c', ROOT/'compile_check.cpp', '-o', build/'caller.bc'])
run([llvm/'llvm-dis', build/'caller.bc', '-o', build/'caller.ll'])
ir = (build/'caller.ll').read_text()
assert 'amdgpu-num-vgpr' not in ir and 'amdgpu-num-sgpr' not in ir
asms = [line for line in ir.splitlines() if 'asm sideeffect' in line]
assert len(asms) == 2
for line in asms:
    assert '"{s[0:1]},{v0},{s24},' in line
    assert set(re.findall(r'~\{([^}]+)\}', line)) == set(contract['clobbers'])
    attr = re.search(r' #([0-9]+)', line)[1]
    assert re.search(r'attributes #'+attr+r' = \{[^}]*\bconvergent\b', ir)
run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-nogpulib',
     '-x', 'ir', '-O2', '-S', build/'caller.bc', '-o', build/'caller.s'])
run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-nogpulib',
     '-x', 'ir', '-O2', '-c', build/'caller.bc', '-o', build/'caller.o'])
# Only caller.o is linked; the fragment has already been embedded by inline asm.
run([llvm/'ld.lld', '-shared', '--no-undefined', build/'caller.o', '-o', build/'caller.co'])
caller = Elf(build/'caller.co')
caller_bytes = caller.body('mono_inline_check')
assert caller_bytes.count(body) == 2
sites = [m.start() for m in re.finditer(re.escape(body), caller_bytes)]
assert all(at % 64 == 0 for at in sites)
assert SYMBOL not in caller.symbols, 'Unexpected linked stage symbol'
notes = run([llvm/'llvm-readelf', '-n', build/'caller.co'])
dis = run([llvm/'llvm-objdump', '--mcpu=gfx1250', '--disassemble-symbols=mono_inline_check', build/'caller.co'])
(build/'caller.elf.txt').write_text(notes)
(build/'caller.disasm.txt').write_text(dis)
rows = disassembly_rows(dis)
assert not any(re.search(r'\bs_(?:getpc|setpc|swappc|swap_pc)', inst) for inst, _, _ in rows)
assert sum(inst == 's_endpgm' for inst, _, _ in rows) == 1
values = {key: int(re.search(r'\.'+key+r':\s*(\d+)', notes)[1]) for key in
          ['vgpr_count', 'sgpr_count', 'vgpr_spill_count', 'sgpr_spill_count',
           'private_segment_fixed_size', 'group_segment_fixed_size', 'wavefront_size']}
assert values['vgpr_count'] >= 46 and values['sgpr_count'] >= 49
assert values['wavefront_size'] == 32
assert all(values[k] == 0 for k in ('vgpr_spill_count', 'sgpr_spill_count',
                                  'private_segment_fixed_size', 'group_segment_fixed_size'))
# Check the actual binary descriptor as well as the YAML note. gfx1250 allocates
# wave32 VGPRs in groups of 16; the SGPR field does not allocate a count on gfx12.
kd = caller.body('mono_inline_check.kd')
assert len(kd) == 64
rsrc1, rsrc2 = struct.unpack_from('<II', kd, 48)
properties = struct.unpack_from('<H', kd, 56)[0]
assert ((rsrc1 & 0x3f)+1)*16 >= values['vgpr_count']
assert not rsrc2 & 1 and properties & (1 << 10)
# Inspect the caller's live values in the current compiler's actual allocation.
text = (build/'caller.s').read_text()
start = text.index('mono_inline_check:')
function = text[start:text.index('\t.section\t.rodata', start)]
outside = re.sub(r'\t;;#ASMSTART.*?\t;;#ASMEND', '[INLINE FRAGMENT]', function, flags=re.S)
(build/'caller.boundary.txt').write_text(outside)
assert len(outside.split('[INLINE FRAGMENT]')) == 3
# Header layout must also compile in ordinary host C++.
(build/'header.cpp').write_text('#include "dq_convert_args.h"\nint main() { DqConvertArgs a{}; return a.head_dim; }\n')
run([llvm/'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I'+str(ROOT),
     '-fsyntax-only', build/'header.cpp'])
report = {'status': 'PASS: static audit and gfx1250 compile/link; GPU not run',
          'compiler': run([llvm/'clang++', '--version']).splitlines()[0],
          'fragment_bytes': len(body), 'unchanged_supplier_bytes': unchanged_bytes,
          'inline_instances_in_caller': len(sites), 'caller_resource_values': values,
          'fixed_input_constraints_checked': True, 'clobber_coverage_checked': True,
          'exec_and_mode_paths_checked': True, 'tile_layout_bijection_checked': True,
          'descriptor_allocation_checked': True, 'ir_or_descriptor_patched': False,
          'gpu_execution': False, 'production_atom_integration': False}
(ROOT/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
