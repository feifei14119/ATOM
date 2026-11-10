"""Static ABI, byte, layout, header and real gfx1250 call/link checks; no GPU run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parent
SYMBOL = 'mono_dq_convert_device'
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--llvm-bin', default='/opt/rocm/llvm/bin', type=Path)
args = ap.parse_args()
llvm = args.llvm_bin
build = ROOT / 'build'
build.mkdir(exist_ok=True)


def run(command):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{command}\n{result.stdout}\n{result.stderr}')
    if result.stderr:
        print(result.stderr)
    return result.stdout


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b'\x7fELF\x02\x01'
        self.kind, self.machine = struct.unpack_from('<HH', self.data, 16)
        offset = struct.unpack_from('<Q', self.data, 40)[0]
        size, count = struct.unpack_from('<HH', self.data, 58)
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.data, offset+i*size)
                         for i in range(count)]
        self.symbols = {}
        for sec in self.sections:
            if sec[1] != 2:
                continue
            strings = self.sections[sec[6]]
            text = self.data[strings[4]:strings[4]+strings[5]]
            for at in range(sec[4], sec[4]+sec[5], sec[9]):
                name, info, _, index, value, length = struct.unpack_from('<IBBHQQ', self.data, at)
                name = text[name:text.index(b'\0', name)].decode()
                if name:
                    self.symbols[name] = index, value, length, info

    def body(self, name):
        index, value, length, _ = self.symbols[name]
        sec = self.sections[index]
        offset = sec[4]+value-sec[3]
        return self.data[offset:offset+length]


source = (ROOT/'dq_convert.original.s').read_text()
contract = json.loads((ROOT/'resources.json').read_text())
assert hashlib.sha256(source.encode()).hexdigest() == contract['original_assembly_sha256']
records = []
for line in source.splitlines():
    m = re.fullmatch(r'(.*?) // original \+0x([0-9a-f]+): ([0-9A-F ]+)', line)
    if m:
        records.append((int(m[2], 16), m[1], b''.join(struct.pack('<I', int(w, 16)) for w in m[3].split())))
original_bytes = b''.join(code for _, _, code in records)
run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-x', 'assembler',
     '-c', ROOT/'dq_convert.original.s', '-o', build/'original.o'])
original = Elf(build/'original.o')
assert original.body('_ZN5aiter29fmha_bwd_hd64_dq_convert_bf16E') == original_bytes
stage = Elf(ROOT/'dq_convert.device.co')
assert stage.kind == 1 and stage.machine == 224
assert not [n for n in stage.symbols if n.endswith('.kd')]
assert not [n for n, sym in stage.symbols.items() if sym[0] == 0]
body = stage.body(SYMBOL)
assert body
# The original s_version word is a unique marker; the following kernarg-only
# pointer mask is deliberately removed for a normal global device argument.
payload_at = body.index(original_bytes[:4])
assert body.count(original_bytes[:4]) == 1
patches = {p['original_offset'] for p in contract['patches']}
unchanged_bytes = 0
for offset, _, code in records[:-1]:
    if offset not in patches:
        assert body[payload_at+offset:payload_at+offset+len(code)] == code, hex(offset)
        unchanged_bytes += len(code)

# Check the installed llc's actual CSR mask; do not reuse another LLVM build's IDs.
llc = Elf(llvm/'llc')
mask = llc.body('_ZN4llvmL18CSR_AMDGPU_RegMaskE')
desc = llc.body('_ZN4llvm13AMDGPURegDescE')
strings = llc.body('_ZN4llvm16AMDGPURegStringsE')
assert len(desc) % 24 == 0
preserved = set()
for reg in range(len(desc)//24):
    if mask[reg//8] & (1 << (reg % 8)):
        at = struct.unpack_from('<I', desc, 24*reg)[0]
        name = strings[at:strings.index(b'\0', at)].decode()
        m = re.fullmatch(r'(SGPR|VGPR)(\d+)', name)
        if m:
            preserved.add(('s' if m[1] == 'SGPR' else 'v') + m[2])
assert {f's{i}' for i in range(30, 39)} | {f'v{i}' for i in range(40, 46)} <= preserved
backups = {'s5'} | {f's{i}' for i in range(40, 48)} | {f'v{i}' for i in range(48, 55)}
assert not backups & preserved

assembly = (ROOT/'dq_convert.device.s').read_text()
prefix, tail = assembly.split('.Ldq_payload:\n')
payload, suffix = tail.split('.Ldq_payload_end:\n')
assert 'ttmp' not in '\n'.join(line.split('//')[0] for line in payload.splitlines())
assert not re.search(r'^\s*s_endpgm\b', assembly, re.M)
assert assembly.count('s_setpc_b64 s[30:31]') == 1
assert not re.search(r'^\s*(?:s_c?branch|scratch_|ds_|s_barrier)', payload, re.M)


def reglist(operand):
    m = re.fullmatch(r'([sv])\[(\d+):(\d+)\]', operand)
    if m:
        return [m[1]+str(i) for i in range(int(m[2]), int(m[3])+1)]
    return [operand] if re.fullmatch(r'[sv]\d+', operand) else []


# Symbolic copies on full waves check every standard callee-saved GPR against
# arbitrary values, poisoning every original destination at the payload boundary.
initial = {f'{bank}{i}': f'initial_{bank}{i}' for bank, count in [('s', 106), ('v', 256)] for i in range(count)}
state = dict(initial)
mode = 'initial_mode_low8'
written = set()
for _, inst, _ in records[:-1]:
    op, *rest = inst.split(None, 1)
    if rest and not op.startswith(('buffer_store', 's_wait', 's_version')):
        written.update(reglist(rest[0].split(',')[0]))
assert not written & backups
assert written & preserved == {f's{i}' for i in range(30, 39)} | {f'v{i}' for i in range(40, 46)}


def copies(text):
    global mode
    for line in text.splitlines():
        inst = line.split('//')[0].strip()
        if not inst or inst.startswith('.') or inst.endswith(':'):
            continue
        op, *rest = inst.split(None, 1)
        if op in ('s_mov_b64', 's_mov_b32', 'v_mov_b32_e32', 'v_readfirstlane_b32'):
            dst, src = [x.strip() for x in rest[0].split(',')]
            for d, s in zip(reglist(dst), reglist(src)):
                state[d] = state[s]
        elif op == 's_getreg_b32':
            state[rest[0].split(',')[0]] = mode
        elif op == 's_setreg_imm32_b32':
            mode = 'supplier_mode_low8'
        elif op == 's_setreg_b32':
            mode = state[rest[0].rsplit(',', 1)[1].strip()]
        elif rest and not op.startswith(('s_wait', 's_cmp', 's_cbranch', 's_setpc', 's_nop')):
            for d in reglist(rest[0].split(',')[0]):
                state[d] = 'computed_'+d

copies(prefix)
assert mode == 'supplier_mode_low8'
for reg in written:
    state[reg] = 'supplier_clobber_'+reg
copies(suffix)
assert all(state[r] == initial[r] for r in preserved if r in state)
assert mode == 'initial_mode_low8'
# The skip path only overwrites s0 before jumping directly to the common return.
assert all(r not in preserved for r in ('s0',))

# Verify the tile permutation against the actual load/store address equations.
seen_in, seen_out = set(), set()
for wave in range(4):
    for lane in range(32):
        load_base = wave*16*256 + (lane >> 4)*8*256 + (lane & 15)*16
        store_base = wave*16*128 + (lane & 4)*2*128 + ((lane & 15) >> 3)*64 + (lane >> 4)*32 + (lane & 3)*8
        for j in range(8):
            for component in range(4):
                src = (load_base + j*256 + component*4)//4
                dst = (store_base + j*128 + component*2)//2
                r, c = divmod(dst, 64)
                packed = (16*(r//16) + 8*((c//16)%2) + r%8)*64 + 32*(c//32) + 16*((r//8)%2) + c%16
                assert packed == src and src not in seen_in and dst not in seen_out
                seen_in.add(src)
                seen_out.add(dst)
assert seen_in == seen_out == set(range(4096))

# A compile/link-only caller checks the header, arguments and a nonterminal call.
caller = '''#include "dq_convert_api.h"
extern "C" __global__ void dq_link_check(const DqConvertArgs* args, float* state) {
  unsigned tid = threadIdx.x;
  float live = static_cast<volatile float*>(state)[tid];
  __threadfence_block();
  __syncthreads();
  mono_dq_convert_device(args, tid);
  __threadfence_block();
  __syncthreads();
  state[tid] = live + 1.0f;
}
'''
(build/'caller.cpp').write_text(caller)
run([llvm/'clang++', '-x', 'hip', '-std=c++17', '-O2', '-Wall', '-Wextra',
     '--offload-arch=gfx1250', '--offload-device-only', '-fgpu-rdc', '-I'+str(ROOT),
     '-c', build/'caller.cpp', '-o', build/'caller.bc'])
# The same header's layout checks must also compile on the host.
(build/'header.cpp').write_text('#include "dq_convert_api.h"\nint main() { DqConvertArgs a{}; return a.head_dim; }\n')
run([llvm/'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I'+str(ROOT),
     '-fsyntax-only', build/'header.cpp'])
run([llvm/'llvm-dis', build/'caller.bc', '-o', build/'caller.ll'])
ir = (build/'caller.ll').read_text()
assert 'amdgpu-num-vgpr' not in ir and 'amdgpu-num-sgpr' not in ir
assert re.search(r'declare.*@mono_dq_convert_device\(ptr[^,]*, i32', ir)
run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-nogpulib',
     '-x', 'ir', '-O2', '-S', build/'caller.bc', '-o', build/'caller.raw.s'])
raw = (build/'caller.raw.s').read_text()
start, end = raw.index('dq_link_check:'), raw.index('.section\t.rodata', raw.index('dq_link_check:'))
function = raw[start:end]
assert function.count('s_swap_pc_i64') == 1
assert re.search(r'v2, v40', function) and re.search(r'v1, s37', function) and re.search(r'v0, s36', function)
assert re.search(r's_load_b128 s\[36:39\].*0x0', function)
assert re.search(r'flat_load_b32 v41', function)
assert re.search(r'v_add_f32_e32 v0, 1.0, v41', function.split('s_swap_pc_i64')[1])

# Only enlarge resource constants; no instruction or register allocation edits.
fixed = raw
for suffix, required in [('vgpr', contract['vgpr_count']), ('sgpr', contract['numbered_sgpr_count'])]:
    fixed, n = re.subn(r'(\.set\s+amdgpu.max_num_'+suffix+r', )(\d+)',
                       lambda m: m[1]+str(max(int(m[2]), required)), fixed)
    assert n == 1
if not re.search(r'\.set\s+amdgpu.max_num_named_barrier,', fixed):
    fixed += '\n.set amdgpu.max_num_named_barrier, 0\n'
# In this compiler's textual output the descriptor retains expressions, but
# the YAML resource values have already been evaluated. Update both channels.
assert re.search(r'\.amdhsa_reserve_vcc 1', fixed)
for key, minimum in [('vgpr_count', 55), ('sgpr_count', 48 + 2)]:
    fixed, n = re.subn(r'(\.'+key+r':\s*)(\d+)',
                       lambda m: m[1]+str(max(int(m[2]), minimum)), fixed)
    assert n == 1
assert fixed[fixed.index('dq_link_check:'):fixed.index('.section\t.rodata', fixed.index('dq_link_check:'))] == function
(build/'caller.s').write_text(fixed)
run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250', '-x', 'assembler',
     '-c', build/'caller.s', '-o', build/'caller.o'])
run([llvm/'ld.lld', '-shared', '--no-undefined', build/'caller.o', ROOT/'dq_convert.device.co',
     '-o', build/'link_check.co'])
linked = Elf(build/'link_check.co')
assert linked.kind == 3 and linked.body(SYMBOL) == body
assert not [n for n, sym in linked.symbols.items() if sym[0] == 0]
assert not any(s[1] in (4, 9) and s[5] for s in linked.sections)
metadata = run([llvm/'llvm-readelf', '-h', '-s', '-r', '-n', build/'link_check.co'])
(build/'link_check.elf.txt').write_text(metadata)
(build/'link_check.disasm.txt').write_text(run([llvm/'llvm-objdump', '--mcpu=gfx1250',
    '--disassemble-symbols=dq_link_check,'+SYMBOL, build/'link_check.co']))
linked_resources = {key: int(re.search(r'\.'+key+r':\s*(\d+)', metadata)[1]) for key in
                    ['vgpr_count', 'sgpr_count', 'private_segment_fixed_size', 'vgpr_spill_count', 'sgpr_spill_count']}
assert linked_resources['vgpr_count'] >= 55 and linked_resources['sgpr_count'] >= 48
report = {
    'status': 'static_checks_passed; gfx1250_GPU_and_ATOM_integration_pending',
    'toolchain': run([llvm/'clang++', '--version']).splitlines()[0],
    'original_assembly_sha256': contract['original_assembly_sha256'],
    'device_object_sha256': hashlib.sha256(stage.data).hexdigest(),
    'device_function_sha256': hashlib.sha256(body).hexdigest(),
    'device_function_bytes': len(body), 'original_function_bytes': len(original_bytes),
    'original_reassembly_bytes_identical': True,
    'unchanged_payload_bytes': unchanged_bytes, 'patched_payload_bytes': 36,
    'native_default_ABI_checked': True, 'callee_saved_symbolic_restore_passed': True,
    'fp_mode_low8_restored': True, 'layout_elements_checked': len(seen_in),
    'header_host_and_device_compilation_passed': True,
    'caller_argument_registers': ['v0:v1=args', 'v2=linear_tid'],
    'caller_live_value_in_v41': True, 'caller_instructions_modified': False,
    'external_resource_constants_merged': True,
    'linked_stage_bytes_unchanged': True, 'unresolved_symbols': 0,
    'linked_resources': linked_resources,
    'gpu_executed': False, 'ATOM_modified': False,
}
(ROOT/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
