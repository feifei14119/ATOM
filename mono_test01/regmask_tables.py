"""Copied ELF/table readers from callee_test01; uses the selected llc register IDs."""
import hashlib
import re
import struct
import subprocess
from pathlib import Path

class Elf:
    """Small ELF64 reader for the installed LLVM tables and AMDGPU objects."""
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b'\x7fELF\x02\x01'
        self.kind, self.machine = struct.unpack_from('<HH', self.data, 16)
        at = struct.unpack_from('<Q', self.data, 40)[0]
        width, count = struct.unpack_from('<HH', self.data, 58)
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.data, at+i*width)
                         for i in range(count)]
        self.symbols = {}
        for sec in self.sections:
            if sec[1] != 2:
                continue
            strings_sec = self.sections[sec[6]]
            strings = self.data[strings_sec[4]:strings_sec[4]+strings_sec[5]]
            for at in range(sec[4], sec[4]+sec[5], sec[9]):
                name, info, _, index, value, size = struct.unpack_from('<IBBHQQ', self.data, at)
                name = strings[name:strings.index(b'\0', name)].decode()
                if name:
                    self.symbols[name] = index, value, size, info

    def blob(self, name):
        index, value, size, _ = self.symbols[name]
        assert 0 < index < len(self.sections) and size
        sec = self.sections[index]
        at = sec[4]+value-sec[3]
        return self.data[at:at+size]

    def absolute(self, name):
        index, value, _, _ = self.symbols[name]
        assert index == 0xfff1, f'Expected absolute symbol: {name}'
        return value


def run(argv):
    argv = [str(arg) for arg in argv]
    result = subprocess.run(argv, text=True, capture_output=True)
    if result.returncode or result.stderr:
        raise RuntimeError(f'Command failed or emitted diagnostics: {argv}\n'
                           f'{result.stdout}\n{result.stderr}')
    return result.stdout


def native_mask(llc):
    # Read THIS compiler's named table, including LO16/HI16 and tuple aliases.
    # Never copy numeric register IDs from another LLVM build. The symbol names
    # and 24-byte MCRegisterDesc layout are checked for the pinned compiler.
    elf = Elf(llc)
    mask = elf.blob('_ZN4llvmL18CSR_AMDGPU_RegMaskE')
    desc = elf.blob('_ZN4llvm13AMDGPURegDescE')
    strings = elf.blob('_ZN4llvm16AMDGPURegStringsE')
    assert len(desc) % 24 == 0
    count = len(desc)//24
    assert len(mask) == ((count+31)//32)*4
    names = []
    for reg in range(count):
        if mask[reg//8] & (1 << (reg % 8)):
            at = struct.unpack_from('<I', desc, reg*24)[0]
            name = strings[at:strings.index(b'\0', at)].decode()
            assert re.fullmatch(r'[A-Za-z0-9_]+', name)
            names.append(name)
    assert {'SGPR30', 'SGPR32', 'SGPR105', 'VGPR40', 'VGPR255'} <= set(names)
    assert 'VGPR0' not in names and 'SGPR0' not in names
    return names, hashlib.sha256(elf.data).hexdigest()


def low_mask(names):
    kept, removed = [], []
    for name in names:
        vgprs = {int(r) for r in re.findall(r'VGPR(\d+)', name)}
        sgprs = {int(r) for r in re.findall(r'SGPR(\d+)', name)}
        # A tuple is preserved only if ALL its component registers survive.
        drop = any(r >= 64 for r in vgprs) or any(r >= 40 for r in sgprs)
        (removed if drop else kept).append(name)
    assert {int(n[4:]) for n in kept if re.fullmatch(r'VGPR\d+', n)} == set(range(40, 48)) | set(range(56, 64))
    assert {int(n[4:]) for n in kept if re.fullmatch(r'SGPR\d+', n)} == set(range(30, 40))
    assert all(re.search(r'[SV]GPR\d+', name) for name in removed)
    return kept, removed

