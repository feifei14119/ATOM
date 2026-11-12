#!/usr/bin/env python3
"""Offline tests of inserted bytes, registers and the final AMDHSA descriptor."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

from mixed_asm import SYMBOL, require, run


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        require(self.data[:6] == b"\x7fELF\x02\x01", "Expected little-endian ELF64")
        self.kind, machine = struct.unpack_from("<HH", self.data, 16)
        require(machine == 224, "Expected AMDGPU ELF")
        offset = struct.unpack_from("<Q", self.data, 40)[0]
        width, count = struct.unpack_from("<HH", self.data, 58)
        self.sections = [struct.unpack_from("<IIQQQQIIQQ", self.data, offset + i * width) for i in range(count)]
        require(not any(s[1] in (4, 9) and s[5] for s in self.sections), "Unexpected relocations")
        self.symbols = {}
        for section in self.sections:
            if section[1] not in (2, 11):
                continue
            strings_section = self.sections[section[6]]
            strings = self.data[strings_section[4]:strings_section[4] + strings_section[5]]
            for at in range(section[4], section[4] + section[5], section[9]):
                name, info, _, index, value, size = struct.unpack_from("<IBBHQQ", self.data, at)
                name = strings[name:strings.index(b"\0", name)].decode()
                if name:
                    self.symbols[name] = (info, index, value, size)

    def span(self, symbol, size=None):
        _, index, value, original_size = self.symbols[symbol]
        require(0 < index < len(self.sections), "Undefined symbol: " + symbol)
        section = self.sections[index]
        start = section[4] + value - section[3]
        return self.data[start:start + (original_size if size is None else size)]


def verify(output, llvm):
    output, llvm = Path(output).resolve(), Path(llvm).resolve()
    (output / "static_report.json").unlink(missing_ok=True)
    generated = (output / "kernel.generated.s").read_text()
    require(not re.search(r"^\s*\.hip\.", generated, re.M), "Unprocessed HIP directive")
    report = json.loads((output / "build_report.json").read_text())
    require(report["status"] == "BUILT_NOT_TESTED", "No completed build")
    elf = Elf(output / "demo.co")
    require(elf.kind == 3, "Expected shared code object")
    require(hashlib.sha256(elf.data).hexdigest() == report["binary_sha256"], "Code object differs from build report")
    require(not any(index == 0 for _, index, _, _ in elf.symbols.values()), "Unresolved external symbol")
    functions = {name for name, (info, _, _, _) in elf.symbols.items() if info & 15 == 2}
    require(functions == {SYMBOL}, "Only the ASM entry should remain; HIP helpers must not be linked")
    require([name for name in elf.symbols if name.endswith(".kd")] == [SYMBOL + ".kd"], "Expected one descriptor")
    checked = []
    for entry in report["blocks"]:
        block = entry["contract"]
        folder = output / block["id"]
        fragment = (folder / "fragment.inc").read_text()
        symbol = SYMBOL + "." + block["id"]
        begin, end = (elf.symbols[symbol + "." + part][2] for part in ("begin", "end"))
        inserted = elf.span(symbol + ".begin", end - begin)
        isolated = ('.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"\n.text\n.globl audit_fragment\n'
                    '.type audit_fragment,@function\naudit_fragment:\n' + fragment
                    + '.size audit_fragment, .-audit_fragment\n')
        (folder / "audit.s").write_text(isolated)
        run([llvm / "llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1100", "-filetype=obj",
             folder / "audit.s", "-o", folder / "audit.o"])
        require(inserted == Elf(folder / "audit.o").span("audit_fragment"), "Inserted bytes differ from isolated assembly")
        writes = {int(x) for x in re.findall(r"^\s*v_\w+\s+v(\d+),", fragment, re.M)}
        authorized = set(block["pool"]) | {block["bindings"][-1]["reg"]}
        require(writes == set(entry["written_vgprs"]), "Register write report mismatch")
        require(writes <= authorized, "Writes escape the output/temp pool")
        require(not writes & {b["reg"] for b in block["bindings"][:2]}, "Input VGPR modified")
        require(not re.search(r"\b(?:s\d+|s\[|exec(?:_lo|_hi)?|m0)\b", fragment), "Unexpected SGPR/EXEC write or use")
        if re.search(r"v_div_scale_f32 v\d+, vcc_lo", fragment):
            require("vcc" in block["clobbers"], "Division VCC clobber is not authorized")
        if block["id"] == "mul_add":
            require(not re.search(r"\bv_fma\w*\b", fragment), "fp_contract=off was not respected for mul_add")
        checked.append({"id": block["id"], "fragment_bytes": len(inserted), "written_vgprs": sorted(writes)})
    disassembly = (output / "kernel.disasm.txt").read_text()
    require(not re.search(r"\bs_(?:swappc_b64|setpc_b64|swap_pc_i64|set_pc_i64)\b|\bscratch_", disassembly),
            "Unexpected device call/return or scratch")
    metadata = (output / "kernel.elf.txt").read_text()
    for key, expected in {"vgpr_count": 64, "sgpr_count": 20, "wavefront_size": 32, "kernarg_segment_size": 24,
                          "group_segment_fixed_size": 0, "private_segment_fixed_size": 0}.items():
        require(re.search(r"\." + key + r":\s*" + str(expected) + r"\b", metadata), "Incorrect metadata: " + key)
    descriptor = elf.span(SYMBOL + ".kd")
    require(len(descriptor) == 64 and struct.unpack_from("<III", descriptor) == (0, 0, 24), "Wrong kernarg/private/LDS ABI")
    rsrc1 = struct.unpack_from("<I", descriptor, 48)[0]
    require((rsrc1 & 63) == 7, "Wrong encoded VGPR allocation for gfx1100 wave32")
    result = {"status": "PASS", "gpu_execution": False, "blocks": checked,
              "functions": sorted(functions), "calls": 0, "private_bytes": 0,
              "encoded_allocated_vgprs": 64, "binary_sha256": report["binary_sha256"]}
    (output / "static_report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Static PASS: {len(checked)} byte-identical HIP fragments, one ASM kernel, no calls/scratch")


if __name__ == "__main__":
    verify(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "build",
           sys.argv[2] if len(sys.argv) > 2 else "/opt/rocm/lib/llvm/bin")
