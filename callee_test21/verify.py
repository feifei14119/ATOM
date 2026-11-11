#!/usr/bin/env python3
"""Check the final ELF, fragment bytes/resources and negative contract cases."""
import json
from pathlib import Path
import re
import struct
import sys

from build import extract, parse, require, run


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        require(self.data[:6] == b"\x7fELF\x02\x01", "Expected ELF64 little-endian")
        self.kind, machine = struct.unpack_from("<HH", self.data, 16)
        require(machine == 224, "Expected AMDGPU ELF")
        offset = struct.unpack_from("<Q", self.data, 40)[0]
        width, count = struct.unpack_from("<HH", self.data, 58)
        self.sections = [struct.unpack_from("<IIQQQQIIQQ", self.data, offset + i * width) for i in range(count)]
        require(not any(s[1] in (4, 9) and s[5] for s in self.sections), "Unexpected relocation")
        self.symbols = {}
        for sec in self.sections:
            if sec[1] != 2:
                continue
            string_sec = self.sections[sec[6]]
            strings = self.data[string_sec[4]:string_sec[4] + string_sec[5]]
            for at in range(sec[4], sec[4] + sec[5], sec[9]):
                name, info, _, index, value, size = struct.unpack_from("<IBBHQQ", self.data, at)
                name = strings[name:strings.index(b"\0", name)].decode()
                if name:
                    self.symbols[name] = (info, index, value, size)

    def span(self, name, size=None):
        _, index, value, original_size = self.symbols[name]
        require(0 < index < len(self.sections), f"Undefined symbol: {name}")
        sec = self.sections[index]
        start = sec[4] + value - sec[3]
        return self.data[start:start + (original_size if size is None else size)]


def rejects(fn, reason):
    try:
        fn()
    except RuntimeError:
        return
    raise RuntimeError("Expected rejection: " + reason)


def main():
    output = Path(sys.argv[1]).resolve()
    llvm = Path(sys.argv[2] if len(sys.argv) > 2 else "/opt/rocm/lib/llvm/bin")
    generated = (output / "kernel.generated.s").read_text()
    require(".flydsl." not in generated, "Unprocessed FlyDSL directive")
    elf = Elf(output / "demo.co")
    require(elf.kind == 3, "Expected linked code object")
    require(not any(index == 0 for _, index, _, _ in elf.symbols.values()), "Undefined symbol")
    require({name for name, (info, _, _, _) in elf.symbols.items() if info & 15 == 2} == {"asm_flydsl_demo"},
            "Expected only the hand-written ASM function, without a linked FlyDSL helper")
    begin, end = (elf.symbols["asm_flydsl_demo.fragment_" + x][2] for x in ("begin", "end"))
    actual = elf.span("asm_flydsl_demo.fragment_begin", end - begin)
    fragment = (output / "fragment.inc").read_text()
    isolated = ('.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"\n.text\n'
                '.globl audit_fragment\n.type audit_fragment,@function\naudit_fragment:\n'
                + fragment + '\n.size audit_fragment, .-audit_fragment\n')
    (output / "fragment.audit.s").write_text(isolated)
    run([llvm / "llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1100", "-filetype=obj",
         output / "fragment.audit.s", "-o", output / "fragment.audit.o"])
    require(actual == Elf(output / "fragment.audit.o").span("audit_fragment"),
            "Inserted fragment differs from independently assembled fragment")
    report = json.loads((output / "build_report.json").read_text())
    expected_writes = set(report["fragment_written_vgprs"])
    writes = {int(x) for x in re.findall(r"^\s*v_[A-Za-z0-9_]+\s+v([0-9]+),", fragment, re.M)}
    require(writes == expected_writes, "Actual fragment writes differ from contract")
    require(writes <= set(report["contract"]["temporary_vgprs"]) | {report['contract']['bindings'][2]['reg']},
            "Fragment writes outside output/temp pool")
    disasm = (output / "kernel.disasm.txt").read_text()
    require(not re.search(r"\b(?:s_swappc_b64|s_setpc_b64|scratch_[A-Za-z0-9_]+)\b", disasm),
            "Unexpected call, return or private-memory instruction")
    meta = (output / "kernel.elf.txt").read_text()
    for key, value in {"vgpr_count": 36, "sgpr_count": 18, "private_segment_fixed_size": 0,
                       "group_segment_fixed_size": 0, "wavefront_size": 32, "kernarg_segment_size": 24}.items():
        require(re.search(r"\." + key + r":\s*" + str(value) + r"\b", meta), "Unexpected metadata: " + key)
    require(max(int(x) for x in re.findall(r"\bv([0-9]+)\b", disasm)) < 36, "VGPR descriptor is too small")
    # Validate the encoded descriptor's VGPR allocation (gfx1100 wave32: granule 8).
    kd = elf.span("asm_flydsl_demo.kd", 64)
    rsrc1 = struct.unpack_from("<I", kd, 48)[0]
    require((rsrc1 & 63) == (36 + 7) // 8 - 1, "Unexpected encoded VGPR allocation")
    source = (Path(__file__).parent / "kernel.s").read_text()
    rejects(lambda: parse(source.replace("v[32:35]", "v[0:3]")), "pool overlaps input/output")
    rejects(lambda: extract((output / "fragment.native.s").read_text().replace(
        "v_mul_f32_e32", "v_div_scale_f32")), "unsupported instruction")
    from build import remap
    parsed, used = extract((output / "fragment.native.s").read_text())
    tiny = dict(report["contract"], temporary_vgprs=[32])
    rejects(lambda: remap(parsed, used, tiny), "insufficient temporary pool")
    static = {"status": "PASS", "fragment_bytes": len(actual), "kernel_bytes": len(elf.span('asm_flydsl_demo')),
              "fragment_written_vgprs": sorted(writes), "metadata_vgprs": 36,
              "encoded_allocated_vgprs": 8 * ((rsrc1 & 63) + 1), "negative_checks": 3,
              "calls": 0, "private_bytes": 0}
    (output / "static_report.json").write_text(json.dumps(static, indent=2) + "\n")
    print(f"Static PASS: {len(actual)} fragment bytes, writes {sorted(writes)}, 3 rejection checks")


if __name__ == "__main__":
    main()
