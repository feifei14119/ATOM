"""Compile-only FlyDSL 0.4.1 adapter export, before any runtime launch.

The gpu.kernel is only a tracing container. Convert it to a seven-argument
ordinary CCC function before LLVM optimization, then let LLVM allocate/save
registers normally. No installed FlyDSL/LLVM sources are modified.
"""
from contextlib import contextmanager, nullcontext
import inspect
import os
from pathlib import Path
import re
import subprocess
import sys


class CapturedFragment(Exception):
    """Stop tracing before execution-engine materialization."""


def run(argv):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Command failed: {argv}\n{result.stdout}{result.stderr}")
    return result.stdout


def configure(output):
    # Set before importing FlyDSL: its environment options are cached.
    os.environ.update({
        "ARCH": "gfx1250", "FLYDSL_GPU_ARCH": "gfx1250", "COMPILE_ONLY": "1",
        "FLYDSL_RUNTIME_ENABLE_CACHE": "0", "FLYDSL_RUNTIME_RUN_ONLY": "0",
        "FLYDSL_COMPILE_LLVM_DIR": "", "FLYDSL_DEBUG_ENABLE_DEBUG_INFO": "0",
        "FLYDSL_RUNTIME_CACHE_DIR": str(Path(output) / "cache"),
    })
    sys.dont_write_bytecode = True


def walk(op):
    yield op
    for region in op.regions:
        for block in region.blocks:
            for child in list(block.operations):
                yield from walk(child.operation)


def convert_fragment(module, symbol):
    from flydsl._mlir import ir
    from flydsl._mlir.dialects import rocdl

    funcs = [op for op in walk(module.operation) if op.name == "llvm.func"
             and "sym_name" in op.attributes
             and ir.StringAttr(op.attributes["sym_name"]).value == symbol]
    if len(funcs) != 1:
        raise RuntimeError(f"Expected one tracing function {symbol}")
    fn = funcs[0]
    block = fn.regions[0].blocks[0]
    signature = [str(a.type) for a in block.arguments]
    if signature != ["i64"] + ["i32"] * 6:
        raise RuntimeError(f"Unexpected fragment ABI: {signature}")

    # A raw CCC argument is divergent in LLVM. Make CTA ID explicitly uniform,
    # including builtin IDs used deep inside imported stage helpers.
    with ir.InsertionPoint.at_block_begin(block):
        uniform_bid = rocdl.readfirstlane(block.arguments[1].type, block.arguments[1])
    ids = {"rocdl.workgroup.id.x": uniform_bid,
           "rocdl.workitem.id.x": block.arguments[2]}
    replaced = {}
    for op in list(walk(fn)):
        if op.name in ids:
            op.results[0].replace_all_uses_with(ids[op.name])
            replaced[op.name] = replaced.get(op.name, 0) + 1
            op.erase()
    attributes = {name: str(fn.attributes[name]) for name in fn.attributes}
    for name in ("rocdl.kernel", "gpu.kernel", "gpu.known_block_size",
                 "rocdl.reqd_work_group_size", "rocdl.flat_work_group_size",
                 "arg_attrs", "res_attrs"):
        if name in fn.attributes:
            del fn.attributes[name]
    fn.attributes["CConv"] = ir.Attribute.parse("#llvm.cconv<ccc>")
    fn.attributes["linkage"] = ir.Attribute.parse("#llvm.linkage<external>")
    fn.attributes["passthrough"] = ir.ArrayAttr.get([
        ir.StringAttr.get("noinline"), ir.StringAttr.get("convergent"),
        ir.StringAttr.get("nounwind"),
        ir.ArrayAttr.get([ir.StringAttr.get("amdgpu-flat-work-group-size"),
                          ir.StringAttr.get("256,256")]),
    ])
    forbidden_ops = ("rocdl.workitem.id", "rocdl.workgroup.id", "rocdl.grid",
                     "rocdl.block", "rocdl.dispatch", "rocdl.kernarg", "rocdl.implicitarg")
    if any(op.name.startswith(forbidden_ops) for op in walk(fn)):
        raise RuntimeError("Unbridged implicit dispatch state")
    if any(op.name == "llvm.mlir.global" for op in walk(module.operation)):
        raise RuntimeError("Fragment-owned LDS/global allocation is unsupported")
    module.operation.verify()
    return {"original_attributes": attributes, "ids_replaced": replaced,
            "signature": "void(i64,i32,i32,i32,i32,i32,i32)",
            "calling_convention": "ccc", "argument_vgprs": list(range(8))}


