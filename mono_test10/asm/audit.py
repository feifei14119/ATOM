"""Static boundary/ELF audit used before launching the compiled Mono kernel."""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from .prepare import ROOT, SYMBOL, SOURCE_SHA, SGPRS, VGPRS, Elf, original_records, rename_sgprs, PATCHES


def instructions(text):
    out = []
    for line in text.splitlines():
        line = line.split('//', 1)[0].strip()
        if line and not line.startswith('.') and not line.endswith(':'):
            out.append(line)
    return out


def registers(operand):
    match = re.fullmatch(r'([sv])\[(\d+):(\d+)\]', operand)
    if match:
        return {match[1]+str(i) for i in range(int(match[2]), int(match[3])+1)}
    return {operand} if re.fullmatch(r'[sv]\d+', operand) else set()


def audit_source():
    original = (ROOT/'dq_convert.original.s').read_bytes()
    assert hashlib.sha256(original).hexdigest() == SOURCE_SHA
    text = (ROOT/'dq_convert.inline.s').read_text()
    prefix, rest = text.split('.Linline_payload:\n')
    payload, suffix = rest.split('.Linline_payload_end:\n')
    expected = []
    for offset, inst, _ in original_records()[:-1]:
        expected.extend(PATCHES[offset][1] if offset in PATCHES else [rename_sgprs(inst)])
    assert instructions(payload) == expected, 'Changed payload: clobbers must be re-audited'
    writes = set()
    for inst in instructions(text):
        op, *operands = inst.split(None, 1)
        if op.startswith(('buffer_store', 's_wait', 's_version', 's_cmp', 's_cbranch', 's_setreg', 's_nop')):
            continue
        if operands:
            writes |= registers(operands[0].split(',')[0].strip())
    declared = {f's{i}' for i in SGPRS} | {f'v{i}' for i in VGPRS}
    assert writes == declared, (writes - declared, declared - writes)
    assert not writes & {'s0', 's1', 's24', 'v0', *[f's{i}' for i in range(30, 40)]}
    executable = '\n'.join(instructions(text))
    assert not re.search(r'\b(?:ttmp\d+|vcc(?:_lo|_hi)?|m0|scratch_\w+|ds_\w+|s_barrier\w*)\b', executable)
    assert not re.search(r'\bs_(?:endpgm|getpc|setpc|swappc|swap_pc)\w*\b', executable)
    exec_writes = [i for i in instructions(payload) if 'exec_lo' in i]
    assert len(exec_writes) == 32
    assert all(exec_writes[i] in ('s_mov_b32 exec_lo, s40', 's_mov_b32 exec_lo, s41')
               and exec_writes[i+1] == 's_mov_b32 exec_lo, -1' for i in range(0, 32, 2))
    assert 's_getreg_b32 s5, hwreg(HW_REG_MODE, 0, 8)' in prefix
    assert 's_setreg_b32 hwreg(HW_REG_MODE, 0, 8), s5' in suffix
    assert prefix.index('s_cbranch_scc1') < prefix.index('s_getreg_b32')
    return {'source_sha256': SOURCE_SHA, 'assembly_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'written_gprs': sorted(writes)}


def load_fragment(build: Path):
    """Decode the .inc, requiring identity with the just-built sized ELF symbol."""
    contract = json.loads((build/'inline_contract.json').read_text())
    audit = audit_source()
    assert contract['assembly_sha256'] == audit['assembly_sha256']
    obj = Elf(build/'dq_convert.inline.co')
    assert (obj.kind, obj.machine) == (1, 224)
    assert not any(s[1] in (4, 9) and s[5] for s in obj.sections), 'Unresolved relocations'
    body = obj.body(SYMBOL)
    assert hashlib.sha256(body).hexdigest() == contract['fragment_sha256']
    assert (build/'dq_convert.inline.bin').read_bytes() == body
    parts = []
    for line in (build/'dq_convert.inline.words.inc').read_text().splitlines():
        if line.startswith('"'):
            value, _ = json.JSONDecoder().raw_decode(line)
            assert re.fullmatch(r'\.long 0x[0-9a-f]{8}(?:, 0x[0-9a-f]{8})*\n', value)
            parts.append(value)
    text = ''.join(parts)
    encoded = b''.join(struct.pack('<I', int(w, 16)) for w in re.findall(r'0x([0-9a-f]{8})', text))
    assert encoded == body
    expected_clobbers = [*[f's{i}' for i in SGPRS], *[f'v{i}' for i in VGPRS], 'scc', 'memory']
    assert contract['clobbers'] == expected_clobbers
    expected_constraints = ','.join(['{s[0:1]}', '{v0}', '{s24}'] + ['~{'+r+'}' for r in expected_clobbers])
    assert contract['constraints'] == expected_constraints
    return 's_branch 1f\n.p2align 6\n1:\n'+text, expected_constraints, body, contract


def audit_embedded(kernel: Path, symbol: str, resources: dict, fragment_dir: Path):
    _, constraints, fragment, contract = load_fragment(fragment_dir)
    obj = Elf(kernel)
    code = obj.body(symbol)
    offsets = [i for i in range(len(code)-len(fragment)+1) if code.startswith(fragment, i)]
    assert len(offsets) == 1, f'Expected exactly one inline fragment in {symbol}, found {offsets}'
    _, address, _, _ = obj.symbols[symbol]
    assert (address + offsets[0]) % 64 == 0, 'Fragment lost 64-byte alignment'
    assert resources['vgpr'] >= contract['minimum_vgprs']
    assert resources['sgpr'] >= contract['minimum_numbered_sgprs']
    return {'fragment_bytes': len(fragment), 'fragment_sha256': contract['fragment_sha256'],
            'offset_in_kernel': offsets[0], 'constraints': constraints,
            'embedded_occurrences': len(offsets), 'source_sha256': SOURCE_SHA}
