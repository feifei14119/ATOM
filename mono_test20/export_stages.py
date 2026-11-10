"""Export ordinary device functions through a scoped FlyDSL 0.4 compiler hook.

No GPU launches and no installed-source modifications. The tracing container
is lowered normally, then converted to a device function in MLIR, before the
serializer performs LLVM optimization. No amdgpu_kernel IR is called as a
device function. Original, lowered and adapted MLIR are retained for review.
"""
from contextlib import contextmanager, nullcontext
import inspect
from pathlib import Path
import re


class CapturedStage(Exception):
    pass


def walk(op):
    yield op
    for region in op.regions:
        for block in region.blocks:
            for child in list(block.operations):
                yield from walk(child.operation)


def convert_stage(module, symbol):
    from flydsl._mlir import ir
    from flydsl._mlir.dialects import llvm
    funcs = [op for op in walk(module.operation) if op.name == 'llvm.func'
             and 'sym_name' in op.attributes and ir.StringAttr(op.attributes['sym_name']).value == symbol]
    assert len(funcs) == 1
    fn = funcs[0]
    block = fn.regions[0].blocks[0]
    assert [str(a.type) for a in block.arguments] == ['i64', 'i32', 'i32', 'i32']
    ids = {'rocdl.workitem.id.x': block.arguments[3], 'rocdl.workgroup.id.x': block.arguments[2]}
    replaced = {}
    for op in list(walk(fn)):
        if op.name in ids:
            assert len(op.results) == 1 and op.results[0].type == ids[op.name].type
            op.results[0].replace_all_uses_with(ids[op.name])
            replaced[op.name] = replaced.get(op.name, 0) + 1
            op.erase()
    # Inspect actual attributes rather than assuming the gpu.kernel marker
    # alone controls calling convention in every MLIR version.
    attrs = {name: str(fn.attributes[name]) for name in fn.attributes}
    for name in list(attrs):
        if name in ('rocdl.kernel', 'gpu.kernel', 'gpu.known_block_size', 'rocdl.reqd_work_group_size',
                    'rocdl.flat_work_group_size', 'arg_attrs', 'res_attrs'):
            del fn.attributes[name]
    fn.attributes['CConv'] = ir.Attribute.parse('#llvm.cconv<ccc>')
    fn.attributes['linkage'] = ir.Attribute.parse('#llvm.linkage<external>')
    fn.attributes['passthrough'] = ir.ArrayAttr.get([
        ir.StringAttr.get('noinline'), ir.StringAttr.get('convergent'),
        ir.StringAttr.get('nounwind'),
        ir.ArrayAttr.get([ir.StringAttr.get('amdgpu-flat-work-group-size'), ir.StringAttr.get('256,256')]),
    ])
    forbidden = ('rocdl.workitem.id', 'rocdl.workgroup.id', 'rocdl.grid', 'rocdl.block',
                 'rocdl.dispatch', 'rocdl.kernarg', 'rocdl.implicitarg')
    assert not any(op.name.startswith(forbidden) for op in walk(fn))
    assert replaced.get('rocdl.workitem.id.x',0)>0, 'Unexpected workitem-ID lowering; review export before use'
    text=str(module)
    for intrinsic in ('llvm.amdgcn.workitem.id','llvm.amdgcn.workgroup.id',
                      'llvm.amdgcn.dispatch.ptr','llvm.amdgcn.kernarg.segment.ptr',
                      'llvm.amdgcn.implicitarg.ptr','llvm.amdgcn.queue.ptr'):
        assert intrinsic not in text, 'Unbridged implicit device argument: '+intrinsic
    assert not any(op.name == 'llvm.mlir.global' for op in walk(module.operation)), 'Callee LDS/global allocation unsupported'
    module.operation.verify()
    return {'original_attributes': attrs, 'ids_replaced': replaced, 'signature': 'void(i64,i32,i32,i32)'}


