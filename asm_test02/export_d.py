#!/usr/bin/env python3
"""Trace the pure FlyDSL D into an ordinary LLVM i32(i32,i32) function.

Uses the direct func/arith lowering demonstrated in callee_test21. No kernel
launch, JIT execution engine, inline ASM insertion or register remapping.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def trace(output):
    os.environ.update(ARCH="gfx1250", FLYDSL_GPU_ARCH="gfx1250", COMPILE_ONLY="1")
    import flydsl.expr as fx
    from flydsl._mlir import ir
    from flydsl._mlir.dialects import func
    from flydsl._mlir.passmanager import PassManager
    from flydsl._mlir._mlir_libs._mlirDialectsLLVM import translate_module_to_llvmir
    from flydsl.compiler.jit_function import _create_mlir_context
    from kernel_D import kernel_D

    with _create_mlir_context(), ir.Location.unknown():
        module = ir.Module.create()
        with ir.InsertionPoint(module.body):
            i32 = ir.IntegerType.get_signless(32)
            fn = func.FuncOp("kernel_D", ([i32, i32], [i32]))
            block = fn.add_entry_block()
            with ir.InsertionPoint(block):
                result = kernel_D(*[fx.Uint32(arg) for arg in block.arguments])
                require(isinstance(result, fx.Uint32), "D must return one FlyDSL Uint32")
                func.ReturnOp([result.ir_value()])
        module.operation.verify()

        def walk(op):
            yield op
            for region in op.regions:
                for block in region.blocks:
                    for child in block.operations:
                        yield from walk(child.operation)

        allowed = {"builtin.module", "func.func", "func.return", "arith.constant", "arith.muli", "arith.addi"}
        require(all(op.name in allowed for op in walk(module.operation)),
                "D exporter supports only pure i32 multiply/add/constant")
        (output / "kernel_D.mlir").write_text(str(module) + "\n")
        pm = PassManager.parse("builtin.module(convert-arith-to-llvm,convert-func-to-llvm,reconcile-unrealized-casts)")
        pm.enable_verifier(True)
        pm.run(module.operation)
        llvm_fn = next(op for op in module.body.operations if op.operation.name == "llvm.func")
        llvm_fn.attributes["CConv"] = ir.Attribute.parse("#llvm.cconv<ccc>")
        llvm_fn.attributes["visibility_"] = ir.IntegerAttr.get(ir.IntegerType.get_signless(64), 2)
        llvm_fn.attributes["passthrough"] = ir.ArrayAttr.get([
            ir.StringAttr.get("noinline"), ir.StringAttr.get("nounwind")])
        module.operation.verify()
        (output / "kernel_D.lowered.mlir").write_text(str(module) + "\n")
        llvm_ir = translate_module_to_llvmir(module.operation)
        # Makefile sets llc's default HSA code object version to 6.
        require('!"amdhsa_code_object_version"' not in llvm_ir,
                "Unexpected frontend code object version override")
        (output / "kernel_D.ll").write_text(llvm_ir)
    (output / "kernel_D.export.json").write_text(json.dumps(dict(
        status="EXPORTED_NOT_EXECUTED", flydsl_version=importlib.metadata.version("flydsl"),
        symbol="kernel_D", signature="i32(i32,i32)", calling_convention="ccc",
        code_object_version=6, target="gfx1250", gpu_executed=False), indent=2) + "\n")
    print("FlyDSL D exported: i32(i32,i32), ordinary CCC function, no GPU execution")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path(__file__).resolve().parent / "build")
    output = parser.parse_args().build_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace(output)


if __name__ == "__main__":
    main()
