"""Experimental FFI bridge to the patched LLVM backend; installed FlyDSL is untouched.

This is an isolated FlyDSL 0.4 compiler adapter, not a claim that upstream
FlyDSL exposes these options. The native backend owns fixed registers, call
regmasks, and spill diagnostics. No MIR or final instruction patching is used.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import inspect
import json
from pathlib import Path
import re

from demo.contract import audit_object, llvm_attributes, run, verify_identity
from demo.build import compile_and_link, require_backend


def walk(op):
    yield op
    for region in op.regions:
        for block in region.blocks:
            for child in list(block.operations):
                yield from walk(child.operation)


def passthrough(op, values, flags=()):
    from flydsl._mlir import ir
    old = list(ir.ArrayAttr(op.attributes["passthrough"])) if "passthrough" in op.attributes else []
    keys = set(values) | set(flags)
    keep = []
    for attr in old:
        key = ir.StringAttr(attr[0]).value if isinstance(attr, ir.ArrayAttr) else ir.StringAttr(attr).value
        if key not in keys:
            keep.append(attr)
    keep.extend(ir.StringAttr.get(flag) for flag in flags)
    keep.extend(ir.ArrayAttr.get([ir.StringAttr.get(key), ir.StringAttr.get(value)])
                for key, value in values.items())
    op.attributes["passthrough"] = ir.ArrayAttr.get(keep)


class AsmFFI:
    """One manifest registration, followed by an ordinary callable in the DSL."""
    def __init__(self, manifest_path):
        from flydsl.expr.extern import ffi
        self.manifest = json.loads(Path(manifest_path).read_text())
        verify_identity(self.manifest)
        self.symbol = self.manifest["symbol"]
        self.function = ffi(self.symbol, [arg["type"] for arg in self.manifest["arguments"]],
                            self.manifest["result"]["type"], is_pure=False)

    def __call__(self, *args):
        from flydsl._mlir import ir
        from flydsl.compiler.kernel_function import CompilationContext
        verify_identity(self.manifest)
        result = self.function(*args)
        result.owner.attributes["convergent"] = ir.UnitAttr.get()
        context = CompilationContext.get_current()
        matches = [op.operation for op in context.gpu_module_body.operations
                   if op.operation.name == "llvm.func" and "sym_name" in op.attributes
                   and ir.StringAttr(op.attributes["sym_name"]).value == self.symbol]
        if len(matches) != 1:
            raise RuntimeError("ffi did not create exactly one ASM declaration")
        passthrough(matches[0], llvm_attributes(self.manifest),
                    ("noinline", "convergent", "nounwind", "norecurse"))
        return result


class CompileOnlyComplete(Exception):
    """Stop after obtaining a genuine gpu.binary, before host/GPU launch."""


def _decode_mlir_bytes(text):
    # GPU serializer binary strings use hexadecimal escapes, never Python escapes.
    if re.fullmatch(r"(?:\\[0-9A-Fa-f]{2})*", text):
        return bytes.fromhex(text.replace("\\", ""))
    result = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "\\":
            if i+1 < len(text) and text[i+1] in '\\"':
                result.append(ord(text[i+1]))
                i += 2
                continue
            if i+2 >= len(text) or not re.fullmatch(r"[0-9A-Fa-f]{2}", text[i+1:i+3]):
                raise ValueError("unexpected non-hex binary escape in MLIR")
            result.append(int(text[i+1:i+3], 16))
            i += 3
        else:
            result.extend(text[i].encode())
            i += 1
    return bytes(result)


def compile_module(module, jf, arch, symbol, manifest, llvm, out, link_libs):
    from flydsl._mlir import ir
    from flydsl._mlir.passmanager import PassManager
    from flydsl.compiler.llvm_options import llvm_options
    if link_libs:
        raise RuntimeError("this bridge accepts manifest device objects, not extra bitcode libraries")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    backend = jf.get_backend(arch=arch)
    hints = jf.CompilationContext.get_compile_hints()
    module = ir.Module.parse(module.operation.get_asm())
    backend.lower_compile_hints(module, compile_hints=hints)
    cfg = jf._pipeline_fragments_for_mode(backend, compile_hints=hints)
    if cfg.external:
        raise RuntimeError("unset FLYDSL_COMPILE_LLVM_DIR: this adapter owns the external LLVM bridge")
    fragments = list(cfg.fragments)
    if not fragments or not fragments[-1].startswith("gpu-module-to-binary"):
        raise RuntimeError("FlyDSL pipeline changed; expected one final serializer")
    (out/"origin.mlir").write_text(str(module))
    with llvm_options(cfg.llvm_opts) if cfg.llvm_opts else nullcontext():
        pm = PassManager.parse("builtin.module("+",".join(fragments[:-1])+")")
        pm.enable_verifier(True)
        pm.run(module.operation)
        entries = [op for op in walk(module.operation) if op.name == "llvm.func"
                   and "sym_name" in op.attributes
                   and ir.StringAttr(op.attributes["sym_name"]).value == symbol]
        if len(entries) != 1:
            raise RuntimeError("expected one named LLVM kernel entry")
        passthrough(entries[0], {"amdgpu-asm-full-wave-calls": "true"},
                    ("amdgpu-no-gpr-spill", "amdgpu-no-private-memory"))
        declarations = [op for op in walk(module.operation) if op.name == "llvm.func"
                        and "sym_name" in op.attributes
                        and ir.StringAttr(op.attributes["sym_name"]).value == manifest["symbol"]]
        if len(declarations) != 1 or len(declarations[0].regions[0].blocks):
            raise RuntimeError("external ASM contract must annotate a declaration, never a wrapper definition")
        # Re-apply through the typed MLIR API after lowering and verify that
        # the declaration and its complete attrs enter LLVM before any RA.
        passthrough(declarations[0], llvm_attributes(manifest),
                    ("noinline", "convergent", "nounwind", "norecurse"))
        module.operation.verify()
        (out/"contract.mlir").write_text(str(module))
        fragment, n = re.subn(r"format=(?:fatbin|bin|binary)", "format=llvm", fragments[-1])
        if n != 1:
            raise RuntimeError("unknown FlyDSL serializer format")
        pm = PassManager.parse("builtin.module("+fragment+")")
        pm.enable_verifier(True)
        pm.run(module.operation)
    offload = str(module)
    (out/"offload.mlir").write_text(offload)
    matches = list(re.finditer(r'\boffload\s*=\s*"((?:[^"\\]|\\.)*)"', offload))
    if len(matches) != 1:
        raise RuntimeError("expected exactly one offload bitcode object")
    match = matches[0]
    bitcode = _decode_mlir_bytes(match[1])
    if not bitcode.startswith(b"BC\xc0\xde"):
        raise RuntimeError("FlyDSL serializer did not emit raw bitcode")
    (out/"caller.raw.bc").write_bytes(bitcode)
    run([Path(llvm)/"opt", "-passes=internalize,globaldce",
         "-internalize-public-api-list="+symbol+","+manifest["symbol"],
         out/"caller.raw.bc", "-o", out/"caller.bc"])
    run([Path(llvm)/"llvm-dis", out/"caller.bc", "-o", out/"caller.ll"])
    report = compile_and_link(out/"caller.bc", manifest, llvm, out, symbol)
    report.update(full_wave_entry="explicit caller assertion; this test has no divergent control flow",
                  bridge="FlyDSL typed MLIR attrs -> LLVM bitcode -> patched llc -> static ELF link",
                  installed_flydsl_modified=False, mir_patched=False)
    binary = Path(report["kernel"]).read_bytes()
    encoded = "".join("\\"+format(byte, "02X") for byte in binary)
    final_text = offload[:match.start()]+'bin = "'+encoded+'"'+offload[match.end():]
    final = ir.Module.parse(final_text)
    final.operation.verify()
    (out/"kernel.mlir").write_text(str(final))
    return final, report


@contextmanager
def asm_codegen(manifest_path, llvm, output, *, symbol="contract_flydsl", compile_only=True,
                assert_full_wave_calls=False):
    """Scope the compiler bridge to exactly this external symbol and restore it."""
    if assert_full_wave_calls is not True:
        raise ValueError("contract v1 requires an explicit assert_full_wave_calls=True; "
                         "the adapter does not prove arbitrary DSL control flow")
    import flydsl.compiler.jit_function as jf
    manifest = json.loads(Path(manifest_path).read_text())
    verify_identity(manifest)
    out, llvm = Path(output).resolve(), Path(llvm).resolve()
    preflight = require_backend(llvm, out)
    audit = audit_object(manifest["object_path"], manifest, llvm)
    audit.pop("disassembly")
    compiler = jf.MlirCompiler
    descriptor, original = compiler.__dict__["compile"], compiler.compile
    if not isinstance(descriptor, classmethod) or set(inspect.signature(original).parameters) != {
            "module", "arch", "func_name", "link_libs"}:
        raise RuntimeError("unsupported FlyDSL compiler interface")
    state = {"compilations": 0}

    def hooked(owner, module, *, arch="", func_name="", link_libs=None):
        if manifest["symbol"] not in module.operation.get_asm():
            return original(module, arch=arch, func_name=func_name, link_libs=link_libs)
        state["compilations"] += 1
        if state["compilations"] != 1:
            raise RuntimeError("unexpected repeated compilation in one bridge context")
        result, report = compile_module(module, jf, arch, symbol, manifest, llvm, out, link_libs)
        report.update(backend=preflight, stage=audit)
        state["report"] = report
        (out/"result.json").write_text(json.dumps(report, indent=2)+"\n")
        if compile_only:
            raise CompileOnlyComplete(symbol)
        return result

    compiler.compile = classmethod(hooked)
    try:
        yield state
    finally:
        compiler.compile = descriptor
    if state["compilations"] != 1:
        raise RuntimeError("contract backend was not invoked; refusing cached/default-ABI output")
