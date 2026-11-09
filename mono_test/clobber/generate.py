#!/usr/bin/env python3
"""Build three non-tail, destructive-stage experiments from a supplier .co.

This is an explicit test ABI, not an arbitrary-kernel binary rewriter.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

from abi import HEADER, kernel, metadata


def checked(condition, message):
    if not condition:
        raise ValueError(message)


def extract(binary, contract, llvm):
    checked(contract["target"] == "gfx1100" and contract["wave_size"] == 32
            and contract["block_size"] == 128 and contract["lds_bytes"] == 512
            and contract["private_bytes"] == 0, "unsupported stage contract")
    info = subprocess.check_output([str(llvm / "llvm-readelf"), "-h", "-s", "-r", "-n", str(binary)], text=True)
    checked("gfx1100" in info and "There are no relocations" in info, "expected self-contained gfx1100 ELF")
    checked(re.search(r"\.private_segment_fixed_size:\s+0\b", info)
            and re.search(r"\.group_segment_fixed_size:\s+512\b", info), "resource metadata differs from contract")
    symbols = [line.split() for line in info.splitlines()
               if line.split() and line.split()[-1] == contract["symbol"]]
    sym = next(s for s in symbols if len(s) == 8 and s[3] == "FUNC")
    start, size = int(sym[1], 16), int(sym[2])
    disasm = subprocess.check_output([str(llvm / "llvm-objdump"), "--mcpu=gfx1100",
                                     f"--disassemble-symbols={contract['symbol']}",
                                     f"--start-address={start}", f"--stop-address={start+size}", str(binary)], text=True)
    rows = []
    for line in disasm.splitlines():
        m = re.match(r"\s*(.*?)\s*//\s*([0-9A-Fa-f]+):\s*((?:[0-9A-Fa-f]{8}(?:\s+|$))+)", line)
        if m:
            rows.append((m[1].strip(), int(m[2], 16), m[3].split()))
    checked(rows[-1][0] == "s_endpgm" and len(rows[-1][2]) == 1, "expected one final kernel exit")
    cursor = start
    for asm, addr, words in rows:
        checked(addr == cursor, "incomplete instruction range")
        cursor += 4 * len(words)
    checked(cursor == start + size, "instruction size mismatch")
    # This supplied test operator has no internal branches, calls or PC-relative data.
    checked(not any(re.search(r"\bs_(?:getpc|setpc|swappc|branch|cbranch|endpgm)", asm)
                    for asm, _, _ in rows[:-1]), "unreviewed control flow")
    for kind, count in [("v", 256), ("s", 106)]:
        for reg in range(count):
            checked(any(re.fullmatch(rf"{kind}_mov_b32(?:_e32)? {kind}{reg}, 0", asm)
                        for asm, _, _ in rows), f"missing poison of {kind}{reg}")
    raw = "\n".join(".long " + ", ".join("0x"+w for w in words) + " // " + asm
                    for asm, _, words in rows[:-1])
    print(f"Verified supplier: {size-4} body bytes; v0-v255, s0-s105 poisoned; exit removed")
    return raw


def spaced(text):
    """Conservative adapter scheduling for this correctness experiment."""
    lines = []
    for line in text.strip().splitlines():
        lines.append(line)
        if line.startswith(("v_", "s_add", "s_lshl", "s_mov_b64")):
            lines.append("s_nop 3")
    return "\n".join(lines) + "\n"


def gid():
    return spaced("""s_lshl_b32 s3, s2, 7
