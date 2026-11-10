"""Packing/auditing for the restricted leaf-ASM demo, not a general ASM verifier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


def run(argv):
    result = subprocess.run([str(x) for x in argv], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"command failed: {argv}\n{result.stdout}\n{result.stderr}")
    return result.stdout, result.stderr


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expand(registers):
    result = set()
    for reg in registers:
        match = re.fullmatch(r"([sv])\[(\d+):(\d+)\]", reg)
        if match:
            first, last = int(match[2]), int(match[3])
            if first > last:
                raise ValueError(f"reversed register interval: {reg}")
            result.update(f"{match[1]}{i}" for i in range(first, last + 1))
        elif re.fullmatch(r"[sv]\d+|scc|vcc", reg):
            result.add(reg)
        else:
            raise ValueError(f"unsupported register: {reg}")
    return result


def register_operands(text):
    return expand(re.findall(r"\b[sv]\[\d+:\d+\]|\b[sv]\d+\b", text))


def llvm_attributes(manifest):
    r = manifest["resources"]
    return {
        "amdgpu-asm-contract": "1",
        "amdgpu-asm-arg-regs": ",".join(a["register"] for a in manifest["arguments"]),
        "amdgpu-asm-result-reg": manifest["result"]["register"],
        "amdgpu-asm-clobbers": ",".join(manifest["clobbers"]),
        "amdgpu-asm-vgpr-count": str(r["vgpr_count"]),
        "amdgpu-asm-sgpr-count": str(r["sgpr_count"]),
        "amdgpu-asm-private-bytes": str(r["private_bytes"]),
    }


class Elf:
    """Minimal bounds-checked ELF64 reader for these AMDGPU test objects."""
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        data = self.data
        if data[:6] != b"\x7fELF\x02\x01" or len(data) < 64:
            raise ValueError("expected little-endian ELF64")
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
        self.type, machine, shoff, shentsize, shnum, shstr = (
            header[1], header[2], header[6], header[11], header[12], header[13])
        if machine != 224 or shentsize != 64 or not shnum or shstr >= shnum:
            raise ValueError("unsupported ELF target/section table")
        if shoff + shnum * shentsize > len(data):
            raise ValueError("truncated ELF section table")
        self.sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff+i*64)
                         for i in range(shnum)]
        names = self.section_data(self.sections[shstr])

        def cstr(blob, offset):
            if offset >= len(blob):
                raise ValueError("invalid ELF string offset")
            return blob[offset:blob.index(b"\0", offset)].decode()

        self.section_names = [cstr(names, section[0]) for section in self.sections]
        self.symbols = {}
        for section in self.sections:
            if section[1] != 2:
                continue
            strings = self.section_data(self.sections[section[6]])
            table = self.section_data(section)
            if section[9] != 24 or len(table) % 24:
                raise ValueError("invalid ELF symbol table")
            for offset in range(0, len(table), 24):
                name, info, other, shndx, value, size = struct.unpack_from("<IBBHQQ", table, offset)
                if name:
                    self.symbols[cstr(strings, name)] = (shndx, value, size, info, other)

    def section_data(self, section):
        offset, size = section[4:6]
        if offset + size > len(self.data):
            raise ValueError("truncated ELF section")
        return self.data[offset:offset+size]

    def symbol_bytes(self, name):
        section, value, size, _, _ = self.symbols[name]
        if section >= len(self.sections) or not size:
            raise ValueError(f"{name}: not a defined, nonempty function")
        sh = self.sections[section]
        offset = value - sh[3]
        blob = self.section_data(sh)
        if offset < 0 or offset + size > len(blob):
            raise ValueError(f"{name}: symbol exceeds section")
        return blob[offset:offset+size]


def audit_object(path, manifest, llvm):
    """Audit a deliberately small, straight-line instruction vocabulary."""
    obj = Elf(path)
    if obj.type != 1:
        raise ValueError("external stage must be ELF ET_REL")
    if manifest["target"] != "gfx1250" or manifest["wavefront_size"] != 32:
        raise ValueError("this prototype only supports gfx1250 wave32")
    header, _ = run([Path(llvm)/"llvm-readobj", "--file-headers", path])
    if "EF_AMDGPU_MACH_AMDGCN_GFX1250" not in header or "AMDGPU_HSA" not in header:
        raise ValueError("ELF target/OS ABI differs from the gfx1250 AMDHSA contract")
    if manifest["entry_exec"] != "full_wave" or not manifest["leaf"]:
        raise ValueError("this prototype requires a full-wave leaf")
    r = manifest["resources"]
    if r["private_bytes"] or r["lds_bytes"]:
        raise ValueError("private/LDS memory are outside this demo contract")
    if any(section[1] in (4, 9) and section[5] for section in obj.sections):
        raise ValueError("external stage relocations are not supported by the audit")
    symbol = manifest["symbol"]
    for name, section in zip(obj.section_names, obj.sections):
        if section[2] & 2 and section[5] and name != ".text":
            raise ValueError(f"unexpected allocated callee section: {name}")
    code = obj.symbol_bytes(symbol)
    start = obj.symbols[symbol][1]
    disassembly, _ = run([Path(llvm)/"llvm-objdump", "--mcpu=gfx1250",
                          "--disassemble-symbols="+symbol, path])
    rows = []
    for line in disassembly.splitlines():
        match = re.match(r"\s*(.*?)\s*//\s*([0-9a-fA-F]+):\s*((?:[0-9a-fA-F]{8}(?:\s+|$))+)", line)
        if match and start <= int(match[2], 16) < start + len(code):
            rows.append((int(match[2], 16)-start, match[1].strip(), match[3].split()))
    reconstructed = b"".join(struct.pack("<I", int(word, 16))
                             for _, _, words in rows for word in words)
    if reconstructed != code:
        raise ValueError("disassembler did not decode the complete symbol")
    read_write, writes = set(), set()
    scalar_writes = {"s_mov_b32", "s_lshl_b32", "s_xor_b32"}
    vector_writes = {"v_mov_b32", "v_xor_b32", "v_add_nc_u32", "v_lshlrev_b32", "global_load_b32"}
    no_writes = {"global_store_b32", "s_wait_loadcnt", "s_wait_storecnt", "s_wait_alu",
                 "s_waitcnt_depctr", "s_setpc_b64", "s_set_pc_i64"}
    returns = 0
    for index, (_, inst, _) in enumerate(rows):
        opcode, _, operands = inst.partition(" ")
        opcode = re.sub(r"_e(?:32|64)$", "", opcode)
        if opcode not in scalar_writes | vector_writes | no_writes:
            raise ValueError(f"unsupported callee instruction: {inst}")
        read_write |= register_operands(operands)
        if opcode in scalar_writes | vector_writes:
            writes |= register_operands(operands.split(",", 1)[0])
        if opcode in scalar_writes - {"s_mov_b32"}:
            writes.add("scc")
        if opcode in {"s_setpc_b64", "s_set_pc_i64"}:
            returns += 1
            if index != len(rows)-1 or operands.strip() != manifest["return_pc"]:
                raise ValueError("callee must end with one declared return-PC jump")
    if returns != 1:
        raise ValueError("missing leaf return")
    allowed_uses = expand(manifest["uses"])
    allowed_writes = expand(manifest["clobbers"])
    if read_write - allowed_uses:
        raise ValueError(f"undeclared register use: {sorted(read_write-allowed_uses)}")
    if writes - allowed_writes:
        raise ValueError(f"undeclared register write: {sorted(writes-allowed_writes)}")
    for bank, limit in (("v", r["vgpr_count"]), ("s", r["sgpr_count"])):
        numbers = [int(reg[1:]) for reg in read_write if re.fullmatch(bank+r"\d+", reg)]
        if numbers and max(numbers) >= limit:
            raise ValueError(f"resource extent does not cover {bank}{max(numbers)}")
    expected_abs = {"num_vgpr": r["vgpr_count"], "numbered_sgpr": r["sgpr_count"],
                    "private_seg_size": 0, "uses_vcc": 0, "uses_flat_scratch": 0,
                    "num_agpr": 0, "num_named_barrier": 0, "has_dyn_sized_stack": 0,
                    "has_recursion": 0, "has_indirect_call": 0}
    for name, expected in expected_abs.items():
        value = obj.symbols.get(symbol+"."+name)
        if not value or value[0] != 0xfff1 or value[1] != expected:
            raise ValueError(f"missing/mismatched resource symbol: {name}")
    return {"object_sha256": digest(obj.data), "symbol_sha256": digest(code),
            "symbol_size": len(code), "instruction_count": len(rows),
            "registers_used": sorted(read_write), "registers_written": sorted(writes),
            "private_instructions": 0, "resources": r,
            "audit_scope": manifest["audit_scope"], "disassembly": disassembly}


def pack_stage(source_dir, output_dir, llvm):
    source_dir, output_dir, llvm = Path(source_dir), Path(output_dir), Path(llvm)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((source_dir/"stage.contract.json").read_text())
    obj = output_dir/"stage.co"
    run([llvm/"llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
         "-filetype=obj", source_dir/"stage.s", "-o", obj])
    audit = audit_object(obj, manifest, llvm)
    manifest.update(object_path=str(obj.resolve()), object_sha256=audit["object_sha256"],
                    source_sha256=digest((source_dir/"stage.s").read_bytes()))
    (output_dir/"stage.dis.s").write_text(audit.pop("disassembly"))
    (output_dir/"stage.contract.json").write_text(json.dumps(manifest, indent=2)+"\n")
    (output_dir/"stage.audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    return manifest, audit


def verify_identity(manifest):
    path = Path(manifest["object_path"])
    if digest(path.read_bytes()) != manifest["object_sha256"]:
        raise ValueError("external ASM object hash differs from its registered contract")
