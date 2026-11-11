#!/usr/bin/env python3
"""Preprocess ASM/FlyDSL, compile native fragments and link one gfx1250 kernel.

This command builds only. It never runs unit tests or launches a GPU kernel.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from contract import ROOT, StepArgs, source_layout
from fragments import SEGMENTS, STAGES, reviewed_source
from native import aggregate, expand, extract, require


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    name: str
    segment: str
    abi: str


def parse(source):
    lines = source.splitlines(keepends=True)
    blocks, opened, declarations, in_macro = [], None, {}, False
    for i, line in enumerate(lines):
        text = line.strip()
        if not text or text.startswith("//"):
            continue
        if text.startswith(".macro "):
            in_macro = True
        elif text == ".endm":
            in_macro = False
        match = re.fullmatch(r"\.flydsl.begin ([A-Za-z_][A-Za-z0-9_]*)", text)
        if match:
            require(opened is None and not in_macro, "Nested/macro FlyDSL blocks unsupported")
            require(match[1] in STAGES, f"Unknown stage {match[1]}")
            opened, declarations = (i, match[1]), {}
            continue
        if text == ".flydsl.end":
            require(opened is not None, "Unmatched .flydsl.end")
            require(set(declarations) == {"function", "segment", "abi"}, "Incomplete FlyDSL block")
            require(declarations["function"] == "fragments.py:" + opened[1], "Unreviewed stage function")
            require(declarations["segment"] in ("target", "draft", "both"), "Invalid segment")
            require(declarations["segment"] == SEGMENTS[opened[1]], "Segment differs from reviewed stage registry")
            require(declarations["abi"] == "leaf-ccc-inline", "Unsupported ABI")
            blocks.append(Block(opened[0], i, opened[1], declarations["segment"], declarations["abi"]))
            opened = None
            continue
        if opened is not None:
            match = re.fullmatch(r"\.flydsl\.(function|segment|abi) ([^\s]+)", text)
            require(match is not None, f"Unexpected fragment line: {text}")
            require(match[1] not in declarations, "Duplicate fragment declaration")
            declarations[match[1]] = match[2]
        else:
            require(".flydsl." not in text, f"Unexpected directive outside a block: {text}")
    require(opened is None, "Unclosed FlyDSL block")
    names = [block.name for block in blocks]
    require(len(names) == len(set(names)), "Duplicate stage block")
    require(set(names) == set(STAGES), "Scheduler must contain every reviewed stage exactly once")
    return lines, blocks


NON_LAYER = {"target_state", "target_front", "draft_meta", "draft_state", "draft_front",
             "target_tail", "draft_tail", "epoch_begin", "epoch_end",
             "handoff_target_state", "handoff_target_front", "handoff_draft_state", "handoff_draft_front"}


def variants(block, cfg):
    name, part = block.name, cfg["part"]
    # Epoch belongs to the launch, including an empty split-draft launch.
    if name in ("epoch_begin", "epoch_end"):
        return (False,)
    if name == "target_tail":
        return (False,) if part == "target" or (part == "all" and cfg["draft_layers"] > 0) else ()
    if name == "draft_tail":
        return (True,) if part != "target" and cfg["draft_layers"] > 0 else ()
    target = part != "draft" and (name in NON_LAYER or cfg["target_layers"] > 0)
    draft = part != "target" and cfg["draft_layers"] > 0
    result = []
    if target and block.segment in ("target", "both"):
        result.append(False)
    if draft and block.segment in ("draft", "both"):
        result.append(True)
    return tuple(result)


def preprocess(lines, blocks, cfg, native):
    output, cursor = [], 0
    for number, block in enumerate(blocks):
        output.extend(lines[cursor:block.start])
        active = variants(block, cfg)
        if not active:
            output.append(f"// {block.name}: unreachable in this compile-time configuration.\n")
        elif len(active) == 1:
            key = (block.name, active[0])
            require(key in native, f"Missing reachable fragment: {key}")
            output.append(expand(native[key], f"b{number}_{'d' if active[0] else 't'}"))
        else:
            prefix = f".Ldispatch_{number}"
            output.append(f"    s_cmp_eq_u32 s52, 0\n    STEP_CJMP scc0, {prefix}_draft\n")
            for draft in active:
                key = (block.name, draft)
                require(key in native, f"Missing reachable fragment: {key}")
                if draft:
                    output.append(prefix + "_draft:\n")
                output.append(expand(native[key], f"b{number}_{'d' if draft else 't'}"))
                if not draft:
                    output.append(f"    STEP_JMP {prefix}_end\n")
            output.append(prefix + "_end:\n")
        cursor = block.end + 1
    output.extend(lines[cursor:])
    generated = "".join(output)
    require(not re.search(r"^\s*\.flydsl\.", generated, re.M), "Preprocessing left custom directives")
    return generated


def constants(cfg):
    values = {
        "STEP_PART": cfg["part_number"], "TARGET_ROWS": cfg["target_rows"],
        "DRAFT_ROWS": cfg["draft_rows"], "TARGET_LAYERS": cfg["target_layers"],
        "DRAFT_LAYERS": cfg["draft_layers"], "FRONT_CTAS": cfg["front_ctas"],
        "SCHED_LDS": cfg["scheduler_lds_offset"], "IDX_LEVELS": 2,
        "LAYER_TABLE_OFFSET": (len(cfg["fp_names"]) + len(cfg["attention_names"])) * 8,
        "LAYER_ROW_BYTES": len(cfg["layer_names"]) * 8,
    }
    values.update({"LK_" + key: i * 8 for i, key in enumerate(cfg["layer_names"])})
    return "".join(f".set {name}, {value}\n" for name, value in values.items())


def resource_include(resource):
    names = {"STEP_VGPR": "vgpr", "STEP_SGPR": "numbered_sgpr", "STEP_PRIVATE": "private",
             "STEP_VCC": "vcc", "STEP_SCRATCH": "scratch", "STEP_NAMED_BARRIERS": "named_barriers"}
    return "".join(f".set {name}, {resource[key]}\n" for name, key in names.items())


def metadata(cfg, resource):
    args = ""
    for name, ty in StepArgs._fields_:
        if name == "_padding":
            continue
        import ctypes
        args += (f"      - .name: {name}\n        .offset: {getattr(StepArgs, name).offset}\n"
                 f"        .size: {ctypes.sizeof(ty)}\n        .value_kind: by_value\n")
    return f""".amdgpu_metadata
