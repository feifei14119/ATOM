#!/usr/bin/env python3
"""Build-time ABI/resource guard for this small HIP arithmetic function.

This deliberately supports the inspected leaf code only. A changed compiler
or C implementation requires reviewing A's interface and resource descriptor.
No HIP runtime or GPU execution is involved.
"""
from pathlib import Path
import json
import re
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def audit_native(text):
    match = re.search(r"^kernel_C:[^\n]*\n(.*?)^\.Lfunc_end\d+:", text, re.M | re.S)
    require(match is not None, "Cannot locate HIP C's native function")
    instructions = []
    for line in match[1].splitlines():
        line = line.split(";", 1)[0].strip()
        if line:
            instructions.append(re.sub(r"\s+", " ", line))
    # Verify the actual register interface, the sole computation, and return.
    patterns = [r"s_wait_loadcnt_dscnt (?:0x0|0)", r"s_wait_kmcnt (?:0x0|0)",
                r"v_mad_u32 v0, v1, v0, (?:7|0x7)", r"s_set(?:_pc_i64|pc_b64) s\[30:31\]"]
    require(len(instructions) == len(patterns) and
            all(re.fullmatch(pattern, line) for pattern, line in zip(patterns, instructions)),
            "HIP C's native ABI/body changed: " + repr(instructions))
    resources = {}
    for key in ("num_vgpr", "num_agpr", "numbered_sgpr", "num_named_barrier", "private_seg_size",
                "uses_vcc", "uses_flat_scratch", "has_dyn_sized_stack", "has_recursion", "has_indirect_call"):
        found = re.search(r"^\s*\.set kernel_C\." + key + r", (\d+)\s*$", text, re.M)
        require(found is not None, "Missing native resource: " + key)
        resources[key] = int(found[1])
    require(resources["num_vgpr"] == 2 and resources["numbered_sgpr"] == 32,
            "Unexpected C register budget")
    require(all(value == 0 for key, value in resources.items() if key not in ("num_vgpr", "numbered_sgpr")),
            "C acquired scratch, special state or nested calls")
    return dict(signature="u32 C(u32 value, u32 multiplier)",
                inputs=["v0", "v1"], result="v0", return_pc="s[30:31]",
                instructions=instructions, resources=resources)


def main():
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
    report = audit_native((directory / "kernel_C.native.s").read_text())
    # llc emits an empty HSA metadata document even for a device-only module.
    notes = (directory / "kernel_C.raw.elf.txt").read_text()
    require(notes.count("NT_AMDGPU_METADATA") == 1, "Unexpected compiler metadata notes")
    require(re.search(r"amdhsa.kernels:\s*\[\]", notes) is not None,
            "Cannot remove metadata for a module containing dispatchable kernels")
    require(not re.search(r"\.kd\b", notes), "C unexpectedly has a kernel descriptor")
    require("There are no relocations" in notes, "C acquired external references")
    report.update(status="ABI_AUDITED_NOT_EXECUTED", empty_metadata_removed_at_next_build_step=True,
                  gpu_executed=False)
    (directory / "kernel_C.abi.json").write_text(json.dumps(report, indent=2) + "\n")
    print("HIP C build ABI: v0/v1 -> v0, return s[30:31], no scratch; empty metadata identified")


if __name__ == "__main__":
    main()