def audit_llvm_ir(text, symbol):
    if not text or not re.search(r"define\s+(?:[^\n@]*\s)?void\s+@" + re.escape(symbol) + r"\(", text):
        raise RuntimeError("LLVM IR export did not produce the expected void CCC function")
    if re.search(r"\b(?:amdgpu_kernel|amdgpu_gfx|amdgpu_cs)\b", text):
        raise RuntimeError("Export retained a kernel/special calling convention")
    for intrinsic in ("workitem.id", "workgroup.id", "dispatch.ptr", "kernarg.segment.ptr",
                      "implicitarg.ptr", "queue.ptr"):
        if "llvm.amdgcn." + intrinsic in text:
            raise RuntimeError("Unbridged implicit argument: " + intrinsic)
    definitions = re.findall(r"^define\b[^\n]*@([^\s(]+)\(", text, re.M)
    if definitions != [symbol]:
        raise RuntimeError(f"Only one leaf definition is supported: {definitions}")


@contextmanager
def capture_fragment(symbol, output, report):
    import flydsl.compiler.jit_function as jf
    from flydsl._mlir import ir
    from flydsl._mlir.passmanager import PassManager
    from flydsl.compiler.llvm_options import llvm_options

    cls = jf.MlirCompiler
    descriptor, original = cls.__dict__["compile"], cls.compile
    if set(inspect.signature(original).parameters) != {"module", "arch", "func_name", "link_libs"}:
        raise RuntimeError("Exporter requires FlyDSL 0.4 MlirCompiler.compile interface")
    captured = []

    def hooked(owner, module, *, arch="", func_name="", link_libs=None):
        if symbol not in str(module):
            raise RuntimeError("Unexpected compilation during fragment export")
        if link_libs or captured:
            raise RuntimeError("Linked libraries/multiple tracing containers are unsupported")
        backend = jf.get_backend(arch=arch)
        hints = jf.CompilationContext.get_compile_hints()
        module = ir.Module.parse(module.operation.get_asm(enable_debug_info=False))
        backend.lower_compile_hints(module, compile_hints=hints)
        pipeline = jf._pipeline_fragments_for_mode(backend, compile_hints=hints)
        parts = list(pipeline.fragments)
        if pipeline.external or not parts[-1].startswith("gpu-module-to-binary"):
            raise RuntimeError("Unexpected FlyDSL lowering pipeline; review exporter")
        (output / "origin.mlir").write_text(str(module))
        with llvm_options(pipeline.llvm_opts) if pipeline.llvm_opts else nullcontext():
            pm = PassManager.parse("builtin.module(" + ",".join(parts[:-1]) + ")")
            pm.enable_verifier(True)
            pm.run(module.operation)
            (output / "lowered.mlir").write_text(str(module))
            for op in list(module.body.operations):
                if op.operation.name != "gpu.module":
                    op.operation.erase()
            report.update(convert_fragment(module, symbol))
            (output / "device.mlir").write_text(str(module))
            llvm_ir = jf._extract_llvm_ir(module)
            audit_llvm_ir(llvm_ir, symbol)
            (output / "fragment.ll").write_text(llvm_ir)
        captured.append(True)
        raise CapturedFragment(symbol)

    cls.compile = classmethod(hooked)
    try:
        yield
    finally:
        cls.compile = descriptor
    if not captured:
        raise RuntimeError("Tracing was not intercepted (possibly a cached container)")


def export_fragment(name, cfg, draft, output, llvm_bin):
    from fragments import create_launcher
    import flydsl.expr as fx

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    launcher, symbol, hx = create_launcher(name, cfg, draft, output)
    report = {"symbol": symbol, "stage": name, "draft": draft}
    previous_lds_base, previous_timeout = hx.lds_base, hx.TOFLAG[0]
    try:
        # All byte offsets now refer to the root's dynamic LDS at address zero.
        # Do not create a per-container external dynamic-shared global.
        hx.lds_base = lambda: fx.Int32(0)
        try:
            with capture_fragment(symbol, output, report):
                launcher(0, 0, 0, 0, 0, 0, 0, stream=fx.Stream(0))
        except CapturedFragment as error:
            if str(error) != symbol:
                raise
        else:
            raise RuntimeError("Fragment capture failed; runtime fallback is forbidden")
    finally:
        hx.lds_base, hx.TOFLAG[0] = previous_lds_base, previous_timeout

    llvm = Path(llvm_bin)
    run([llvm / "opt", "-passes=default<O3>", "-S", output / "fragment.ll",
         "-o", output / "fragment.optimized.ll"])
    audit_llvm_ir((output / "fragment.optimized.ll").read_text(), symbol)
    run([llvm / "llc", "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
         "-mattr=+wavefrontsize32,+real-true16", "-O3", "-filetype=asm",
         output / "fragment.optimized.ll", "-o", output / "fragment.native.s"])
    return (output / "fragment.native.s").read_text(), report
