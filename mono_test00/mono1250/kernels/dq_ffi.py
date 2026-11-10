"""Standard FlyDSL FFI + bitcode linking; no custom compiler or MIR pipeline."""
from pathlib import Path

import flydsl.expr as fx
from flydsl._mlir import ir
from flydsl._mlir.dialects import llvm
from flydsl.expr.extern import ffi
from flydsl.compiler.extern_link import link_extern

WRAPPER = 'mono_dq_convert_wrapper'
BITCODE = Path(__file__).resolve().parents[2]/'build/wrapper/dq_wrapper.bc'
stage = link_extern(
    ffi(WRAPPER, ['uint64', 'uint32'], 'void', is_pure=False),
    bitcode_path=str(BITCODE),
)


def drain_global():
    llvm.inline_asm(None, [], 's_wait_storecnt 0\ns_wait_loadcnt 0\n', '~{memory}',
                    has_side_effects=True, is_align_stack=False,
                    asm_dialect=llvm.AsmDialect.AD_ATT)


def invoke_dq_convert(args_address, tid):
    if not BITCODE.is_file():
        raise RuntimeError('Build the wrapper first with build_wrapper.py or run.sh')
    block = ir.InsertionPoint.current.block
    previous = {op.operation for op in block.operations}
    stage(fx.Int64(args_address), fx.Int32(tid))
    # Current ffi emits a C-convention call but has no convergence option.
    # Add only that semantic attribute to the call it just emitted, before
    # MLIR optimization. The linked BC definition also carries convergent,
    # and noinline. Registers/resources are left to normal LLVM.
    calls = [op for op in block.operations if op.operation not in previous
             and op.operation.name == 'llvm.call' and 'callee' in op.attributes
             and ir.FlatSymbolRefAttr(op.attributes['callee']).value == WRAPPER]
    if len(calls) != 1:
        raise RuntimeError('ffi must emit one direct call to the wrapper; API changed?')
    calls[0].attributes['convergent'] = ir.UnitAttr.get()
