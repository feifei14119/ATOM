// Generated from dq_convert.original.s by prepare.py.
// CUSTOM device ABI: default argument ABI, call-preserved mask restricted
// to v<64 / s<40. MUST use callsite_regmask.py before register allocation.
// v0:v1 = uniform 240-byte args record address; v2 = linear thread ID.
// s30:s31 = return address. Full EXEC, wave32, VGPR bank 0.
// s30:s38 -> s40:s48; v40:v45 -> v64:v69. Retained GPRs never written.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text
.globl mono_dq_convert_lowctx
.hidden mono_dq_convert_lowctx
.p2align 6
.type mono_dq_convert_lowctx,@function
mono_dq_convert_lowctx:
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_wait_dscnt 0
    s_wait_kmcnt 0
    s_wait_xcnt 0
    s_waitcnt_depctr 0
    // Materialize supplier inputs from ordinary device-function arguments.
    v_readfirstlane_b32 s0, v0
    v_readfirstlane_b32 s1, v1
    v_readfirstlane_b32 s24, v2
    s_waitcnt_depctr 0
    s_lshr_b32 s24, s24, 5
    v_and_b32_e32 v0, 31, v2
    s_waitcnt_depctr 0
    s_cmp_ge_u32 s24, 4
    s_cbranch_scc1 .Ldevice_return
    s_getreg_b32 s5, hwreg(HW_REG_MODE, 0, 8)
    s_setreg_imm32_b32 hwreg(HW_REG_MODE, 0, 8), 0xc0
    s_nop 7
