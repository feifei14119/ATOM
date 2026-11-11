"""Final-ELF checks for the in-place register-contract expansion."""
import json
from pathlib import Path
import re
import struct
import subprocess

CALL_OPS = ('s_swappc_b64', 's_swap_pc_i64', 's_setpc_b64', 's_set_pc_i64', 's_call_b64')


def text_section(elf: bytes):
    """(file offset, size) of .text in an ELF64 code object."""
    shoff, = struct.unpack_from('<Q', elf, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', elf, 0x3a)
    def section(i):
        return struct.unpack_from('<IIQQQQIIQQ', elf, shoff + i * shentsize)
    strtab = section(shstrndx)
    for i in range(shnum):
        s = section(i)
        name_at = strtab[4] + s[0]
        name = elf[name_at:elf.index(b'\0', name_at)]
        if name == b'.text':
            return s[4], s[5]
    raise RuntimeError('no .text in the code object')


def audit_contract(kernel_co: Path, symbol: str, resource: dict, sidecar: Path, report_file: Path, objdump: Path):
    info = json.loads(sidecar.read_text())
    fragment = (sidecar.parent / f"{info['name']}.fragment.bin").read_bytes()
    elf = kernel_co.read_bytes()
    text_off, text_size = text_section(elf)
    text = elf[text_off:text_off + text_size]

    hits = [m.start() for m in re.finditer(re.escape(fragment), text)]
    if len(hits) != 1:
        raise AssertionError(f'expected the {len(fragment)}-byte fragment once in .text, found {len(hits)}')
    if hits[0] % 64:
        raise AssertionError(f'fragment at .text+{hits[0]:#x} is not 64-byte aligned')

    dis = subprocess.run([str(objdump), '--mcpu=gfx1250', '-d', str(kernel_co)],
                         capture_output=True, text=True, check=True).stdout
    calls = [line.strip() for line in dis.splitlines() if any(f' {op} ' in f' {line.strip()} ' for op in CALL_OPS)]
    if calls:
        raise AssertionError(f'kernel contains call/return instructions: {calls[:4]}')
    for key in ('scratch', 'vgpr_spill', 'sgpr_spill'):
        if resource.get(key):
            raise AssertionError(f'{key} = {resource[key]}, expected 0')

    lines = [json.loads(l) for l in report_file.read_text().splitlines() if l.strip()]
    mine = [r for r in lines if r['function'] == symbol]
    if len(mine) != 1:
        raise AssertionError(f'expected one contract report for {symbol}, found {len(mine)}')
    rep = mine[0]
    if rep['status'] != 'ok' or len(rep['callsites']) != 1 or rep['callsites'][0]['contract'] != info['name']:
        raise AssertionError(f'unexpected contract report: {rep}')
    if rep['vgpr_spills'] or rep['sgpr_lane_spills'] or rep['stack_objects']:
        raise AssertionError(f'spills around the contract call: {rep}')
    return {
        'fragment_text_offset': hits[0],
        'fragment_bytes': len(fragment),
        'fragment_sha256': info['fragment_sha256'],
        'call_instructions': 0,
        'scratch': resource.get('scratch'),
        'vgpr_spill': resource.get('vgpr_spill'),
        'sgpr_spill': resource.get('sgpr_spill'),
        'llvm_report': rep,
    }
