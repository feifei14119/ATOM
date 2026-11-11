"""Small ELF64/AMDGPU metadata reader for build-time ABI/link checks."""
import struct

from native import require


def unpack_msgpack(data):
    """Decode the MessagePack types used in AMDHSA metadata, without GPU imports."""
    position = 0

    def take(count):
        nonlocal position
        require(position + count <= len(data), "Truncated metadata")
        value = data[position:position + count]
        position += count
        return value

    def number(code):
        return struct.unpack(">" + code, take(struct.calcsize(code)))[0]

    def value():
        tag = take(1)[0]
        if tag < 0x80:
            return tag
        if tag >= 0xe0:
            return tag - 256
        if 0xa0 <= tag <= 0xbf:
            return take(tag & 31).decode()
        if 0x90 <= tag <= 0x9f:
            return [value() for _ in range(tag & 15)]
        if 0x80 <= tag <= 0x8f:
            return {value(): value() for _ in range(tag & 15)}
        if tag in (0xc0, 0xc2, 0xc3):
            return {0xc0: None, 0xc2: False, 0xc3: True}[tag]
        if tag in (0xca, 0xcb, 0xcc, 0xcd, 0xce, 0xcf, 0xd0, 0xd1, 0xd2, 0xd3):
            return number({0xca: "f", 0xcb: "d", 0xcc: "B", 0xcd: "H", 0xce: "I",
                           0xcf: "Q", 0xd0: "b", 0xd1: "h", 0xd2: "i", 0xd3: "q"}[tag])
        if tag in (0xd9, 0xda, 0xdb):
            return take(number({0xd9: "B", 0xda: "H", 0xdb: "I"}[tag])).decode()
        if tag in (0xdc, 0xdd):
            return [value() for _ in range(number("H" if tag == 0xdc else "I"))]
        if tag in (0xde, 0xdf):
            return {value(): value() for _ in range(number("H" if tag == 0xde else "I"))}
        raise RuntimeError(f"Unsupported metadata MessagePack tag 0x{tag:x}")

    decoded = value()
    require(position == len(data), "Trailing bytes in metadata")
    return decoded


class Elf:
    def __init__(self, data):
        self.data = data
        require(data[:6] == b"\x7fELF\x02\x01", "Expected little-endian ELF64")
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
        self.kind, self.machine = header[1:3]
        sections = [struct.unpack_from("<IIQQQQIIQQ", data, header[6] + i * header[11])
                    for i in range(header[12])]
        names = self.payload(sections[header[13]])
        self.sections = {self.string(names, s[0]): s for s in sections}
        self.symbols = {}
        for section in sections:
            if section[1] not in (2, 11):
                continue
            strings = self.payload(sections[section[6]])
            for i in range(0, section[5], section[9]):
                name, info, other, shndx, address, size = struct.unpack_from(
                    "<IBBHQQ", data, section[4] + i)
                name = self.string(strings, name)
                if name:
                    self.symbols[name] = (shndx, address, size, info)
        self.indexed_sections = sections

    @staticmethod
    def string(data, offset):
        return data[offset:data.index(b"\0", offset)].decode()

    def payload(self, section):
        return self.data[section[4]:section[4] + section[5]]

    def body(self, symbol):
        index, address, size, _ = self.symbols[symbol]
        section = self.indexed_sections[index]
        offset = section[4] + address - section[3]
        return self.data[offset:offset + size]

    def metadata(self):
        notes = []
        for section in self.sections.values():
            if section[1] != 7:
                continue
            data, offset = self.payload(section), 0
            while offset < len(data):
                namesz, descsz, kind = struct.unpack_from("<III", data, offset)
                offset += 12
                owner = data[offset:offset + namesz].rstrip(b"\0")
                offset += (namesz + 3) // 4 * 4
                desc = data[offset:offset + descsz]
                offset += (descsz + 3) // 4 * 4
                if owner == b"AMDGPU" and kind == 32:
                    notes.append(unpack_msgpack(desc))
        require(len(notes) == 1, "Expected one AMDGPU metadata note")
        return notes[0]


def audit_binary(data, cfg, resource):
    elf = Elf(data)
    require(elf.kind == 3 and elf.machine == 224, "Expected AMDGPU shared code object")
    require(not [s for s in elf.sections.values() if s[1] in (4, 9) and s[5]],
            "Unresolved relocations in final code object")
    require(not [name for name, (index, _, _, info) in elf.symbols.items()
                 if index == 0 and info >> 4 in (1, 2)], "Undefined external symbols")
    symbol = cfg["symbol"]
    require([n for n in elf.symbols if n.endswith(".kd")] == [symbol + ".kd"],
            "Expected exactly one launched kernel descriptor")
    require(not any(n.startswith("step31_") for n in elf.symbols),
            "Ordinary fragment functions leaked into final code object")
    require(elf.body(symbol), "Empty launched kernel")
    descriptor = elf.body(symbol + ".kd")
    require(len(descriptor) == 64, "Unexpected AMDHSA descriptor size")
    require(struct.unpack_from("<III", descriptor) == (0, resource["private"], 72),
            "Descriptor LDS/private/kernarg ABI differs from generated contract")
    kernels = elf.metadata()["amdhsa.kernels"]
    require(len(kernels) == 1, "Expected one metadata kernel")
    kernel = kernels[0]
    expected = {".name": symbol, ".symbol": symbol + ".kd", ".kernarg_segment_size": 72,
                ".kernarg_segment_align": 8, ".wavefront_size": 32,
                ".group_segment_fixed_size": 0, ".private_segment_fixed_size": resource["private"],
                ".vgpr_count": resource["vgpr"], ".sgpr_count": resource["sgpr"],
                ".max_flat_workgroup_size": 256, ".reqd_workgroup_size": [256, 1, 1]}
    for key, value in expected.items():
        require(kernel.get(key) == value, f"ELF metadata mismatch: {key}")
    require([a[".offset"] for a in kernel[".args"]] == [0, 8, 16, 24, 32, 40, 48, 56, 64],
            "Metadata argument offsets differ from StepArgs")
    return {"descriptors": [symbol + ".kd"], "undefined_symbols": [],
            "relocations": 0, "kernel_metadata": kernel}