.Lpayload_begin:
    s_version UC_VERSION_GFX12|UC_VERSION_W32_BIT // original +0x0000: s_version UC_VERSION_GFX12|UC_VERSION_W32_BIT
    // Replaced original +0x0004: s_and_b32 s1, s1, 0xffff
    s_nop 0
    s_nop 0
    s_load_b64 s[12:13], s[0:1], 0x0 // original +0x000c: s_load_b64 s[12:13], s[0:1], 0x0
    s_load_b64 s[16:17], s[0:1], 0x10 // original +0x0014: s_load_b64 s[16:17], s[0:1], 0x10
    s_load_b64 s[6:7], s[0:1], 0x20 // original +0x001c: s_load_b64 s[6:7], s[0:1], 0x20
    s_load_b32 s46, s[0:1], 0x40 // original +0x0024: s_load_b32 s36, s[0:1], 0x40
    s_load_b64 s[10:11], s[0:1], 0x50 // original +0x002c: s_load_b64 s[10:11], s[0:1], 0x50
    s_load_b32 s47, s[0:1], 0x70 // original +0x0034: s_load_b32 s37, s[0:1], 0x70
    s_load_b32 s42, s[0:1], 0x90 // original +0x003c: s_load_b32 s32, s[0:1], 0x90
    s_load_b64 s[8:9], s[0:1], 0x30 // original +0x0044: s_load_b64 s[8:9], s[0:1], 0x30
    s_load_b64 s[44:45], s[0:1], 0x60 // original +0x004c: s_load_b64 s[34:35], s[0:1], 0x60
    s_load_b32 s43, s[0:1], 0x80 // original +0x0054: s_load_b32 s33, s[0:1], 0x80
    s_wait_kmcnt 0x0 // original +0x005c: s_wait_kmcnt 0x0
    // Replaced original +0x0060: v_and_b32_e32 v0, 31, v0
    s_nop 0
    // Replaced original +0x0064: s_mov_b32 s2, ttmp9
    s_mov_b32 s2, 0
    // Replaced original +0x0068: s_and_b32 s3, ttmp7, 0xffff
    s_mov_b32 s3, 0
    s_nop 0
    // Replaced original +0x0070: s_bfe_u32 s4, ttmp7, 0x100010
    s_mov_b32 s4, 0
    s_nop 0
    // Replaced original +0x0078: s_bfe_u32 s24, ttmp8, 0x50019
    s_nop 0
    s_nop 0
    s_and_b32 s13, s13, 0x1fffff // original +0x0080: s_and_b32 s13, s13, 0x1fffff
    s_and_b32 s13, s13, 0x1fffffff // original +0x0088: s_and_b32 s13, s13, 0x1fffffff
    s_mov_b32 s14, 0 // original +0x0090: s_mov_b32 s14, 0
    s_mov_b32 s15, 0x4000 // original +0x0094: s_mov_b32 s15, 0x4000
    s_and_b32 s17, s17, 0x1fffff // original +0x009c: s_and_b32 s17, s17, 0x1fffff
    s_and_b32 s17, s17, 0x1fffffff // original +0x00a4: s_and_b32 s17, s17, 0x1fffffff
    s_mov_b32 s18, 0 // original +0x00ac: s_mov_b32 s18, 0
    s_mov_b32 s19, 0x4000 // original +0x00b0: s_mov_b32 s19, 0x4000
    v_mov_b32_e32 v69, 0 // original +0x00b8: v_mov_b32_e32 v45, 0
    s_mov_b32 s20, s12 // original +0x00bc: s_mov_b32 s20, s12
    s_mov_b32 s21, s13 // original +0x00c0: s_mov_b32 s21, s13
    s_mov_b32 s22, s16 // original +0x00c4: s_mov_b32 s22, s16
    s_mov_b32 s23, s17 // original +0x00c8: s_mov_b32 s23, s17
    s_mul_i32 s25, s46, 64 // original +0x00cc: s_mul_i32 s25, s36, 64
    s_mul_hi_u32 s48, s2, s25 // original +0x00d0: s_mul_hi_u32 s38, s2, s25
    s_mul_i32 s25, s2, s25 // original +0x00d4: s_mul_i32 s25, s2, s25
    s_mul_i32 s26, s3, s6 // original +0x00d8: s_mul_i32 s26, s3, s6
    s_mul_hi_u32 s29, s3, s6 // original +0x00dc: s_mul_hi_u32 s29, s3, s6
    s_mul_i32 s27, s3, s7 // original +0x00e0: s_mul_i32 s27, s3, s7
    s_add_co_u32 s29, s29, s27 // original +0x00e4: s_add_co_u32 s29, s29, s27
    s_add_co_u32 s28, s25, s26 // original +0x00e8: s_add_co_u32 s28, s25, s26
    s_add_co_ci_u32 s29, s29, s48 // original +0x00ec: s_add_co_ci_u32 s29, s29, s38
    s_mul_i32 s26, s4, s8 // original +0x00f0: s_mul_i32 s26, s4, s8
    s_mul_hi_u32 s27, s4, s8 // original +0x00f4: s_mul_hi_u32 s27, s4, s8
    s_mul_i32 s48, s4, s9 // original +0x00f8: s_mul_i32 s38, s4, s9
    s_add_co_u32 s27, s27, s48 // original +0x00fc: s_add_co_u32 s27, s27, s38
    s_add_co_u32 s28, s28, s26 // original +0x0100: s_add_co_u32 s28, s28, s26
    s_add_co_ci_u32 s29, s29, s27 // original +0x0104: s_add_co_ci_u32 s29, s29, s27
    s_add_co_u32 s25, s43, 31 // original +0x0108: s_add_co_u32 s25, s33, 31
    s_and_b32 s25, s25, 0xffffffe0 // original +0x010c: s_and_b32 s25, s25, 0xffffffe0
    s_mul_i32 s26, s2, 64 // original +0x0114: s_mul_i32 s26, s2, 64
    s_sub_co_i32 s26, s25, s26 // original +0x0118: s_sub_co_i32 s26, s25, s26
    s_mul_hi_u32 s27, s26, s46 // original +0x011c: s_mul_hi_u32 s27, s26, s36
    s_mul_i32 s26, s26, s46 // original +0x0120: s_mul_i32 s26, s26, s36
    s_add_co_u32 s12, s28, s20 // original +0x0124: s_add_co_u32 s12, s28, s20
    s_add_co_ci_u32 s13, s29, s21 // original +0x0128: s_add_co_ci_u32 s13, s29, s21
    s_and_b32 s13, s13, 0x1ffffff // original +0x012c: s_and_b32 s13, s13, 0x1ffffff
    s_lshl_b32 s14, s26, 25 // original +0x0134: s_lshl_b32 s14, s26, 25
    s_or_b32 s13, s13, s14 // original +0x0138: s_or_b32 s13, s13, s14
    s_lshr_b32 s14, s26, 7 // original +0x013c: s_lshr_b32 s14, s26, 7
    s_lshl_b32 s15, s27, 25 // original +0x0140: s_lshl_b32 s15, s27, 25
    s_or_b32 s14, s14, s15 // original +0x0144: s_or_b32 s14, s14, s15
    s_lshr_b32 s15, s27, 7 // original +0x0148: s_lshr_b32 s15, s27, 7
    s_and_b32 s15, s15, 63 // original +0x014c: s_and_b32 s15, s15, 63
    s_or_b32 s15, s15, 0x4000 // original +0x0150: s_or_b32 s15, s15, 0x4000
    s_mul_i32 s25, s47, 64 // original +0x0158: s_mul_i32 s25, s37, 64
    s_mul_hi_u32 s48, s2, s25 // original +0x015c: s_mul_hi_u32 s38, s2, s25
    s_mul_i32 s25, s2, s25 // original +0x0160: s_mul_i32 s25, s2, s25
    s_mul_i32 s26, s3, s10 // original +0x0164: s_mul_i32 s26, s3, s10
    s_mul_hi_u32 s28, s3, s10 // original +0x0168: s_mul_hi_u32 s28, s3, s10
    s_mul_i32 s27, s3, s11 // original +0x016c: s_mul_i32 s27, s3, s11
    s_add_co_u32 s28, s28, s27 // original +0x0170: s_add_co_u32 s28, s28, s27
    s_add_co_u32 s29, s25, s26 // original +0x0174: s_add_co_u32 s29, s25, s26
    s_add_co_ci_u32 s28, s28, s48 // original +0x0178: s_add_co_ci_u32 s28, s28, s38
    s_mul_i32 s26, s4, s44 // original +0x017c: s_mul_i32 s26, s4, s34
    s_mul_hi_u32 s27, s4, s44 // original +0x0180: s_mul_hi_u32 s27, s4, s34
    s_mul_i32 s48, s4, s45 // original +0x0184: s_mul_i32 s38, s4, s35
    s_add_co_u32 s27, s27, s48 // original +0x0188: s_add_co_u32 s27, s27, s38
    s_add_co_u32 s29, s29, s26 // original +0x018c: s_add_co_u32 s29, s29, s26
    s_add_co_ci_u32 s28, s28, s27 // original +0x0190: s_add_co_ci_u32 s28, s28, s27
    s_mul_i32 s26, s2, 64 // original +0x0194: s_mul_i32 s26, s2, 64
    s_sub_co_i32 s26, s43, s26 // original +0x0198: s_sub_co_i32 s26, s33, s26
    s_mul_hi_u32 s27, s26, s47 // original +0x019c: s_mul_hi_u32 s27, s26, s37
    s_mul_i32 s26, s26, s47 // original +0x01a0: s_mul_i32 s26, s26, s37
    s_add_co_u32 s16, s29, s22 // original +0x01a4: s_add_co_u32 s16, s29, s22
    s_add_co_ci_u32 s17, s28, s23 // original +0x01a8: s_add_co_ci_u32 s17, s28, s23
    s_and_b32 s17, s17, 0x1ffffff // original +0x01ac: s_and_b32 s17, s17, 0x1ffffff
    s_lshl_b32 s18, s26, 25 // original +0x01b4: s_lshl_b32 s18, s26, 25
    s_or_b32 s17, s17, s18 // original +0x01b8: s_or_b32 s17, s17, s18
    s_lshr_b32 s18, s26, 7 // original +0x01bc: s_lshr_b32 s18, s26, 7
    s_lshl_b32 s19, s27, 25 // original +0x01c0: s_lshl_b32 s19, s27, 25
    s_or_b32 s18, s18, s19 // original +0x01c4: s_or_b32 s18, s18, s19
    s_lshr_b32 s19, s27, 7 // original +0x01c8: s_lshr_b32 s19, s27, 7
    s_and_b32 s19, s19, 63 // original +0x01cc: s_and_b32 s19, s19, 63
    s_or_b32 s19, s19, 0x4000 // original +0x01d0: s_or_b32 s19, s19, 0x4000
    v_lshrrev_b32_e32 v66, 4, v0 // original +0x01d8: v_lshrrev_b32_e32 v42, 4, v0
    v_lshlrev_b32_e32 v66, 3, v66 // original +0x01dc: v_lshlrev_b32_e32 v42, 3, v42
    v_mul_i32_i24_e32 v66, s46, v66 // original +0x01e0: v_mul_i32_i24_e32 v42, s36, v42
    v_and_b32_e32 v67, 15, v0 // original +0x01e4: v_and_b32_e32 v43, 15, v0
    v_mul_i32_i24_e32 v67, 16, v67 // original +0x01e8: v_mul_i32_i24_e32 v43, 16, v43
    v_add_nc_u32_e32 v67, v66, v67 // original +0x01ec: v_add_nc_u32_e32 v43, v42, v43
    v_mov_b32_e32 v4, v67 // original +0x01f0: v_mov_b32_e32 v4, v43
    s_mul_i32 s25, 16, s46 // original +0x01f4: s_mul_i32 s25, 16, s36
    s_mul_i32 s25, s24, s25 // original +0x01f8: s_mul_i32 s25, s24, s25
    v_add_nc_u32_e32 v4, s25, v4 // original +0x01fc: v_add_nc_u32_e32 v4, s25, v4
    v_mov_b32_e32 v6, 0 // original +0x0200: v_mov_b32_e32 v6, 0
    v_and_b32_e64 v66, v0, 4 // original +0x0204: v_and_b32_e64 v42, v0, 4
    v_lshlrev_b32_e32 v66, 1, v66 // original +0x020c: v_lshlrev_b32_e32 v42, 1, v42
    v_mul_i32_i24_e64 v66, v66, s47 // original +0x0210: v_mul_i32_i24_e64 v42, v42, s37
    v_and_b32_e64 v67, v0, 15 // original +0x0218: v_and_b32_e64 v43, v0, 15
    v_lshrrev_b32_e32 v67, 3, v67 // original +0x0220: v_lshrrev_b32_e32 v43, 3, v43
    v_mul_i32_i24_e64 v67, v67, 64 // original +0x0224: v_mul_i32_i24_e64 v43, v43, 64
    v_lshrrev_b32_e32 v68, 4, v0 // original +0x022c: v_lshrrev_b32_e32 v44, 4, v0
    v_mul_i32_i24_e64 v68, v68, 32 // original +0x0230: v_mul_i32_i24_e64 v44, v44, 32
    v_and_b32_e64 v69, v0, 3 // original +0x0238: v_and_b32_e64 v45, v0, 3
    v_mul_i32_i24_e64 v69, v69, 8 // original +0x0240: v_mul_i32_i24_e64 v45, v45, 8
    v_add_nc_u32_e32 v6, v66, v6 // original +0x0248: v_add_nc_u32_e32 v6, v42, v6
    v_add_nc_u32_e32 v6, v67, v6 // original +0x024c: v_add_nc_u32_e32 v6, v43, v6
    v_add_nc_u32_e32 v6, v68, v6 // original +0x0250: v_add_nc_u32_e32 v6, v44, v6
    v_add_nc_u32_e32 v6, v69, v6 // original +0x0254: v_add_nc_u32_e32 v6, v45, v6
    s_mul_i32 s25, 16, s47 // original +0x0258: s_mul_i32 s25, 16, s37
    s_mul_i32 s25, s24, s25 // original +0x025c: s_mul_i32 s25, s24, s25
    v_add_nc_u32_e32 v6, s25, v6 // original +0x0260: v_add_nc_u32_e32 v6, s25, v6
    v_and_b32_e32 v66, 15, v0 // original +0x0264: v_and_b32_e32 v42, 15, v0
    v_lshlrev_b32_e32 v66, 2, v66 // original +0x0268: v_lshlrev_b32_e32 v42, 2, v42
    s_sub_co_i32 s25, s42, 0 // original +0x026c: s_sub_co_i32 s25, s32, 0
    v_cmp_lt_u32_e64 s40, v66, s25 // original +0x0270: v_cmp_lt_u32_e64 s30, v42, s25
    v_and_b32_e32 v66, 15, v0 // original +0x0278: v_and_b32_e32 v42, 15, v0
    v_lshrrev_b32_e32 v66, 1, v66 // original +0x027c: v_lshrrev_b32_e32 v42, 1, v42
    v_lshlrev_b32_e32 v66, 3, v66 // original +0x0280: v_lshlrev_b32_e32 v42, 3, v42
    s_sub_co_i32 s25, s42, 0 // original +0x0284: s_sub_co_i32 s25, s32, 0
    v_cmp_lt_u32_e64 s41, v66, s25 // original +0x0288: v_cmp_lt_u32_e64 s31, v42, s25
    s_mul_i32 s25, s46, 0 // original +0x0290: s_mul_i32 s25, s36, 0
    v_add_nc_u32_e32 v5, s25, v4 // original +0x0294: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v8, 0 // original +0x0298: v_mov_b32_e32 v8, 0
    v_mov_b32_e32 v9, 0 // original +0x029c: v_mov_b32_e32 v9, 0
    v_mov_b32_e32 v10, 0 // original +0x02a0: v_mov_b32_e32 v10, 0
    v_mov_b32_e32 v11, 0 // original +0x02a4: v_mov_b32_e32 v11, 0
    s_mov_b32 exec_lo, s40 // original +0x02a8: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[8:11], v5, s[12:15], null offen // original +0x02ac: buffer_load_b128 v[8:11], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x02b8: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x02bc: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 1 // original +0x02c4: s_mul_i32 s25, s36, 1
    v_add_nc_u32_e32 v5, s25, v4 // original +0x02c8: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v12, 0 // original +0x02cc: v_mov_b32_e32 v12, 0
    v_mov_b32_e32 v13, 0 // original +0x02d0: v_mov_b32_e32 v13, 0
    v_mov_b32_e32 v14, 0 // original +0x02d4: v_mov_b32_e32 v14, 0
    v_mov_b32_e32 v15, 0 // original +0x02d8: v_mov_b32_e32 v15, 0
    s_mov_b32 exec_lo, s40 // original +0x02dc: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[12:15], v5, s[12:15], null offen // original +0x02e0: buffer_load_b128 v[12:15], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x02ec: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x02f0: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 2 // original +0x02f8: s_mul_i32 s25, s36, 2
    v_add_nc_u32_e32 v5, s25, v4 // original +0x02fc: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v16, 0 // original +0x0300: v_mov_b32_e32 v16, 0
    v_mov_b32_e32 v17, 0 // original +0x0304: v_mov_b32_e32 v17, 0
    v_mov_b32_e32 v18, 0 // original +0x0308: v_mov_b32_e32 v18, 0
    v_mov_b32_e32 v19, 0 // original +0x030c: v_mov_b32_e32 v19, 0
    s_mov_b32 exec_lo, s40 // original +0x0310: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[16:19], v5, s[12:15], null offen // original +0x0314: buffer_load_b128 v[16:19], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x0320: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x0324: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 3 // original +0x032c: s_mul_i32 s25, s36, 3
    v_add_nc_u32_e32 v5, s25, v4 // original +0x0330: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v20, 0 // original +0x0334: v_mov_b32_e32 v20, 0
    v_mov_b32_e32 v21, 0 // original +0x0338: v_mov_b32_e32 v21, 0
    v_mov_b32_e32 v22, 0 // original +0x033c: v_mov_b32_e32 v22, 0
    v_mov_b32_e32 v23, 0 // original +0x0340: v_mov_b32_e32 v23, 0
    s_mov_b32 exec_lo, s40 // original +0x0344: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[20:23], v5, s[12:15], null offen // original +0x0348: buffer_load_b128 v[20:23], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x0354: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x0358: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 4 // original +0x0360: s_mul_i32 s25, s36, 4
    v_add_nc_u32_e32 v5, s25, v4 // original +0x0364: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v24, 0 // original +0x0368: v_mov_b32_e32 v24, 0
    v_mov_b32_e32 v25, 0 // original +0x036c: v_mov_b32_e32 v25, 0
    v_mov_b32_e32 v26, 0 // original +0x0370: v_mov_b32_e32 v26, 0
    v_mov_b32_e32 v27, 0 // original +0x0374: v_mov_b32_e32 v27, 0
    s_mov_b32 exec_lo, s40 // original +0x0378: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[24:27], v5, s[12:15], null offen // original +0x037c: buffer_load_b128 v[24:27], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x0388: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x038c: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 5 // original +0x0394: s_mul_i32 s25, s36, 5
    v_add_nc_u32_e32 v5, s25, v4 // original +0x0398: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v28, 0 // original +0x039c: v_mov_b32_e32 v28, 0
    v_mov_b32_e32 v29, 0 // original +0x03a0: v_mov_b32_e32 v29, 0
    v_mov_b32_e32 v30, 0 // original +0x03a4: v_mov_b32_e32 v30, 0
    v_mov_b32_e32 v31, 0 // original +0x03a8: v_mov_b32_e32 v31, 0
    s_mov_b32 exec_lo, s40 // original +0x03ac: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[28:31], v5, s[12:15], null offen // original +0x03b0: buffer_load_b128 v[28:31], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x03bc: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x03c0: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 6 // original +0x03c8: s_mul_i32 s25, s36, 6
    v_add_nc_u32_e32 v5, s25, v4 // original +0x03cc: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v32, 0 // original +0x03d0: v_mov_b32_e32 v32, 0
    v_mov_b32_e32 v33, 0 // original +0x03d4: v_mov_b32_e32 v33, 0
    v_mov_b32_e32 v34, 0 // original +0x03d8: v_mov_b32_e32 v34, 0
    v_mov_b32_e32 v35, 0 // original +0x03dc: v_mov_b32_e32 v35, 0
    s_mov_b32 exec_lo, s40 // original +0x03e0: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[32:35], v5, s[12:15], null offen // original +0x03e4: buffer_load_b128 v[32:35], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x03f0: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x03f4: v_add_nc_u32_e32 v5, 0x100, v5
    s_mul_i32 s25, s46, 7 // original +0x03fc: s_mul_i32 s25, s36, 7
    v_add_nc_u32_e32 v5, s25, v4 // original +0x0400: v_add_nc_u32_e32 v5, s25, v4
    v_mov_b32_e32 v36, 0 // original +0x0404: v_mov_b32_e32 v36, 0
    v_mov_b32_e32 v37, 0 // original +0x0408: v_mov_b32_e32 v37, 0
    v_mov_b32_e32 v38, 0 // original +0x040c: v_mov_b32_e32 v38, 0
    v_mov_b32_e32 v39, 0 // original +0x0410: v_mov_b32_e32 v39, 0
    s_mov_b32 exec_lo, s40 // original +0x0414: s_mov_b32 exec_lo, s30
    buffer_load_b128 v[36:39], v5, s[12:15], null offen // original +0x0418: buffer_load_b128 v[36:39], v5, s[12:15], null offen
    s_mov_b32 exec_lo, -1 // original +0x0424: s_mov_b32 exec_lo, -1
    v_add_nc_u32_e32 v5, 0x100, v5 // original +0x0428: v_add_nc_u32_e32 v5, 0x100, v5
    s_wait_loadcnt 0x7 // original +0x0430: s_wait_loadcnt 0x7
    v_cvt_pk_bf16_f32 v64, v8, v9 // original +0x0434: v_cvt_pk_bf16_f32 v40, v8, v9
    v_cvt_pk_bf16_f32 v65, v10, v11 // original +0x043c: v_cvt_pk_bf16_f32 v41, v10, v11
    s_mul_i32 s25, s47, 0 // original +0x0444: s_mul_i32 s25, s37, 0
    s_lshl_b32 s26, 0, 7 // original +0x0448: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x044c: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x0450: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x0454: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x0458: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x0464: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x6 // original +0x0468: s_wait_loadcnt 0x6
    v_cvt_pk_bf16_f32 v64, v12, v13 // original +0x046c: v_cvt_pk_bf16_f32 v40, v12, v13
    v_cvt_pk_bf16_f32 v65, v14, v15 // original +0x0474: v_cvt_pk_bf16_f32 v41, v14, v15
    s_mul_i32 s25, s47, 1 // original +0x047c: s_mul_i32 s25, s37, 1
    s_lshl_b32 s26, 0, 7 // original +0x0480: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x0484: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x0488: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x048c: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x0490: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x049c: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x5 // original +0x04a0: s_wait_loadcnt 0x5
    v_cvt_pk_bf16_f32 v64, v16, v17 // original +0x04a4: v_cvt_pk_bf16_f32 v40, v16, v17
    v_cvt_pk_bf16_f32 v65, v18, v19 // original +0x04ac: v_cvt_pk_bf16_f32 v41, v18, v19
    s_mul_i32 s25, s47, 2 // original +0x04b4: s_mul_i32 s25, s37, 2
    s_lshl_b32 s26, 0, 7 // original +0x04b8: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x04bc: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x04c0: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x04c4: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x04c8: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x04d4: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x4 // original +0x04d8: s_wait_loadcnt 0x4
    v_cvt_pk_bf16_f32 v64, v20, v21 // original +0x04dc: v_cvt_pk_bf16_f32 v40, v20, v21
    v_cvt_pk_bf16_f32 v65, v22, v23 // original +0x04e4: v_cvt_pk_bf16_f32 v41, v22, v23
    s_mul_i32 s25, s47, 3 // original +0x04ec: s_mul_i32 s25, s37, 3
    s_lshl_b32 s26, 0, 7 // original +0x04f0: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x04f4: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x04f8: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x04fc: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x0500: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x050c: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x3 // original +0x0510: s_wait_loadcnt 0x3
    v_cvt_pk_bf16_f32 v64, v24, v25 // original +0x0514: v_cvt_pk_bf16_f32 v40, v24, v25
    v_cvt_pk_bf16_f32 v65, v26, v27 // original +0x051c: v_cvt_pk_bf16_f32 v41, v26, v27
    s_mul_i32 s25, s47, 4 // original +0x0524: s_mul_i32 s25, s37, 4
    s_lshl_b32 s26, 0, 7 // original +0x0528: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x052c: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x0530: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x0534: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x0538: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x0544: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x2 // original +0x0548: s_wait_loadcnt 0x2
    v_cvt_pk_bf16_f32 v64, v28, v29 // original +0x054c: v_cvt_pk_bf16_f32 v40, v28, v29
    v_cvt_pk_bf16_f32 v65, v30, v31 // original +0x0554: v_cvt_pk_bf16_f32 v41, v30, v31
    s_mul_i32 s25, s47, 5 // original +0x055c: s_mul_i32 s25, s37, 5
    s_lshl_b32 s26, 0, 7 // original +0x0560: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x0564: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x0568: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x056c: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x0570: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x057c: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x1 // original +0x0580: s_wait_loadcnt 0x1
    v_cvt_pk_bf16_f32 v64, v32, v33 // original +0x0584: v_cvt_pk_bf16_f32 v40, v32, v33
    v_cvt_pk_bf16_f32 v65, v34, v35 // original +0x058c: v_cvt_pk_bf16_f32 v41, v34, v35
    s_mul_i32 s25, s47, 6 // original +0x0594: s_mul_i32 s25, s37, 6
    s_lshl_b32 s26, 0, 7 // original +0x0598: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x059c: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x05a0: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x05a4: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x05a8: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x05b4: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x0 // original +0x05b8: s_wait_loadcnt 0x0
    v_cvt_pk_bf16_f32 v64, v36, v37 // original +0x05bc: v_cvt_pk_bf16_f32 v40, v36, v37
    v_cvt_pk_bf16_f32 v65, v38, v39 // original +0x05c4: v_cvt_pk_bf16_f32 v41, v38, v39
    s_mul_i32 s25, s47, 7 // original +0x05cc: s_mul_i32 s25, s37, 7
    s_lshl_b32 s26, 0, 7 // original +0x05d0: s_lshl_b32 s26, 0, 7
    v_add_nc_u32_e32 v7, s25, v6 // original +0x05d4: v_add_nc_u32_e32 v7, s25, v6
    v_add_nc_u32_e32 v7, s26, v7 // original +0x05d8: v_add_nc_u32_e32 v7, s26, v7
    s_mov_b32 exec_lo, s41 // original +0x05dc: s_mov_b32 exec_lo, s31
    buffer_store_b64 v[64:65], v7, s[16:19], null offen // original +0x05e0: buffer_store_b64 v[40:41], v7, s[16:19], null offen
    s_mov_b32 exec_lo, -1 // original +0x05ec: s_mov_b32 exec_lo, -1
    s_wait_loadcnt 0x0 // original +0x05f0: s_wait_loadcnt 0x0

