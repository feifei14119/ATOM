"""gfx1100 proof: restrict one device call before RA, without a function VGPR cap.

This is a pinned-toolchain MIR prototype. ATOM should implement the equivalent
mask change inside its LLVM codegen pipeline, avoiding MIR serialization.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b"\x7fELF\x02\x01"
        at = struct.unpack_from("<Q", self.data, 40)[0]
        width, count = struct.unpack_from("<HH", self.data, 58)
        self.sections = [struct.unpack_from("<IIQQQQIIQQ", self.data, at + i * width)
                         for i in range(count)]
        self.symbols = {}
        for section in self.sections:
            if section[1] != 2:
                continue
            strings_sec = self.sections[section[6]]
            strings = self.data[strings_sec[4]:strings_sec[4] + strings_sec[5]]
            for at in range(section[4], section[4] + section[5], section[9]):
                name, info, other, index, value, size = struct.unpack_from("<IBBHQQ", self.data, at)
                name = strings[name:strings.index(b"\0", name)].decode()
                if name:
                    self.symbols[name] = (index, value, size)

    def blob(self, name):
        index, value, size = self.symbols[name]
        section = self.sections[index]
        at = section[4] + value - section[3]
        return self.data[at:at + size]

    def absolute(self, name):
        index, value, size = self.symbols[name]
        assert index == 0xFFF1, f"Expected absolute resource symbol: {name}"
        return value


def native_mask(llc):
    # Obtain the exact installed compiler's tables, including all register
    # aliases. Never reuse numeric register IDs from another LLVM build.
    # These symbols and MCRegisterDesc's 24-byte layout are ROCm-7.2-specific.
    elf = Elf(llc)
    mask = elf.blob("_ZN4llvmL18CSR_AMDGPU_RegMaskE")
    desc = elf.blob("_ZN4llvm13AMDGPURegDescE")
    strings = elf.blob("_ZN4llvm16AMDGPURegStringsE")
    assert len(desc) % 24 == 0
    count = len(desc) // 24
    assert len(mask) == ((count + 31) // 32) * 4
    names = []
    for reg in range(count):
        if mask[reg // 8] & (1 << (reg % 8)):
            at = struct.unpack_from("<I", desc, reg * 24)[0]
            name = strings[at:strings.index(b"\0", at)].decode()
            assert re.fullmatch(r"[A-Za-z0-9_]+", name)
            names.append(name)
    assert {f"VGPR{i}" for i in range(40, 48)} <= set(names)
    assert {"SGPR30", "SGPR31", "SGPR32", "SGPR105"} <= set(names)
    assert "VGPR0" not in names
    return names, hashlib.sha256(elf.data).hexdigest()


def function_body(assembly):
    start = assembly.index("mono_kernel:")
    end = assembly.index(".section\t.rodata", start)
    return assembly[start:end]


def run(argv):
    result = subprocess.run([str(x) for x in argv], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode or result.stderr:
        raise RuntimeError(f"Command failed or emitted diagnostics: {argv}\n"
                           f"{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bitcode", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--llvm-bin", default="/opt/rocm/llvm/bin", type=Path)
    ap.add_argument("--vgpr-first", type=int, default=40)
    ap.add_argument("--vgpr-count", type=int, default=8)
    args = ap.parse_args()
    llvm = args.llvm_bin
    out = args.output.parent
    out.mkdir(parents=True, exist_ok=True)
    version = run([llvm / "clang++", "--version"])
    assert "7b800a19466229b8479a78de19143dc33c3ab9b5" in version, "Revalidate prototype for this toolchain"
    names, tool_sha = native_mask(llvm / "llc")
    bank = set(range(args.vgpr_first, args.vgpr_first + args.vgpr_count))
    assert bank and {f"VGPR{i}" for i in bank} <= set(names), "Bank must be a subset of the ordinary ABI"
    kept = []
    removed = []
    for name in names:
        # Covers full-width VGPRs, LO16/HI16 views, and every register tuple.
        ids = {int(x) for x in re.findall(r"VGPR(\d+)", name)}
        (removed if ids and not ids <= bank else kept).append(name)
    assert all("VGPR" in name for name in removed), "Do not change SGPR/special mask bits"
    assert [n for n in kept if re.fullmatch(r"VGPR\d+", n)] == [f"VGPR{i}" for i in sorted(bank)]

    # This prototype supports the known leaf stage contract, not arbitrary .co.
    stage = Elf(args.stage)
    code_sha = hashlib.sha256(stage.blob("stage_sub_device")).hexdigest()
    assert code_sha == "040b7830b48375bd886e11e41256c3df26bc62a7f6b6bc8c4f0d1d6bc19bef87", "Re-audit changed ASM ABI/resources"
    resource_map = {key: stage.absolute("stage_sub_device." + symbol) for key, symbol in (
        ("vgpr", "num_vgpr"), ("sgpr", "numbered_sgpr"),
        ("agpr", "num_agpr"), ("private", "private_seg_size"),
        ("named_barrier", "num_named_barrier"))}
    assert resource_map["private"] == resource_map["agpr"] == resource_map["named_barrier"] == 0

    clean_ir = out / "mono_kernel.codegen.ll"
    # Remove unused HIP assert/printf helpers. Keep the same main kernel and
    # external stage; this is dead-code removal, not stage/function splitting.
    run([llvm / "opt", "-S", "-passes=internalize,globaldce",
         "-internalize-public-api-list=mono_kernel,stage_sub_device",
         args.bitcode, "-o", clean_ir])
    assert "amdgpu-num-vgpr" not in clean_ir.read_text(), "No function-wide VGPR cap allowed"
    flags = [llvm / "llc", "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1100",
             "-O2", "-verify-machineinstrs"]
    baseline_path = out / "mono_kernel.baseline.s"
    raw_mir = out / "mono_kernel.before_regmask.mir"
    run(flags + [clean_ir, "-o", baseline_path])
    run(flags + ["-stop-after=finalize-isel", clean_ir, "-o", raw_mir])
    baseline = baseline_path.read_text()
    mir = raw_mir.read_text()
    assert re.findall(r"^name:\s+(\S+)", mir, re.M) == ["mono_kernel"]

    # ROCm 7.2's MIR parser demands full VCC on this opcode even though its
    # wave32 printer emits VCC_LO. Keep the real VCC_LO dependency and add the
    # parser's full-register operand as undef (no new high-half dependency).
    # The unmodified-call roundtrip below MUST reproduce every baseline
    # instruction, so normalization is not silently trusted.
    mir, normalized = re.subn(
        r"^(\s*S_CBRANCH_VCC(?:NZ|Z) [^\n]*\$vcc_lo)\s*$",
        r"\1, implicit undef $vcc", mir, flags=re.M)
    roundtrip_mir = out / "mono_kernel.roundtrip.mir"
    roundtrip_mir.write_text(mir)
    raw_roundtrip = out / "mono_kernel.roundtrip.raw.s"
    run(flags + ["-start-after=finalize-isel", roundtrip_mir, "-o", raw_roundtrip])
    assert function_body(raw_roundtrip.read_text()) == function_body(baseline), "MIR roundtrip changed baseline instructions"

    # Fix only descriptor state lost by this pinned MIR serialization. Never
    # inherit baseline resource counts: custom RA may legitimately change them.
    user_sgprs = int(re.search(r"\.amdhsa_user_sgpr_count (\d+)", baseline)[1])

    def finish_assembly(text):
        text, n = re.subn(r"(\.amdhsa_user_sgpr_count )\d+",
                          lambda m: m[1] + str(user_sgprs), text)
        assert n == 1
        text = re.sub(r"(; COMPUTE_PGM_RSRC2:USER_SGPR: )\d+",
                      lambda m: m[1] + str(user_sgprs), text)
        if not re.search(r"\.set\s+amdgpu.max_num_named_barrier,", text):
            text += "\n.set amdgpu.max_num_named_barrier, 0\n"
        # Include known external leaf usage; generic linking does not infer it.
        for suffix, value in (("vgpr", resource_map["vgpr"]),
                              ("sgpr", resource_map["sgpr"]),
                              ("agpr", resource_map["agpr"])):
            text, n = re.subn(r"(\.set\s+amdgpu.max_num_" + suffix + r", )([0-9]+)",
                              lambda m: m[1] + str(max(int(m[2]), value)), text)
            assert n == 1
        return text

    (out / "mono_kernel.roundtrip.s").write_text(finish_assembly(raw_roundtrip.read_text()))
    custom = "CustomRegMask(" + ",".join("$" + name.lower() for name in kept) + ")"
    mir, n = re.subn(r"(^.*SI_CALL[^\n]*@stage_sub_device, )csr_amdgpu",
                     lambda m: m[1] + custom, mir, flags=re.M)
    assert n == 1, "Expected exactly one target call before register allocation"
    custom_mir = out / "mono_kernel.callsite.mir"
    custom_mir.write_text(mir)
    raw_custom = out / "mono_kernel.regmask.raw.s"
    run(flags + ["-start-after=finalize-isel", custom_mir, "-o", raw_custom])
    final = finish_assembly(raw_custom.read_text())
    args.output.write_text(final)
    (out / "mono_kernel.function.s").write_text(function_body(final))
    report = {
        "caller": "mono_kernel", "callee": "stage_sub_device", "calls_changed": 1,
        "point": "after finalize-isel, before register allocation",
        "caller_vgpr_limit": None, "preserved_vgprs": sorted(bank),
        "standard_sgpr_and_special_mask_unchanged": True,
        "original_mask_name_count": len(names), "custom_mask_name_count": len(kept),
        "removed_alias_count": len(removed), "kept_register_names": kept,
        "llc_sha256": tool_sha, "stage_function_sha256": code_sha,
        "stage_resources": resource_map,
        "mir_vcc_operands_normalized": normalized,
        "baseline_roundtrip_instructions_identical": True,
        "restored_user_sgpr_count": user_sgprs,
        "prototype_scope": "ROCm 7.2 gfx1100; known stage; not an ATOM backend integration",
    }
    (out / "callsite_regmask.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: one pre-RA call regmask, VGPR {min(bank)}-{max(bank)}, no function-wide cap")


if __name__ == "__main__":
    main()
