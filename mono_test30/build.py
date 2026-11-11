#!/usr/bin/env python3
"""Compile only: never load or execute the resulting gfx1250 code object."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-bin", type=Path,
                        default=Path("/home/feifei/repo/llvm-project-asm-contract/build-contract/bin"))
    parser.add_argument("--output", type=Path, default=ROOT/"build")
    args = parser.parse_args()
    out, llvm = args.output.resolve(), args.llvm_bin.resolve()
    for key,value in {
        "ARCH":"gfx1250", "FLYDSL_GPU_ARCH":"gfx1250", "COMPILE_ONLY":"1",
        "FLYDSL_RUNTIME_ENABLE_CACHE":"0", "FLYDSL_COMPILE_LLVM_DIR":"",
        "FLYDSL_RUNTIME_CACHE_DIR":str(out/"cache"),
    }.items():
        os.environ[key] = value
    from build_support import begin_build, pack_stage
    begin_build(out)
    _,audit = pack_stage(llvm,out/"stage")
    print("[compiled] independent full WQKV ASM",flush=True)
    import flydsl.expr as fx
    from compiler import asm_codegen, CompileOnlyComplete
    from mono_kernel import build_mono, SYMBOL
    from mono1250.plan.trace import recording
    manifest=out/"stage/wqkv.contract.json"
    launch=build_mono(manifest)
    state=None
    try:
        with recording() as trace:
            with asm_codegen(manifest,llvm,out,symbol=SYMBOL,assert_full_wave_calls=True) as state:
                # Only Python tracing runs: the compiler hook raises before launch.
                launch(*([0]*15),stream=fx.Stream(0))
    except CompileOnlyComplete as done:
        if str(done)!=SYMBOL:
            raise
    else:
        raise RuntimeError("compile-only hook did not stop execution; refusing GPU launch")
    if not state or "report" not in state:
        raise RuntimeError("missing actual compiler report")
    accesses=[{"stage":a.stage,"region":a.region,"space":a.space.value,"kind":a.kind} for a in trace.accesses]
    expected={("x8","poll"),("x8s","poll"),("qkv","put")}
    actual={(a["region"],a["kind"]) for a in accesses if a["stage"]=="k1.wqkv_a"}
    if not expected <= actual:
        raise RuntimeError("opaque stage is missing plan effects")
    (out/"plan.accesses.json").write_text(json.dumps(accesses,indent=2)+"\n")
    state["report"]["stage_audit"]=audit
    (out/"result.json").write_text(json.dumps(state["report"],indent=2)+"\n")
    print(json.dumps({key:state["report"][key] for key in
                      ("status","kernel","metadata","device_calls","strict_policy_status","gpu_execution")},indent=2))


if __name__=="__main__":
    main()