.Lpayload_end:
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_wait_dscnt 0
    s_wait_kmcnt 0
    s_wait_xcnt 0
    s_waitcnt_depctr 0
    s_setreg_b32 hwreg(HW_REG_MODE, 0, 8), s5
    s_nop 7
.Ldevice_return:
    s_setpc_b64 s[30:31]
.Ldevice_end:
.size mono_dq_convert_lowctx, .Ldevice_end-mono_dq_convert_lowctx
.set mono_dq_convert_lowctx.payload_offset, .Lpayload_begin-mono_dq_convert_lowctx
.set mono_dq_convert_lowctx.payload_size, .Lpayload_end-.Lpayload_begin
.set mono_dq_convert_lowctx.num_vgpr, 70
.set mono_dq_convert_lowctx.numbered_sgpr, 49
.set mono_dq_convert_lowctx.num_agpr, 0
.set mono_dq_convert_lowctx.private_seg_size, 0
.set mono_dq_convert_lowctx.num_named_barrier, 0
.set mono_dq_convert_lowctx.uses_vcc, 0
.set mono_dq_convert_lowctx.uses_flat_scratch, 0
.set mono_dq_convert_lowctx.has_dyn_sized_stack, 0
.set mono_dq_convert_lowctx.has_recursion, 0
.set mono_dq_convert_lowctx.has_indirect_call, 0
.section .note.GNU-stack,"",@progbits