v_add_nc_u32 v1, s3, v0
v_lshlrev_b32 v1, 2, v1""")


def pointer(offset):
    return f"s_load_b64 s[4:5], s[0:1], {offset}\ns_waitcnt lgkmcnt(0)\n"


def load_value(offset, dest):
    return pointer(offset) + f"global_load_b32 v{dest}, v1, s[4:5]\ns_waitcnt vmcnt(0)\n"


def store_value(offset, source):
    return pointer(offset) + f"global_store_b32 v1, v{source}, s[4:5]\ns_waitcnt_vscnt null, 0\n"


def seed_flags():
    return "s_mov_b32 vcc_lo, 0x5a5aa5a5\ns_cmp_eq_u32 s2, s2\n"


def private_address():
    return spaced("s_mov_b64 s[10:11], src_private_base\nv_mov_b32 v20, 0\nv_mov_b32 v21, s11")


def save_private(full):
    out = "s_cselect_b32 s9, 1, 0\n" + private_address()
    values = [(0, "s0"), (4, "s1"), (8, "v0"), (12, "s2")]
    if full:
        values += [(16, "v8"), (20, "s8"), (24, "vcc_lo"), (28, "s9"), (32, "exec_lo")]
    for offset, reg in values:
        out += spaced(f"v_mov_b32 v22, {reg}")
        out += f"flat_store_b32 v[20:21], v22 offset:{offset} dlc\n"
    return out + "s_waitcnt_vscnt null, 0\ns_waitcnt lgkmcnt(0)\n"


def restore_private(full):
    # The stage sets EXEC=0; recover a converged full wave before vector loads.
    out = "s_mov_b32 exec_lo, -1\n" + private_address()
    loads = [(0, 22), (4, 23), (8, 0), (12, 24)]
    if full:
        loads += [(16, 8), (20, 25), (24, 26), (28, 27), (32, 28)]
    for offset, reg in loads:
        out += f"flat_load_b32 v{reg}, v[20:21] offset:{offset} glc dlc\n"
    out += "s_waitcnt vmcnt(0) lgkmcnt(0)\n"
    out += spaced("v_readfirstlane_b32 s0, v22\nv_readfirstlane_b32 s1, v23\nv_readfirstlane_b32 s2, v24")
    if full:
        out += spaced("v_readfirstlane_b32 s8, v25\nv_readfirstlane_b32 vcc_lo, v26\nv_readfirstlane_b32 s9, v28")
        out += "s_mov_b32 exec_lo, s9\n"
    out += "s_barrier\n"
    if full:
        out += spaced("v_readfirstlane_b32 s9, v27") + "s_cmp_eq_u32 s9, 1\n"
    return out


def phase_header():
    out = "v_cmpx_eq_u32 v0, 0\n"
    for offset, source in [(512, "s0"), (516, "s1"), (520, "s2")]:
        out += spaced(f"v_mov_b32 v20, {offset}\nv_mov_b32 v22, {source}")
        out += "ds_write_b32 v20, v22\n"
    return out + "s_waitcnt lgkmcnt(0)\ns_mov_b32 exec_lo, -1\ns_barrier\n"


def phase_resume():
    # No register identity survives. Each wave takes a NEW logical wave index.
    # Only memory values indexed by logical work item may cross this boundary.
    out = "s_mov_b32 exec_lo, -1\ns_waitcnt vmcnt(0) lgkmcnt(0)\ns_waitcnt_vscnt null, 0\ns_barrier\n"
    out += spaced("v_mov_b32 v20, 524\nv_mov_b32 v22, 0")
    out += "s_mov_b32 exec_lo, 1\nds_write_b32 v20, v22\ns_waitcnt lgkmcnt(0)\ns_mov_b32 exec_lo, -1\ns_barrier\n"
    out += spaced("v_mov_b32 v22, 1")
    out += "s_mov_b32 exec_lo, 1\nds_add_rtn_u32 v23, v20, v22\ns_waitcnt lgkmcnt(0)\n"
    out += spaced("v_readfirstlane_b32 s3, v23")
    out += "s_mov_b32 exec_lo, -1\n"
    out += spaced("v_mbcnt_lo_u32_b32 v0, -1, 0\ns_lshl_b32 s3, s3, 5\nv_add_nc_u32 v0, s3, v0")
    for offset, reg in [(512, 22), (516, 23), (520, 24)]:
        out += spaced(f"v_mov_b32 v20, {offset}") + f"ds_read_b32 v{reg}, v20\n"
    out += "s_waitcnt lgkmcnt(0)\n"
    out += spaced("v_readfirstlane_b32 s0, v22\nv_readfirstlane_b32 s1, v23\nv_readfirstlane_b32 s2, v24")
    return out


def capture_flags(checkpoint):
    # Capture before gid() changes SCC. Each logical item gets 8 diagnostic words.
    out = "s_cselect_b32 s9, 1, 0\n"
    out += spaced("v_mov_b32 v12, vcc_lo\nv_mov_b32 v13, exec_lo\nv_mov_b32 v14, s9\nv_mov_b32 v15, s8")
    out += gid() + pointer(40) + spaced("v_lshlrev_b32 v2, 3, v1")
    for i in range(4):
        out += f"global_store_b32 v2, v{12+i}, s[4:5] offset:{checkpoint*16+i*4}\n"
    return out + "s_waitcnt_vscnt null, 0\n"


def build(name, mode, blob):
    out = phase_header() if mode == "phase" else ""
    out += gid() + load_value(0, 8)
    out += spaced("v_add_f32 v8, v8, v8\nv_add_f32 v8, 3.0, v8\ns_add_u32 s8, s2, 17")
    if mode == "phase":
        out += store_value(32, 8)
    out += seed_flags()
    for stage in range(2):
        if mode != "phase":
            out += save_private(mode == "preserve")
        if stage:
            out += spaced("s_add_u32 s0, s0, 8\ns_addc_u32 s1, s1, 0")
        out += f"s_branch .L{name}_stage{stage}\n.p2align 6\n.L{name}_stage{stage}:\n{blob}\n"
        out += f"s_branch .L{name}_resume{stage}\n.L{name}_resume{stage}:\n"
        if mode == "phase":
            out += phase_resume() + gid() + load_value(32, 8)
            out += spaced(f"s_add_u32 s8, s2, {17+stage}") + seed_flags()
        else:
            out += restore_private(mode == "preserve")
        out += capture_flags(stage)
        if stage == 0:
            out += load_value(8, 9) + spaced("v_add_f32 v8, v8, v9\ns_add_u32 s8, s8, 1")
            out += store_value(32, 8) + seed_flags()
        else:
            out += load_value(16, 9)
            out += spaced("v_add_f32 v8, v8, v9\nv_cvt_f32_u32 v9, s8\nv_add_f32 v8, v8, v9")
            out += store_value(24, 8) + "s_endpgm\n"
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--llvm-bin", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    blob = extract(args.stage, json.loads(args.contract.read_text()), args.llvm_bin)
    text, entries = HEADER, []
    for mode in ["unsafe", "preserve", "phase"]:
        name = "mono_" + mode
        private, lds = (0, 544) if mode == "phase" else (64, 512)
        text += kernel(name, build(name, mode, blob), 6, private, lds)
        entries.append((name, 6, private, lds))
    args.output.write_text(text + metadata(entries))


if __name__ == "__main__":
    main()
