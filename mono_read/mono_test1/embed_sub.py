"""Turn the fixed gfx1100 device-function binary into C++ .long string literals."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--stage', required=True, type=Path)
ap.add_argument('--output', required=True, type=Path)
ap.add_argument('--llvm-bin', default='/opt/rocm/llvm/bin', type=Path)
args = ap.parse_args()
data = args.stage.read_bytes()
assert data[:6] == b'\x7fELF\x02\x01'
assert struct.unpack_from('<HH', data, 16) == (1, 224), 'Expected relocatable AMDGPU ELF'
at = struct.unpack_from('<Q', data, 40)[0]
width, count = struct.unpack_from('<HH', data, 58)
sections = [struct.unpack_from('<IIQQQQIIQQ', data, at+i*width) for i in range(count)]
assert not any(s[1] in (4, 9) and s[5] for s in sections), 'Relocations need adaptation'
symbol = None
for sec in sections:
    if sec[1] != 2:
        continue
    strings_sec = sections[sec[6]]
    strings = data[strings_sec[4]:strings_sec[4]+strings_sec[5]]
    for at in range(sec[4], sec[4]+sec[5], sec[9]):
        name, info, _, index, value, size = struct.unpack_from('<IBBHQQ', data, at)
        if strings[name:strings.index(b'\0', name)] == b'stage_sub_device':
            assert info & 15 == 2 and index
            symbol = index, value, size
assert symbol, 'Missing sized stage_sub_device function'
index, start, size = symbol
sec = sections[index]
body_at = sec[4]+start-sec[3]
body = data[body_at:body_at+size]
# This hash pins the ABI, clobbers, synchronization and relative branches.
assert hashlib.sha256(body).hexdigest() == '040b7830b48375bd886e11e41256c3df26bc62a7f6b6bc8c4f0d1d6bc19bef87', 'Changed supplier: re-audit before embedding'
info = subprocess.check_output([str(args.llvm_bin/'llvm-readelf'), '-h', str(args.stage)], text=True)
assert 'gfx1100' in info
text = subprocess.check_output([str(args.llvm_bin/'llvm-objdump'), '--mcpu=gfx1100',
    '--disassemble-symbols=stage_sub_device', '--start-address='+str(start),
    '--stop-address='+str(start+size), str(args.stage)], text=True)
rows = []
for line in text.splitlines():
    m = re.match(r'\s*(.*?)\s*//\s*([0-9A-Fa-f]+):\s*((?:[0-9A-Fa-f]{8}(?:\s+|$))+)', line)
    if m:
        rows.append((m[1].strip(), int(m[2], 16), m[3].split()))
assert rows[-1][0] == 's_setpc_b64 s[30:31]'
assert len(rows[-1][2]) == 1 and size == 292
rebuilt = b''.join(struct.pack('<I', int(w, 16)) for _, _, words in rows for w in words)
assert rebuilt == body
instruction_offsets = {address for _, address, _ in rows}
for instruction, address, words in rows[:-1]:
    if instruction.startswith('s_cbranch_'):
        displacement = int(words[0], 16) & 0xffff
        if displacement >= 0x8000:
            displacement -= 0x10000
        assert address+4+4*displacement in instruction_offsets
    assert not re.search(r'\bs_(?:getpc|setpc|swappc)_b64\b|\bs_endpgm\b', instruction)
lines = ['// Generated instruction words. The sole final return was removed.']
for instruction, _, words in rows[:-1]:
    line = '.long ' + ', '.join('0x'+w.lower() for w in words) + '\n'
    lines.append(json.dumps(line) + ' // ' + instruction)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text('\n'.join(lines)+'\n')
args.output.with_suffix('.bin').write_bytes(body[:-4])
report = {'target': 'gfx1100', 'supplier_function_bytes': size,
          'embedded_bytes': size-4, 'removed': 'final s_setpc_b64 s[30:31]',
          'payload_sha256': hashlib.sha256(body[:-4]).hexdigest(),
          'payload_clobbers': ['s0-s3', 'v8-v15', 'vcc', 'scc', 'memory'],
          'exec_restored_by_supplier': True, 'relative_branches_preserved': True}
args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
print('Generated inline .long payload: 288 bytes; original body unchanged except final return')
