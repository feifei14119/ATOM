"""Inspect only the live-state kernel, excluding unrelated HIP helper code."""
import json
from pathlib import Path
import re
import sys

build = Path(sys.argv[1])
assembly = (build / "live_state.s").read_text()
start = assembly.index("live_state_kernel:")
end = assembly.index(".section\t.rodata", start)
body = assembly[start:end]
assert body.count("s_swappc_b64") == 1
before, after = body.split("s_swappc_b64")
assert "scratch_store_b32" in before, "Expected compiler-generated save before call"
assert "scratch_load_b32" in after, "Expected compiler-generated reload after call"
assert "global_store_b32" in after, "Expected use of preserved state after call"
metadata = (build / "live_state.elf.txt").read_text()
resources = {}
for key in ("vgpr_count", "sgpr_count", "private_segment_fixed_size",
            "group_segment_fixed_size", "vgpr_spill_count", "sgpr_spill_count"):
    resources[key] = int(re.search(r"\." + key + r":\s*(\d+)", metadata)[1])
assert resources["private_segment_fixed_size"] > 0
assert resources["vgpr_spill_count"] > 0
(build / "live_state.function.s").write_text(body)
report = {"compiler_save_before_call": True, "compiler_reload_after_call": True,
          "post_call_output_store": True, "resources": resources}
(build / "live_check.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS: compiler-generated scratch save/reload surrounds the nonterminal device call")
print(json.dumps(report, indent=2))
