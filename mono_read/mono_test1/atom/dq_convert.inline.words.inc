// Generated from dq_convert.inline.co. Do not edit instruction words manually.
".long 0xbfc00000\n" // s_wait_loadcnt 0x0
".long 0xbfc10000\n" // s_wait_storecnt 0x0
".long 0xbfc60000\n" // s_wait_dscnt 0x0
".long 0xbfc70000\n" // s_wait_kmcnt 0x0
".long 0xbfc50000\n" // s_wait_xcnt 0x0
".long 0xbf880000\n" // s_wait_alu depctr_hold_cnt(0) depctr_sa_sdst(0) depctr_va_vdst(0) depctr_va_sdst(0) depctr_va_ssrc(0) depctr_va_vcc(0) depctr_vm_vsrc(0)
".long 0xbf098418\n" // s_cmp_ge_u32 s24, 4
".long 0xbfa20189\n" // s_cbranch_scc1 393
".long 0xb8853801\n" // s_getreg_b32 s5, hwreg(HW_REG_WAVE_MODE, 0, 8)
".long 0xb9803801, 0x000000c0\n" // s_setreg_imm32_b32 hwreg(HW_REG_WAVE_MODE, 0, 8), 0xc0
".long 0xbf800007\n" // s_nop 7
".long 0xb0804009\n" // s_version UC_VERSION_GFX12|UC_VERSION_W32_BIT
".long 0xbf800000\n" // s_nop 0
".long 0xbf800000\n" // s_nop 0
".long 0xf4002300, 0xf8000000\n" // s_load_b64 s[12:13], s[0:1], 0x0
".long 0xf4002400, 0xf8000010\n" // s_load_b64 s[16:17], s[0:1], 0x10
".long 0xf4002180, 0xf8000020\n" // s_load_b64 s[6:7], s[0:1], 0x20
".long 0xf4000b80, 0xf8000040\n" // s_load_b32 s46, s[0:1], 0x40
".long 0xf4002280, 0xf8000050\n" // s_load_b64 s[10:11], s[0:1], 0x50
".long 0xf4000bc0, 0xf8000070\n" // s_load_b32 s47, s[0:1], 0x70
".long 0xf4000a80, 0xf8000090\n" // s_load_b32 s42, s[0:1], 0x90
".long 0xf4002200, 0xf8000030\n" // s_load_b64 s[8:9], s[0:1], 0x30
".long 0xf4002b00, 0xf8000060\n" // s_load_b64 s[44:45], s[0:1], 0x60
".long 0xf4000ac0, 0xf8000080\n" // s_load_b32 s43, s[0:1], 0x80
".long 0xbfc70000\n" // s_wait_kmcnt 0x0
".long 0xbf800000\n" // s_nop 0
".long 0xbe820080\n" // s_mov_b32 s2, 0
".long 0xbe830080\n" // s_mov_b32 s3, 0
".long 0xbf800000\n" // s_nop 0
".long 0xbe840080\n" // s_mov_b32 s4, 0
".long 0xbf800000\n" // s_nop 0
".long 0xbf800000\n" // s_nop 0
".long 0xbf800000\n" // s_nop 0
".long 0x8b0dff0d, 0x001fffff\n" // s_and_b32 s13, s13, 0x1fffff
".long 0x8b0dff0d, 0x1fffffff\n" // s_and_b32 s13, s13, 0x1fffffff
".long 0xbe8e0080\n" // s_mov_b32 s14, 0
".long 0xbe8f00ff, 0x00004000\n" // s_mov_b32 s15, 0x4000
".long 0x8b11ff11, 0x001fffff\n" // s_and_b32 s17, s17, 0x1fffff
".long 0x8b11ff11, 0x1fffffff\n" // s_and_b32 s17, s17, 0x1fffffff
".long 0xbe920080\n" // s_mov_b32 s18, 0
".long 0xbe9300ff, 0x00004000\n" // s_mov_b32 s19, 0x4000
".long 0x7e5a0280\n" // v_mov_b32_e32 v45, 0
".long 0xbe94000c\n" // s_mov_b32 s20, s12
".long 0xbe95000d\n" // s_mov_b32 s21, s13
".long 0xbe960010\n" // s_mov_b32 s22, s16
".long 0xbe970011\n" // s_mov_b32 s23, s17
".long 0x9619c02e\n" // s_mul_i32 s25, s46, 64
".long 0x96b01902\n" // s_mul_hi_u32 s48, s2, s25
".long 0x96191902\n" // s_mul_i32 s25, s2, s25
".long 0x961a0603\n" // s_mul_i32 s26, s3, s6
".long 0x969d0603\n" // s_mul_hi_u32 s29, s3, s6
".long 0x961b0703\n" // s_mul_i32 s27, s3, s7
".long 0x801d1b1d\n" // s_add_co_u32 s29, s29, s27
".long 0x801c1a19\n" // s_add_co_u32 s28, s25, s26
".long 0x821d301d\n" // s_add_co_ci_u32 s29, s29, s48
".long 0x961a0804\n" // s_mul_i32 s26, s4, s8
".long 0x969b0804\n" // s_mul_hi_u32 s27, s4, s8
".long 0x96300904\n" // s_mul_i32 s48, s4, s9
".long 0x801b301b\n" // s_add_co_u32 s27, s27, s48
".long 0x801c1a1c\n" // s_add_co_u32 s28, s28, s26
".long 0x821d1b1d\n" // s_add_co_ci_u32 s29, s29, s27
".long 0x80199f2b\n" // s_add_co_u32 s25, s43, 31
".long 0x8b19ff19, 0xffffffe0\n" // s_and_b32 s25, s25, 0xffffffe0
".long 0x961ac002\n" // s_mul_i32 s26, s2, 64
".long 0x819a1a19\n" // s_sub_co_i32 s26, s25, s26
".long 0x969b2e1a\n" // s_mul_hi_u32 s27, s26, s46
".long 0x961a2e1a\n" // s_mul_i32 s26, s26, s46
".long 0x800c141c\n" // s_add_co_u32 s12, s28, s20
".long 0x820d151d\n" // s_add_co_ci_u32 s13, s29, s21
".long 0x8b0dff0d, 0x01ffffff\n" // s_and_b32 s13, s13, 0x1ffffff
".long 0x840e991a\n" // s_lshl_b32 s14, s26, 25
".long 0x8c0d0e0d\n" // s_or_b32 s13, s13, s14
".long 0x850e871a\n" // s_lshr_b32 s14, s26, 7
".long 0x840f991b\n" // s_lshl_b32 s15, s27, 25
".long 0x8c0e0f0e\n" // s_or_b32 s14, s14, s15
".long 0x850f871b\n" // s_lshr_b32 s15, s27, 7
".long 0x8b0fbf0f\n" // s_and_b32 s15, s15, 63
".long 0x8c0fff0f, 0x00004000\n" // s_or_b32 s15, s15, 0x4000
".long 0x9619c02f\n" // s_mul_i32 s25, s47, 64
".long 0x96b01902\n" // s_mul_hi_u32 s48, s2, s25
".long 0x96191902\n" // s_mul_i32 s25, s2, s25
".long 0x961a0a03\n" // s_mul_i32 s26, s3, s10
".long 0x969c0a03\n" // s_mul_hi_u32 s28, s3, s10
".long 0x961b0b03\n" // s_mul_i32 s27, s3, s11
".long 0x801c1b1c\n" // s_add_co_u32 s28, s28, s27
".long 0x801d1a19\n" // s_add_co_u32 s29, s25, s26
".long 0x821c301c\n" // s_add_co_ci_u32 s28, s28, s48
".long 0x961a2c04\n" // s_mul_i32 s26, s4, s44
".long 0x969b2c04\n" // s_mul_hi_u32 s27, s4, s44
".long 0x96302d04\n" // s_mul_i32 s48, s4, s45
".long 0x801b301b\n" // s_add_co_u32 s27, s27, s48
".long 0x801d1a1d\n" // s_add_co_u32 s29, s29, s26
".long 0x821c1b1c\n" // s_add_co_ci_u32 s28, s28, s27
".long 0x961ac002\n" // s_mul_i32 s26, s2, 64
".long 0x819a1a2b\n" // s_sub_co_i32 s26, s43, s26
".long 0x969b2f1a\n" // s_mul_hi_u32 s27, s26, s47
".long 0x961a2f1a\n" // s_mul_i32 s26, s26, s47
".long 0x8010161d\n" // s_add_co_u32 s16, s29, s22
".long 0x8211171c\n" // s_add_co_ci_u32 s17, s28, s23
".long 0x8b11ff11, 0x01ffffff\n" // s_and_b32 s17, s17, 0x1ffffff
".long 0x8412991a\n" // s_lshl_b32 s18, s26, 25
".long 0x8c111211\n" // s_or_b32 s17, s17, s18
".long 0x8512871a\n" // s_lshr_b32 s18, s26, 7
".long 0x8413991b\n" // s_lshl_b32 s19, s27, 25
".long 0x8c121312\n" // s_or_b32 s18, s18, s19
".long 0x8513871b\n" // s_lshr_b32 s19, s27, 7
".long 0x8b13bf13\n" // s_and_b32 s19, s19, 63
".long 0x8c13ff13, 0x00004000\n" // s_or_b32 s19, s19, 0x4000
".long 0x32540084\n" // v_lshrrev_b32_e32 v42, 4, v0
".long 0x30545483\n" // v_lshlrev_b32_e32 v42, 3, v42
".long 0x1254542e\n" // v_mul_i32_i24_e32 v42, s46, v42
".long 0x3656008f\n" // v_and_b32_e32 v43, 15, v0
".long 0x12565690\n" // v_mul_i32_i24_e32 v43, 16, v43
".long 0x4a56572a\n" // v_add_nc_u32_e32 v43, v42, v43
".long 0x7e08032b\n" // v_mov_b32_e32 v4, v43
".long 0x96192e90\n" // s_mul_i32 s25, 16, s46
".long 0x96191918\n" // s_mul_i32 s25, s24, s25
".long 0x4a080819\n" // v_add_nc_u32_e32 v4, s25, v4
".long 0x7e0c0280\n" // v_mov_b32_e32 v6, 0
".long 0xd51b002a, 0x00010900\n" // v_and_b32_e64 v42, v0, 4
".long 0x30545481\n" // v_lshlrev_b32_e32 v42, 1, v42
".long 0xd509002a, 0x00005f2a\n" // v_mul_i32_i24_e64 v42, v42, s47
".long 0xd51b002b, 0x00011f00\n" // v_and_b32_e64 v43, v0, 15
".long 0x32565683\n" // v_lshrrev_b32_e32 v43, 3, v43
".long 0xd509002b, 0x0001812b\n" // v_mul_i32_i24_e64 v43, v43, 64
".long 0x32580084\n" // v_lshrrev_b32_e32 v44, 4, v0
".long 0xd509002c, 0x0001412c\n" // v_mul_i32_i24_e64 v44, v44, 32
".long 0xd51b002d, 0x00010700\n" // v_and_b32_e64 v45, v0, 3
".long 0xd509002d, 0x0001112d\n" // v_mul_i32_i24_e64 v45, v45, 8
".long 0x4a0c0d2a\n" // v_add_nc_u32_e32 v6, v42, v6
".long 0x4a0c0d2b\n" // v_add_nc_u32_e32 v6, v43, v6
".long 0x4a0c0d2c\n" // v_add_nc_u32_e32 v6, v44, v6
".long 0x4a0c0d2d\n" // v_add_nc_u32_e32 v6, v45, v6
".long 0x96192f90\n" // s_mul_i32 s25, 16, s47
".long 0x96191918\n" // s_mul_i32 s25, s24, s25
".long 0x4a0c0c19\n" // v_add_nc_u32_e32 v6, s25, v6
".long 0x3654008f\n" // v_and_b32_e32 v42, 15, v0
".long 0x30545482\n" // v_lshlrev_b32_e32 v42, 2, v42
".long 0x8199802a\n" // s_sub_co_i32 s25, s42, 0
".long 0xd4490028, 0x0000332a\n" // v_cmp_lt_u32_e64 s40, v42, s25
".long 0x3654008f\n" // v_and_b32_e32 v42, 15, v0
".long 0x32545481\n" // v_lshrrev_b32_e32 v42, 1, v42
".long 0x30545483\n" // v_lshlrev_b32_e32 v42, 3, v42
".long 0x8199802a\n" // s_sub_co_i32 s25, s42, 0
".long 0xd4490029, 0x0000332a\n" // v_cmp_lt_u32_e64 s41, v42, s25
".long 0x9619802e\n" // s_mul_i32 s25, s46, 0
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e100280\n" // v_mov_b32_e32 v8, 0
".long 0x7e120280\n" // v_mov_b32_e32 v9, 0
".long 0x7e140280\n" // v_mov_b32_e32 v10, 0
".long 0x7e160280\n" // v_mov_b32_e32 v11, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x40801808, 0x00000005\n" // buffer_load_b128 v[8:11], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619812e\n" // s_mul_i32 s25, s46, 1
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e180280\n" // v_mov_b32_e32 v12, 0
".long 0x7e1a0280\n" // v_mov_b32_e32 v13, 0
".long 0x7e1c0280\n" // v_mov_b32_e32 v14, 0
".long 0x7e1e0280\n" // v_mov_b32_e32 v15, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x4080180c, 0x00000005\n" // buffer_load_b128 v[12:15], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619822e\n" // s_mul_i32 s25, s46, 2
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e200280\n" // v_mov_b32_e32 v16, 0
".long 0x7e220280\n" // v_mov_b32_e32 v17, 0
".long 0x7e240280\n" // v_mov_b32_e32 v18, 0
".long 0x7e260280\n" // v_mov_b32_e32 v19, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x40801810, 0x00000005\n" // buffer_load_b128 v[16:19], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619832e\n" // s_mul_i32 s25, s46, 3
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e280280\n" // v_mov_b32_e32 v20, 0
".long 0x7e2a0280\n" // v_mov_b32_e32 v21, 0
".long 0x7e2c0280\n" // v_mov_b32_e32 v22, 0
".long 0x7e2e0280\n" // v_mov_b32_e32 v23, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x40801814, 0x00000005\n" // buffer_load_b128 v[20:23], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619842e\n" // s_mul_i32 s25, s46, 4
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e300280\n" // v_mov_b32_e32 v24, 0
".long 0x7e320280\n" // v_mov_b32_e32 v25, 0
".long 0x7e340280\n" // v_mov_b32_e32 v26, 0
".long 0x7e360280\n" // v_mov_b32_e32 v27, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x40801818, 0x00000005\n" // buffer_load_b128 v[24:27], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619852e\n" // s_mul_i32 s25, s46, 5
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e380280\n" // v_mov_b32_e32 v28, 0
".long 0x7e3a0280\n" // v_mov_b32_e32 v29, 0
".long 0x7e3c0280\n" // v_mov_b32_e32 v30, 0
".long 0x7e3e0280\n" // v_mov_b32_e32 v31, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x4080181c, 0x00000005\n" // buffer_load_b128 v[28:31], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619862e\n" // s_mul_i32 s25, s46, 6
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e400280\n" // v_mov_b32_e32 v32, 0
".long 0x7e420280\n" // v_mov_b32_e32 v33, 0
".long 0x7e440280\n" // v_mov_b32_e32 v34, 0
".long 0x7e460280\n" // v_mov_b32_e32 v35, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x40801820, 0x00000005\n" // buffer_load_b128 v[32:35], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0x9619872e\n" // s_mul_i32 s25, s46, 7
".long 0x4a0a0819\n" // v_add_nc_u32_e32 v5, s25, v4
".long 0x7e480280\n" // v_mov_b32_e32 v36, 0
".long 0x7e4a0280\n" // v_mov_b32_e32 v37, 0
".long 0x7e4c0280\n" // v_mov_b32_e32 v38, 0
".long 0x7e4e0280\n" // v_mov_b32_e32 v39, 0
".long 0xbefe0028\n" // s_mov_b32 exec_lo, s40
".long 0xc405c07c, 0x40801824, 0x00000005\n" // buffer_load_b128 v[36:39], v5, s[12:15], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0x4a0a0aff, 0x00000100\n" // v_add_nc_u32_e32 v5, 0x100, v5
".long 0xbfc00007\n" // s_wait_loadcnt 0x7
".long 0xd76d0028, 0x00021308\n" // v_cvt_pk_bf16_f32 v40, v8, v9
".long 0xd76d0029, 0x0002170a\n" // v_cvt_pk_bf16_f32 v41, v10, v11
".long 0x9619802f\n" // s_mul_i32 s25, s47, 0
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00006\n" // s_wait_loadcnt 0x6
".long 0xd76d0028, 0x00021b0c\n" // v_cvt_pk_bf16_f32 v40, v12, v13
".long 0xd76d0029, 0x00021f0e\n" // v_cvt_pk_bf16_f32 v41, v14, v15
".long 0x9619812f\n" // s_mul_i32 s25, s47, 1
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00005\n" // s_wait_loadcnt 0x5
".long 0xd76d0028, 0x00022310\n" // v_cvt_pk_bf16_f32 v40, v16, v17
".long 0xd76d0029, 0x00022712\n" // v_cvt_pk_bf16_f32 v41, v18, v19
".long 0x9619822f\n" // s_mul_i32 s25, s47, 2
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00004\n" // s_wait_loadcnt 0x4
".long 0xd76d0028, 0x00022b14\n" // v_cvt_pk_bf16_f32 v40, v20, v21
".long 0xd76d0029, 0x00022f16\n" // v_cvt_pk_bf16_f32 v41, v22, v23
".long 0x9619832f\n" // s_mul_i32 s25, s47, 3
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00003\n" // s_wait_loadcnt 0x3
".long 0xd76d0028, 0x00023318\n" // v_cvt_pk_bf16_f32 v40, v24, v25
".long 0xd76d0029, 0x0002371a\n" // v_cvt_pk_bf16_f32 v41, v26, v27
".long 0x9619842f\n" // s_mul_i32 s25, s47, 4
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00002\n" // s_wait_loadcnt 0x2
".long 0xd76d0028, 0x00023b1c\n" // v_cvt_pk_bf16_f32 v40, v28, v29
".long 0xd76d0029, 0x00023f1e\n" // v_cvt_pk_bf16_f32 v41, v30, v31
".long 0x9619852f\n" // s_mul_i32 s25, s47, 5
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00001\n" // s_wait_loadcnt 0x1
".long 0xd76d0028, 0x00024320\n" // v_cvt_pk_bf16_f32 v40, v32, v33
".long 0xd76d0029, 0x00024722\n" // v_cvt_pk_bf16_f32 v41, v34, v35
".long 0x9619862f\n" // s_mul_i32 s25, s47, 6
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00000\n" // s_wait_loadcnt 0x0
".long 0xd76d0028, 0x00024b24\n" // v_cvt_pk_bf16_f32 v40, v36, v37
".long 0xd76d0029, 0x00024f26\n" // v_cvt_pk_bf16_f32 v41, v38, v39
".long 0x9619872f\n" // s_mul_i32 s25, s47, 7
".long 0x841a8780\n" // s_lshl_b32 s26, 0, 7
".long 0x4a0e0c19\n" // v_add_nc_u32_e32 v7, s25, v6
".long 0x4a0e0e1a\n" // v_add_nc_u32_e32 v7, s26, v7
".long 0xbefe0029\n" // s_mov_b32 exec_lo, s41
".long 0xc406c07c, 0x40802028, 0x00000007\n" // buffer_store_b64 v[40:41], v7, s[16:19], null offen
".long 0xbefe00c1\n" // s_mov_b32 exec_lo, -1
".long 0xbfc00000\n" // s_wait_loadcnt 0x0
".long 0xbfc00000\n" // s_wait_loadcnt 0x0
".long 0xbfc10000\n" // s_wait_storecnt 0x0
".long 0xbfc60000\n" // s_wait_dscnt 0x0
".long 0xbfc70000\n" // s_wait_kmcnt 0x0
".long 0xbfc50000\n" // s_wait_xcnt 0x0
".long 0xbf880000\n" // s_wait_alu depctr_hold_cnt(0) depctr_sa_sdst(0) depctr_va_vdst(0) depctr_va_sdst(0) depctr_va_ssrc(0) depctr_va_vcc(0) depctr_vm_vsrc(0)
".long 0xb9053801\n" // s_setreg_b32 hwreg(HW_REG_WAVE_MODE, 0, 8), s5
".long 0xbf800007\n" // s_nop 7
