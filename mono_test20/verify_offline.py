#!/usr/bin/env python3
"""CPU/static checks of the real ASM scheduler and all three compiled variants.

This does not simulate the mathematical stages and is not GPU validation.
It checks the handwritten scheduling against ATOM's plan, full call targets,
source preservation, actual code objects and inherited inline payload.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT=Path(__file__).resolve().parent
BUILD=ROOT/'build'


def check_schedule():
    from mono1250.kernels.reference_plan import C1ReferencePlan
    source=(ROOT/'mono_kernel.s').read_text()
    body=source.split('mono_asm_projection:\n')[1].split('.Lmono_end:')[0]
    lines=[x.split('//')[0].strip() for x in body.splitlines()]
    lines=[x for x in lines if x]
    labels={x[:-1]:i for i,x in enumerate(lines) if x.endswith(':')}
    total={'slice':0,'norm':0,'wqkv':0}
    plan=C1ReferencePlan().stages
    # Two endpoints of every physical wave test tid propagation in every CTA.
    for bid in range(256):
        for tid in [32*w+lane for w in range(8) for lane in (0,31)]:
            regs={'s0':0x76543210,'s1':0x1234,'v0':tid,'ttmp6':0,'ttmp9':bid}
            scc,pc,steps=0,0,0
            calls=[]
            def value(x):
                return regs[x] if x in regs else int(x,0)
            while pc<len(lines):
                line=lines[pc];pc+=1;steps+=1
                assert steps<100
                if line.endswith(':'): continue
                op,*rest=line.split(None,1)
                if op=='s_endpgm':break
                if op=='CALL_STAGE':
                    kind=rest[0].removeprefix('mono_stage_')
                    assert (regs['s36'],regs['s37'],regs['s38'],regs['v40'])==(0x76543210,0x1234,bid,tid)
                    assert (regs['s32'],regs['s33'],regs['s34'])==(0,0,0)
                    calls.append((kind,regs['s39']))
                    # Abstract a legal callee: destroy volatile numbered GPRs
                    # while preserving the root's declared live ABI state.
                    for n in ('s0','s1','s2','s3','s4','v0','v1','v2','v3','v4'):
                        regs[n]=0xDEADBEEF
                    scc=1
                    continue
                args=[x.strip() for x in rest[0].split(',')]
                if op=='s_cbranch_scc1':
                    if scc:pc=labels[args[0]]
                elif op.startswith('s_cmp_'):
                    a,b=map(value,args)
                    scc=int(a>=b if op=='s_cmp_ge_u32' else a!=b if op=='s_cmp_lg_u32' else a==b)
                elif op=='s_mov_b64':
                    assert args==['s[36:37]','s[0:1]']
                    regs['s36'],regs['s37']=regs['s0'],regs['s1']
                elif op=='s_getreg_b32':regs[args[0]]=0  # ordinary, non-clustered grid
                elif op=='s_cselect_b32':regs[args[0]]=value(args[1 if scc else 2])
                elif op in ('s_mov_b32','v_mov_b32_e32'):regs[args[0]]=value(args[1])
                else:
                    dst,a,b=args[0],value(args[1]),value(args[2])
                    if op=='s_bfe_u32':v=(a>>(b&31))&((1<<((b>>16)&127))-1)
                    elif op=='s_and_b32':v=a&b
                    elif op=='s_add_co_i32':v=a+b
                    elif op=='s_mul_i32':v=a*b
                    elif op=='s_sub_u32':v=a-b
                    else:raise AssertionError('Unmodeled scheduler instruction: '+op)
                    regs[dst]=v&0xFFFFFFFF
            expected=[(kind,t) for kind,key in [('slice','k1.slice'),('norm','k1.norm'),('wqkv','k1.wqkv_a')]
                      for t in plan[key].tasks(bid)]
            assert calls==expected,(bid,tid,calls,expected)
            if tid==0:
                for kind,_ in calls:total[kind]+=1
    assert total==dict(slice=160,norm=1,wqkv=112)
    return dict(ctas=256,tid_samples_per_cta=16,tasks=total,volatile_state_destroyed_between_calls=True)


def check_sources():
    snapshot=json.loads((ROOT/'PARENT_SNAPSHOT.json').read_text())['mono_test10']
    # The parent can be absent on a copied target-machine checkout; when it
    # exists, verify no experiment edited it. Always verify local math files.
    parent=ROOT.parent/'mono_test10'
    checked=0
    if parent.exists():
        for name,digest in snapshot.items():
            assert hashlib.sha256((parent/name).read_bytes()).hexdigest()==digest,name
            checked+=1
    for name in ('reference.py','asm_host.py','asm/dq_convert.original.s',
                 'asm/dq_convert.inline.s','mono1250/kernels/dq_inline.py'):
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==snapshot[name],name
    # All copied Mono computation modules retain exactly the old text apart
    # from routing three AITER helper imports to the unmodified vendored files.
    for name,digest in snapshot.items():
        if name.startswith('mono1250/') and name.endswith('.py'):
            text=(ROOT/name).read_text().replace('from vendor_aiter import','from aiter.ops.flydsl.kernels import')
            text=text.replace('from vendor_aiter.dpp_utils import','from aiter.ops.flydsl.kernels.dpp_utils import')
            text=text.replace('from vendor_aiter.kernels_common import','from aiter.ops.flydsl.kernels.kernels_common import')
            assert hashlib.sha256(text.encode()).hexdigest()==digest,name
    for name,info in json.loads((ROOT/'vendor_aiter/SOURCE.json').read_text()).items():
        assert hashlib.sha256((ROOT/'vendor_aiter'/name).read_bytes()).hexdigest()==info['sha256']
    for p in ROOT.rglob('*.py'):
        if 'build' not in p.relative_to(ROOT).parts:ast.parse(p.read_text(),filename=str(p))
    return dict(parent_files_checked=checked,original_compute_unchanged=True,vendor_helpers_unchanged=True)


def verify():
    from asm.prepare import Elf
    from asm.audit import audit_embedded
    from mono1250.runtime.compile import kernel_resources
    build=json.loads((BUILD/'asm_mono/build.json').read_text())
    assert build['status']=='BUILT'
    variants={}
    descriptors={}
    for variant in ('native','inline','asm_mono'):
        path=BUILD/variant/'kernel.co'
        elf=Elf(path)
        name=next(n for n in elf.symbols if n.endswith('.kd'))
        descriptors[variant]=elf.body(name)
        variants[variant]=kernel_resources(elf.data)
        if variant=='inline':audit_embedded(path,name[:-3],variants[variant],BUILD/'asm')
    # All stages and the ASM entry must start with the same floating-point
    # modes as the normal FlyDSL kernel. Compare actual resource descriptor.
    modes={name:(struct.unpack_from('<I',data,48)[0]>>12)&255 for name,data in descriptors.items()}
    assert len(set(modes.values()))==1,modes
    result=dict(status='OFFLINE_CHECKS_PASS',gpu_tests_run=False,sources=check_sources(),
                schedule=check_schedule(),resources=variants,float_modes=modes,
                asm_build_audit=build['audit'])
    (BUILD/'OFFLINE_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print('[offline/check] PASS: schedule, caller state model, source identity, descriptor modes and ELF boundaries; no GPU execution')
    return result


if __name__=='__main__':
    from build_asm_mono import configure
    configure()
    verify()
