#!/usr/bin/env python3
"""离线汇编 ASM 调度壳；不导入 torch，不加载 HIP，不执行 GPU kernel。"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
from pathlib import Path

from contract import ROOT, SYMBOL, StepArgs, source_layout


def run(argv):
    return subprocess.check_output([str(v) for v in argv], text=True)


def write_includes(out, cfg):
    """生成实际表偏移和 kernarg metadata；不手工维护 FPTRS/LKEYS 索引。"""
    constants = {
        "ASM_SYNTAX_ONLY": 1,
        "STEP_PART": cfg["part_number"], "BUILD_RANK": cfg["rank"],
        "TARGET_ROWS": cfg["target_rows"], "DRAFT_ROWS": cfg["draft_rows"],
        "TARGET_LAYERS": cfg["target_layers"], "DRAFT_LAYERS": cfg["draft_layers"],
        "FRONT_CTAS": cfg["front_ctas"], "RECV_HALF": cfg["recv_half_bytes"],
        "IDX_LEVELS": 2,
        "LAYER_TABLE_OFFSET": 8 * (len(cfg["fp_names"]) + len(cfg["attention_names"])),
        "LAYER_ROW_BYTES": 8 * len(cfg["layer_names"]),
    }
    constants.update({f"LY_{key}": value for key, value in cfg["layout"].items()})
    for prefix, names, start in (
        ("FP", cfg["fp_names"], 0),
        ("AT", cfg["attention_names"], 8 * len(cfg["fp_names"])),
        ("LK", cfg["layer_names"], 0),
        ("TP", cfg["tail_names"], 0),
    ):
        constants.update({f"{prefix}_{name}": start + 8 * i
                          for i, name in enumerate(names)})
    (out / "step_constants.inc").write_text(
        "// Generated from current step.py/layout.py; all offsets are bytes.\n"
        + "".join(f".set {key}, {value}\n" for key, value in constants.items())
    )
    args = ""
    for name, ty in StepArgs._fields_:
        if name.startswith("_"):
            continue
        args += (
            f"      - .name: {name}\n"
            f"        .offset: {getattr(StepArgs, name).offset}\n"
            f"        .size: {ctypes.sizeof(ty)}\n"
            "        .value_kind: by_value\n"
        )
    # pointers 作为 64-bit 整数按值传递，与 step.body 的 Int64 对应。
    # 没有隐式 queue_ptr / dispatch_ptr / scratch 等参数；stage 集成后需重审。
    (out / "step_metadata.inc").write_text(f""".amdgpu_metadata
---
amdhsa.version: [1, 2]
amdhsa.target: amdgcn-amd-amdhsa--gfx1250
amdhsa.kernels:
  - .name: {SYMBOL}
    .symbol: {SYMBOL}.kd
    .kernarg_segment_size: 72
    .kernarg_segment_align: 8
    .group_segment_fixed_size: 0
    .private_segment_fixed_size: 0
    .wavefront_size: 32
    .sgpr_count: 60
    .vgpr_count: 64
    .max_flat_workgroup_size: 256
    .reqd_workgroup_size: [256, 1, 1]
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
    .args:
{args}...
.end_amdgpu_metadata
""")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llvm-bin", type=Path, default=Path("/opt/rocm/llvm/bin"))
    p.add_argument("--rows", type=int, default=6)
    p.add_argument("--rank", type=int, default=0)
    p.add_argument("--part", choices=("all", "target", "draft"), default="all")
    args = p.parse_args()
    cfg = source_layout(args.rows, args.rank, args.part)
    out = ROOT / "build" / f"{args.part}_r{args.rank}_t{args.rows}"
    out.mkdir(parents=True, exist_ok=True)
    write_includes(out, cfg)
    obj, co = out / "step.syntax.o", out / "step.syntax.co"
    # llvm-mc: .s -> ET_REL；ld.lld: ET_REL -> HIP 可识别的 ELF code-object 容器。
    # 此处只有带 trap 的壳，容器格式正确不代表数学计算已经实现。
    run([args.llvm_bin / "llvm-mc", "-triple=amdgcn-amd-amdhsa",
         "-mcpu=gfx1250", "-filetype=obj", "-I", out, "-I", ROOT,
         ROOT / "step_asm.s", "-o", obj])
    run([args.llvm_bin / "ld.lld", "-shared", "--no-undefined", obj, "-o", co])
    disassembly = run([args.llvm_bin / "llvm-objdump", "--mcpu=gfx1250",
                       "-d", co])
    (out / "step.disasm.txt").write_text(disassembly)
    (out / "step.notes.txt").write_text(
        run([args.llvm_bin / "llvm-readobj", "--notes", "--symbols", co])
    )
    assert "s_trap" in disassembly, "伪调用必须明确保留 trap"
    assert SYMBOL in disassembly
    cfg.update(
        artifact_kind="syntax_only_trap_placeholders",
        compute_stages_implemented=False,
        code_object=str(co),
        warning="DO NOT LAUNCH: FlyDSL stage calls are placeholders.",
    )
    (out / "manifest.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"离线汇编/链接完成：{co}")
    print(f"TR={cfg['target_rows']}, TRD={cfg['draft_rows']}, "
          f"dynamic LDS={cfg['dynamic_lds_bytes']} bytes")
    print("这是含 trap 的语法检查产物，没有运行 GPU，也不能计算网络输出。")


if __name__ == "__main__":
    main()