@contextmanager
def capture_stage(symbol, out, report):
    import flydsl.compiler.jit_function as jf
    from flydsl._mlir import ir
    from flydsl._mlir.passmanager import PassManager
    from flydsl.compiler.llvm_options import llvm_options
    from mono1250.runtime.compile import _code_object
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    cls = jf.MlirCompiler
    descriptor = cls.__dict__['compile']
    original = cls.compile
    if set(inspect.signature(original).parameters) != {'module','arch','func_name','link_libs'}:
        raise RuntimeError('This exporter requires the FlyDSL 0.4 MlirCompiler.compile interface')
    captured = []

    def hooked(owner, module, *, arch='', func_name='', link_libs=None):
        if symbol not in str(module):
            return original(module, arch=arch, func_name=func_name, link_libs=link_libs)
        assert not link_libs and not captured
        backend = jf.get_backend(arch=arch)
        hints = jf.CompilationContext.get_compile_hints()
        module = ir.Module.parse(module.operation.get_asm())
        backend.lower_compile_hints(module, compile_hints=hints)
        cfg = jf._pipeline_fragments_for_mode(backend, compile_hints=hints)
        assert not cfg.external
        fragments = list(cfg.fragments)
        assert fragments[-1].startswith('gpu-module-to-binary')
        (out/'origin.mlir').write_text(str(module))
        with llvm_options(cfg.llvm_opts) if cfg.llvm_opts else nullcontext():
            pm = PassManager.parse('builtin.module('+','.join(fragments[:-1])+')')
            pm.enable_verifier(True); pm.run(module.operation)
            (out/'lowered.mlir').write_text(str(module))
            # The host tracing launcher is not exported and must not retain a
            # gpu.launch_func referencing the now ordinary device function.
            for op in list(module.body.operations):
                if op.operation.name != 'gpu.module':
                    op.operation.erase()
            report[symbol] = convert_stage(module, symbol)
            (out/'device.mlir').write_text(str(module))
            binary_module = ir.Module.parse(str(module))
            assembly_module = ir.Module.parse(str(module))
            isa_frag, count = re.subn(r'format=(?:fatbin|bin|binary)', 'format=isa', fragments[-1])
            assert count == 1
            pm = PassManager.parse('builtin.module('+isa_frag+')')
            pm.enable_verifier(True); pm.run(assembly_module.operation)
            isa_text = str(assembly_module)
            (out/'isa.mlir').write_text(isa_text)
            isa_matches = re.findall(r'\bassembly\s*=\s*"((?:[^"\\]|\\.)*)"', isa_text)
            assert len(isa_matches) == 1
            assembly = _code_object('bin = "'+isa_matches[0]+'"').decode()
            assert '.amdgcn_target' in assembly and symbol+':' in assembly
            (out/'stage.s').write_text(assembly)
            bin_frag, count = re.subn(r'format=(?:fatbin|bin|binary)', 'format=bin', fragments[-1])
            assert count == 1
            pm = PassManager.parse('builtin.module('+bin_frag+')')
            pm.enable_verifier(True); pm.run(binary_module.operation)
            binary_text = str(binary_module)
            matches = re.findall(r'\bbin\s*=\s*"((?:[^"\\]|\\.)*)"',binary_text)
            assert len(matches)==1
            binary = _code_object('bin = "'+matches[0]+'"')
            assert binary.startswith(b'\x7fELF')
            (out/'stage.codegen.co').write_bytes(binary)
            frag, count = re.subn(r'format=(?:fatbin|bin|binary)', 'format=llvm', fragments[-1])
            assert count == 1
            pm = PassManager.parse('builtin.module('+frag+')')
            pm.enable_verifier(True); pm.run(module.operation)
        text = str(module)
        (out/'offload.mlir').write_text(text)
        matches = re.findall(r'\boffload\s*=\s*"((?:[^"\\]|\\.)*)"', text)
        assert len(matches) == 1
        bc = _code_object('bin = "'+matches[0]+'"')
        assert bc.startswith(b'BC\xc0\xde')
        (out/'stage.bc').write_bytes(bc)
        captured.append(True)
        # Stop before materializing the tracing launcher's execution engine.
        raise CapturedStage(symbol)

    cls.compile = classmethod(hooked)
    try:
        yield
    finally:
        cls.compile = descriptor
    assert captured, 'The stage was not exported; cached tracing containers are unsupported'
