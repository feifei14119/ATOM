#!/usr/bin/env python3
"""Reconstruct and adapt one pinned gfx1250 AITER binary; no GPU execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ORIGINAL = "_ZN5aiter29fmha_bwd_hd64_dq_convert_bf16E"
KERNEL = "mono_dq_convert_kernel"
STAGE = "mono_dq_convert_stage"
SHA = "1784adcc12b4c43a0ce49b12033abff49ab01e84d0c96b2c98b8cd79ec1d00b2"
BODY_SHA = "d758be8e2e0f5e12990f854466bcc0cb33fe1a3643036b2260b468893da016be"


def check(condition, message):
    if not condition:
        raise ValueError(message)


def run(argv):
    p = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    check(p.returncode == 0 and not p.stderr.strip(),
          f"command failed or emitted diagnostics: {argv}\n{p.stdout}{p.stderr}")
    return p.stdout


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Elf:
    """Small read-only ELF64 reader, with bounds checks for these artifacts."""
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        check(self.data[:6] == b"\x7fELF\x02\x01", "expected little-endian ELF64")
        check(struct.unpack_from("<H", self.data, 18)[0] == 224, "expected AMDGPU")
        shoff = struct.unpack_from("<Q", self.data, 40)[0]
        entsize, count, strindex = struct.unpack_from("<HHH", self.data, 58)
        check(entsize == 64 and shoff+count*entsize <= len(self.data), "bad section table")
        sections = [struct.unpack_from("<IIQQQQIIQQ", self.data, shoff+i*64) for i in range(count)]
        strings = self.section_data(sections[strindex])
        self.sections = {self.string(strings, s[0]): s for s in sections}
        self.symbols = {}
        for s in sections:
            if s[1] != 2:  # SHT_SYMTAB, including sized local continuation symbols
                continue
            strings = self.section_data(sections[s[6]])
            check(s[9] == 24, "unexpected symbol entry size")
            for off in range(s[4], s[4]+s[5], 24):
                name, info, other, section, value, size = struct.unpack_from("<IBBHQQ", self.data, off)
                if name:
                    self.symbols[self.string(strings, name)] = dict(
                        value=value, size=size, section=sections[section] if section else None,
                        type=info & 15)

    @staticmethod
    def string(data, start):
        return data[start:data.index(b"\0", start)].decode()

    def section_data(self, section):
        offset, size = section[4:6]
        check(offset+size <= len(self.data), "section extends beyond file")
        return self.data[offset:offset+size]

    def symbol_data(self, name):
        s = self.symbols[name]
        section = s["section"]
        check(section is not None, f"undefined symbol {name}")
        off = s["value"]-section[3]
        check(0 <= off and off+s["size"] <= section[5], "symbol exceeds section")
        return self.section_data(section)[off:off+s["size"]]


def disassemble(llvm, path):
    text = run([llvm / "llvm-objdump", "-d", "--mcpu=gfx1250", path])
    rows = []
    for line in text.splitlines():
        m = re.match(r"\s*(.*?)\s*//\s*([0-9a-fA-F]+):\s*((?:[0-9a-fA-F]{8}(?:\s+|$))+)", line)
        if m:
            words = [int(w, 16) for w in m[3].split()]
            rows.append(dict(asm=m[1], addr=int(m[2], 16), words=words))
    return text, rows


def words_bytes(rows):
    return b"".join(struct.pack("<I", w) for r in rows for w in r["words"])


def descriptor(name):
    # Decoded from the supplier descriptor, then checked byte for byte (except
    # the entry offset) against it. In particular FP32 denorm mode is ZERO.
    return f"""
