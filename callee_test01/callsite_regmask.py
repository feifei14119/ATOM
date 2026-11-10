"""ROCm 7.2 / gfx1100 prototype: a low-register preservation ABI at two calls.

The modification happens after finalize-isel, BEFORE all register allocators.
For production ATOM, implement the same mask change inside the LLVM backend;
this standalone prototype uses MIR serialization and audits its round trip.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

COMMIT = '7b800a19466229b8479a78de19143dc33c3ab9b5'
CALLEE = 'stage_probe_lowctx'
PAYLOAD_SHA = '811cad1494f520906e7f414f2a8112bd8a1263f692685aa3b3c9413de02a3380'


class Elf:
    """Small ELF64 reader for the installed LLVM tables and AMDGPU objects."""
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b'\x7fELF\x02\x01'
        self.kind, self.machine = struct.unpack_from('<HH', self.data, 16)
        at = struct.unpack_from('<Q', self.data, 40)[0]
        width, count = struct.unpack_from('<HH', self.data, 58)
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.data, at+i*width)
                         for i in range(count)]
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
                    self.symbols[name] = index, value, size, info

    def blob(self, name):
        index, value, size, _ = self.symbols[name]
        assert 0 < index < len(self.sections) and size
        sec = self.sections[index]
        at = sec[4]+value-sec[3]
        return self.data[at:at+size]

    def absolute(self, name):
        index, value, _, _ = self.symbols[name]
        assert index == 0xfff1, f'Expected absolute symbol: {name}'
        return value


def run(argv):
    argv = [str(arg) for arg in argv]
    result = subprocess.run(argv, text=True, capture_output=True)
    if result.returncode or result.stderr:
        raise RuntimeError(f'Command failed or emitted diagnostics: {argv}\n'
                           f'{result.stdout}\n{result.stderr}')
    return result.stdout


def native_mask(llc):
    # Read THIS compiler's named table, including LO16/HI16 and tuple aliases.
    # Never copy numeric register IDs from another LLVM build. The symbol names
    # and 24-byte MCRegisterDesc layout are checked for the pinned compiler.
    elf = Elf(llc)
    mask = elf.blob('_ZN4llvmL18CSR_AMDGPU_RegMaskE')
    desc = elf.blob('_ZN4llvm13AMDGPURegDescE')
    strings = elf.blob('_ZN4llvm16AMDGPURegStringsE')
    assert len(desc) % 24 == 0
    count = len(desc)//24
    assert len(mask) == ((count+31)//32)*4
    names = []
    for reg in range(count):
        if mask[reg//8] & (1 << (reg % 8)):
            at = struct.unpack_from('<I', desc, reg*24)[0]
            name = strings[at:strings.index(b'\0', at)].decode()
            assert re.fullmatch(r'[A-Za-z0-9_]+', name)
            names.append(name)
    assert {'SGPR30', 'SGPR32', 'SGPR105', 'VGPR40', 'VGPR255'} <= set(names)
    assert 'VGPR0' not in names and 'SGPR0' not in names
    return names, hashlib.sha256(elf.data).hexdigest()


def low_mask(names):
    kept, removed = [], []
    for name in names:
        vgprs = {int(r) for r in re.findall(r'VGPR(\d+)', name)}
        sgprs = {int(r) for r in re.findall(r'SGPR(\d+)', name)}
        # A tuple is preserved only if ALL its component registers survive.
        drop = any(r >= 64 for r in vgprs) or any(r >= 40 for r in sgprs)
        (removed if drop else kept).append(name)
    assert {int(n[4:]) for n in kept if re.fullmatch(r'VGPR\d+', n)} == set(range(40, 48)) | set(range(56, 64))
    assert {int(n[4:]) for n in kept if re.fullmatch(r'SGPR\d+', n)} == set(range(30, 40))
    assert all(re.search(r'[SV]GPR\d+', name) for name in removed)
    return kept, removed


def function_body(assembly):
    start = assembly.index('caller_kernel:')
    end = assembly.index('.section\t.rodata', start)
    return assembly[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bitcode', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--llvm-bin', type=Path, default=Path('/opt/rocm/llvm/bin'))
    args = parser.parse_args()
    llvm, out = args.llvm_bin, args.output.parent
    out.mkdir(parents=True, exist_ok=True)
    assert COMMIT in run([llvm/'clang++', '--version']), 'Revalidate for another compiler'
    names, tool_sha = native_mask(llvm/'llc')
    kept, removed = low_mask(names)

    stage = Elf(args.stage)
    assert stage.kind == 1 and stage.machine == 224
    body = stage.blob(CALLEE)
    offset = stage.absolute(CALLEE+'.payload_offset')
    size = stage.absolute(CALLEE+'.payload_size')
    assert offset == 0 and len(body) == size+4
    assert hashlib.sha256(body[:size]).hexdigest() == PAYLOAD_SHA, 'Re-audit changed ASM'
    resources = {key: stage.absolute(CALLEE+'.'+key) for key in
                 ('num_vgpr', 'numbered_sgpr', 'num_agpr', 'private_seg_size', 'num_named_barrier')}
    assert resources == {'num_vgpr': 256, 'numbered_sgpr': 106, 'num_agpr': 0,
                         'private_seg_size': 0, 'num_named_barrier': 0}

    # Drop unused HIP assert/printf runtime helpers. The actual kernel and its
    # two external calls remain unchanged; no register attributes are inserted.
    clean_ir = out/'caller.codegen.ll'
    run([llvm/'opt', '-S', '-passes=internalize,globaldce',
         '-internalize-public-api-list=caller_kernel,'+CALLEE,
         args.bitcode, '-o', clean_ir])
    ir = clean_ir.read_text()
    assert 'amdgpu-num-vgpr' not in ir and 'amdgpu-num-sgpr' not in ir
    flags = [llvm/'llc', '-mtriple=amdgcn-amd-amdhsa', '-mcpu=gfx1100', '-O2',
             '-verify-machineinstrs', '-amdgpu-assume-external-call-stack-size=0']
    baseline_path = out/'caller.default_abi.s'
    raw_mir = out/'caller.before_regmask.mir'
    run(flags+[clean_ir, '-o', baseline_path])
    run(flags+['-stop-after=finalize-isel', clean_ir, '-o', raw_mir])
    baseline = baseline_path.read_text()
    mir = raw_mir.read_text()
    assert re.findall(r'^name:\s+(\S+)', mir, re.M) == ['caller_kernel']

    # Pinned ROCm MIR parser compatibility: its wave32 printer may emit VCC_LO
    # on an opcode whose parser also requires the full VCC operand. Add only an
    # undef operand, and require the unmodified-call round trip to be identical.
    mir, normalized = re.subn(
        r'^(\s*S_CBRANCH_VCC(?:NZ|Z) [^\n]*\$vcc_lo)\s*$',
        r'\1, implicit undef $vcc', mir, flags=re.M)
    roundtrip_mir = out/'caller.roundtrip.mir'
    roundtrip_mir.write_text(mir)
    roundtrip_s = out/'caller.roundtrip.raw.s'
    run(flags+['-start-after=finalize-isel', roundtrip_mir, '-o', roundtrip_s])
    assert function_body(roundtrip_s.read_text()) == function_body(baseline), \
        'Unmodified MIR round trip changed instructions'

    # MIR loses user-SGPR preload count in this compiler. Recover ONLY that
    # descriptor field from the unmodified pipeline, not its register counts.
    user_sgprs = int(re.search(r'\.amdhsa_user_sgpr_count (\d+)', baseline)[1])
    def finish_assembly(text):
        text, count = re.subn(r'(\.amdhsa_user_sgpr_count )\d+',
                             lambda m: m[1]+str(user_sgprs), text)
        assert count == 1
        text = re.sub(r'(; COMPUTE_PGM_RSRC2:USER_SGPR: )\d+',
                      lambda m: m[1]+str(user_sgprs), text)
        if not re.search(r'\.set\s+amdgpu.max_num_named_barrier,', text):
            text += '\n.set amdgpu.max_num_named_barrier, 0\n'
        return text
    (out/'caller.roundtrip.s').write_text(finish_assembly(roundtrip_s.read_text()))

    custom = 'CustomRegMask('+','.join('$'+name.lower() for name in kept)+')'
    mir, changed = re.subn(r'(^.*SI_CALL[^\n]*@'+CALLEE+r', )csr_amdgpu\b',
                          lambda m: m[1]+custom, mir, flags=re.M)
    assert changed == 2, 'Expected exactly two target calls BEFORE allocation'
    custom_mir = out/'caller.lowctx.mir'
    custom_mir.write_text(mir)
    raw_custom = out/'caller.lowctx.raw.s'
    run(flags+['-start-after=finalize-isel', custom_mir, '-o', raw_custom])
    args.output.write_text(finish_assembly(raw_custom.read_text()))
    # Keep final MIR for an independent live-register audit at the call sites.
    run(flags+['-start-after=finalize-isel', '-stop-after=amdgpu-resource-usage',
               custom_mir, '-o', out/'caller.allocated.mir'])
    (out/'caller.function.s').write_text(function_body(args.output.read_text()))
    report = {'caller': 'caller_kernel', 'callee': CALLEE, 'calls_changed': changed,
              'point': 'after finalize-isel, before every register allocator',
              'preserved_vgprs': list(range(40, 48))+list(range(56, 64)),
              'preserved_sgprs': list(range(30, 40)), 'special_mask_bits_unchanged': True,
              'function_register_limits': None, 'native_mask_names': names,
              'kept_mask_names': kept, 'removed_mask_names': removed,
              'llc_sha256': tool_sha, 'llvm_commit': COMMIT,
              'stage_payload_sha256': PAYLOAD_SHA, 'stage_resources': resources,
              'mir_vcc_operands_normalized': normalized,
              'baseline_roundtrip_instructions_identical': True,
              'restored_user_sgpr_count': user_sgprs,
              'scope': 'Pinned gfx1100 MIR prototype; not a production ATOM backend change'}
    (out/'callsite_regmask.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: two pre-RA call masks; preserved v40-v47/v56-v63 and s30-s39; no function-wide GPR cap')


if __name__ == '__main__':
    main()
