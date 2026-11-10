"""Emit an actual C-ABI external call, with a pre-RA low-context regmask later."""
import flydsl.expr as fx
from flydsl._mlir import ir
from flydsl._mlir.dialects import llvm
from flydsl.compiler.kernel_function import CompilationContext

CALLEE = 'mono_dq_convert_lowctx'
DECLARATION = '''llvm.func @mono_dq_convert_lowctx(!llvm.ptr, i32)
    attributes {passthrough = ["noinline", "convergent", "noduplicate", "nounwind"]}'''


def drain_global():
    llvm.inline_asm(None, [], 's_wait_storecnt 0\ns_wait_loadcnt 0\n', '~{memory}',
                    has_side_effects=True, is_align_stack=False,
                    asm_dialect=llvm.AsmDialect.AD_ATT)


def invoke_dq_convert(args_address, tid):
    ctx = CompilationContext.get_current()
    if ctx is None:
        raise RuntimeError('dq_convert must be emitted inside a FlyDSL compilation context')
    block = ctx.gpu_module_body
    declarations = [op for op in block.operations if 'sym_name' in op.attributes
                    and ir.StringAttr(op.attributes['sym_name']).value == CALLEE]
    if not declarations:
        template = ir.Module.parse('module { '+DECLARATION+' }')
        declaration = list(template.body.operations)[0].operation.clone(ip=False)
        ir.InsertionPoint.at_block_begin(block).insert(declaration)
    else:
        assert len(declarations) == 1
    ptr = llvm.inttoptr(ir.Type.parse('!llvm.ptr'), fx.Int64(args_address).ir_value())
    linear_tid = fx.Int32(tid).ir_value()
    # Resource floors, as in callee_test01. Empty asm emits no instruction.
    # This is NOT the call's preservation mask and NOT an allocation ceiling.
    llvm.inline_asm(None, [], '', '~{v69},~{s48}', has_side_effects=True,
                    is_align_stack=False, asm_dialect=llvm.AsmDialect.AD_ATT)
    # Parsing a canonical call template avoids version-dependent positional
    # arguments in generated Python CallOp bindings. Clone only the call and
    # substitute its two operands; no helper function enters the GPU module.
    template = ir.Module.parse('''module {
      '''+DECLARATION+'''
      llvm.func @__call_template(%arg0: !llvm.ptr, %arg1: i32) {
        llvm.call @mono_dq_convert_lowctx(%arg0, %arg1) {convergent} : (!llvm.ptr, i32) -> ()
        llvm.return
      }
    }''')
    helper = list(template.body.operations)[1]
    call = list(helper.regions[0].blocks[0].operations)[0].operation.clone(ip=False)
    call.operands[0], call.operands[1] = ptr, linear_tid
    ir.InsertionPoint.current.insert(call)