.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel {name}
  .amdhsa_group_segment_fixed_size 0
  .amdhsa_private_segment_fixed_size 0
  .amdhsa_kernarg_size 240
  .amdhsa_user_sgpr_count 2
  .amdhsa_user_sgpr_kernarg_segment_ptr 1
  .amdhsa_user_sgpr_kernarg_preload_length 0
  .amdhsa_user_sgpr_kernarg_preload_offset 0
  .amdhsa_system_sgpr_workgroup_id_x 1
  .amdhsa_system_sgpr_workgroup_id_y 1
  .amdhsa_system_sgpr_workgroup_id_z 1
  .amdhsa_system_vgpr_workitem_id 2
  .amdhsa_wavefront_size32 1
  .amdhsa_enable_private_segment 0
  .amdhsa_uses_dynamic_stack 0
  .amdhsa_next_free_vgpr 46
  .amdhsa_next_free_sgpr 48
  .amdhsa_reserve_vcc 0
  .amdhsa_named_barrier_count 0
  .amdhsa_float_round_mode_32 0
  .amdhsa_float_round_mode_16_64 0
  .amdhsa_float_denorm_mode_32 0
  .amdhsa_float_denorm_mode_16_64 3
  .amdhsa_fp16_overflow 0
  .amdhsa_memory_ordered 1
  .amdhsa_forward_progress 1
  .amdhsa_inst_pref_size 13
  .amdhsa_round_robin_scheduling 0
.end_amdhsa_kernel
"""


HEADER = '.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"\n.amdhsa_code_object_version 6\n.text\n'


def metadata(note, name, block):
    content = note[note.index("amdhsa.kernels:"):]
    content = content[:content.index("\n...")+4].replace(ORIGINAL, name)
    content = content.replace(".max_flat_workgroup_size: 128", f".max_flat_workgroup_size: {block}")
    if block == 256:
        content = content.replace("    .uniform_work_group_size:",
                                  "    .reqd_workgroup_size: [256, 1, 1]\n    .uniform_work_group_size:")
    return ".amdgpu_metadata\n---\n" + content + "\n.end_amdgpu_metadata\n"


def asm_line(row, start):
    encoded = " ".join(f"{w:08X}" for w in row["words"])
    return f"{row['asm']} // original +0x{row['addr']-start:04x}: {encoded}\n"


def generate(source, llvm, out):
    binary = Elf(source)
    check(sha(binary.data) == SHA, "supplier differs from the reviewed binary")
    out.mkdir(parents=True, exist_ok=True)
    dis, rows = disassemble(llvm, source)
    note = run([llvm / "llvm-readelf", "-h", "-S", "-s", "-r", "-n", source])
    check("There are no relocations" in note, "unexpected supplier relocations")
    section = binary.sections[".text"]
    entry = binary.symbols[ORIGINAL]
    check(entry["size"] == 0 and entry["value"] == section[3] == 0x1900,
          "supplier entry/section changed")
    check(len(rows) == 422 and words_bytes(rows) == binary.section_data(section),
          "disassembly does not cover the complete .text")
    ends = [i for i, r in enumerate(rows) if r["asm"] == "s_endpgm"]
    check(len(ends) == 1, "expected one exit")
    code, padding = rows[:ends[0]+1], rows[ends[0]+1:]
    check(all(r["asm"] == "s_code_end" for r in padding), "unreviewed code after exit")
    check(len(code) == 292 and len(words_bytes(code)) == 1528, "code size changed")
    check(sha(words_bytes(code[:-1])) == BODY_SHA, "body hash changed")
    check(not re.search(r"\bs_(?:branch|cbranch|swappc|setpc|getpc|barrier)",
                        "\n".join(r["asm"] for r in code)), "unexpected control flow")
    (out / "dq_convert.original.co").write_bytes(binary.data)
    (out / "dq_convert.original.disasm.txt").write_text(dis)
    (out / "dq_convert.original.elf.txt").write_text(note)
    original = ("// Reconstructed, assemblable original; source .co SHA-256: " + SHA + "\n"
                + HEADER + f".protected {ORIGINAL}\n.globl {ORIGINAL}\n.p2align 8\n.type {ORIGINAL},@function\n{ORIGINAL}:\n"
                + "".join(asm_line(r, entry["value"]) for r in code)
                + f".Loriginal_end:\n.size {ORIGINAL}, .Loriginal_end-{ORIGINAL}\n"
                + f".fill {len(padding)}, 4, 0xbf9f0000 // original s_code_end padding\n"
                + descriptor(ORIGINAL) + metadata(note, ORIGINAL, 128))
    (out / "dq_convert.original.s").write_text(original)

    edits = {
        0x64: ([0xBE820075], "s_mov_b32 s2, 0"),
        0x68: ([0x8B03FF73, 0xFFFF], "s_mov_b32 s3, 0\ns_nop 0"),
        0x70: ([0x9304FF73, 0x100010], "s_mov_b32 s4, 0\ns_nop 0"),
    }
    adapted = []
    for row in code[:-1]:
        offset = row["addr"]-entry["value"]
        if offset in edits:
            old, new = edits[offset]
            check(row["words"] == old, f"patch mismatch at {offset:#x}")
            adapted.append(f"// PATCH original +0x{offset:04x}: {row['asm']}\n{new}\n")
        else:
            adapted.append(asm_line(row, entry["value"]))
    mono = f"""// gfx1250 Mono-ready operator fragment plus an independent launch wrapper.
