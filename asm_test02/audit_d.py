#!/usr/bin/env python3
"""Build-time guard for FlyDSL D's native ABI, resources and empty metadata."""
from pathlib import Path
import json
import re
import sys

from audit_c import require


def audit_native(text):
    match = re.search(r"^kernel_D:[^\n]*\n(.*?)^\.Lfunc_end\d+:", text, re.M | re.S)
    require(match is not None, "Cannot locate FlyDSL D's native function")
    instructions = [re.sub(r"\s+", " ", line.split(";", 1)[0].strip())
                    for line in match[1].splitlines() if line.split(";", 1)[0].strip()]
    patterns = [r"s_wait_loadcnt_dscnt (?:0x0|0)", r"s_wait_kmcnt (?:0x0|0)",
                r"v_mad_u32 v0, v0, v1, (?:11|0xb)", r"s_set(?:_pc_i64|pc_b64) s\[30:31\]"]
    require(len(instructions) == len(patterns) and
            all(re.fullmatch(pattern, line) for pattern, line in zip(patterns, instructions)),
            "FlyDSL D's native ABI/body changed: " + repr(instructions))
    resources = {}
    for key in ("num_vgpr", "num_agpr", "numbered_sgpr", "num_named_barrier", "private_seg_size",
                "uses_vcc", "uses_flat_scratch", "has_dyn_sized_stack", "has_recursion", "has_indirect_call"):
        found = re.search(r"^\s*\.set kernel_D\." + key + r", (\d+)\s*$", text, re.M)
        require(found is not None, "Missing native resource: " + key)
        resources[key] = int(found[1])
    require(resources["num_vgpr"] == 2 and resources["numbered_sgpr"] == 32,
            "Unexpected D register budget")
    require(all(value == 0 for key, value in resources.items() if key not in ("num_vgpr", "numbered_sgpr")),
            "D acquired scratch, special state or nested calls")
    return dict(signature="u32 D(u32 value, u32 multiplier)", inputs=["v0", "v1"],
                result="v0", return_pc="s[30:31]", instructions=instructions, resources=resources)


def main():
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
    report = audit_native((directory / "kernel_D.native.s").read_text())
    notes = (directory / "kernel_D.raw.elf.txt").read_text()
    require(notes.count("NT_AMDGPU_METADATA") == 1, "Unexpected D metadata notes")
    require(re.search(r"amdhsa.kernels:\s*\[\]", notes) is not None and
            not re.search(r"\.kd\b", notes), "D must have no dispatchable kernel")
    require("There are no relocations" in notes, "D acquired external references")
    report.update(status="ABI_AUDITED_NOT_EXECUTED", empty_metadata_removed_at_next_build_step=True,
                  gpu_executed=False)
    (directory / "kernel_D.abi.json").write_text(json.dumps(report, indent=2) + "\n")
    print("FlyDSL D build ABI: v0/v1 -> v0, return s[30:31], no scratch; empty metadata identified")


if __name__ == "__main__":
    main()
