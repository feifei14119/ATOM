// Full C1 WQKV device function. No input payload is loaded by its caller.
// gfx1250, wave32, 256 threads, HIDDEN=5120, t0=0, n=1.
// ABI: qkv=s2:3, tag=s0, xl=s1, red=s4, task=s5, t0=v4, n=s6,
// weight=s8:9, weight_scale=s10:11, x8s=s12:13, x8=s14:15,
// tid=v0, diag=s16:17, failure=s18:19, bid=s7, poll_limit=s22.
// s30:31 is the return PC. EXEC and all input registers are preserved.
// This is a readable, conservative interface example, not a tuned kernel.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text

// Conservative dependency waits keep the example independent of scheduling.
.macro A instruction:vararg
    \instruction
    s_wait_alu 0
.endm

// Read one tagged pair with a wave-wide retry. On timeout publish a failure
// flag and supply zero data; all waves still execute the same CTA barriers.
// v2 holds the byte offset. v18/v19 are NOT used here (weight registers).
.macro POLL payload, tagreg, base
    s_mov_b32 s24, s22
.Lpoll\@:
    global_load_b64 v[\payload:\tagreg], v2, \base scope:SCOPE_DEV
    A v_mov_b32 v14, 0
    global_load_b32 v15, v14, s[18:19] scope:SCOPE_DEV
    s_wait_loadcnt 0
    A v_cmp_ne_u32 vcc_lo, 0, v15
    s_cbranch_vccnz .Lfailed\@
    A v_cmp_ne_u32 vcc_lo, s0, v\tagreg
    s_cbranch_vccz .Lready\@
    A s_sub_u32 s24, s24, 1
    s_cmp_eq_u32 s24, 0
    s_cbranch_scc1 .Ltimeout\@
    s_sleep 64
    s_branch .Lpoll\@
.Ltimeout\@:
    A v_mov_b32 v15, 1
    global_atomic_or_b32 v14, v15, s[18:19] scope:SCOPE_DEV
    s_wait_storecnt 0
.Lfailed\@:
    A v_mov_b32 v\payload, 0
    A v_mov_b32 v\tagreg, s0
.Lready\@:
.endm

.globl mono_wqkv_asm
.hidden mono_wqkv_asm
.type mono_wqkv_asm,@function
.p2align 6
mono_wqkv_asm:
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_wait_dscnt 0
    s_wait_alu 0

    // Eight waves handle K steps w, w+8, ..., w+32.
    A v_lshrrev_b32 v8, 5, v0
    A v_and_b32 v9, 15, v0
    A v_lshrrev_b32 v10, 4, v0
    A v_and_b32 v10, 1, v10
    A s_mul_i32 s23, s5, 81920
    A s_lshr_b32 s26, s5, 1
    A s_mul_i32 s26, s26, 160

    // First K-step weight prefetch precedes input mailbox polling.
    A v_lshlrev_b32 v12, 11, v8
    A v_add_nc_u32 v12, s23, v12
    A v_lshlrev_b32 v11, 8, v10
    A v_add_nc_u32 v12, v11, v12
    A v_lshlrev_b32 v11, 4, v9
    A v_add_nc_u32 v12, v11, v12
    global_load_b128 v[16:19], v12, s[8:9] scope:SCOPE_DEV
    global_load_b128 v[20:23], v12, s[8:9] offset:512 scope:SCOPE_DEV
    global_load_b128 v[24:27], v12, s[8:9] offset:1024 scope:SCOPE_DEV
    global_load_b128 v[28:31], v12, s[8:9] offset:1536 scope:SCOPE_DEV
    A v_lshlrev_b32 v13, 2, v8
    A v_add_nc_u32 v13, s26, v13
    global_load_b32 v56, v13, s[10:11] scope:SCOPE_DEV

    // The entire X row: 1280 packed words, five words per CTA thread.
    A v_mov_b32 v1, v0
    s_mov_b32 s21, 5
.Lcopy_x:
    A v_mul_lo_u32 v2, 1280, v4
    A v_add_nc_u32 v2, v1, v2
    A v_lshlrev_b32 v2, 3, v2
    POLL 6, 7, "s[14:15]"
    A v_lshlrev_b32 v3, 2, v1
    A v_add_nc_u32 v3, s1, v3
    ds_store_b32 v3, v6
    A v_add_nc_u32 v1, 256, v1
    A s_sub_u32 s21, s21, 1
    s_cmp_lg_u32 s21, 0
    s_cbranch_scc1 .Lcopy_x
    s_wait_dscnt 0
    s_barrier_signal -1
    s_barrier_wait -1

    // X is now prepared by this function, not by FlyDSL.
    .set acc, 48
    .rept 8
        A v_mov_b32 v[acc], 0
        .set acc, acc+1
    .endr
    s_mov_b32 s21, 0
