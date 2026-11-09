"""Audit this example's ELF linkage, function bytes and call/return boundary."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b"\x7fELF\x02\x01", "Expected little-endian ELF64"
        self.kind, machine = struct.unpack_from("<HH", self.data, 16)
        assert machine == 224, "Expected EM_AMDGPU"
        offset = struct.unpack_from("<Q", self.data, 40)[0]
        entry_size, count = struct.unpack_from("<HH", self.data, 58)
        self.sections = [struct.unpack_from("<IIQQQQIIQQ", self.data, offset + i * entry_size)
                         for i in range(count)]
        self.symbols = {}
        for section in self.sections:
            if section[1] != 2:  # SHT_SYMTAB
                continue
            strings_section = self.sections[section[6]]
            strings = self.data[strings_section[4]:strings_section[4] + strings_section[5]]
            for at in range(section[4], section[4] + section[5], section[9]):
                name, info, other, index, value, size = struct.unpack_from("<IBBHQQ", self.data, at)
                name = strings[name:strings.index(b"\0", name)].decode()
                if name:
                    self.symbols[name] = (index, value, size, info)

    def body(self, name):
        index, value, size, info = self.symbols[name]
        assert info & 15 == 2 and size > 0, f"Expected sized function: {name}"
        section = self.sections[index]
        start = section[4] + value - section[3]
        return self.data[start:start + size]


build, stage_path = Path(sys.argv[1]), Path(sys.argv[2])
stage = Elf(stage_path)
caller = Elf(build / "mono_kernel.o")
linked = Elf(build / "mono_kernel.co")
assert stage.kind == caller.kind == 1, "Link inputs must be ELF REL"
assert linked.kind == 3, "Final module must be ELF DYN"
assert "sub_kernel" not in stage.symbols and "sub_kernel.kd" not in stage.symbols
assert caller.symbols["stage_sub_device"][0] == 0, "Expected undefined callee before link"
assert linked.symbols["stage_sub_device"][0] != 0
assert "mono_kernel.kd" in linked.symbols
assert not [name for name, sym in linked.symbols.items() if sym[0] == 0]
assert not any(s[1] in (4, 9) and s[5] for s in linked.sections), "Unresolved relocation sections"
body = stage.body("stage_sub_device")
assert body == linked.body("stage_sub_device"), "Linking unexpectedly changed the stage body"

disasm = (build / "mono_kernel.disasm.txt").read_text()
assert len(re.findall(r"\bs_swappc_b64\b", disasm)) == 1
assert len(re.findall(r"\bs_setpc_b64\b", disasm)) == 1
metadata = (build / "mono_kernel.elf.txt").read_text()
assert re.findall(r"^\s+\.name:\s+(\S+)", metadata, re.M) == ["mono_kernel"]
resources = {}
for key in ("vgpr_count", "sgpr_count", "private_segment_fixed_size",
            "group_segment_fixed_size", "vgpr_spill_count", "sgpr_spill_count"):
    resources[key] = int(re.search(r"\." + key + r":\s*(\d+)", metadata)[1])
for key in ("private_segment_fixed_size", "vgpr_spill_count", "sgpr_spill_count"):
    assert resources[key] == 0, f"Zero-spill requirement failed: {key}={resources[key]}"
assert not re.search(r"\bscratch_(?:load|store)\w*", disasm)

# Scope this to mono_kernel, not unrelated helpers emitted by the HIP headers.
assembly = (build / "mono_kernel.s").read_text()
start = assembly.index("mono_kernel:")
end = assembly.index(".section\t.rodata", start)
function = assembly[start:end]
(build / "mono_kernel.function.s").write_text(function)
before, after = function.split("s_swappc_b64")
# This small example has one volatile scalar load held across its only call.
# Audit that it is placed in the allowed preserved bank and consumed by the
# subsequent addition. This is an example-specific check, not a general CFG
# liveness proof or a validator for arbitrary supplier ABI behavior.
mask_report = json.loads((build / "callsite_regmask.json").read_text())
bank = {f"v{i}" for i in mask_report["preserved_vgprs"]}
assert mask_report["calls_changed"] == 1
assert mask_report["standard_sgpr_and_special_mask_unchanged"]
assert mask_report["baseline_roundtrip_instructions_identical"]
loads = [v for v in re.findall(r"(?:flat|global)_load_b32\s+(v\d+),", before) if v in bank]
preserved_bias = [reg for reg in loads if re.search(
    r"v_(?:dual_)?add_f32[^\n]*\b" + reg + r"\b", after)]
assert len(preserved_bias) == 1, "Expected pre-call load into the selected bank used by post-call addition"
ir = (build / "mono_kernel.ll").read_text()
assert '"amdgpu-num-vgpr"' not in ir
report = {
    "stage_elf": "REL", "final_elf": "DYN",
    "stage_function_bytes": len(body),
    "stage_function_sha256": hashlib.sha256(body).hexdigest(),
    "stage_bytes_unchanged_after_link": True,
    "device_calls": 1, "device_returns": 1,
    "unresolved_symbols": 0, "final_relocations": 0,
    "launchable_kernel": "mono_kernel", "resources": resources,
    "nonterminal_call_in_mono": True,
    "lane_bias_callee_saved_vgpr": preserved_bias[0],
    "caller_vgpr_limit": None,
    "callsite_preserved_vgprs": mask_report["preserved_vgprs"],
    "zero_scratch_and_spills": True,
}
(build / "link_check.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS: ELF REL stage -> ELF DYN Mono; resolved symbol; unchanged stage bytes; real call/return")
print("PASS: mono_kernel itself retains lane bias across the call in " + preserved_bias[0] + "; no scratch/spills")
print(json.dumps(report, indent=2))