// NO caller register save/restore here: the compiler-visible outer boundary
// owns that policy. See contract.json. This stage has no s_endpgm or PC return.
{HEADER}
.protected {KERNEL}
.globl {KERNEL}
.p2align 8
.type {KERNEL},@function
{KERNEL}:
  s_branch {STAGE}

// Exported, nonzero-sized fragment: copy exactly this symbol's bytes into Mono.
.protected {STAGE}
.globl {STAGE}
.type {STAGE},@function
{STAGE}:
  // Precondition: all 8 wave32 waves of the 256-thread CTA enter converged.
  // The caller has drained earlier work and saved its live register bank.
  s_bfe_u32 s40, ttmp8, 0x50019
  s_cmp_lt_u32 s40, 4
  s_cbranch_scc0 .Lmono_stage_done
  v_mbcnt_lo_u32_b32 v0, -1, 0
  s_nop 3
.globl mono_dq_convert_payload
mono_dq_convert_payload:
""" + "".join(adapted) + f"""
.globl mono_dq_convert_payload_end
mono_dq_convert_payload_end:
  // The original s_endpgm at payload+0x5f4 is replaced by direct continuation.
  s_branch .Lmono_stage_done
.Lmono_stage_done:
  // Kernel termination no longer drains the stage. Complete its own accesses.
  s_wait_loadcnt 0
  s_wait_storecnt 0
  s_wait_kmcnt 0
  s_mov_b32 exec_lo, -1
  s_branch mono_dq_convert_stage_end
.protected mono_dq_convert_stage_end
.globl mono_dq_convert_stage_end
mono_dq_convert_stage_end:
.size {STAGE}, mono_dq_convert_stage_end-{STAGE}
  // OUTSIDE the fragment: only the standalone wrapper terminates the kernel.
  // When extracted into Mono, caller leave/restore begins at this address.
  s_endpgm