.Lk_step:
    A s_lshl_b32 s27, s21, 3
    A v_add_nc_u32 v11, s27, v8
    s_cmp_eq_u32 s21, 0
    s_cbranch_scc1 .Lweights_ready
    A v_lshlrev_b32 v12, 11, v11
    A v_add_nc_u32 v12, s23, v12
    A v_lshlrev_b32 v13, 8, v10
    A v_add_nc_u32 v12, v13, v12
    A v_lshlrev_b32 v13, 4, v9
    A v_add_nc_u32 v12, v13, v12
    global_load_b128 v[16:19], v12, s[8:9] scope:SCOPE_DEV
    global_load_b128 v[20:23], v12, s[8:9] offset:512 scope:SCOPE_DEV
    global_load_b128 v[24:27], v12, s[8:9] offset:1024 scope:SCOPE_DEV
    global_load_b128 v[28:31], v12, s[8:9] offset:1536 scope:SCOPE_DEV
    A v_lshlrev_b32 v13, 2, v11
    A v_add_nc_u32 v13, s26, v13
    global_load_b32 v56, v13, s[10:11] scope:SCOPE_DEV
.Lweights_ready:
    // Four input E8M0 codes are independent tagged i32 mailbox elements.
    A v_mul_lo_u32 v2, 160, v4
    A v_lshlrev_b32 v13, 2, v11
    A v_add_nc_u32 v2, v13, v2
    A v_lshlrev_b32 v2, 3, v2
    POLL 58, 59, "s[12:13]"
    A v_add_nc_u32 v2, 8, v2
    POLL 60, 61, "s[12:13]"
    A v_add_nc_u32 v2, 8, v2
    POLL 62, 63, "s[12:13]"
    A v_add_nc_u32 v2, 8, v2
    POLL 64, 65, "s[12:13]"
    A v_lshlrev_b32 v60, 8, v60
    A v_lshlrev_b32 v62, 16, v62
    A v_lshlrev_b32 v64, 24, v64
    A v_or_b32 v57, v58, v60
    A v_or_b32 v57, v57, v62
    A v_or_b32 v57, v57, v64

    A v_lshlrev_b32 v3, 7, v11
    A v_lshlrev_b32 v13, 4, v10
    A v_add_nc_u32 v3, v3, v13
    A v_add_nc_u32 v3, s1, v3
    ds_load_b128 v[32:35], v3
    ds_load_b128 v[36:39], v3 offset:32
    ds_load_b128 v[40:43], v3 offset:64
    ds_load_b128 v[44:47], v3 offset:96
    s_wait_loadcnt 0
    s_wait_dscnt 0
    A v_wmma_scale_f32_16x16x128_f8f6f4 v[48:55], v[16:31], v[32:47], v[48:55], v56, v57
    A s_add_u32 s21, s21, 1
    s_cmp_lt_u32 s21, 5
    s_cbranch_scc1 .Lk_step

    // Lanes 0 and 16 contribute eight rows each to red[wave][row].
    A v_cmp_eq_u32 vcc_lo, 0, v9
    A s_and_saveexec_b32 s20, vcc_lo
    A v_lshlrev_b32 v3, 6, v8
    A v_lshlrev_b32 v13, 5, v10
    A v_add_nc_u32 v3, v3, v13
    A v_add_nc_u32 v3, s4, v3
    ds_store_b128 v3, v[48:51]
    ds_store_b128 v3, v[52:55] offset:16
    A s_mov_b32 exec_lo, s20
    s_wait_dscnt 0
    s_barrier_signal -1
    s_barrier_wait -1

    // CTA threads 0..15 sum waves in the same order as stage_wqkv_c1.
    A v_cmp_gt_u32 vcc_lo, 16, v0
    A s_and_saveexec_b32 s20, vcc_lo
    A v_lshlrev_b32 v3, 2, v0
    A v_add_nc_u32 v3, s4, v3
    A v_mov_b32 v66, 0
    .set part, 0
    .rept 8
        ds_load_b32 v6, v3 offset:part
        s_wait_dscnt 0
        A v_add_f32 v66, v66, v6
        .set part, part+64
    .endr
    A v_cvt_pk_bf16_f32 v66, v66, v66
    A v_lshlrev_b32 v66, 16, v66
    A v_mov_b32 v67, s0
    A s_lshl_b32 s27, s5, 4
    A v_add_nc_u32 v2, s27, v0
    A v_lshlrev_b32 v2, 3, v2
    global_store_b64 v2, v[66:67], s[2:3] scope:SCOPE_DEV
    A s_mov_b32 exec_lo, s20
    s_wait_storecnt 0
    s_barrier_signal -1
    s_barrier_wait -1

    // Intentional extra clobbers make the non-default register contract clear.
    A v_mov_b32 v95, 0x95
    s_mov_b32 s40, 0x40
    s_mov_b32 s48, 0x48
    s_mov_b32 s63, 0x63
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_wait_dscnt 0
    s_wait_alu 0
    s_setpc_b64 s[30:31]
.Lend:
.size mono_wqkv_asm, .Lend-mono_wqkv_asm
.set mono_wqkv_asm.num_vgpr, 96
.set mono_wqkv_asm.numbered_sgpr, 64
.set mono_wqkv_asm.private_seg_size, 0
.set mono_wqkv_asm.num_agpr, 0
.set mono_wqkv_asm.num_named_barrier, 0
.set mono_wqkv_asm.uses_vcc, 1
.set mono_wqkv_asm.uses_flat_scratch, 0
.set mono_wqkv_asm.has_dyn_sized_stack, 0
.set mono_wqkv_asm.has_recursion, 0
.set mono_wqkv_asm.has_indirect_call, 0
.section .note.GNU-stack,"",@progbits
