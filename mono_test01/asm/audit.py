"""Audit the source ABI, standalone object, and final linked supplier symbol."""
import hashlib
import re
import struct
from .prepare import ROOT, SYMBOL, SOURCE_SHA, Elf, run, render, symbol_rows

# gfx1250 disassembly may use either spelling.
RETURN = ('s_setpc_b64 s[30:31]', 's_set_pc_i64 s[30:31]')
CALL = r'\bs_(?:swappc_b64|swap_pc_i64)\b'


def instructions(text):
    return [s for line in text.splitlines()
            if (s := line.split('//', 1)[0].strip()) and not s.startswith('.') and not s.endswith(':')]


def gprs(operand):
    m = re.fullmatch(r'([sv])\[(\d+):(\d+)\]', operand)
    if m:
        return {m[1]+str(i) for i in range(int(m[2]), int(m[3])+1)}
    return {operand} if re.fullmatch(r'[sv]\d+', operand) else set()


def audit_source():
    text = (ROOT/'dq_convert.lowctx.s').read_text()
    assert text == render(), 'Changed supplier adaptation requires a new audit'
    insts = instructions(text)
    writes = set()
    for inst in insts:
        op, *args = inst.split(None, 1)
        if op.startswith(('buffer_store', 's_wait', 's_version', 's_cmp', 's_cbranch', 's_setreg', 's_setpc', 's_nop')):
            continue
        if args:
            writes |= gprs(args[0].split(',')[0].strip())
    expected = {f's{i}' for i in [*range(30), *range(40, 49)]} | {
        f'v{i}' for i in [0, *range(4, 40), *range(64, 70)]}
    assert writes == expected, (writes - expected, expected - writes)
    preserved = {f'v{i}' for i in [*range(40, 48), *range(56, 64)]} | {f's{i}' for i in range(30, 40)}
    assert not writes & preserved
    code = '\n'.join(insts)
    assert not re.search(r'\b(?:ttmp\d+|vcc(?:_lo|_hi)?|m0|scratch_\w+|ds_\w+|s_barrier\w*)\b', code)
    assert not re.search(r'\bs_(?:endpgm|getpc|swappc|swap_pc)\w*\b', code)
    assert insts[-1] == 's_setpc_b64 s[30:31]'
    execs = [i for i in insts if 'exec_lo' in i]
    assert len(execs) == 32
    assert all(execs[i] in ('s_mov_b32 exec_lo, s40', 's_mov_b32 exec_lo, s41')
               and execs[i+1] == 's_mov_b32 exec_lo, -1' for i in range(0, 32, 2))
    assert 's_getreg_b32 s5, hwreg(HW_REG_MODE, 0, 8)' in insts
    assert 's_setreg_b32 hwreg(HW_REG_MODE, 0, 8), s5' in insts
    return {'original_sha256': SOURCE_SHA, 'assembly_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'written_gprs': sorted(writes), 'preserved_gprs_untouched': sorted(preserved),
            'mode_low8_restored': True, 'entry_exit_exec': 'full wave32',
            'gpu_validation': 'NOT RUN by source audit'}


def audit_object(path, llvm):
    result = audit_source()
    obj = Elf(path)
    assert (obj.kind, obj.machine) == (1, 224)
    assert not any(s[1] in (4, 9) and s[5] for s in obj.sections), 'Supplier has relocations'
    assert not any(n.endswith('.kd') for n in obj.symbols)
    resource = {key: obj.absolute(SYMBOL+'.'+key) for key in
                ('num_vgpr', 'numbered_sgpr', 'num_agpr', 'private_seg_size', 'num_named_barrier')}
    assert resource == dict(num_vgpr=70, numbered_sgpr=49, num_agpr=0, private_seg_size=0, num_named_barrier=0)
    dis = run([llvm/'llvm-objdump', '--mcpu=gfx1250', '--disassemble-symbols='+SYMBOL, path])
    path.with_suffix('.disasm.txt').write_text(dis)
    rows = symbol_rows(dis, obj, SYMBOL)
    assert rows and rows[-1][0] in RETURN
    decoded = b''.join(struct.pack('<I', int(word, 16)) for _, _, words in rows for word in words)
    assert decoded == obj.blob(SYMBOL), 'Disassembly does not cover the complete function'
    assert not any(re.search(r'\b(?:scratch_|s_endpgm|s_swappc|s_swap_pc)', i) for i, _, _ in rows)
    result.update(symbol=SYMBOL, resources=resource, function_bytes=len(obj.blob(SYMBOL)),
                  function_sha256=hashlib.sha256(obj.blob(SYMBOL)).hexdigest())
    return result


def audit_linked(path, stage, symbol, resource, llvm):
    obj, supplier = Elf(path), Elf(stage)
    assert obj.kind == 3 and obj.machine == 224
    assert obj.blob(SYMBOL) == supplier.blob(SYMBOL), 'Link changed supplier machine instructions'
    assert resource['vgpr'] >= 70 and resource['sgpr'] >= 49
    assert not [n for n, info in obj.symbols.items() if info[0] == 0], 'Undefined ELF symbols'
    dis = run([llvm/'llvm-objdump', '--mcpu=gfx1250', '--disassemble-symbols='+symbol, path])
    assert len(re.findall(CALL, dis)) == 1, 'Expected one real device call'
    return {'linked_supplier_bytes_identical': True, 'real_device_calls': 1,
            'supplier_sha256': hashlib.sha256(supplier.blob(SYMBOL)).hexdigest(),
            'vgpr_floor': 70, 'numbered_sgpr_floor': 49}
