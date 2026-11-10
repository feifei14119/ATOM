"""Source, bitcode-IR and final-linked-ELF checks for the standard ABI wrapper."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from asm.audit import load_fragment
from asm.prepare import SGPRS, VGPRS, Elf, disassembly_rows

ROOT = Path(__file__).resolve().parent
WRAPPER = 'mono_dq_convert_wrapper'
CALL_OPS = ('s_swappc_b64', 's_swap_pc_i64')
RETURN_OPS = ('s_setpc_b64', 's_set_pc_i64')


def audit_wrapper_source():
    header = (ROOT/'asm/dq_convert_inline.h').read_text()
    declared = re.findall(r'"([sv]\d+|scc|memory)"', header)
    expected = [*[f's{i}' for i in SGPRS], *[f'v{i}' for i in VGPRS], 'scc', 'memory']
    assert declared == expected, 'C++ clobbers must match the supplier write-set contract'
    for token in ('"{s[0:1]}"(address)', '"{v0}"(lane)', '"{s24}"(wave)',
                  '#include "dq_convert.inline.words.inc"'):
        assert token in header, f'Missing fixed input/fragment: {token}'
    cpp = (ROOT/'asm/dq_wrapper.cpp').read_text()
    assert re.search(r'extern "C" __device__ __attribute__\(\(noinline, convergent\)\)', cpp)
    assert 'stage_dq_convert_inline(' in cpp
    assert 'amdgpu_num_vgpr' not in cpp+header and 'amdgpu_num_sgpr' not in cpp+header
    return {'clobbers': expected, 'ordinary_device_function': WRAPPER,
            'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                              ('asm/dq_wrapper.cpp', 'asm/dq_wrapper.h', 'asm/dq_convert_inline.h')}}


def decode_llvm_string(s):
    out, i = [], 0
    while i < len(s):
        if s[i] != '\\':
            out.append(s[i]); i += 1
        elif s[i+1] in '\\"':
            out.append(s[i+1]); i += 2
        else:
            out.append(chr(int(s[i+1:i+3], 16))); i += 3
    return ''.join(out)


def audit_wrapper_ir(text, fragment_dir):
    _, constraints, fragment, _ = load_fragment(fragment_dir)
    definitions = re.findall(r'^define\b[^\n]*@([^ (]+)\(', text, re.M)
    assert definitions == [WRAPPER], f'Unexpected definitions: {definitions}'
    m = re.search(r'^define\b[^\n]*@'+WRAPPER+r'\(([^\n]*)\)([^\n]*)\{\n(.*?)^\}', text, re.M | re.S)
    assert m, 'Missing wrapper IR body'
    params = m[1].split(',')
    assert len(params) == 2 and params[0].strip().startswith('i64 ') and params[1].strip().startswith('i32 ')
    assert not any(s in m[0].split('\n', 1)[0] for s in ('amdgpu_kernel', 'inreg', 'byval', 'sret'))
    groups = re.findall(r'#(\d+)', m[2])
    attrs = m[2]
    for n in groups:
        attr = re.search(r'^attributes #'+n+r' = \{([^\n]*)\}', text, re.M)
        assert attr
        attrs += ' '+attr[1]
    for name in ('noinline', 'convergent'):
        assert re.search(r'\b'+name+r'\b', attrs), f'Missing wrapper attribute {name}'
    assert '"target-cpu"="gfx1250"' in attrs
    assert '+wavefrontsize64' not in attrs and '-wavefrontsize32' not in attrs
    assert not re.search(r'\b(?:readnone|readonly|speculatable|alwaysinline)\b|memory\(none\)', attrs)
    assert 'amdgpu-num-vgpr' not in text and 'amdgpu-num-sgpr' not in text
    pairs = re.findall(r'\basm\s+sideeffect\s+"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"', m[3])
    assert len(pairs) == 1, 'Expected exactly one opaque side-effecting ASM boundary'
    asm, actual = map(decode_llvm_string, pairs[0])
    assert actual == constraints, (actual, constraints)
    words = re.findall(r'^\.long (.+)$', asm, re.M)
    encoded = b''.join(struct.pack('<I', int(w.strip(), 16)) for line in words for w in line.split(','))
    assert encoded == fragment
    assert asm.startswith('s_branch 1f\n.p2align 6\n1:\n')
    assert not re.search(r'\bsext i32', m[3]), 'Address halves must remain unsigned before joining'
    assert not re.search(r'\bcall\b[^\n]*@(?!(?:llvm\.))', m[3]), 'Wrapper must be a leaf'
    return {'signature': 'void(i64, i32)', 'attributes': attrs.strip(),
            'clobbers_match_fragment': True, 'opaque_bytes_match_fragment': True,
            'fragment_sha256': hashlib.sha256(fragment).hexdigest(),
            'normal_codegen_will_allocate_registers': True}


def audit_codegen_envelope(text):
    # LLVM's AMDGPU ASM printer delimits the user block with these comments.
    # Inspection only: no numeric regmask IDs or machine-code editing.
    assert text.count(';;#ASMSTART') == 1 and text.count(';;#ASMEND') == 1
    before, rest = text.split(';;#ASMSTART')
    _, after = rest.split(';;#ASMEND')
    result = {}
    for key in ('num_vgpr', 'numbered_sgpr', 'private_seg_size'):
        match = re.search(r'\.set\s+(?:\.L)?'+WRAPPER+r'\.'+key+r',\s*(\d+)\b', text)
        result[key] = int(match[1]) if match else None
    result['scratch_store_instructions_before'] = len(re.findall(r'^\s*scratch_store\w*\b', before, re.M))
    result['scratch_load_instructions_after'] = len(re.findall(r'^\s*scratch_load\w*\b', after, re.M))
    result['return_instruction_present'] = bool(re.search(r'^\s*s_(?:setpc_b64|set_pc_i64)\b', after, re.M))
    assert result['return_instruction_present']
    assert not re.search(r'^\s*s_(?:swappc_b64|swap_pc_i64|endpgm)\b', before+'\n'+after, re.M)
    result['scope'] = 'Offline wrapper codegen only; final Mono resources can differ'
    return result


def audit_linked_wrapper(kernel, symbol, resources, fragment_dir, llvm):
    _, constraints, fragment, contract = load_fragment(fragment_dir)
    obj = Elf(kernel)
    assert (obj.kind, obj.machine) == (3, 224)
    assert WRAPPER in obj.symbols and obj.symbols[WRAPPER][2] > 0, 'No separately emitted wrapper'
    wrapper = obj.body(WRAPPER)
    mono = obj.body(symbol)
    offsets = [i for i in range(len(wrapper)-len(fragment)+1) if wrapper.startswith(fragment, i)]
    assert len(offsets) == 1, f'Expected one intact fragment in wrapper, found {offsets}'
    assert fragment not in mono, 'Wrapper was expanded into Mono'
    assert (obj.symbols[WRAPPER][1]+offsets[0]) % 64 == 0
    assert resources['vgpr'] >= contract['minimum_vgprs']
    assert resources['sgpr'] >= contract['minimum_numbered_sgprs']
    assert not [n for n, info in obj.symbols.items() if info[0] == 0], 'Unresolved ELF symbols'

    def disassemble(name):
        cmd = [str(llvm/'llvm-objdump'), '--mcpu=gfx1250', '--disassemble-symbols='+name, str(kernel)]
        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f'{cmd}\n{result.stdout}\n{result.stderr}')
        return result.stdout

    caller_dis, wrapper_dis = disassemble(symbol), disassemble(WRAPPER)
    kernel.with_name('mono.function.disasm.txt').write_text(caller_dis)
    kernel.with_name('wrapper.function.disasm.txt').write_text(wrapper_dis)
    def symbol_rows(name, text):
        # Newer llvm-objdump continues past the symbol size into alignment padding.
        _, value, size, _ = obj.symbols[name]
        rows = disassembly_rows(text)
        inside = [row for row in rows if row[1] < value+size]
        assert all(i in ('s_code_end', 's_nop 0') for i, _, _ in rows[len(inside):]), \
            f'Non-padding instructions after {name}'
        return inside
    caller_rows, wrapper_rows = symbol_rows(symbol, caller_dis), symbol_rows(WRAPPER, wrapper_dis)
    assert caller_rows and wrapper_rows
    def bytes_of(rows):
        return b''.join(struct.pack('<I', int(w, 16)) for _, _, words in rows for w in words)
    assert bytes_of(caller_rows) == mono and bytes_of(wrapper_rows) == wrapper
    caller_calls = [i for i, _, _ in caller_rows if i.startswith(CALL_OPS)]
    assert len(caller_calls) == 1, 'Expected one real Mono device-call site'
    assert not any(i.startswith((*CALL_OPS, 's_endpgm')) for i, _, _ in wrapper_rows)
    assert sum(i.startswith(RETURN_OPS) for i, _, _ in wrapper_rows) == 1
    start = obj.symbols[WRAPPER][1]+offsets[0]
    stop = start+len(fragment)
    before = '\n'.join(i for i, addr, _ in wrapper_rows if addr < start)
    after = '\n'.join(i for i, addr, _ in wrapper_rows if addr >= stop)
    kernel.with_name('wrapper.envelope.txt').write_text(
        '// Compiler-generated wrapper BEFORE opaque ASM\n'+before+
        '\n\n// Compiler-generated wrapper AFTER opaque ASM\n'+after+'\n')
    def scratch_counts(rows):
        return {kind: sum(i.startswith('scratch_'+kind) for i, _, _ in rows) for kind in ('load', 'store')}
    # This reports the exact compiled envelope; it is not a general symbolic
    # verifier of arbitrary spill/prologue instructions or inactive-lane state.
    return {'wrapper_symbol': WRAPPER, 'real_device_calls': 1, 'standard_abi': True,
            'fragment_occurrences_in_wrapper': 1, 'fragment_occurrences_in_mono': 0,
            'fragment_sha256': hashlib.sha256(fragment).hexdigest(), 'constraints': constraints,
            'wrapper_bytes': len(wrapper), 'fragment_offset_in_wrapper': offsets[0],
            'compiler_bytes_before_fragment': offsets[0],
            'compiler_bytes_after_fragment': len(wrapper)-offsets[0]-len(fragment),
            'scratch_instructions': {'mono': scratch_counts(caller_rows), 'wrapper': scratch_counts(wrapper_rows)},
            'save_restore_evidence': 'wrapper.envelope.txt; compiler handles standard ABI, GPU A/B verifies exercised contexts'}