---
amdhsa.version: [1, 2]
amdhsa.target: amdgcn-amd-amdhsa--gfx1250
amdhsa.kernels:
  - .name: {cfg['symbol']}
    .symbol: {cfg['symbol']}.kd
    .kernarg_segment_size: 72
    .kernarg_segment_align: 8
    .group_segment_fixed_size: 0
    .private_segment_fixed_size: {resource['private']}
    .wavefront_size: 32
    .sgpr_count: {resource['sgpr']}
    .vgpr_count: {resource['vgpr']}
    .max_flat_workgroup_size: 256
    .reqd_workgroup_size: [256, 1, 1]
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
    .args:
{args}...
.end_amdgpu_metadata
"""


def build(cfg, output, llvm_bin, source=ROOT / "step.s"):
    from export import configure, export_fragment, run
    from elf import audit_binary

    output, llvm_bin = Path(output).resolve(), Path(llvm_bin).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name in ("kernel.co", "kernel.pending.co", "step.generated.s", "build_report.json", "manifest.json"):
        (output / name).unlink(missing_ok=True)
    report = {"status": "BUILDING_NOT_TESTED", "gpu_execution": False, "tests_executed": False,
              "config": cfg, "exports": {}}
    try:
        configure(output)
        for tool in ("llc", "opt", "llvm-mc", "ld.lld", "llvm-objdump", "llvm-readelf"):
            require((llvm_bin / tool).is_file(), f"Missing LLVM tool: {tool}")
        reviewed_source()
        source_text = Path(source).read_text()
        lines, blocks = parse(source_text)
        natives = {}
        for block in blocks:
            for draft in variants(block, cfg):
                key = (block.name, draft)
                variant = f"{'draft' if draft else 'target'}/{block.name}"
                print(f"[compile-only] {variant}", flush=True)
                text, details = export_fragment(block.name, cfg, draft, output / "fragments" / variant, llvm_bin)
                natives[key] = extract(text, details["symbol"])
                details["resources"] = natives[key].resources
                report["exports"][variant] = details
        resource = aggregate(natives.values())
        generated = preprocess(lines, blocks, cfg, natives)
        (output / "step.generated.s").write_text(generated)
        (output / "constants.inc").write_text(constants(cfg))
        (output / "resources.inc").write_text(resource_include(resource))
        (output / "metadata.inc").write_text(metadata(cfg, resource))
        run([llvm_bin / "llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
             "-mattr=+wavefrontsize32,+real-true16", "-filetype=obj", "-I", output,
             output / "step.generated.s", "-o", output / "kernel.o"])
        pending = output / "kernel.pending.co"
        run([llvm_bin / "ld.lld", "-shared", "--no-undefined", output / "kernel.o", "-o", pending])
        report["elf_audit"] = audit_binary(pending.read_bytes(), cfg, resource)
        (output / "kernel.disasm.txt").write_text(run([
            llvm_bin / "llvm-objdump", "--mcpu=gfx1250", "--mattr=+real-true16", "-d", pending]))
        (output / "kernel.elf.txt").write_text(run([llvm_bin / "llvm-readelf", "-h", "-s", "-r", "-n", pending]))
        report["resources"] = resource
        report["llvm_version"] = run([llvm_bin / "llc", "--version"]).splitlines()[0]
        import importlib.metadata
        report["flydsl_version"] = importlib.metadata.version("flydsl")
        report["binary_sha256"] = hashlib.sha256(pending.read_bytes()).hexdigest()
        report["local_sources_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in ROOT.iterdir() if p.suffix in (".py", ".s")}
        pending.replace(output / "kernel.co")
        manifest = dict(cfg, status="BUILT_NOT_TESTED", compute_stages_implemented=True,
                        code_object=str(output / "kernel.co"), binary_sha256=report["binary_sha256"],
                        resources=resource, elf_audit=report["elf_audit"], tests_executed=False)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        report["status"] = "BUILT_NOT_TESTED"
        print(f"Built {output / 'kernel.co'} (no tests or GPU execution)", flush=True)
        return manifest
    except Exception as error:
        for name in ("kernel.co", "kernel.pending.co", "manifest.json"):
            (output / name).unlink(missing_ok=True)
        report.update(status="BUILD_FAILED_NOT_TESTED", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        (output / "build_report.json").write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=6)
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--layers", type=int, default=40)
    parser.add_argument("--draft-layers", type=int, default=3)
    parser.add_argument("--part", choices=("all", "target", "draft"), default="all")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--llvm-bin", type=Path, default=Path("/opt/rocm/lib/llvm/bin"))
    args = parser.parse_args()
    cfg = source_layout(args.rows, args.rank, args.part, args.layers, args.draft_layers)
    build(cfg, args.build_dir, args.llvm_bin)


if __name__ == "__main__":
    main()
