"""Independent ELF / allocated-MIR checks for this single-basic-block test.

The live-register audit examines actual defs/uses, ignoring the mask as a kill
set, so an incorrectly retained high register cannot disappear from the check.
It is a GPR audit of this fixture, not a general CFG or arbitrary-lane analyzer.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

from callsite_regmask import CALLEE, PAYLOAD_SHA, Elf


def gprs(text):
    regs = set()
    for name in re.findall(r'\$([a-zA-Z][a-zA-Z0-9_]*)', text):
        if re.fullmatch(r'(?:[sv]gpr\d+)(?:_[sv]gpr\d+)*', name):
            regs.update(re.findall(r'[sv]gpr\d+', name))
        elif re.search(r'[sv]gpr\d+', name):
            raise AssertionError(f'Unreviewed partial GPR operand: {name}')
    return regs


def call_liveness(mir, kept_names):
    body = mir.split('body:', 1)[1]
    assert len(re.findall(r'^  bb\.', body, re.M)) == 1, 'Audit needs one basic block'
    assert not re.search(r'\b(?:S_CBRANCH\w*|S_BRANCH|PHI)\b', body)
    allowed = {name.lower() for name in kept_names if re.fullmatch(r'[SV]GPR\d+', name)}
    live, reports = set(), []
    lines = body.splitlines()
    for index in range(len(lines)-1, -1, -1):
        line = lines[index].strip()
        if not line or line in ('}', '...') or line.startswith(('bb.', 'liveins:', 'BUNDLE')):
            continue
        if 'CFI_INSTRUCTION' in line:
            continue
        line = line.split(' :: ')[0]
        # Register names inside the mask are not instruction uses or defs.
        mask = re.search(r'CustomRegMask\(([^)]*)\)', line)
        if mask:
            assert 'SI_CALL' in line and '@'+CALLEE in line
            actual = {name.lstrip('$').upper() for name in mask[1].split(',')}
            assert actual == set(kept_names)
            line = line[:mask.start()]+line[mask.end():]
        lhs, rhs = line.split(' = ', 1) if ' = ' in line else ('', line)
        defs, uses = gprs(lhs), set()
        for operand in rhs.split(','):
            if 'implicit-def' in operand:
                defs |= gprs(operand)
            elif 'undef' not in operand:
                uses |= gprs(operand)
        if 'SI_CALL' in line:
            # Return-value defs are new values; everything else needed after
            # this call must come from its preserved register set (or memory).
            crossing = live-defs
            assert crossing <= allowed, f'Unprotected live GPRs: {sorted(crossing-allowed)}'
            reports.append({'mir_body_line': index+1,
                            'cross_call_vgprs': sorted(int(r[4:]) for r in crossing if r.startswith('vgpr')),
                            'cross_call_sgprs': sorted(int(r[4:]) for r in crossing if r.startswith('sgpr')),
                            'new_return_defs': sorted(defs)})
        live = (live-defs) | uses
    assert len(reports) == 2
    return list(reversed(reports))


def main():
    build = Path(sys.argv[1])
    report = json.loads((build/'callsite_regmask.json').read_text())
    assert report['calls_changed'] == 2 and report['function_register_limits'] is None
    native, kept, removed = [set(report[key]) for key in
                             ('native_mask_names', 'kept_mask_names', 'removed_mask_names')]
    assert native == kept | removed and not kept & removed
    # Verify every full/half/tuple bit, not just v40/v56 and individual SGPRs.
    for name in native:
        high = any(int(r) >= 64 for r in re.findall(r'VGPR(\d+)', name)) or \
               any(int(r) >= 40 for r in re.findall(r'SGPR(\d+)', name))
        assert (name in kept) == (not high), name
    assert {r for r in kept if re.fullmatch(r'VGPR\d+', r)} == \
        {f'VGPR{r}' for r in list(range(40, 48))+list(range(56, 64))}
    assert {r for r in kept if re.fullmatch(r'SGPR\d+', r)} == {f'SGPR{r}' for r in range(30, 40)}
    assert {'SGPR30', 'SGPR31', 'SGPR32', 'SGPR33', 'SGPR34'} <= kept

    # The only instruction modifications in pre-RA MIR are two mask operands.
    before = (build/'caller.roundtrip.mir').read_text()
    after = (build/'caller.lowctx.mir').read_text()
    normalized, count = re.subn(r'CustomRegMask\([^)]*\)', 'csr_amdgpu', after)
    assert count == 2 and normalized == before
    assert report['baseline_roundtrip_instructions_identical']
    assert 'amdgpu-num-vgpr' not in after and 'amdgpu-num-sgpr' not in after
    assert not re.search(r'%\d+:', (build/'caller.allocated.mir').read_text().split('body:', 1)[1])
    live = call_liveness((build/'caller.allocated.mir').read_text(), kept)

    stage, linked = Elf(build/'stage_probe.co'), Elf(build/'caller.co')
    assert stage.kind == 1 and linked.kind == 3 and stage.machine == linked.machine == 224
    for elf in (stage, linked):
        assert not any(s[1] in (4, 9) and s[5] for s in elf.sections)
        assert not any(index == 0 for index, _, _, _ in elf.symbols.values())
    code = stage.blob(CALLEE)
    assert linked.blob(CALLEE) == code
    assert stage.absolute(CALLEE+'.private_seg_size') == 0
    assert len(code) == 2340 and hashlib.sha256(code[:-4]).hexdigest() == PAYLOAD_SHA
    assert 'stage_probe' not in linked.symbols, 'Keep the custom-ABI symbol distinct'
    disasm = (build/'caller.disasm.txt').read_text()
    stage_asm = (build/'stage_probe.disasm.txt').read_text()
    assert len(re.findall(r'\bs_swappc_b64\b', disasm)) == 2
    assert len(re.findall(r'\bs_setpc_b64\b', stage_asm)) == 1
    assert not re.search(r'\bscratch_\w+|\bs_endpgm\b', stage_asm)
    assert {int(r) for r in re.findall(r'v_mov_b32_e32 v(\d+), 0xdeadbeef', stage_asm)} == set(range(64, 256))
    assert {int(r) for r in re.findall(r's_mov_b32 s(\d+), 0xbaadf00d', stage_asm)} == set(range(40, 106))
    # The supplier has no other writes to preserved low registers. All vector
    # destinations are v0,v9-v17 or v64-v255; the only other scalar write is s0.
    writes = re.findall(r'^\s*(?:v_\w+|global_load_b32) ([sv]\d+),', stage_asm, re.M)
    assert all(not (r.startswith('v') and int(r[1:]) in list(range(40, 48))+list(range(56, 64))) for r in writes)
    assert not re.search(r'^\s*s_\w+ s(?:3[0-9])(?:,|\])', stage_asm, re.M)

    meta = (build/'caller.elf.txt').read_text()
    assert re.findall(r'^\s+\.name:\s+(\S+)', meta, re.M) == ['caller_kernel']
    assert re.search(r'\.max_flat_workgroup_size:\s*256\b', meta)
    resources = {key: int(re.search(r'\.'+key+r':\s*(\d+)', meta)[1]) for key in
                 ('vgpr_count', 'sgpr_count', 'private_segment_fixed_size',
                  'group_segment_fixed_size', 'vgpr_spill_count', 'sgpr_spill_count')}
    assert resources['vgpr_count'] == 256 and resources['sgpr_count'] >= 108
    caller_s = (build/'caller.function.s').read_text()
    assert 'v72' in caller_s and 'v255' in caller_s, 'High registers are usable outside calls'
    assert '.long' not in caller_s, 'The supplier must be separately linked, not embedded'
    result = {'mode': 'custom low-context device ABI', 'target': 'gfx1100',
              'preserved_vgprs': report['preserved_vgprs'], 'preserved_sgprs': report['preserved_sgprs'],
              'allocated_call_liveness': live, 'callee_bytes': len(code),
              'same_payload_sha256_as_test00': PAYLOAD_SHA, 'callee_save_restore_bytes': 0,
              'callee_private_bytes': 0, 'callee_scratch_instructions': 0,
              'caller_scratch_instructions': len(re.findall(r'\bscratch_\w+', caller_s)),
              'resources': resources, 'function_register_limits': None,
              'audit_scope': 'single basic block, GPR defs/uses; fixture uses explicit whole-wave spill/reload'}
    (build/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: custom call masks, final GPR liveness below boundaries, unchanged payload, ordinary PC calls')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
