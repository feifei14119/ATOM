// A separately assembled, callable gfx1250 / wave32 leaf device function.
// Custom ABI: v2=a, v3=b; returns a+b in v2, modulo 2^32.
// Clobbers v2 only; preserves v0/v1/v3, all SGPRs, EXEC, VCC, SCC and MODE.
// s[30:31] holds the return PC supplied by A's s_swappc_b64.
// B has no kernel descriptor: s_setpc is a function return, not s_endpgm.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text
.globl kernel_B
.protected kernel_B
.type kernel_B,@function
.p2align 8
kernel_B:
    // Caller establishes VGPR bank 0 and waits for the argument loads.
    v_add_nc_u32 v2, v2, v3
    s_setpc_b64 s[30:31]
.Lkernel_B_end:
.size kernel_B, .Lkernel_B_end-kernel_B
.p2alignl 7, 0xbf9f0000
.fill 96, 4, 0xbf9f0000
.section .note.GNU-stack,"",@progbits
