#!/usr/bin/env python3
"""Compile a real FlyDSL kernel through the new external-ASM contract backend.

This is build-only. The same demo/test.cpp host can launch its kernel.co using
the symbol contract_flydsl on gfx1250.
"""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-bin", type=Path,
                        default=Path("/home/feifei/repo/llvm-project-asm-contract/build-contract/bin"))
    parser.add_argument("--output", type=Path, default=ROOT/"build/flydsl")
    args = parser.parse_args()
    out = args.output.resolve()
    from demo.build import begin_build
    begin_build(out)
    for key, value in {
        "ARCH": "gfx1250", "FLYDSL_GPU_ARCH": "gfx1250", "COMPILE_ONLY": "1",
        "FLYDSL_RUNTIME_ENABLE_CACHE": "0", "FLYDSL_COMPILE_LLVM_DIR": "",
        "FLYDSL_RUNTIME_CACHE_DIR": str(out/"cache"),
    }.items():
        os.environ[key] = value
    import flydsl
    import flydsl.compiler as flyc
    import flydsl.expr as fx
    from flydsl.expr.typing import Int32, Int64
    from flydsl._mlir import ir
    from flydsl._mlir.dialects import llvm
    from demo.contract import pack_stage
    from flydsl_adapter import AsmFFI, CompileOnlyComplete, asm_codegen
    pack_stage(ROOT/"demo", out/"stage", args.llvm_bin)
    manifest = out/"stage/stage.contract.json"
    stage = AsmFFI(manifest)

    def address(value):
        return llvm.inttoptr(ir.Type.parse("!llvm.ptr<1>"), fx.Int64(value).ir_value())

    def load(value):
        return fx.Int32(llvm.load(fx.Int32.ir_type, address(value), alignment=4, volatile_=True))

    def store(value, dest):
        llvm.store(fx.Int32(value).ir_value(), address(dest), alignment=4)

    @flyc.kernel(name="contract_flydsl", known_block_size=[32, 8, 1])
    def caller(records: Int64, uniform_seed: Int64, grid_x: Int32):
        tx, ty = fx.Int32(fx.thread_idx.x), fx.Int32(fx.thread_idx.y)
        bx, by = fx.Int32(fx.block_idx.x), fx.Int32(fx.block_idx.y)
        index = (by*grid_x+bx)*256+ty*32+tx
        record = records+fx.Int64(index)*64
        before, seed = load(record), load(uniform_seed)
        live_lane = before ^ fx.Int32(0x2468ace0)
        live_uniform = seed ^ fx.Int32(0xa5a5a5a5)
        r0 = fx.Int32(stage(bx, by, record, tx, ty, 37))
        r1 = fx.Int32(stage(bx, by, record, tx, ty, 0xa13579bd))
        store(r0, record+4)
        store(r1, record+8)
        store(live_lane, record+12)
        store(live_uniform, record+16)
        store(r0 ^ r1, record+20)

    @flyc.jit
    def trace(records: Int64, seed: Int64, grid_x: Int32, stream: fx.Stream):
        caller(records, seed, grid_x).launch(grid=(3, 2, 1), block=(32, 8, 1), stream=stream)

    state = None
    try:
        with asm_codegen(manifest, args.llvm_bin, out, assert_full_wave_calls=True) as state:
            trace(0, 0, 3, stream=fx.Stream(0))
    except CompileOnlyComplete as finished:
        if str(finished) != "contract_flydsl":
            raise
    else:
        raise RuntimeError("build-only bridge did not intercept the kernel; refusing to launch")
    if not state or "report" not in state:
        raise RuntimeError("missing contract compilation report")
    state["report"]["flydsl_version"] = flydsl.__version__
    (out/"result.json").write_text(json.dumps(state["report"], indent=2)+"\n")
    print(json.dumps({key: state["report"][key] for key in
                      ("status", "kernel", "metadata", "device_calls", "strict_policy_status", "gpu_execution", "flydsl_version")}, indent=2))
    print("Detailed report:", out/"result.json")


if __name__ == "__main__":
    main()
