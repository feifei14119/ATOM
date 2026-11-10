"""Check that actual instruction bytes and compiler-visible constraints agree."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

build = Path(sys.argv[1])
data = (build/'mono_kernel.co').read_bytes()
assert data[:6] == b'\x7fELF\x02\x01'
assert struct.unpack_from('<HH', data, 16) == (3, 224)
at = struct.unpack_from('<Q', data, 40)[0]
width, count = struct.unpack_from('<HH', data, 58)
sections = [struct.unpack_from('<IIQQQQIIQQ', data, at+i*width) for i in range(count)]
assert not any(s[1] in (4, 9) and s[5] for s in sections)
symbols = {}
for sec in sections:
    if sec[1] != 2:
        continue
    strings_sec = sections[sec[6]]
    strings = data[strings_sec[4]:strings_sec[4]+strings_sec[5]]
    for at in range(sec[4], sec[4]+sec[5], sec[9]):
        name, info, _, index, value, size = struct.unpack_from('<IBBHQQ', data, at)
        name = strings[name:strings.index(b'\0', name)].decode()
        if name:
            symbols[name] = index, value, size
assert 'stage_sub_device' not in symbols
assert not [name for name, (index, _, _) in symbols.items() if index == 0]
index, value, size = symbols['mono_kernel']
sec = sections[index]
assert sec[2] & 4, 'Kernel must be in an executable section'
body_at = sec[4]+value-sec[3]
body = data[body_at:body_at+size]
payload = (build/'sub_words.bin').read_bytes()
assert len(payload) == 288 and body.count(payload) == 1
assert (value+body.index(payload)) % 64 == 0

ir = (build/'mono_kernel.ll').read_text()
inline = [line for line in ir.splitlines() if 'asm sideeffect' in line and '.long' in line]
assert len(inline) == 1
line = inline[0]
clobbered = {f'v{i}' for i in range(8, 16)} | {f's{i}' for i in range(4)}
fixed_inputs = [f'v{i}' for i in range(8)] + ['v31', 's8', 's9', 's12']
constraints = re.search(r'", "([^"]+)"\(i32', line)[1].split(',')
assert constraints[:12] == [f'{{{r}}}' for r in fixed_inputs], 'Expected direct fixed-register constraints'
assert set(constraints[12:]) == {f'~{{{r}}}' for r in clobbered | {'vcc', 'scc', 'memory'}}
assert not set(fixed_inputs) & clobbered, 'Read-only fixed inputs must not also be clobbers'
parameters = line.split('"(i32', 1)[1].split(') #', 1)[0]
assert 'i64' not in parameters and parameters.count('i32') == 11
attribute = re.search(r'\) #(\d+)', line)[1]
assert re.search(r'attributes #'+attribute+r' = \{[^}]*\bconvergent\b', ir)
assert 'amdgpu-num-vgpr' not in ir and 'amdgpu-num-sgpr' not in ir
assert '@stage_sub_device' not in ir

assembly = (build/'mono_kernel.s').read_text()
start = assembly.index('mono_kernel:')
end = assembly.index('.section\t.rodata', start)
function = assembly[start:end]
assert function.count(';;#ASMSTART') == function.count(';;#ASMEND') == 1
assert '.long' in function
# No hand-written setup moves inside the asm. The compiler still prepares its
# fixed inputs outside the region; check every pointer word, not just v0.
before, inline_region = function.split(';;#ASMSTART')
inline_region = inline_region.split(';;#ASMEND')[0]
setup = inline_region.split('.long')[0]
assert not re.search(r'\b[sv]_(?:dual_)?mov_b(?:32|64)', setup)
entry = before[before.rfind('\n.LBB'):]
for reg in range(8):
    assert re.search(r'\bv'+str(reg)+r', s\d+', entry), f'Missing compiler setup for v{reg}'
assert 's_add_u32 s8,' in entry and 's_addc_u32 s9,' in entry
assert re.search(r'\bv31, v0\b', before)
entry_lines = [line.strip() for line in entry.splitlines()
               if re.match(r'\s*[sv]_(?:dual_)?mov_b', line)]
disasm = (build/'mono_kernel.disasm.txt').read_text()
assert not re.search(r'\bs_(?:getpc|setpc|swappc)_b64\b', disasm)
assert 's_branch' in disasm and 's_barrier' in disasm
metadata = (build/'mono_kernel.elf.txt').read_text()
assert re.findall(r'^\s+\.name:\s+(\S+)', metadata, re.M) == ['mono_kernel']
resources = {key: int(re.search(r'\.'+key+r':\s*(\d+)', metadata)[1]) for key in
             ['vgpr_count', 'sgpr_count', 'private_segment_fixed_size', 'group_segment_fixed_size',
              'vgpr_spill_count', 'sgpr_spill_count']}
assert resources['vgpr_count'] >= 32 and resources['sgpr_count'] >= 13
report = {'inline_asm_present_in_IR': True, 'all_pointer_words_passed_as_i32': True,
          'direct_fixed_input_constraints': constraints[:12],
          'handwritten_entry_moves_inside_asm': 0,
          'compiler_generated_entry_moves': entry_lines,
          'input_registers_disjoint_from_clobbers': True,
          'clobbered_gprs': sorted(clobbered), 'function_register_count_limit': None,
          'convergent_and_memory_clobber': True, 'embedded_bytes': len(payload),
          'payload_sha256': hashlib.sha256(payload).hexdigest(),
          'payload_exactly_once_in_executable_kernel': True,
          'payload_64_byte_aligned': True, 'device_call_or_return': False,
          'external_stage_symbol': False, 'resources': resources}
(build/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
print('PASS: .long in real inline asm; complete inputs/clobbers; exact executable payload; no device call/return')
print(json.dumps(resources, indent=2))
