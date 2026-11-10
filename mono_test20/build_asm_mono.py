#!/usr/bin/env python3
"""Compile three FlyDSL device stages and the hand-written Mono entry; no GPU execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys

ROOT = Path(__file__).resolve().parent
BUILD = ROOT/'build'
SYMBOL = 'mono_asm_projection'
KINDS = ('slice', 'norm', 'wqkv')


def configure():
    for key, value in {
        'ARCH': 'gfx1250', 'FLYDSL_GPU_ARCH': 'gfx1250',
        'COMPILE_ONLY': '1', 'FLYDSL_RUNTIME_ENABLE_CACHE': '0',
        'FLYDSL_COMPILE_LLVM_DIR': '',
        'FLYDSL_RUNTIME_CACHE_DIR': str(BUILD/'cache/flydsl'),
    }.items():
        os.environ[key] = value
    sys.dont_write_bytecode = True


def run(argv):
    p = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f'{argv}\n{p.stdout}\n{p.stderr}')
    return p.stdout


def resources(text, symbol):
    # Current leaf stages emit literal resource values. Refuse unresolved
    # expressions/nested calls instead of guessing the required stack size.
    out = {}
    for key in ('num_vgpr','num_agpr','numbered_sgpr','private_seg_size',
                'num_named_barrier','uses_vcc','uses_flat_scratch',
                'has_dyn_sized_stack','has_recursion','has_indirect_call'):
        values = re.findall(r'^\s*\.set\s+(?:\.L)?'+re.escape(symbol)+r'\.'+key+r',\s*(\d+)\s*$',text,re.M)
        if len(values) != 1:
            raise RuntimeError(f'{symbol}: non-literal or absent resource {key}; adapt the resource audit')
        out[key] = int(values[0])
    assert not any(out[k] for k in ('num_agpr','num_named_barrier','has_dyn_sized_stack','has_recursion','has_indirect_call'))
    assert not re.search(r'\bs_(?:swappc_b64|swap_pc_i64)\b',text), 'Only leaf stages supported'
    assert not re.search(r'\bttmp\d+\b',text), 'Stage still depends on dispatch state'
    assert not re.search(r'\bs_(?:getpc_b64|get_pc_i64)\b',text), 'PC-relative data references need a relocatable export'
    assert not re.search(r'\bs_endpgm\b',text), 'Exported stage must return, not terminate a wave'
    returns = re.findall(r'\bs_(?:setpc_b64|set_pc_i64)\s+([^\n;]+)',text)
    assert returns and all(x.strip() == 's[30:31]' for x in returns), returns
    return out


def write_metadata(out, stage_resources):
    vgpr = max(41, *(r['num_vgpr'] for r in stage_resources.values()))
    sgpr = max(40, *(r['numbered_sgpr'] for r in stage_resources.values()))
    private = max(r['private_seg_size'] for r in stage_resources.values())
    vcc = max(r['uses_vcc'] for r in stage_resources.values())
    constants = dict(MONO_VGPR=vgpr, MONO_SGPR=sgpr, MONO_PRIVATE=private,
                     MONO_VCC=vcc, MONO_SCRATCH_ENABLE=int(private>0))
    (out/'mono_resources.inc').write_text('// Derived from actual compiler resources, not register limits.\n'+
        ''.join(f'.set {k}, {v}\n' for k,v in constants.items()))
    from stage_kernels import ARGUMENTS
    args = ''.join(f'      - .name: {name}\n        .offset: {i*8}\n        .size: 8\n        .value_kind: by_value\n'
                   for i,name in enumerate(ARGUMENTS))
    (out/'mono_metadata.inc').write_text(f'''// One launched kernel; the stages have no launch descriptors.
.amdgpu_metadata
---
amdhsa.version: [1, 2]
amdhsa.target: amdgcn-amd-amdhsa--gfx1250
amdhsa.kernels:
  - .name: {SYMBOL}
    .symbol: {SYMBOL}.kd
    .kernarg_segment_size: 120
    .kernarg_segment_align: 8
    .group_segment_fixed_size: 14848
    .private_segment_fixed_size: {private}
    .wavefront_size: 32
    .sgpr_count: {sgpr+2*vcc}
    .vgpr_count: {vgpr}
    .max_flat_workgroup_size: 256
    .reqd_workgroup_size: [256, 1, 1]
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
    .args:
{args}...
.end_amdgpu_metadata
''')
    return dict(vgpr=vgpr, numbered_sgpr=sgpr, sgpr=sgpr+2*vcc, private=private, lds=14848)


def disassemble(llvm, obj, symbol):
    return run([llvm/'llvm-objdump','--mcpu=gfx1250','--mattr=+real-true16',
                '--disassemble-symbols='+symbol,obj])


def package_stage(llvm, target, name):
    """Repackage an already ABI-correct, self-contained device function.

    FlyDSL's own LLVM performs codegen AND assembly. Its temporary linked ELF
    is not launched. Extract only the sized function after rejecting all
    relocations, external data, implicit-state references and helper calls.
    This avoids passing newer LLVM ISA syntax to an older ROCm assembler.
    """
    from asm.prepare import Elf
    generated=Elf(target/'stage.codegen.co')
    assert generated.kind==3 and generated.machine==224
    assert not any(s[1] in (4,9) and s[5] for s in generated.sections), 'Relocations in device function'
    funcs=[n for n,(idx,_,size,info) in generated.symbols.items() if idx and size and info&15==2]
    assert funcs==[name], funcs
    index,address,size,_=generated.symbols[name]
    # Apart from dynamic-link tables and notes, no allocated program data.
    # Such data would need a real relocatable object instead of extraction.
    shstr=generated.sections[struct.unpack_from('<H',generated.data,62)[0]]
    strings=generated.data[shstr[4]:shstr[4]+shstr[5]]
    def section_name(s):
        return strings[s[0]:strings.index(b'\0',s[0])].decode()
    assert not any(s[1] in (1,8) and s[2]&2 and s[5] and i!=index
                   and section_name(s)!='.relro_padding'
                   for i,s in enumerate(generated.sections)), 'External allocated data in stage'
    payload=generated.body(name)
    assert payload and len(payload)==size
    (target/'stage.bin').write_bytes(payload)
    source=f'''.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text
.globl {name}
.hidden {name}
.type {name},@function
.p2align 8
{name}:
.incbin "stage.bin"
.size {name}, .-{name}
// Preserve the normal AMDGPU end-of-code prefetch padding outside the symbol.
.p2alignl 7, 0xbf9f0000
.fill 96, 4, 0xbf9f0000
.section .note.GNU-stack,"",@progbits
'''
    (target/'stage.package.s').write_text(source)
    obj=target/'stage.o'
    run([llvm/'llvm-mc','-triple=amdgcn-amd-amdhsa','-mcpu=gfx1250',
         '-filetype=obj','-I',target,target/'stage.package.s','-o',obj])
    assert Elf(obj).body(name)==payload
    return obj


def audit_final(llvm, binary, objects, resource):
    from asm.prepare import Elf
    from asm.audit import load_fragment
    final = Elf(binary)
    assert final.kind == 3 and final.machine == 224
    assert not [n for n,(index,_,_,info) in final.symbols.items() if index==0 and info>>4==1]
    _,_,fragment,_ = load_fragment(BUILD/'asm')
    entry = final.body(SYMBOL)
    assert fragment not in entry
    # Decode the three literal rel64 call sequences, not objdump's rendering
    # of 64-bit immediates (older objdump can print their values incorrectly).
    addresses=[]
    for offset in range(0,len(entry)-20,4):
        words=struct.unpack_from('<5I',entry,offset)
        if words[0]==0xBE804700 and words[1]==0xA980FE00 and words[4]==0xBE9E4900:
            displacement=words[2] | words[3]<<32
            addresses.append((final.symbols[SYMBOL][1]+offset+4+displacement)&((1<<64)-1))
    assert addresses==[final.symbols['mono_stage_'+k][1] for k in KINDS], addresses
    for kind,obj in objects.items():
        name = 'mono_stage_'+kind
        # Stage objects have only internal branches; equality also rejects
        # hidden runtime relocations or accidental code transformation.
        assert final.body(name) == Elf(obj).body(name), f'Linked bytes changed: {name}'
        payload = final.body(name)
        count = sum(payload.startswith(fragment,i) for i in range(len(payload)))
        assert count == (1 if kind=='wqkv' else 0), (kind,count)
        if count:
            offset = payload.index(fragment)
            assert (final.symbols[name][1]+offset)%64 == 0
    text = disassemble(llvm,binary,SYMBOL)
    assert len(re.findall(r'\bs_(?:swappc_b64|swap_pc_i64)\b',text)) == 3
    assert len(re.findall(r'\bs_endpgm\b',text)) == 1
    (binary.parent/'mono.function.disasm.txt').write_text(text)
    from mono1250.runtime.compile import kernel_resources, _note_uint
    actual = kernel_resources(final.data)
    assert actual['vgpr']==resource['vgpr'] and actual['sgpr']==resource['sgpr']
    assert actual['scratch']==resource['private'] and actual['lds']==14848
    assert _note_uint(final.data,b'.wavefront_size') == 32
    assert _note_uint(final.data,b'.kernarg_segment_size') == 120
    descriptors = [n for n in final.symbols if n.endswith('.kd')]
    assert descriptors == [SYMBOL+'.kd'], descriptors
    return dict(kernel=actual, fragment_in_wqkv_only=True, real_calls=3, call_targets=addresses,
                leaf_bytes_unchanged=True, kernel_descriptors=descriptors)


def build(llvm):
    configure()
    llvm=Path(llvm).resolve()
    for name in ('clang++','llvm-mc','ld.lld','llvm-objdump','llvm-readelf'):
        assert (llvm/name).is_file(), f'Missing {llvm/name}'
    out=BUILD/'asm_mono';out.mkdir(parents=True,exist_ok=True)
    report={'status':'BUILDING','gpu_execution':False,'stages':{},'exports':{},
            'assembler_version':run([llvm/'llvm-mc','--version'])}
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(ROOT.rglob('*')) if p.is_file() and 'build' not in p.relative_to(ROOT).parts
        and p.suffix in ('.py','.s','.h','.cpp')}
    try:
        print(run([sys.executable,ROOT/'asm/prepare.py','--llvm-bin',llvm]),end='')
        import flydsl
        import flydsl.expr as fx
        from stage_kernels import build_stage, LDS_BYTES
        from export_stages import capture_stage, CapturedStage
        from mono1250.kernels.reference_plan import C1ReferencePlan
        plan=C1ReferencePlan().stages
        assert [(plan[k].base,plan[k].count) for k in ('k1.slice','k1.norm','k1.wqkv_a')] == [(0,160),(168,1),(176,112)]
        assert LDS_BYTES==14848
        report['flydsl_version']=flydsl.__version__
        objects={}
        for kind in KINDS:
            print('[stage/export] '+kind,flush=True)
            name='mono_stage_'+kind
            target=BUILD/'stages'/kind
            try:
                with capture_stage(name,target,report['exports']):
                    build_stage(kind)(0,0,0,0,stream=fx.Stream(0))
            except CapturedStage as e:
                assert str(e)==name
            else:
                raise RuntimeError('Stage tracing was not intercepted; no fallback allowed')
            text=(target/'stage.s').read_text()
            report['stages'][kind]=resources(text,name)
            assert 'amdhsa.kernels:  []' in text, 'Unexpected callee kernel metadata'
            obj=package_stage(llvm,target,name)
            objects[kind]=obj
            (target/'stage.disasm.txt').write_text(disassemble(llvm,obj,name))
        resource=write_metadata(out,report['stages'])
        report['resources']=resource
        run([llvm/'llvm-mc','-triple=amdgcn-amd-amdhsa','-mcpu=gfx1250',
             '-mattr=+real-true16','-filetype=obj','-I',out,ROOT/'mono_kernel.s','-o',out/'mono.o'])
        binary=out/'kernel.co'
        run([llvm/'ld.lld','-shared','--no-undefined',out/'mono.o',*objects.values(),'-o',binary])
        report['audit']=audit_final(llvm,binary,objects,resource)
        (out/'kernel.disasm.txt').write_text(run([llvm/'llvm-objdump','--mcpu=gfx1250','--mattr=+real-true16','-d',binary]))
        (out/'kernel.elf.txt').write_text(run([llvm/'llvm-readelf','-h','-s','-r','-n',binary]))
        report['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
        report['status']='BUILT'
        print('[asm-mono/build] BUILT '+str(binary)+' '+json.dumps(resource),flush=True)
        return binary,report
    except Exception as e:
        report.update(status='FAIL',error=f'{type(e).__name__}: {e}')
        raise
    finally:
        (out/'build.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--llvm-bin',type=Path,default=Path('/opt/rocm/llvm/bin'))
    build(p.parse_args().llvm_bin)
