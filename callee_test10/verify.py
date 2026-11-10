"""Audit the ELF contract; optionally emit the stage's exact bytes as .long.

Only Python's standard library and the installed LLVM tools are used.
This does not edit LLVM IR, register allocation, code descriptors or metadata.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b'\x7fELF\x02\x01', 'Expected ELF64 little endian'
        self.kind, machine = struct.unpack_from('<HH', self.data, 16)
        assert machine == 224, 'Expected AMDGPU'
        offset = struct.unpack_from('<Q', self.data, 40)[0]
        width, count = struct.unpack_from('<HH', self.data, 58)
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.data, offset+i*width)
                         for i in range(count)]
        assert not any(s[1] in (4, 9) and s[5] for s in self.sections), \
            'Unresolved relocations cannot be embedded or launched in this test'
        self.symbols = {}
        for sec in self.sections:
            if sec[1] != 2:
                continue
            strings_sec = self.sections[sec[6]]
            strings = self.data[strings_sec[4]:strings_sec[4]+strings_sec[5]]
            for at in range(sec[4], sec[4]+sec[5], sec[9]):
                name, info, _, index, value, size = struct.unpack_from('<IBBHQQ', self.data, at)
                name = strings[name:strings.index(b'\0', name)].decode()
                if name:
                    self.symbols[name] = (info, index, value, size)

    def function(self, name):
        info, index, value, size = self.symbols[name]
        assert info & 15 == 2 and 0 < index < len(self.sections) and size
        sec = self.sections[index]
        assert sec[2] & 4, 'Expected executable section'
        at = sec[4] + value - sec[3]
        return self.data[at:at+size]


def emit(source, output, llvm):
    elf = Elf(source)
    assert elf.kind == 1, 'Expected ET_REL stage function'
    body = elf.function('stage_probe')
    headers = subprocess.check_output([str(llvm/'llvm-readelf'), '-h', str(source)], text=True)
    assert 'gfx1100' in headers
    disasm = subprocess.check_output([str(llvm/'llvm-objdump'), '--mcpu=gfx1100',
        '--disassemble-symbols=stage_probe', str(source)], text=True)
    rows = []
    for line in disasm.splitlines():
        match = re.match(r'\s*(.*?)\s*//\s*[0-9a-fA-F]+:\s*'
                         r'((?:[0-9a-fA-F]{8}(?:\s+|$))+)', line)
        if match:
            rows.append((match[1].strip(), match[2].split()))
    assert rows and rows[-1][0] == 's_setpc_b64 s[30:31]' and len(rows[-1][1]) == 1
    rebuilt = b''.join(struct.pack('<I', int(word, 16)) for _, words in rows for word in words)
    assert rebuilt == body, 'Disassembly must cover exactly the symbol bytes'
    for instruction, _ in rows[:-1]:
        assert not re.search(r'\bs_(?:getpc|setpc|swappc|branch|cbranch|endpgm)', instruction)
    lines = ['// Generated from stage_probe.co; only the final return is removed.']
    for instruction, words in rows[:-1]:
        lines.append(json.dumps('.long ' + ', '.join('0x'+word.lower() for word in words) + '\n')
                     + ' // ' + instruction)
    output.write_text('\n'.join(lines)+'\n')
    output.with_suffix('.bin').write_bytes(body[:-4])
    print(f'Emitted {len(body)-4} bytes as .long; removed only final s_setpc_b64')


def check(mode, build):
    assert mode in ('device', 'inline')
    stage = Elf(build/'stage_probe.co')
    linked = Elf(build/'caller.co')
    assert stage.kind == 1 and linked.kind == 3
    assert not any(index == 0 for _, index, _, _ in linked.symbols.values())
    body = stage.function('stage_probe')
    payload_offset = stage.symbols['stage_probe.payload_offset'][2]
    payload_size = stage.symbols['stage_probe.payload_size'][2]
    payload = body[payload_offset:payload_offset+payload_size]
    stage_disasm = (build/'stage_probe.disasm.txt').read_text()
    instructions = {line.split('//', 1)[0].strip() for line in stage_disasm.splitlines()}
    # Check actual instruction destinations, not just the declared clobbers.
    overwritten_vgprs = {int(r) for r in re.findall(
        r'v_mov_b32_e32 v(\d+), 0xdeadbeef', stage_disasm)}
    overwritten_sgprs = {int(r) for r in re.findall(
        r's_mov_b32 s(\d+), 0xbaadf00d', stage_disasm)}
    assert overwritten_vgprs == set(range(64, 256))
    assert overwritten_sgprs == set(range(40, 106))
    caller = linked.function('caller_kernel')
    disasm = (build/'caller.disasm.txt').read_text()
    ir = (build/'caller.ll').read_text()
    assert 'amdgpu-num-vgpr' not in ir and 'amdgpu-num-sgpr' not in ir
    if mode == 'device':
        assert linked.function('stage_probe') == body
        assert len(re.findall(r'\bs_swappc_b64\b', disasm)) == 2
        assert 's_setpc_b64 s[30:31]' in disasm
        calls = [line for line in ir.splitlines() if re.search(r'\bcall\b.*@stage_probe\(', line)]
        assert len(calls) == 2
        saved_vgprs = [r for start in range(72, 256, 16) for r in range(start, start+8)]
        saved_sgprs = [r for start in (48, 64, 80) for r in range(start, start+8)] + list(range(96, 106))
        assert {int(r) for r in re.findall(r'scratch_store_b32 off, v(\d+), s32', stage_disasm)} == set(saved_vgprs) | {18}
        assert {int(r) for r in re.findall(r'scratch_load_b32 v(\d+), off, s32', stage_disasm)} == set(saved_vgprs) | {18}
        for i, r in enumerate(saved_vgprs):
            suffix = '' if i == 0 else ' offset:'+str(4*i)
            assert f'scratch_store_b32 off, v{r}, s32{suffix}' in instructions
            assert f'scratch_load_b32 v{r}, off, s32{suffix}' in instructions
        # Every high preserved SGPR is copied into v18 and then recovered from it.
        assert {int(r) for r in re.findall(r'v_mov_b32_e32 v18, s(\d+)', stage_disasm)} == set(saved_sgprs)
        assert {int(r) for r in re.findall(r'v_readfirstlane_b32 s(\d+), v18', stage_disasm)} == set(saved_sgprs)
        stores = [int(offset) for offset in re.findall(r'scratch_store_b32 off, v18, s32 offset:(\d+)', stage_disasm)]
        loads = [int(offset) for offset in re.findall(r'scratch_load_b32 v18, off, s32 offset:(\d+)', stage_disasm)]
        assert stores == loads == list(range(384, 520, 4))
        assert stage.symbols['stage_probe.private_seg_size'][2] == 528
    else:
        assert 'stage_probe' not in linked.symbols
        assert payload == body[:-4]
        assert (build/'stage_words.bin').read_bytes() == payload
        assert caller.count(payload) == 2, 'Exact fragment must occur at both call sites'
        assert not re.search(r'\bs_(?:getpc|setpc|swappc)_b64\b', disasm)
        calls = [line for line in ir.splitlines() if 'asm sideeffect' in line and '.long' in line]
        assert len(calls) == 2
        for call in calls:
            constraints = re.search(r'", "([^\"]+)"\(', call)[1].split(',')
            assert constraints[0] == '={v0}'
            assert '0' in constraints, 'bias must be tied to the v0 output'
            assert constraints[1] == '=&s'
            fixed = {f'{{v{i}}}' for i in range(1, 9)} | {'{v31}', '{s12}', '{s13}'}
            clobbers = {f'~{{v{i}}}' for i in range(9, 18)} | {'~{s0}', '~{scc}', '~{memory}'}
            clobbers |= {f'~{{v{i}}}' for i in range(64, 256)} | {f'~{{s{i}}}' for i in range(40, 105)}
            assert set(constraints) == fixed | clobbers | {'={v0}', '=&s', '0'}
        assembly = (build/'caller.s').read_text()
        regions = [region for region in re.findall(r';;#ASMSTART(.*?);;#ASMEND', assembly, re.S)
                   if '.long' in region]
        assert len(regions) == 2
        for region in regions:
            saved = re.search(r's_mov_b32 s(\d+), s105', region)
            assert saved and int(saved[1]) < 40 and int(saved[1]) not in (0, 12, 13)
            assert re.search(r's_mov_b32 s105, s'+saved[1]+r'\b', region)
    meta = (build/'caller.elf.txt').read_text()
    assert re.search(r'\.max_flat_workgroup_size:\s*256\b', meta)
    assert re.findall(r'^\s+\.name:\s+(\S+)', meta, re.M) == ['caller_kernel']
    resources = {key: int(re.search(r'\.'+key+r':\s*(\d+)', meta)[1]) for key in
                 ('vgpr_count', 'sgpr_count', 'private_segment_fixed_size',
                  'group_segment_fixed_size', 'vgpr_spill_count', 'sgpr_spill_count')}
    assert resources['vgpr_count'] == 256
    assert resources['sgpr_count'] >= 108  # 106 numbered SGPRs plus the reserved VCC pair.
    if mode == 'device':
        assert resources['private_segment_fixed_size'] >= 528
    else:
        assert resources['private_segment_fixed_size'] == 0
    report = {'mode': mode, 'target': 'gfx1100', 'stage_function_bytes': len(body),
              'payload_bytes': len(payload),
              'payload_sha256': hashlib.sha256(payload).hexdigest(),
              'overwritten_vgprs': 'v64-v255 (192)', 'overwritten_sgprs': 's40-s105 (66)',
              'callee_saved_vgprs_restored': 96 if mode == 'device' else 0,
              'callee_saved_sgprs_restored': 34 if mode == 'device' else 0,
              'inline_reserved_s105_preserved': mode == 'inline',
              'max_threads_per_block': 256,
              'call_sites': 2, 'register_limits': None, 'resources': resources,
              'scratch_instruction_count': len(re.findall(r'\bscratch_\w+', disasm))}
    (build/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS static audit: ' + json.dumps(report))


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == 'emit':
        emit(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    elif len(sys.argv) == 4 and sys.argv[1] == 'check':
        check(sys.argv[2], Path(sys.argv[3]))
    else:
        sys.exit('Usage: verify.py emit stage.co output.inc LLVM_DIR | check device|inline BUILD')
