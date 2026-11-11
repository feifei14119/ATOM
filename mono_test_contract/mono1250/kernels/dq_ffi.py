"""Supplier dq_convert as a register-contract call: no wrapper, no call ABI."""
import os
from functools import lru_cache
from pathlib import Path

import flydsl.expr as fx
from flydsl._mlir.dialects import llvm
from flydsl.compiler.asm_contract import ffi_contract

SIDECAR = Path(os.environ.get('MONO_CONTRACT_SIDECAR') or
               Path(__file__).resolve().parents[2]/'build/contract/dq_convert.contract.json')


@lru_cache(None)
def dq_convert():
    if not SIDECAR.is_file():
        raise RuntimeError('Pack the contract first with build_contract.py or run.sh')
    return ffi_contract(SIDECAR)


def drain_global():
    llvm.inline_asm(None, [], 's_wait_storecnt 0\ns_wait_loadcnt 0\n', '~{memory}',
                    has_side_effects=True, is_align_stack=False,
                    asm_dialect=llvm.AsmDialect.AD_ATT)


def invoke_dq_convert(args_address, tid):
    tid = fx.Int32(tid)
    dq_convert()(args=fx.Int64(args_address), lane=tid & 31, wave=tid >> 5)
