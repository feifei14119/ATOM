"""Adapt dq_convert to the v<64/s<40 device ABI; --source-only never compiles."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from regmask_tables import Elf, run

SYMBOL = 'mono_dq_convert_lowctx'
SOURCE_SHA = '4050f8e1eacf2463c98adeb8f2aeee2ca93e2792de3a43e58088cbd36a05a711'
PATCHES = {
    0x04: ('s_and_b32 s1, s1, 0xffff', ['s_nop 0', 's_nop 0']),
    0x60: ('v_and_b32_e32 v0, 31, v0', ['s_nop 0']),
    0x64: ('s_mov_b32 s2, ttmp9', ['s_mov_b32 s2, 0']),
    0x68: ('s_and_b32 s3, ttmp7, 0xffff', ['s_mov_b32 s3, 0', 's_nop 0']),
    0x70: ('s_bfe_u32 s4, ttmp7, 0x100010', ['s_mov_b32 s4, 0', 's_nop 0']),
    0x78: ('s_bfe_u32 s24, ttmp8, 0x50019', ['s_nop 0', 's_nop 0']),
}

def original_records():
    source = (ROOT / 'dq_convert.original.s').read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA, 'Changed supplier: re-audit first'
    records = []
    for line in source.decode().splitlines():
        m = re.fullmatch(r'(.*?) // original \+0x([0-9a-f]+): ([0-9A-F ]+)', line)
        if m:
            records.append((int(m[2], 16), m[1], m[3].split()))
    assert len(records) == 292 and records[-1] == (0x5f4, 's_endpgm', ['BFB00000'])
    return records


def disassembly_rows(text):
    rows = []
    for line in text.splitlines():
        m = re.match(r'\s*(.*?)\s*//\s*([0-9A-Fa-f]+):\s*((?:[0-9A-Fa-f]{8}(?:\s+|$))+)', line)
        if m:
            rows.append((m[1].strip(), int(m[2], 16), m[3].split()))
    return rows


def rename_registers(inst):
    # Avoid all retained GPRs, including the low callee-saved VGPR stripe.
    def reg(kind, n):
        n = int(n)
        if kind == 's' and 30 <= n <= 38:
            n += 10
        if kind == 'v' and 40 <= n <= 45:
            n += 24
        return str(n)
    inst = re.sub(r'\b([sv])\[(\d+):(\d+)\]',
                  lambda m: m[1]+'['+reg(m[1], m[2])+':'+reg(m[1], m[3])+']', inst)
    return re.sub(r'\b([sv])(\d+)\b', lambda m: m[1]+reg(m[1], m[2]), inst)


def render():
    prefix = f'''// Generated from dq_convert.original.s by prepare.py.
// CUSTOM device ABI: default argument ABI, call-preserved mask restricted
// to v<64 / s<40. MUST use callsite_regmask.py before register allocation.
// v0:v1 = uniform 240-byte args record address; v2 = linear thread ID.
// s30:s31 = return address. Full EXEC, wave32, VGPR bank 0.
// s30:s38 -> s40:s48; v40:v45 -> v64:v69. Retained GPRs never written.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text
.globl {SYMBOL}
.hidden {SYMBOL}
.p2align 6
.type {SYMBOL},@function
{SYMBOL}:
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_wait_dscnt 0
    s_wait_kmcnt 0
    s_wait_xcnt 0
    s_waitcnt_depctr 0
    // Materialize supplier inputs from ordinary device-function arguments.
    v_readfirstlane_b32 s0, v0
    v_readfirstlane_b32 s1, v1
    v_readfirstlane_b32 s24, v2
    s_waitcnt_depctr 0
    s_lshr_b32 s24, s24, 5
    v_and_b32_e32 v0, 31, v2
    s_waitcnt_depctr 0
    s_cmp_ge_u32 s24, 4
    s_cbranch_scc1 .Ldevice_return
    s_getreg_b32 s5, hwreg(HW_REG_MODE, 0, 8)
    s_setreg_imm32_b32 hwreg(HW_REG_MODE, 0, 8), 0xc0
    s_nop 7
.Lpayload_begin:
'''
    lines = []
    for offset, inst, words in original_records()[:-1]:
        if offset in PATCHES:
            old, new = PATCHES[offset]
            assert old == inst and len(words) == len(new)
            lines.append(f'    // Replaced original +0x{offset:04x}: {inst}')
            lines.extend('    '+s for s in new)
        else:
            lines.append(f'    {rename_registers(inst)} // original +0x{offset:04x}: {inst}')
    suffix = f'''
.Lpayload_end:
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_wait_dscnt 0
    s_wait_kmcnt 0
    s_wait_xcnt 0
    s_waitcnt_depctr 0
    s_setreg_b32 hwreg(HW_REG_MODE, 0, 8), s5
    s_nop 7
.Ldevice_return:
    s_setpc_b64 s[30:31]
.Ldevice_end:
.size {SYMBOL}, .Ldevice_end-{SYMBOL}
.set {SYMBOL}.payload_offset, .Lpayload_begin-{SYMBOL}
.set {SYMBOL}.payload_size, .Lpayload_end-.Lpayload_begin
.set {SYMBOL}.num_vgpr, 70
.set {SYMBOL}.numbered_sgpr, 49
.set {SYMBOL}.num_agpr, 0
.set {SYMBOL}.private_seg_size, 0
.set {SYMBOL}.num_named_barrier, 0
.set {SYMBOL}.uses_vcc, 0
.set {SYMBOL}.uses_flat_scratch, 0
.set {SYMBOL}.has_dyn_sized_stack, 0
.set {SYMBOL}.has_recursion, 0
.set {SYMBOL}.has_indirect_call, 0
.section .note.GNU-stack,"",@progbits
'''
    return prefix+'\n'.join(lines)+'\n'+suffix


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-only', action='store_true')
    ap.add_argument('--llvm-bin', type=Path, default=Path('/opt/rocm/llvm/bin'))
    ap.add_argument('--out-dir', type=Path, default=ROOT.parent/'build/asm')
    args = ap.parse_args()
    path, text = ROOT/'dq_convert.lowctx.s', render()
    if args.source_only:
        path.write_text(text)
        print('Generated dq_convert.lowctx.s; compilation NOT RUN')
        return
    assert path.read_text() == text, 'Adapted source differs from the audited generator'
    from asm.audit import audit_source, audit_object
    audit_source()
    out, llvm = args.out_dir, args.llvm_bin
    out.mkdir(parents=True, exist_ok=True)
    for kind in ('original', 'lowctx'):
        run([llvm/'clang++', '--target=amdgcn-amd-amdhsa', '-mcpu=gfx1250',
             '-x', 'assembler', '-c', ROOT/f'dq_convert.{kind}.s', '-o', out/f'dq_convert.{kind}.co'])
    original = Elf(out/'dq_convert.original.co').blob('_ZN5aiter29fmha_bwd_hd64_dq_convert_bf16E')
    expected = b''.join(struct.pack('<I', int(w, 16)) for _, _, words in original_records() for w in words)
    assert original == expected, 'Original assembly no longer reproduces supplier instructions'
    report = audit_object(out/'dq_convert.lowctx.co', llvm)
    (out/'resources.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Built independent low-context device .co; no .inc or .long extraction')


if __name__ == '__main__':
    main()