.Lmono_kernel_end:
.size {KERNEL}, .Lmono_kernel_end-{KERNEL}
""" + descriptor(KERNEL) + metadata(note, KERNEL, 256)
    (out / "dq_convert.mono.s").write_text(mono)
    contract = {
        "status": "assembled_and_statically_checked_only; gfx1250 execution pending",
        "supplier_sha256": SHA, "supplier_body_sha256": BODY_SHA,
        "target": "gfx1250", "wave_size": 32, "caller_block_size": 256,
        "computing_physical_waves": [0, 1, 2, 3],
        "kernel_symbol": KERNEL, "fragment_symbol": STAGE,
        "fragment_end_symbol": "mono_dq_convert_stage_end",
        "payload_symbol": "mono_dq_convert_payload",
        "payload_end_symbol": "mono_dq_convert_payload_end",
        "entry": {"s[0:1]": "240-byte stage parameter block; ordinary global or kernarg memory",
                  "EXEC_LO": "0xffffffff", "TTMP8[29:25]": "original physical waveIDinGroup, 0..7",
                  "prior_work": "caller drains prior memory/async/ALU dependencies before entry"},
        "virtual_grid": [0, 0, 0],
        "shape": {"rows": 64, "columns": 64, "input_bytes": 16384, "output_bytes": 8192},
        "input_layout": "input[64*(16*(r//16)+8*((c//16)%2)+r%8) + 32*(c//32)+16*((r//8)%2)+c%16] = logical[r*64+c]",
        "resources": {"vgpr_count": 46, "sgpr_count": 48, "lds_bytes": 0, "private_bytes": 0,
                      "float_denorm_mode_32": 0, "float_denorm_mode_16_64": 3},
        "conservative_fragment_clobbers": ["v0-v45", "s0-s47", "EXEC_LO", "SCC", "memory"],
        "unchanged_special_state": ["TTMP", "MODE", "M0", "VCC"],
        "exit": "branch to byte immediately after fragment; full EXEC; stage loads/stores drained",
        "caller_obligations": [
            "Declare compiler-visible net clobbers before register allocation; the .co cannot do so.",
            "Save/restore R_keep outside the fragment; this object does not protect caller GPRs.",
            "Provide a distinct input/output tile per real CTA; standalone wrapper launch grid is [1,1,1].",
            "Pack input and initialize the 240-byte parameter block as documented.",
            "Use a full-CTA join and suitable cache scope before consuming other waves' output.",
            "Reconcile final caller descriptor, FP modes, scratch/spills and persistent-grid occupancy.",
        ],
        "patches": [{"offset": off, "old_words": [f"{w:08X}" for w in old],
                     "replacement_assembly": new} for off, (old, new) in edits.items()],
    }
    (out / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    print("Generated original and Mono-adapted assembly, metadata, and contract")


def verify(llvm, out):
    src = Elf(out / "dq_convert.original.co")
    rebuilt = Elf(out / "dq_convert.roundtrip.co")
    mono = Elf(out / "dq_convert.mono.co")
    check(sha(src.data) == SHA, "original copy changed")
    check(rebuilt.section_data(rebuilt.sections[".text"]) == src.section_data(src.sections[".text"]),
          "original assembly does not reproduce the entire 2048-byte .text")
    source_body = src.section_data(src.sections[".text"])[:1524]
    start = mono.symbols["mono_dq_convert_payload"]["value"]
    end = mono.symbols["mono_dq_convert_payload_end"]["value"]
    section = mono.sections[".text"]
    payload = mono.section_data(section)[start-section[3]:end-section[3]]
    check(len(payload) == 1524, "adapted payload extent changed")
    patch_ranges = [(0x64, 0x68), (0x68, 0x70), (0x70, 0x78)]
    for i, (old, new) in enumerate(zip(source_body, payload)):
        check(old == new or any(lo <= i < hi for lo, hi in patch_ranges),
              f"unapproved payload byte change at {i:#x}")
    # Verify replacement encodings by disassembling the final linked object.
    dis, rows = disassemble(llvm, out / "dq_convert.mono.co")
    by_addr = {r["addr"]: r["asm"] for r in rows}
    for off, expected in [(0x64, "s_mov_b32 s2, 0"), (0x68, "s_mov_b32 s3, 0"),
                          (0x6c, "s_nop 0"), (0x70, "s_mov_b32 s4, 0"), (0x74, "s_nop 0")]:
        check(by_addr[start+off] == expected, f"incorrect patch at {off:#x}")
    desc_reports = {}
    for label, elf, symbol in [("roundtrip", rebuilt, ORIGINAL), ("mono", mono, KERNEL)]:
        before, after = src.symbol_data(ORIGINAL+".kd"), elf.symbol_data(symbol+".kd")
        check(before[:16]+before[24:] == after[:16]+after[24:], f"{label} resource descriptor changed")
        entry_delta = struct.unpack_from("<q", after, 16)[0]
        check(elf.symbols[symbol+".kd"]["value"]+entry_delta == elf.symbols[symbol]["value"], "wrong kernel entry")
        desc_reports[label] = {"resource_bytes_match_original": True,
                               "entry_offset": entry_delta,
                               "rsrc1": hex(struct.unpack_from('<I', after, 48)[0]),
                               "rsrc2": hex(struct.unpack_from('<I', after, 52)[0])}
        note = run([llvm / "llvm-readelf", "-h", "-S", "-s", "-r", "-n", out / f"dq_convert.{label if label == 'mono' else 'roundtrip'}.co"])
        check("There are no relocations" in note and "gfx1250" in note, "bad final target/relocations")
        for key, value in [("vgpr_count", 46), ("sgpr_count", 48), ("wavefront_size", 32),
                           ("group_segment_fixed_size", 0), ("private_segment_fixed_size", 0),
                           ("kernarg_segment_size", 240), ("max_flat_workgroup_size", 256 if label == 'mono' else 128)]:
            check(re.search(r"\."+key+rf":\s*{value}\b", note), f"bad metadata {key}")
        (out / f"dq_convert.{label}.elf.txt").write_text(note)
    frag = mono.symbols[STAGE]
    size, address = frag["size"], frag["value"]
    check(address+size == mono.symbols["mono_dq_convert_stage_end"]["value"], "bad fragment end")
    fragment_rows = [r for r in rows if address <= r["addr"] < address+size]
    check(words_bytes(fragment_rows) == mono.symbol_data(STAGE), "incomplete fragment decode")
    text = "\n".join(r["asm"] for r in fragment_rows)
    check(not re.search(r"\bs_(?:endpgm|getpc|setpc|swappc)\b|\bs_(?:getpc|setpc|swappc)_", text),
          "fragment contains kernel exit or indirect call/return")
    # Check branch destinations from signed simm16, including the fall-through
    # continuation at the one-past-end address. No unresolved external branch.
    branches = []
    instruction_starts = {r["addr"] for r in fragment_rows}
    for row in fragment_rows:
        if row["asm"].startswith(("s_branch ", "s_cbranch_")):
            word = row["words"][0]
            imm = struct.unpack("<h", struct.pack("<H", word & 0xffff))[0]
            target = row["addr"]+4+4*imm
            check(target in instruction_starts or target == address+size, "branch escapes fragment")
            branches.append({"offset": row["addr"]-address, "target_offset": target-address})
    check(len(branches) == 3 and branches[-1]["target_offset"] == size, "unexpected direct continuation")
    check(by_addr[address+size] == "s_endpgm", "standalone terminator missing outside fragment")
    check("s_wait_storecnt 0x0" in text and "s_wait_loadcnt 0x0" in text, "output not drained")
    check("s_wait_kmcnt 0x0" in text, "scalar loads not drained")
    # Every TTMP operand is a source, never a destination, for this pinned code.
    for row in fragment_rows:
        if "ttmp" in row["asm"]:
            check(row["asm"].startswith("s_bfe_u32 ") and "ttmp8" in row["asm"], "unreviewed TTMP access")
    blob = mono.symbol_data(STAGE)
    (out / "dq_convert.mono.disasm.txt").write_text(dis)
    (out / "dq_convert.mono.stage.bin").write_bytes(blob)
    (out / "dq_convert.mono.stage.inc").write_text(
        "// Complete position-independent stage, including wave gate and output drain.\n"
        "// Insert caller leave/restore immediately after the last word. No kernel exit.\n"
        + "".join(".long " + ", ".join(f"0x{w:08x}" for w in r["words"])
                  + f" // +0x{r['addr']-address:04x}: {r['asm']}\n" for r in fragment_rows))
    # Prove the exported include can be assembled twice at different offsets,
    # and that its relative continuation reaches the following caller code.
    # This is an object-only placement check, not a runnable/save-restoring Mono.
    placement = HEADER + "\n.globl placement_check\nplacement_check:\n"
    for index in range(2):
        placement += (f".globl fragment_{index}\n.type fragment_{index},@function\nfragment_{index}:\n"
                      + (out / "dq_convert.mono.stage.inc").read_text()
                      + f".globl continuation_{index}\ncontinuation_{index}:\n"
                      + f".size fragment_{index}, continuation_{index}-fragment_{index}\n"
                      + f"s_mov_b32 s41, {0x12340000+index}\n")
    placement += "s_endpgm\n"
    (out / "embedding_check.s").write_text(placement)
    run([llvm / "clang++", "--target=amdgcn-amd-amdhsa", "-mcpu=gfx1250", "-x", "assembler",
         "-c", out / "embedding_check.s", "-o", out / "embedding_check.o"])
    placed = Elf(out / "embedding_check.o")
    for index in range(2):
        symbol = placed.symbols[f"fragment_{index}"]
        check(placed.symbol_data(f"fragment_{index}") == blob, "embedding changed stage bytes")
        check(symbol["value"]+size == placed.symbols[f"continuation_{index}"]["value"],
              "continuation is not immediately after embedded fragment")
    # Host-side address mapping proof, independent of BF16 numeric rounding.
    seen_src, seen_dst = set(), set()
    for wave in range(4):
        for lane in range(32):
            for j in range(8):
                for k in range(4):
                    si = (16*wave+8*(lane//16)+j)*64 + 4*(lane%16)+k
                    rr = 16*wave+8*((lane & 4)//4)+j
                    cc = 32*((lane%16)//8)+16*(lane//16)+4*(lane%4)+k
                    inverse = (16*(rr//16)+8*((cc//16)%2)+rr%8)*64 + 32*(cc//32)+16*((rr//8)%2)+cc%16
                    check(inverse == si, "pack equation disagrees with instruction addresses")
                    seen_src.add(si)
                    seen_dst.add(rr*64+cc)
    check(seen_src == seen_dst == set(range(4096)), "layout is not a full tile permutation")
    report = {"target": "gfx1250", "gpu_executed": False, "supplier_sha256": SHA,
              "roundtrip_text_bytes_identical": 2048, "payload_bytes": len(payload),
              "approved_patch_bytes": 20, "unchanged_payload_bytes": 1504,
              "fragment_symbol": STAGE, "fragment_bytes": size, "fragment_sha256": sha(blob),
              "branch_destinations": branches, "fragment_has_endpgm": False,
              "fragment_has_pc_call_return": False, "standalone_kernel_symbol": KERNEL,
              "descriptor_checks": desc_reports, "layout_addresses_verified": 4096,
              "static_embedding_copies_verified": 2,
              "mono_code_object_sha256": sha(mono.data)}
    (out / "verification.json").write_text(json.dumps(report, indent=2)+"\n")
    print(f"PASS original .text: 2048 bytes identical; descriptor resources identical")
    print(f"PASS adapted payload: 1504 unchanged bytes; only 20 approved patch bytes")
    print(f"PASS fragment: {size} bytes, 3 direct branches, no endpgm/PC call-return")
    print("PASS standalone descriptor/metadata, resolved branches, 4096-address pack permutation")
    print("PASS two static embeddings: identical bytes, each branches to its own continuation")
    print("GPU execution: not performed (requires gfx1250)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["generate", "verify"])
    p.add_argument("--source", type=Path)
    p.add_argument("--llvm-bin", type=Path, default=Path("/opt/rocm/llvm/bin"))
    p.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()
    if args.action == "generate":
        check(args.source is not None, "--source required for generate")
        generate(args.source, args.llvm_bin, args.output)
    else:
        verify(args.llvm_bin, args.output)


if __name__ == "__main__":
    main()
