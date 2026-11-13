#!/usr/bin/env python3
"""Optional offline checks of separate assembly and the resolved call target.

Run via make check. This does not load HIP or execute a GPU kernel.
"""
from pathlib import Path
import json
import struct
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        require(self.data[:6] == b"\x7fELF\x02\x01", "Expected little-endian ELF64")
        self.kind, machine = struct.unpack_from("<HH", self.data, 16)
        require(machine == 224, "Expected EM_AMDGPU")
        offset = struct.unpack_from("<Q", self.data, 40)[0]
        width, count = struct.unpack_from("<HH", self.data, 58)
        self.sections = [struct.unpack_from("<IIQQQQIIQQ", self.data, offset + i * width)
                         for i in range(count)]
        self.symbols, tables, self.relocations = {}, {}, []
        for si, sec in enumerate(self.sections):
            if sec[1] not in (2, 11):  # SYMTAB / DYNSYM
                continue
            strings_sec = self.sections[sec[6]]
            strings = self.data[strings_sec[4]:strings_sec[4] + strings_sec[5]]
            table = []
            for at in range(sec[4], sec[4] + sec[5], sec[9]):
                name, info, _, index, value, size = struct.unpack_from("<IBBHQQ", self.data, at)
                name = strings[name:strings.index(b"\0", name)].decode()
                symbol = dict(name=name, info=info, section=index, value=value, size=size)
                table.append(symbol)
                if name:
                    self.symbols[name] = symbol
            tables[si] = table
        for sec in self.sections:
            require(sec[1] != 9 or sec[5] == 0, "Unexpected REL (without explicit addend)")
            if sec[1] != 4:  # RELA
                continue
            for at in range(sec[4], sec[4] + sec[5], sec[9]):
                offset, info, addend = struct.unpack_from("<QQq", self.data, at)
                self.relocations.append(dict(section=sec[7], offset=offset, kind=info & 0xffffffff,
                                             symbol=tables[sec[6]][info >> 32]["name"], addend=addend))

    def symbol_bytes(self, name):
        sym = self.symbols[name]
        require(0 < sym["section"] < len(self.sections), "Undefined symbol: " + name)
        return self.section_bytes(sym["section"], sym["value"], sym["size"])

    def section_bytes(self, index, address, size):
        sec = self.sections[index]
        offset = address - sec[3]
        require(0 <= offset and offset + size <= sec[5], "Read outside ELF section")
        return self.data[sec[4] + offset:sec[4] + offset + size]


def main():
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
    a, b, linked = [Elf(directory / name) for name in ("kernel_A.o", "kernel_B.o", "demo.co")]
    require(a.kind == b.kind == 1, "A/B must be independent ET_REL objects")
    require(linked.kind == 3, "Expected linked ET_DYN code object")
    require(a.symbols["kernel_B"]["section"] == 0, "A.o must have an undefined reference to B")
    require("kernel_A" not in b.symbols, "B.o must be independent of A")
    require(b.symbols["kernel_B"]["section"] != 0, "B.o must define B")
    require(not linked.relocations, "Final code object must have resolved all relocations")
    require(all(s["section"] != 0 for s in linked.symbols.values()), "Unresolved final symbol")
    descriptors = {n for n in linked.symbols if n.endswith(".kd")}
    require(descriptors == {"kernel_A.kd"}, "Only A is a dispatchable kernel")
    require(linked.symbol_bytes("kernel_B") == b.symbol_bytes("kernel_B"), "Linker changed B's body")

    calls = [r for r in a.relocations if r["symbol"] == "kernel_B"]
    require(len(calls) == 1, "Expected exactly one cross-object call relocation")
    call = calls[0]
    require(call["kind"] == 5 and call["addend"] == 4, "Expected R_AMDGPU_REL64 + 4")
    a_symbol, b_symbol = linked.symbols["kernel_A"], linked.symbols["kernel_B"]
    a_start = a.symbols["kernel_A"]["value"]
    literal_address = a_symbol["value"] + call["offset"] - a_start
    delta = struct.unpack("<q", linked.section_bytes(a_symbol["section"], literal_address, 8))[0]
    # s_getpc's result is the s_add address, 4 bytes before its literal.
    pc_base = literal_address - 4
    require(pc_base + delta == b_symbol["value"], "Relocated call does not target B")
    # All bytes of A apart from the relocated literal must remain unchanged.
    before, after = bytearray(a.symbol_bytes("kernel_A")), bytearray(linked.symbol_bytes("kernel_A"))
    offset = call["offset"] - a_start
    before[offset:offset + 8] = after[offset:offset + 8]
    require(before == after, "Unexpected modification of A outside the relocation")
    descriptor = linked.symbol_bytes("kernel_A.kd")
    entry_delta = struct.unpack_from("<q", descriptor, 16)[0]
    require(linked.symbols["kernel_A.kd"]["value"] + entry_delta == a_symbol["value"],
            "Kernel descriptor does not point to A")
    report = dict(status="PASS", target="gfx1250", call_relocation="R_AMDGPU_REL64",
                  a_address=a_symbol["value"], b_address=b_symbol["value"],
                  pc_base=pc_base, relocated_delta=delta, b_bytes=len(b.symbol_bytes("kernel_B")),
                  final_relocations=0, gpu_executed=False)
    (directory / "static_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Static PASS: independent A.o/B.o; {pc_base:#x} + {delta:#x} = B at {b_symbol['value']:#x}")


if __name__ == "__main__":
    main()
