#!/usr/bin/env python3
"""Fuse the known gfx1100 sub leaf into Mono before final assembly.

Input is GPU machine code, not C++/IR. This deliberately supports the current
ROCm 7.2 demo ABI, not arbitrary kernels or a general binary inliner.
"""
import argparse
from pathlib import Path
import re
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(tool, *args):
    return subprocess.check_output([str(tool), *map(str, args)], text=True)


def extract_leaf(binary, llvm_bin):
    info = run(llvm_bin / "llvm-readelf", "-h", "-s", "-r", binary)
    require("gfx1100" in info and "EM_AMDGPU" in info, "expected gfx1100 ELF")
    require("There are no relocations" in info,
            "the supplied leaf must be self-contained, with no relocations")
    symbols = {}
    for line in info.splitlines():
        fields = line.split()
        if len(fields) == 8 and re.fullmatch(r"\d+:", fields[0]):
            symbols[fields[7]] = fields
    name = "stage_sub_device"
    require(name in symbols, "missing stage_sub_device symbol (stripped binary?)")
    sym = symbols[name]
    require(sym[3] == "FUNC" and sym[6].isdigit(), "expected a defined function")
    start, size = int(sym[1], 16), int(sym[2])
    # Fixed ABI/resource contract for this demo; don't silently accept a new stage.
    for suffix, value in {"num_vgpr": 32, "numbered_sgpr": 32,
                          "num_agpr": 0, "num_named_barrier": 0,
                          "private_seg_size": 0, "uses_flat_scratch": 0,
                          "has_dyn_sized_stack": 0, "has_recursion": 0,
                          "has_indirect_call": 0}.items():
        field = symbols.get(f"{name}.{suffix}")
        require(field and field[6] == "ABS" and int(field[1], 16) == value,
                f"unsupported or missing resource contract: {name}.{suffix}")
    text = run(llvm_bin / "llvm-objdump", "--mcpu=gfx1100",
               f"--disassemble-symbols={name}", f"--start-address={start}",
               f"--stop-address={start + size}", binary)
    rows = []
    for line in text.splitlines():
        match = re.match(r"\s*(.*?)\s*//\s*([0-9A-Fa-f]+):\s*"
                         r"((?:[0-9A-Fa-f]{8}(?:\s+|$))+)", line)
        if match:
            rows.append((match[1].strip(), int(match[2], 16), match[3].split()))
    require(rows and rows[-1][0] == "s_setpc_b64 s[30:31]"
            and len(rows[-1][2]) == 1, "expected a single final device return")
    cursor = start
    # This allowlist covers the current leaf, including its alignment NOPs.
    # Unknown instructions require review rather than speculative binary rewriting.
    allowed = set("""s_waitcnt v_and_b32_e32 s_mov_b32 s_delay_alu
        v_cmpx_lt_i32_e64 s_load_b32 v_mov_b32_e32 s_cmp_lt_u32 s_cselect_b32
        s_add_u32 s_addc_u32 global_load_u16 s_nop v_ashrrev_i32_e32
        v_lshlrev_b64 v_add_co_u32 v_add_co_ci_u32_e64 flat_load_b32
        v_dual_add_f32 v_cmp_ge_i32_e32 flat_store_b32 s_or_b32
        s_and_not1_b32 s_waitcnt_vscnt s_barrier buffer_gl0_inv
        v_cmpx_eq_u32_e32 s_cbranch_execz s_cbranch_execnz""".split())
    instruction_addresses = {address for _, address, _ in rows}
    for index, (asm, address, words) in enumerate(rows):
        require(address == cursor, "incomplete or unrecognized disassembly")
        cursor += 4 * len(words)
        if index == len(rows) - 1:
            continue
        mnemonic = asm.split()[0]
        require(mnemonic in allowed, f"unsupported leaf instruction: {asm}")
        if mnemonic.startswith("s_cbranch_"):
            offset = int(words[0], 16) & 0xffff
            offset = offset - 0x10000 if offset >= 0x8000 else offset
            require(address + 4 + 4 * offset in instruction_addresses,
                    "branch leaves the supplied function")
    require(cursor == start + size, "symbol size does not match disassembly")
    # Preserve exact instruction words and all internal relative branch offsets.
    # The removed final return is replaced by the caller's 4-byte s_endpgm.
    return "\n".join(
        "\t.long " + ", ".join("0x" + word for word in words) + " // " + asm
        for asm, _, words in rows[:-1])


def fuse(caller, leaf):
    require('.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"' in caller,
            "caller must target gfx1100")
    start = caller.index("\t.protected\tmono_kernel")
    end = caller.index("\t.section\t.AMDGPU.csdata", start)
    kernel = caller[start:end]
    # Match the exact ROCm 7.2 call-site sequence. Keep all ABI argument setup.
    setup = ("\ts_getpc_b64 s[18:19]\n"
             "\ts_add_u32 s18, s18, stage_sub_device@rel32@lo+4\n"
             "\ts_addc_u32 s19, s19, stage_sub_device@rel32@hi+12\n")
    call = "\ts_swappc_b64 s[30:31], s[18:19]\n\ts_endpgm\n"
    require(kernel.count(setup) == 1 and kernel.count(call) == 1,
            "unsupported caller layout: regenerate/review for this compiler")
    kernel = kernel.replace(setup, "")
    # This call is the last operation of CTA 0. A direct branch skips alignment
    # padding; the leaf then falls through to the caller's s_endpgm, with no return.
    kernel = kernel.replace(call, "\ts_branch .Lmono_sub_body\n"
                            "\t.p2align 6\n.Lmono_sub_body:\n" + leaf
                            + "\n.Lmono_sub_end:\n\ts_endpgm\n")
    require(not re.search(r"\bs_(?:getpc|setpc|swappc)_b64\b", kernel),
            "unexpected remaining indirect control flow")
    # Retain conservative compiler resource allocation. Dropping unused HIP
    # helper bodies must not lower the registers allocated for the opaque leaf.
    maxima = "\n".join(re.findall(r"^\s*\.set amdgpu\.max_.*$", caller, re.M))
    if "amdgpu.max_num_named_barrier," not in maxima:
        # ROCm 7.2 -S omits this definition; gfx1100 uses legacy s_barrier.
        maxima += "\n\t.set amdgpu.max_num_named_barrier, 0"
    metadata = caller[caller.index("\t.amdgpu_metadata"):]
    return ("// Generated by fuse_sub.py: binary leaf embedded without a call/return.\n"
            '\t.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"\n'
            "\t.amdhsa_code_object_version 6\n\t.text\n" + kernel + maxima
            + "\n\t.text\n\t.p2alignl 7, 3214868480\n"
            '\t.fill 96, 4, 3214868480\n\t.section ".note.GNU-stack","",@progbits\n'
            + metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caller", required=True, type=Path)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--llvm-bin", required=True, type=Path)
    args = parser.parse_args()
    try:
        leaf = extract_leaf(args.stage, args.llvm_bin)
        result = fuse(args.caller.read_text(), leaf)
        args.output.write_text(result)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Cannot fuse this binary/caller: {error}\n")
    print(f"Fused {args.stage} into {args.output}; direct branch, no call/return")


if __name__ == "__main__":
    main()
