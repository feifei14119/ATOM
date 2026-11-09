"""gfx1100 wave32 adapter; one schema defines clobbers and LDS saves."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Bank:
    sgprs: int = 8
    vgprs: int = 8

    def __post_init__(self):
        if not (3 <= self.sgprs <= 16 and 1 <= self.vgprs <= 8):
            raise ValueError("demo supports 3..16 SGPRs and 1..8 VGPRs")

    @property
    def scalars(self):
        # Reserved by this ROCm backend; do not declare these as clobbered.
        # They are protected as well, even though this caller does not use them.
        return list(range(self.sgprs)) + [32, 105]

    @property
    def names(self):
        return [f"v{i}" for i in range(self.vgprs)] + [f"s{i}" for i in self.scalars]

    @property
    def stride(self):
        return len(self.names) * 4

    @property
    def lds_bytes(self):
        return 1024 + 128 * self.stride

    @property
    def clobbers(self):
        return ",".join(
            [f"~{{v{i}}}" for i in range(self.vgprs, 256)]
            + [f"~{{s{i}}}" for i in range(106) if i not in self.scalars]
            + ["~{vcc}", "~{scc}", "~{memory}"])


def spaced(code):
    # Deliberately conservative scheduling, not a performance-tuned adapter.
    return "\n".join(line + ("\ns_nop 3" if line.startswith(
        ("v_", "s_lshl", "s_mov_b64")) else "")
        for line in code.strip().splitlines()) + "\n"


def enter(bank):
    # Precondition: full EXEC; v0 is the current logical thread index.
    out = "s_nop 7\ns_waitcnt vmcnt(0) lgkmcnt(0)\ns_waitcnt_vscnt null, 0\n"
    out += spaced(f"v_mul_lo_u32 v64, v0, {bank.stride}\nv_add_nc_u32 v64, 1024, v64")
    for slot, reg in enumerate(bank.names):
        if reg.startswith("s"):
            out += spaced(f"v_mov_b32 v65, {reg}")
            src = "v65"
        else:
            src = reg
        out += f"ds_write_b32 v64, {src} offset:{slot*4}\n"
    out += "s_waitcnt lgkmcnt(0)\n"
    # Reset the fixed-address ticket before the supplier erases identity.
    out += "v_cmpx_eq_u32 v0, 0\n"
    out += spaced("v_mov_b32 v64, 512\nv_mov_b32 v65, 0")
    out += "ds_write_b32 v64, v65\ns_waitcnt lgkmcnt(0)\ns_mov_b32 exec_lo, -1\ns_barrier\n"
    return out


def leave(bank):
    out = "s_mov_b32 exec_lo, -1\ns_waitcnt vmcnt(0) lgkmcnt(0)\ns_waitcnt_vscnt null, 0\ns_barrier\n"
    out += spaced("v_mov_b32 v64, 512\nv_mov_b32 v65, 1")
    out += "s_mov_b32 exec_lo, 1\nds_add_rtn_u32 v66, v64, v65\ns_waitcnt lgkmcnt(0)\n"
    out += spaced("v_readfirstlane_b32 s64, v66")
    out += "s_mov_b32 exec_lo, -1\n"
    # Whole logical-wave contexts may migrate to a different physical wave.
    out += spaced("v_mbcnt_lo_u32_b32 v64, -1, 0\ns_lshl_b32 s64, s64, 5\nv_add_nc_u32 v64, s64, v64")
    out += spaced(f"v_mul_lo_u32 v64, v64, {bank.stride}\nv_add_nc_u32 v64, 1024, v64")
    for slot, reg in enumerate(bank.names):
        if reg.startswith("s"):
            out += f"ds_read_b32 v65, v64 offset:{slot*4}\ns_waitcnt lgkmcnt(0)\n"
            out += spaced(f"v_readfirstlane_b32 {reg}, v65")
        else:
            out += f"ds_read_b32 {reg}, v64 offset:{slot*4}\n"
    out += "s_waitcnt lgkmcnt(0)\ns_nop 7\ns_barrier\n"
    return out


def boundary(bank, blob, index):
    return (f"// BEGIN protected boundary {index}\n" + enter(bank)
            + f"s_branch .Lbinary_{index}\n.p2align 6\n.Lbinary_{index}:\n"
            + blob + f"\ns_branch .Lresume_{index}\n.Lresume_{index}:\n"
            + leave(bank) + f"// END protected boundary {index}\n")
