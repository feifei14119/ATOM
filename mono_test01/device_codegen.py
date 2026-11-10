"""Local FlyDSL compile hook: LLVM bitcode -> pre-RA regmask -> linked ELF.

Installed FlyDSL files are never edited. The hook exists only while compiling
the lowctx launcher and returns a normal module containing gpu.binary to its
ordinary launcher. No final GPU instruction bytes are patched.
"""
from contextlib import contextmanager, nullcontext
import inspect
import re

from callsite_regmask import compile_caller
from asm.prepare import SYMBOL


def compile_module(source, config, symbol, llvm, out):
    from flydsl._mlir import ir
    from flydsl._mlir.passmanager import PassManager
    from flydsl.compiler.llvm_options import llvm_options
    from mono1250.runtime.compile import _code_object

    fragments = list(config.fragments)
    binary_indices = [i for i, f in enumerate(fragments) if f.strip().startswith('gpu-module-to-binary')]
    assert binary_indices == [len(fragments)-1], 'FlyDSL pipeline changed; expected one final binary pass'
    assert not getattr(config, 'external', False), 'Unset FLYDSL_COMPILE_LLVM_DIR for this local hook'
    module = ir.Module.parse(source)
    module.operation.verify()
    out.mkdir(parents=True, exist_ok=True)
    (out/'origin.mlir').write_text(source)
    opts = config.llvm_opts
    with llvm_options(opts) if opts else nullcontext():
        pm = PassManager.parse('builtin.module('+','.join(fragments[:-1])+')')
        pm.enable_verifier(True)
        pm.run(module.operation)
        module.operation.verify()
        (out/'before_binary.mlir').write_text(str(module))
        # The standard ROCDL serializer with format=llvm does the same device
        # bitcode linking/LLVM optimization, then stops BEFORE machine codegen.
        # This keeps OCML/control constants/target attributes from normal FlyDSL.
        fragment, n = re.subn(r'format=(?:fatbin|bin|binary)', 'format=llvm', fragments[-1])
        assert n == 1, 'Unknown gpu-module-to-binary format'
        pm = PassManager.parse('builtin.module('+fragment+')')
        pm.enable_verifier(True)
        pm.run(module.operation)
    offload = str(module)
    (out/'offload.mlir').write_text(offload)
    matches = list(re.finditer(r'\boffload\s*=\s*"((?:[^"\\]|\\.)*)"', offload))
    assert len(matches) == 1, 'Expected exactly one LLVM offload object'
    m = matches[0]
    bitcode = _code_object('bin = "'+m[1]+'"')
    assert bitcode.startswith(b'BC\xc0\xde'), 'Expected raw LLVM bitcode'
    bc = out/'caller.bc'
    bc.write_bytes(bitcode)
    binary, report = compile_caller(bc, out.parent/'asm/dq_convert.lowctx.co', symbol, out, llvm, opts)
    # Populate the ordinary gpu.binary container with the linked ELF. This is
    # object construction, not a post-RA call insertion or machine-code patch.
    encoded = ''.join('\\'+format(x, '02X') for x in binary)
    final_text = offload[:m.start()]+'bin = "'+encoded+'"'+offload[m.end():]
    result = ir.Module.parse(final_text)
    result.operation.verify()
    assert _code_object(str(result)) == binary
    (out/'kernel.mlir').write_text(str(result))
    return result, report


def lowered_source(jf, module, arch, link_libs):
    """Repeat MlirCompiler.compile's steps before its pass pipeline (FlyDSL 0.4)."""
    if link_libs:
        raise RuntimeError('extern link_libs are not supported by the lowctx hook')
    module.operation.verify()
    backend = jf.get_backend(arch=arch)
    hints = jf.CompilationContext.get_compile_hints()
    module = jf.ir.Module.parse(module.operation.get_asm(enable_debug_info=jf.env.debug.enable_debug_info))
    backend.lower_compile_hints(module, compile_hints=hints)
    return str(module), jf._pipeline_fragments_for_mode(backend, compile_hints=hints)


@contextmanager
def lowctx_codegen(symbol, llvm, out):
    import flydsl.compiler.jit_function as jf
    cls = getattr(jf, 'MlirCompiler', None)
    if cls is None or 'compile' not in cls.__dict__:
        raise RuntimeError('This integration requires FlyDSL MlirCompiler.compile(module, *, arch, func_name, '
                           'link_libs). Installed FlyDSL is incompatible; no fallback to the default ABI is allowed.')
    descriptor = cls.__dict__['compile']
    if not isinstance(descriptor, classmethod):
        raise RuntimeError('FlyDSL MlirCompiler.compile API changed')
    original = cls.compile
    if set(inspect.signature(original).parameters) != {'module', 'arch', 'func_name', 'link_libs'}:
        raise RuntimeError('FlyDSL compile signature changed; adapt device_codegen.py first')
    state = {'compilations': 0}

    def hooked(owner, module, *, arch='', func_name='', link_libs=None):
        if SYMBOL not in module.operation.get_asm():
            return original(module, arch=arch, func_name=func_name, link_libs=link_libs)
        state['compilations'] += 1
        if state['compilations'] != 1:
            raise RuntimeError('Unexpected repeated custom compilation')
        source, config = lowered_source(jf, module, arch, link_libs)
        module, report = compile_module(source, config, symbol, llvm, out)
        state['report'] = report
        return module

    cls.compile = classmethod(hooked)
    try:
        yield state
        if state['compilations'] != 1:
            raise RuntimeError('Lowctx codegen hook was not used; refusing an unpatched/default-ABI module')
    finally:
        cls.compile = descriptor
