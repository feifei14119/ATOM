#!/usr/bin/env python3
"""Single-device A/B test: native Mono vs Mono with standard-ABI bitcode wrapper dq conversion."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
THREADS, GRID = 256, 256
COMMIT = "7c925f72b22ee6a815fd6d63734bbcff5fa72a08"


def write_report(report):
    BUILD.mkdir(exist_ok=True)
    temporary = BUILD / "result.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(BUILD / "result.json")


def versions():
    out = {"python": sys.version, "platform": platform.platform()}
    for name in ("torch", "flydsl", "amd-aiter", "aiter", "triton"):
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return out


def source_fingerprints():
    # Record edited copies too, so a future ASM experiment has its own identity.
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(ROOT.rglob("*")) if path.is_file()
            and path.suffix in (".py", ".cpp", ".h", ".s", ".sh")
            and "build" not in path.relative_to(ROOT).parts}


def compile_and_check(report, hip, stream, properties, variant):
    from mono1250.kernels.reference_projection import build_projection_c1, projection_symbol
    from mono1250.runtime.compile import compile_only, _code_object, kernel_resources, _note_uint

    print(f"[compile/{variant}] slice -> RMSNorm/FP8 -> WQKV; 256 CTAs x 256 threads, wave32", flush=True)
    # feeds_index here ONLY exposes normed/NB for the oracle. This builder has
    # no index_query/scoring stages. fold=False has no previous-layer dependency.
    if variant == "native":
        launch = build_projection_c1(front=True, fold=False, feeds_index=True, threads=THREADS)
        symbol = projection_symbol(True, False, True, THREADS)
        argc = 14
    else:
        from mono1250.kernels.projection_asm import build_projection_asm, asm_symbol
        launch, symbol, argc = build_projection_asm(), asm_symbol(), 15
    with compile_only():
        launch(*([0] * argc), stream=stream)
    artifacts = list(launch._mem_cache.values())
    if len(artifacts) != 1:
        raise RuntimeError(f"Expected one compiled artifact, got {len(artifacts)}; FlyDSL API changed?")
    module_text = artifacts[0]._ir_text
    binary = _code_object(module_text)
    if not binary.startswith(b"\x7fELF"):
        raise RuntimeError("FlyDSL did not produce an ELF code object")
    artifact_dir = BUILD / variant
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "kernel.mlir").write_text(module_text)
    (artifact_dir / "kernel.co").write_bytes(binary)
    resource = kernel_resources(binary)
    resource["wavefront_size"] = _note_uint(binary, b".wavefront_size")
    resource["kernarg_bytes"] = _note_uint(binary, b".kernarg_segment_size")
    resource["sha256"] = hashlib.sha256(binary).hexdigest()
    resource["symbol"] = symbol
    report.setdefault("kernels", {})[variant] = resource
    write_report(report)
    if resource["wavefront_size"] != 32:
        raise RuntimeError(f"Wrong wavefront size: {resource['wavefront_size']}")
    # The original FlyDSL launcher packs the arguments. Record kernarg size,
    # rather than assuming a particular compiler's hidden-argument layout.
    # Spills are reported, not automatically rejected: the HIP occupancy answer
    # for this actual binary is the criterion for this correctness test.
    residency = hip.occupancy(binary, symbol, THREADS, properties.multi_processor_count, GRID)
    report.setdefault("residency", {})[variant] = residency
    (artifact_dir / "resources.json").write_text(json.dumps({"kernel": resource, "residency": residency}, indent=2) + "\n")
    if variant == "ffi":
        from wrapper_audit import audit_linked_wrapper
        report["wrapper_boundary"] = audit_linked_wrapper(
            artifact_dir / "kernel.co", symbol, resource, BUILD / "asm",
            Path(report["options"]["llvm_bin"]))
        (artifact_dir / "boundary.json").write_text(json.dumps(report["wrapper_boundary"], indent=2) + "\n")
        wrapper_bc = BUILD / "wrapper/dq_wrapper.bc"
        if hashlib.sha256(wrapper_bc.read_bytes()).hexdigest() != report["wrapper_build"]["bitcode_sha256"]:
            raise RuntimeError("Wrapper bitcode changed during Mono compilation")
    tool = Path(report["options"]["llvm_bin"]) / "llvm-objdump"
    executable = str(tool) if tool.is_file() else shutil.which("llvm-objdump")
    if executable:
        result = subprocess.run([executable, "--mcpu=gfx1250", "-d", str(artifact_dir / "kernel.co")], capture_output=True, text=True)
        (artifact_dir / "kernel.disasm.txt").write_text(result.stdout + result.stderr)
        report.setdefault("disassembly_exit_code", {})[variant] = result.returncode
    print(f"[resources/{variant}] " + json.dumps(resource), flush=True)
    print(f"[residency/{variant}] " + json.dumps(residency), flush=True)
    return launch, hashlib.sha256(binary).hexdigest()


def run_cases(args, report, hip, stream, launchers, binary_shas):
    import torch
    from hip_runtime import Buffer
    from reference import make_inputs, verify, exact, HIDDEN, HC, ROWS, MIX, SLICES
    from mono1250.kernels.reference_plan import C1ReferencePlan
    from mono1250.runtime.compile import _code_object
    from asm_host import DqWorkspace

    layout = C1ReferencePlan(feeds_index=True).k1_scratch_layout()
    scratch_bytes = max(offset + size for offset, size in layout.values())
    scratch_init = torch.full((scratch_bytes // 4,), 0x5A5A5A5A, dtype=torch.int32)
    scratch_init[1::2] = 0  # stale tags; every launch deliberately reuses tag 1
    written = {"lin", "pmix", "x8", "x8s", "nb", "qkv"}
    buffers = {}
    outputs = {}
    inp = None
    workspace = None
    try:
        workspace = DqWorkspace(hip)
        for repeat in range(args.repeat):
            for number, case in enumerate(args.cases):
                inp, outputs = None, {}
                seed = args.seed + repeat * 1009 + number * 37
                report["active_case"] = {"name": case, "repeat": repeat, "seed": seed}
                write_report(report)
                print(f"[case] {case}, repeat={repeat}, seed={seed}, layer=0/tag=1", flush=True)
                inp = make_inputs(case, seed)
                payloads = {
                    "res_in": inp.residual,
                    "pend": torch.zeros(HIDDEN, dtype=torch.bfloat16),
                    "post_in": torch.zeros(HC, dtype=torch.float32),
                    "comb_in": torch.zeros(HC, HC, dtype=torch.float32),
                    "pre_in": inp.pre,
                    "hc_fn": inp.hc_fn,
                    "res_out": torch.full((HC, HIDDEN), -37.5, dtype=torch.bfloat16),
                    "scratch": scratch_init,
                    "diag": torch.zeros(GRID * 8 + 1, dtype=torch.int32),
                    "layer": torch.zeros(1, dtype=torch.int32),
                    "attn_w": inp.norm_weight,
                    "normed": torch.full((HIDDEN,), float("nan"), dtype=torch.bfloat16),
                    "weight": inp.packed_weight,
                    "scale": inp.weight_scale,
                }
                all_outputs, metrics = {}, {}
                for variant in ("native", "ffi"):
                    report["active_case"]["variant"] = variant
                    write_report(report)
                    for name, payload in payloads.items():
                        if name not in buffers:
                            buffers[name] = Buffer(hip, name, payload.numel() * payload.element_size(),
                                                   uncached=name in ("scratch", "diag"))
                        buffers[name].upload(payload)
                    pointers = [buffers[name].ptr for name in payloads]
                    if variant == "ffi":
                        workspace.reset(seed)
                        pointers.append(workspace.args.ptr)
                    # One fused launch per variant. The ASM is inside a callable wrapper;
                    # it is never launched as a separate GPU kernel.
                    launch = launchers[variant]
                    launch(*pointers, stream=stream)
                    torch.cuda.current_stream().synchronize()
                    report["gpu_launches"] += 1
                    current = list(launch._mem_cache.values())
                    if len(current) != 1 or hashlib.sha256(_code_object(current[0]._ir_text)).hexdigest() != binary_shas[variant]:
                        raise RuntimeError("Launch used a different binary from the residency-checked artifact")
                    raw = {name: buf.download(immutable=name not in ("scratch", "diag", "normed"))
                           for name, buf in buffers.items()}
                    diag = raw["diag"].view(torch.int32)
                    if bool(diag.any()):
                        (BUILD / "mailbox_failure.json").write_text(json.dumps(diag.tolist()) + "\n")
                        raise AssertionError(f"{variant}: mailbox polling failed; failure word={diag[-1].item()}")
                    words = raw["scratch"].view(torch.int32)
                    region = {}
                    for name, (offset, nbytes) in layout.items():
                        data = words[offset // 4:(offset + nbytes) // 4]
                        if name in written:
                            pairs = data.reshape(-1, 2)
                            exact(variant + "/" + name + " tags", pairs[:, 1], torch.ones_like(pairs[:, 1]))
                            region[name] = pairs[:, 0].contiguous()
                        else:
                            exact(name + " untouched", data, scratch_init[offset // 4:(offset + nbytes) // 4])
                    outputs = {
                        "lin": region["lin"].view(torch.bfloat16),
                        "pmix": region["pmix"].view(torch.float32).reshape(SLICES, MIX + 1),
                        "x8": region["x8"].view(torch.uint8),
                        "x8s": region["x8s"],
                        "qkv": region["qkv"].view(torch.float32),
                        "nb": region["nb"].view(torch.bfloat16),
                        "normed": raw["normed"].view(torch.bfloat16),
                    }
                    exact("QKV shape", torch.tensor(outputs["qkv"].numel()), torch.tensor(ROWS))
                    metrics[variant] = verify(inp, outputs)
                    if case != "zero" and metrics[variant]["qkv_nonzero"] == 0:
                        raise AssertionError("Nonzero test produced an all-zero QKV")
                    if variant == "ffi":
                        metrics[variant]["asm_tiles"] = workspace.verify(outputs["qkv"])
                        report["asm_task_invocations"] += metrics[variant]["asm_tiles"]["tasks"]
                    all_outputs[variant] = outputs
                for name, native in all_outputs["native"].items():
                    exact("A/B " + name, all_outputs["ffi"][name].view(torch.uint8), native.view(torch.uint8))
                report["active_case"].pop("variant")
                record = dict(report["active_case"], status="PASS", ab_bitwise="PASS", metrics=metrics)
                report["tests"].append(record)
                write_report(report)
                print(f"[PASS] {case}: native/ASM bitwise match; 112 full ASM tiles and post-ASM QKV publication OK", flush=True)
        report.pop("active_case", None)
    except Exception:
        # CPU-only reproduction data; preserve the exact failing inputs/output.
        if inp is not None:
            torch.save({"case": report.get("active_case"), "residual": inp.residual,
                        "pre": inp.pre, "hc_fn": inp.hc_fn, "norm_weight": inp.norm_weight,
                        "weight_bytes": inp.weight_fp8.view(torch.uint8), "scale": inp.weight_scale,
                        "outputs": outputs}, BUILD / "failure.pt")
        raise
    finally:
        # No additional launches. Kernel execution is synchronized above.
        for buffer in buffers.values():
            buffer.close()
        if workspace is not None:
            workspace.close()


def main(args, report):
    import torch
    if torch.version.hip is None or not torch.cuda.is_available():
        raise RuntimeError("A ROCm-enabled PyTorch installation and a gfx1250 GPU are required")
    if args.device < 0 or args.device >= torch.cuda.device_count():
        raise ValueError(f"Device {args.device} is outside the visible device list")
    torch.cuda.set_device(args.device)
    torch.cuda.init()
    prop = torch.cuda.get_device_properties(args.device)
    arch = prop.gcnArchName.split(":", 1)[0]
    report["device"] = {"index": args.device, "name": prop.name, "arch": prop.gcnArchName,
                        "cus": prop.multi_processor_count, "rocm": torch.version.hip}
    write_report(report)
    if arch != "gfx1250":
        raise RuntimeError(f"This test requires gfx1250; selected device is {arch}. It will not silently skip.")
    if not hasattr(torch, "float8_e4m3fn"):
        raise RuntimeError("PyTorch must provide torch.float8_e4m3fn (OCP FP8)")
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    # Native FlyDSL external-bitcode support; no compiler hook or MIR edits.
    import flydsl
    import flydsl.expr as fx
    from flydsl.expr import rocdl
    from flydsl.expr.extern import ffi
    from flydsl.compiler.extern_link import link_extern
    import aiter
    if not hasattr(rocdl, "WMMAScale"):
        raise RuntimeError("FlyDSL lacks rocdl.WMMAScale; install the gfx1250-capable AITER/FlyDSL environment")
    if not callable(ffi) or not callable(link_extern):
        raise RuntimeError("FlyDSL ffi + link_extern APIs are required")
    from build_wrapper import build
    llvm_bin = Path(args.llvm_bin).resolve()
    report["options"]["llvm_bin"] = str(llvm_bin)
    report["wrapper_build"] = build(llvm_bin)
    write_report(report)
    from hip_runtime import Hip
    report["modules"] = {"flydsl": flydsl.__file__, "aiter": aiter.__file__}
    hip = Hip()
    report["hip_library"] = hip.path
    stream = fx.Stream(torch.cuda.current_stream())
    print("[device] " + json.dumps(report["device"]), flush=True)
    launchers, binary_shas = {}, {}
    for variant in ("native", "ffi"):
        launchers[variant], binary_shas[variant] = compile_and_check(report, hip, stream, prop, variant)
    run_cases(args, report, hip, stream, launchers, binary_shas)
    expected = len(args.cases) * args.repeat
    if (len(report["tests"]) != expected or report["gpu_launches"] != 2 * expected
            or report["asm_task_invocations"] != 112 * expected):
        raise RuntimeError("Not all requested cases completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=int, default=0, help="logical HIP device index (default: 0)")
    parser.add_argument("--repeat", type=int, default=3, help="repetitions with changed inputs (default: 3)")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--llvm-bin", default=str(Path(os.environ.get("ROCM_PATH", "/opt/rocm")) / "llvm/bin"))
    parser.add_argument("--cases", nargs="+", choices=("zero", "pattern", "random"), default=["zero", "pattern", "random"])
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    # Also isolate caches when invoking this file directly instead of run.sh.
    for key, value in {
        "ARCH": "gfx1250", "GPU_ARCHS": "gfx1250", "COMPILE_ONLY": "0",
        "FLYDSL_RUNTIME_ENABLE_CACHE": "0",
        "FLYDSL_COMPILE_LLVM_DIR": "",
        "FLYDSL_RUNTIME_CACHE_DIR": str(BUILD / "cache/flydsl"),
        "AITER_JIT_DIR": str(BUILD / "cache/aiter"),
        "TORCH_EXTENSIONS_DIR": str(BUILD / "cache/torch_extensions"),
        "TRITON_CACHE_DIR": str(BUILD / "cache/triton"),
        "XDG_CACHE_HOME": str(BUILD / "cache/xdg"),
    }.items():
        os.environ[key] = value
    sys.dont_write_bytecode = True
    report = {"status": "RUNNING", "upstream_commit": COMMIT, "options": vars(args),
              "versions": versions(), "source_sha256": source_fingerprints(), "tests": [], "gpu_launches": 0,
              "asm_task_invocations": 0}
    write_report(report)
    started = time.monotonic()
    try:
        main(args, report)
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
        report["traceback"] = traceback.format_exc()
        traceback.print_exc()
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        write_report(report)
    if report["status"] != "PASS":
        print(f"[FAIL] See {BUILD / 'result.json'}", flush=True)
        sys.exit(1)
    print(f"[PASS] {len(report['tests'])} A/B pairs, {report['gpu_launches']} fused launches, "
          f"{report['asm_task_invocations']} ASM task invocations; {BUILD / 'result.json'}", flush=True)
