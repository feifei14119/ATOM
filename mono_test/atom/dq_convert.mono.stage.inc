// Complete position-independent stage, including wave gate and output drain.
// Insert caller leave/restore immediately after the last word. No kernel exit.
.long 0x9328ff74, 0x00050019 // +0x0000: s_bfe_u32 s40, ttmp8, 0x50019
.long 0xbf0a8428 // +0x0008: s_cmp_lt_u32 s40, 4
.long 0xbfa10181 // +0x000c: s_cbranch_scc0 385
.long 0xd71f0000, 0x000100c1 // +0x0010: v_mbcnt_lo_u32_b32 v0, -1, 0
.long 0xbf800003 // +0x0018: s_nop 3
.long 0xb0804009 // +0x001c: s_version UC_VERSION_GFX12|UC_VERSION_W32_BIT
.long 0x8b01ff01, 0x0000ffff // +0x0020: s_and_b32 s1, s1, 0xffff
.long 0xf4002300, 0xf8000000 // +0x0028: s_load_b64 s[12:13], s[0:1], 0x0
.long 0xf4002400, 0xf8000010 // +0x0030: s_load_b64 s[16:17], s[0:1], 0x10
.long 0xf4002180, 0xf8000020 // +0x0038: s_load_b64 s[6:7], s[0:1], 0x20
.long 0xf4000900, 0xf8000040 // +0x0040: s_load_b32 s36, s[0:1], 0x40
.long 0xf4002280, 0xf8000050 // +0x0048: s_load_b64 s[10:11], s[0:1], 0x50
.long 0xf4000940, 0xf8000070 // +0x0050: s_load_b32 s37, s[0:1], 0x70
.long 0xf4000800, 0xf8000090 // +0x0058: s_load_b32 s32, s[0:1], 0x90
.long 0xf4002200, 0xf8000030 // +0x0060: s_load_b64 s[8:9], s[0:1], 0x30
.long 0xf4002880, 0xf8000060 // +0x0068: s_load_b64 s[34:35], s[0:1], 0x60
.long 0xf4000840, 0xf8000080 // +0x0070: s_load_b32 s33, s[0:1], 0x80
.long 0xbfc70000 // +0x0078: s_wait_kmcnt 0x0
.long 0x3600009f // +0x007c: v_and_b32_e32 v0, 31, v0
.long 0xbe820080 // +0x0080: s_mov_b32 s2, 0
.long 0xbe830080 // +0x0084: s_mov_b32 s3, 0
.long 0xbf800000 // +0x0088: s_nop 0
.long 0xbe840080 // +0x008c: s_mov_b32 s4, 0
.long 0xbf800000 // +0x0090: s_nop 0
.long 0x9318ff74, 0x00050019 // +0x0094: s_bfe_u32 s24, ttmp8, 0x50019
.long 0x8b0dff0d, 0x001fffff // +0x009c: s_and_b32 s13, s13, 0x1fffff
.long 0x8b0dff0d, 0x1fffffff // +0x00a4: s_and_b32 s13, s13, 0x1fffffff
.long 0xbe8e0080 // +0x00ac: s_mov_b32 s14, 0
.long 0xbe8f00ff, 0x00004000 // +0x00b0: s_mov_b32 s15, 0x4000
.long 0x8b11ff11, 0x001fffff // +0x00b8: s_and_b32 s17, s17, 0x1fffff
.long 0x8b11ff11, 0x1fffffff // +0x00c0: s_and_b32 s17, s17, 0x1fffffff
.long 0xbe920080 // +0x00c8: s_mov_b32 s18, 0
.long 0xbe9300ff, 0x00004000 // +0x00cc: s_mov_b32 s19, 0x4000
.long 0x7e5a0280 // +0x00d4: v_mov_b32_e32 v45, 0
.long 0xbe94000c // +0x00d8: s_mov_b32 s20, s12
.long 0xbe95000d // +0x00dc: s_mov_b32 s21, s13
.long 0xbe960010 // +0x00e0: s_mov_b32 s22, s16
.long 0xbe970011 // +0x00e4: s_mov_b32 s23, s17
.long 0x9619c024 // +0x00e8: s_mul_i32 s25, s36, 64
.long 0x96a61902 // +0x00ec: s_mul_hi_u32 s38, s2, s25
.long 0x96191902 // +0x00f0: s_mul_i32 s25, s2, s25
.long 0x961a0603 // +0x00f4: s_mul_i32 s26, s3, s6
.long 0x969d0603 // +0x00f8: s_mul_hi_u32 s29, s3, s6
.long 0x961b0703 // +0x00fc: s_mul_i32 s27, s3, s7
.long 0x801d1b1d // +0x0100: s_add_co_u32 s29, s29, s27
.long 0x801c1a19 // +0x0104: s_add_co_u32 s28, s25, s26
.long 0x821d261d // +0x0108: s_add_co_ci_u32 s29, s29, s38
.long 0x961a0804 // +0x010c: s_mul_i32 s26, s4, s8
.long 0x969b0804 // +0x0110: s_mul_hi_u32 s27, s4, s8
.long 0x96260904 // +0x0114: s_mul_i32 s38, s4, s9
.long 0x801b261b // +0x0118: s_add_co_u32 s27, s27, s38
.long 0x801c1a1c // +0x011c: s_add_co_u32 s28, s28, s26
.long 0x821d1b1d // +0x0120: s_add_co_ci_u32 s29, s29, s27
.long 0x80199f21 // +0x0124: s_add_co_u32 s25, s33, 31
.long 0x8b19ff19, 0xffffffe0 // +0x0128: s_and_b32 s25, s25, 0xffffffe0
.long 0x961ac002 // +0x0130: s_mul_i32 s26, s2, 64
.long 0x819a1a19 // +0x0134: s_sub_co_i32 s26, s25, s26
.long 0x969b241a // +0x0138: s_mul_hi_u32 s27, s26, s36
.long 0x961a241a // +0x013c: s_mul_i32 s26, s26, s36
.long 0x800c141c // +0x0140: s_add_co_u32 s12, s28, s20
.long 0x820d151d // +0x0144: s_add_co_ci_u32 s13, s29, s21
.long 0x8b0dff0d, 0x01ffffff // +0x0148: s_and_b32 s13, s13, 0x1ffffff
.long 0x840e991a // +0x0150: s_lshl_b32 s14, s26, 25
.long 0x8c0d0e0d // +0x0154: s_or_b32 s13, s13, s14
.long 0x850e871a // +0x0158: s_lshr_b32 s14, s26, 7
.long 0x840f991b // +0x015c: s_lshl_b32 s15, s27, 25
.long 0x8c0e0f0e // +0x0160: s_or_b32 s14, s14, s15
.long 0x850f871b // +0x0164: s_lshr_b32 s15, s27, 7
.long 0x8b0fbf0f // +0x0168: s_and_b32 s15, s15, 63
.long 0x8c0fff0f, 0x00004000 // +0x016c: s_or_b32 s15, s15, 0x4000
.long 0x9619c025 // +0x0174: s_mul_i32 s25, s37, 64
.long 0x96a61902 // +0x0178: s_mul_hi_u32 s38, s2, s25
.long 0x96191902 // +0x017c: s_mul_i32 s25, s2, s25
.long 0x961a0a03 // +0x0180: s_mul_i32 s26, s3, s10
.long 0x969c0a03 // +0x0184: s_mul_hi_u32 s28, s3, s10
.long 0x961b0b03 // +0x0188: s_mul_i32 s27, s3, s11
.long 0x801c1b1c // +0x018c: s_add_co_u32 s28, s28, s27
.long 0x801d1a19 // +0x0190: s_add_co_u32 s29, s25, s26
.long 0x821c261c // +0x0194: s_add_co_ci_u32 s28, s28, s38
.long 0x961a2204 // +0x0198: s_mul_i32 s26, s4, s34
.long 0x969b2204 // +0x019c: s_mul_hi_u32 s27, s4, s34
.long 0x96262304 // +0x01a0: s_mul_i32 s38, s4, s35
.long 0x801b261b // +0x01a4: s_add_co_u32 s27, s27, s38
.long 0x801d1a1d // +0x01a8: s_add_co_u32 s29, s29, s26
.long 0x821c1b1c // +0x01ac: s_add_co_ci_u32 s28, s28, s27
.long 0x961ac002 // +0x01b0: s_mul_i32 s26, s2, 64
.long 0x819a1a21 // +0x01b4: s_sub_co_i32 s26, s33, s26
.long 0x969b251a // +0x01b8: s_mul_hi_u32 s27, s26, s37
.long 0x961a251a // +0x01bc: s_mul_i32 s26, s26, s37
.long 0x8010161d // +0x01c0: s_add_co_u32 s16, s29, s22
.long 0x8211171c // +0x01c4: s_add_co_ci_u32 s17, s28, s23
.long 0x8b11ff11, 0x01ffffff // +0x01c8: s_and_b32 s17, s17, 0x1ffffff
.long 0x8412991a // +0x01d0: s_lshl_b32 s18, s26, 25
.long 0x8c111211 // +0x01d4: s_or_b32 s17, s17, s18
.long 0x8512871a // +0x01d8: s_lshr_b32 s18, s26, 7
.long 0x8413991b // +0x01dc: s_lshl_b32 s19, s27, 25
.long 0x8c121312 // +0x01e0: s_or_b32 s18, s18, s19
.long 0x8513871b // +0x01e4: s_lshr_b32 s19, s27, 7
.long 0x8b13bf13 // +0x01e8: s_and_b32 s19, s19, 63
.long 0x8c13ff13, 0x00004000 // +0x01ec: s_or_b32 s19, s19, 0x4000
.long 0x32540084 // +0x01f4: v_lshrrev_b32_e32 v42, 4, v0
.long 0x30545483 // +0x01f8: v_lshlrev_b32_e32 v42, 3, v42
.long 0x12545424 // +0x01fc: v_mul_i32_i24_e32 v42, s36, v42
.long 0x3656008f // +0x0200: v_and_b32_e32 v43, 15, v0
.long 0x12565690 // +0x0204: v_mul_i32_i24_e32 v43, 16, v43
.long 0x4a56572a // +0x0208: v_add_nc_u32_e32 v43, v42, v43
.long 0x7e08032b // +0x020c: v_mov_b32_e32 v4, v43
.long 0x96192490 // +0x0210: s_mul_i32 s25, 16, s36
.long 0x96191918 // +0x0214: s_mul_i32 s25, s24, s25
.long 0x4a080819 // +0x0218: v_add_nc_u32_e32 v4, s25, v4
.long 0x7e0c0280 // +0x021c: v_mov_b32_e32 v6, 0
.long 0xd51b002a, 0x00010900 // +0x0220: v_and_b32_e64 v42, v0, 4
.long 0x30545481 // +0x0228: v_lshlrev_b32_e32 v42, 1, v42
.long 0xd509002a, 0x00004b2a // +0x022c: v_mul_i32_i24_e64 v42, v42, s37
.long 0xd51b002b, 0x00011f00 // +0x0234: v_and_b32_e64 v43, v0, 15
.long 0x32565683 // +0x023c: v_lshrrev_b32_e32 v43, 3, v43
.long 0xd509002b, 0x0001812b // +0x0240: v_mul_i32_i24_e64 v43, v43, 64
.long 0x32580084 // +0x0248: v_lshrrev_b32_e32 v44, 4, v0
.long 0xd509002c, 0x0001412c // +0x024c: v_mul_i32_i24_e64 v44, v44, 32
.long 0xd51b002d, 0x00010700 // +0x0254: v_and_b32_e64 v45, v0, 3
.long 0xd509002d, 0x0001112d // +0x025c: v_mul_i32_i24_e64 v45, v45, 8
.long 0x4a0c0d2a // +0x0264: v_add_nc_u32_e32 v6, v42, v6
.long 0x4a0c0d2b // +0x0268: v_add_nc_u32_e32 v6, v43, v6
.long 0x4a0c0d2c // +0x026c: v_add_nc_u32_e32 v6, v44, v6
.long 0x4a0c0d2d // +0x0270: v_add_nc_u32_e32 v6, v45, v6
.long 0x96192590 // +0x0274: s_mul_i32 s25, 16, s37
.long 0x96191918 // +0x0278: s_mul_i32 s25, s24, s25
.long 0x4a0c0c19 // +0x027c: v_add_nc_u32_e32 v6, s25, v6
.long 0x3654008f // +0x0280: v_and_b32_e32 v42, 15, v0
.long 0x30545482 // +0x0284: v_lshlrev_b32_e32 v42, 2, v42
.long 0x81998020 // +0x0288: s_sub_co_i32 s25, s32, 0
.long 0xd449001e, 0x0000332a // +0x028c: v_cmp_lt_u32_e64 s30, v42, s25
.long 0x3654008f // +0x0294: v_and_b32_e32 v42, 15, v0
.long 0x32545481 // +0x0298: v_lshrrev_b32_e32 v42, 1, v42
.long 0x30545483 // +0x029c: v_lshlrev_b32_e32 v42, 3, v42
.long 0x81998020 // +0x02a0: s_sub_co_i32 s25, s32, 0
.long 0xd449001f, 0x0000332a // +0x02a4: v_cmp_lt_u32_e64 s31, v42, s25
.long 0x96198024 // +0x02ac: s_mul_i32 s25, s36, 0
.long 0x4a0a0819 // +0x02b0: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e100280 // +0x02b4: v_mov_b32_e32 v8, 0
.long 0x7e120280 // +0x02b8: v_mov_b32_e32 v9, 0
.long 0x7e140280 // +0x02bc: v_mov_b32_e32 v10, 0
.long 0x7e160280 // +0x02c0: v_mov_b32_e32 v11, 0
.long 0xbefe001e // +0x02c4: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x40801808, 0x00000005 // +0x02c8: buffer_load_b128 v[8:11], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x02d4: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x02d8: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198124 // +0x02e0: s_mul_i32 s25, s36, 1
.long 0x4a0a0819 // +0x02e4: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e180280 // +0x02e8: v_mov_b32_e32 v12, 0
.long 0x7e1a0280 // +0x02ec: v_mov_b32_e32 v13, 0
.long 0x7e1c0280 // +0x02f0: v_mov_b32_e32 v14, 0
.long 0x7e1e0280 // +0x02f4: v_mov_b32_e32 v15, 0
.long 0xbefe001e // +0x02f8: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x4080180c, 0x00000005 // +0x02fc: buffer_load_b128 v[12:15], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x0308: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x030c: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198224 // +0x0314: s_mul_i32 s25, s36, 2
.long 0x4a0a0819 // +0x0318: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e200280 // +0x031c: v_mov_b32_e32 v16, 0
.long 0x7e220280 // +0x0320: v_mov_b32_e32 v17, 0
.long 0x7e240280 // +0x0324: v_mov_b32_e32 v18, 0
.long 0x7e260280 // +0x0328: v_mov_b32_e32 v19, 0
.long 0xbefe001e // +0x032c: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x40801810, 0x00000005 // +0x0330: buffer_load_b128 v[16:19], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x033c: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x0340: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198324 // +0x0348: s_mul_i32 s25, s36, 3
.long 0x4a0a0819 // +0x034c: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e280280 // +0x0350: v_mov_b32_e32 v20, 0
.long 0x7e2a0280 // +0x0354: v_mov_b32_e32 v21, 0
.long 0x7e2c0280 // +0x0358: v_mov_b32_e32 v22, 0
.long 0x7e2e0280 // +0x035c: v_mov_b32_e32 v23, 0
.long 0xbefe001e // +0x0360: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x40801814, 0x00000005 // +0x0364: buffer_load_b128 v[20:23], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x0370: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x0374: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198424 // +0x037c: s_mul_i32 s25, s36, 4
.long 0x4a0a0819 // +0x0380: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e300280 // +0x0384: v_mov_b32_e32 v24, 0
.long 0x7e320280 // +0x0388: v_mov_b32_e32 v25, 0
.long 0x7e340280 // +0x038c: v_mov_b32_e32 v26, 0
.long 0x7e360280 // +0x0390: v_mov_b32_e32 v27, 0
.long 0xbefe001e // +0x0394: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x40801818, 0x00000005 // +0x0398: buffer_load_b128 v[24:27], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x03a4: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x03a8: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198524 // +0x03b0: s_mul_i32 s25, s36, 5
.long 0x4a0a0819 // +0x03b4: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e380280 // +0x03b8: v_mov_b32_e32 v28, 0
.long 0x7e3a0280 // +0x03bc: v_mov_b32_e32 v29, 0
.long 0x7e3c0280 // +0x03c0: v_mov_b32_e32 v30, 0
.long 0x7e3e0280 // +0x03c4: v_mov_b32_e32 v31, 0
.long 0xbefe001e // +0x03c8: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x4080181c, 0x00000005 // +0x03cc: buffer_load_b128 v[28:31], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x03d8: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x03dc: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198624 // +0x03e4: s_mul_i32 s25, s36, 6
.long 0x4a0a0819 // +0x03e8: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e400280 // +0x03ec: v_mov_b32_e32 v32, 0
.long 0x7e420280 // +0x03f0: v_mov_b32_e32 v33, 0
.long 0x7e440280 // +0x03f4: v_mov_b32_e32 v34, 0
.long 0x7e460280 // +0x03f8: v_mov_b32_e32 v35, 0
.long 0xbefe001e // +0x03fc: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x40801820, 0x00000005 // +0x0400: buffer_load_b128 v[32:35], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x040c: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x0410: v_add_nc_u32_e32 v5, 0x100, v5
.long 0x96198724 // +0x0418: s_mul_i32 s25, s36, 7
.long 0x4a0a0819 // +0x041c: v_add_nc_u32_e32 v5, s25, v4
.long 0x7e480280 // +0x0420: v_mov_b32_e32 v36, 0
.long 0x7e4a0280 // +0x0424: v_mov_b32_e32 v37, 0
.long 0x7e4c0280 // +0x0428: v_mov_b32_e32 v38, 0
.long 0x7e4e0280 // +0x042c: v_mov_b32_e32 v39, 0
.long 0xbefe001e // +0x0430: s_mov_b32 exec_lo, s30
.long 0xc405c07c, 0x40801824, 0x00000005 // +0x0434: buffer_load_b128 v[36:39], v5, s[12:15], null offen
.long 0xbefe00c1 // +0x0440: s_mov_b32 exec_lo, -1
.long 0x4a0a0aff, 0x00000100 // +0x0444: v_add_nc_u32_e32 v5, 0x100, v5
.long 0xbfc00007 // +0x044c: s_wait_loadcnt 0x7
.long 0xd76d0028, 0x00021308 // +0x0450: v_cvt_pk_bf16_f32 v40, v8, v9
.long 0xd76d0029, 0x0002170a // +0x0458: v_cvt_pk_bf16_f32 v41, v10, v11
.long 0x96198025 // +0x0460: s_mul_i32 s25, s37, 0
.long 0x841a8780 // +0x0464: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x0468: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x046c: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x0470: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x0474: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x0480: s_mov_b32 exec_lo, -1
.long 0xbfc00006 // +0x0484: s_wait_loadcnt 0x6
.long 0xd76d0028, 0x00021b0c // +0x0488: v_cvt_pk_bf16_f32 v40, v12, v13
.long 0xd76d0029, 0x00021f0e // +0x0490: v_cvt_pk_bf16_f32 v41, v14, v15
.long 0x96198125 // +0x0498: s_mul_i32 s25, s37, 1
.long 0x841a8780 // +0x049c: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x04a0: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x04a4: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x04a8: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x04ac: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x04b8: s_mov_b32 exec_lo, -1
.long 0xbfc00005 // +0x04bc: s_wait_loadcnt 0x5
.long 0xd76d0028, 0x00022310 // +0x04c0: v_cvt_pk_bf16_f32 v40, v16, v17
.long 0xd76d0029, 0x00022712 // +0x04c8: v_cvt_pk_bf16_f32 v41, v18, v19
.long 0x96198225 // +0x04d0: s_mul_i32 s25, s37, 2
.long 0x841a8780 // +0x04d4: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x04d8: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x04dc: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x04e0: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x04e4: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x04f0: s_mov_b32 exec_lo, -1
.long 0xbfc00004 // +0x04f4: s_wait_loadcnt 0x4
.long 0xd76d0028, 0x00022b14 // +0x04f8: v_cvt_pk_bf16_f32 v40, v20, v21
.long 0xd76d0029, 0x00022f16 // +0x0500: v_cvt_pk_bf16_f32 v41, v22, v23
.long 0x96198325 // +0x0508: s_mul_i32 s25, s37, 3
.long 0x841a8780 // +0x050c: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x0510: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x0514: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x0518: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x051c: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x0528: s_mov_b32 exec_lo, -1
.long 0xbfc00003 // +0x052c: s_wait_loadcnt 0x3
.long 0xd76d0028, 0x00023318 // +0x0530: v_cvt_pk_bf16_f32 v40, v24, v25
.long 0xd76d0029, 0x0002371a // +0x0538: v_cvt_pk_bf16_f32 v41, v26, v27
.long 0x96198425 // +0x0540: s_mul_i32 s25, s37, 4
.long 0x841a8780 // +0x0544: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x0548: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x054c: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x0550: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x0554: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x0560: s_mov_b32 exec_lo, -1
.long 0xbfc00002 // +0x0564: s_wait_loadcnt 0x2
.long 0xd76d0028, 0x00023b1c // +0x0568: v_cvt_pk_bf16_f32 v40, v28, v29
.long 0xd76d0029, 0x00023f1e // +0x0570: v_cvt_pk_bf16_f32 v41, v30, v31
.long 0x96198525 // +0x0578: s_mul_i32 s25, s37, 5
.long 0x841a8780 // +0x057c: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x0580: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x0584: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x0588: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x058c: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x0598: s_mov_b32 exec_lo, -1
.long 0xbfc00001 // +0x059c: s_wait_loadcnt 0x1
.long 0xd76d0028, 0x00024320 // +0x05a0: v_cvt_pk_bf16_f32 v40, v32, v33
.long 0xd76d0029, 0x00024722 // +0x05a8: v_cvt_pk_bf16_f32 v41, v34, v35
.long 0x96198625 // +0x05b0: s_mul_i32 s25, s37, 6
.long 0x841a8780 // +0x05b4: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x05b8: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x05bc: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x05c0: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x05c4: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x05d0: s_mov_b32 exec_lo, -1
.long 0xbfc00000 // +0x05d4: s_wait_loadcnt 0x0
.long 0xd76d0028, 0x00024b24 // +0x05d8: v_cvt_pk_bf16_f32 v40, v36, v37
.long 0xd76d0029, 0x00024f26 // +0x05e0: v_cvt_pk_bf16_f32 v41, v38, v39
.long 0x96198725 // +0x05e8: s_mul_i32 s25, s37, 7
.long 0x841a8780 // +0x05ec: s_lshl_b32 s26, 0, 7
.long 0x4a0e0c19 // +0x05f0: v_add_nc_u32_e32 v7, s25, v6
.long 0x4a0e0e1a // +0x05f4: v_add_nc_u32_e32 v7, s26, v7
.long 0xbefe001f // +0x05f8: s_mov_b32 exec_lo, s31
.long 0xc406c07c, 0x40802028, 0x00000007 // +0x05fc: buffer_store_b64 v[40:41], v7, s[16:19], null offen
.long 0xbefe00c1 // +0x0608: s_mov_b32 exec_lo, -1
.long 0xbfc00000 // +0x060c: s_wait_loadcnt 0x0
.long 0xbfa00000 // +0x0610: s_branch 0
.long 0xbfc00000 // +0x0614: s_wait_loadcnt 0x0
.long 0xbfc10000 // +0x0618: s_wait_storecnt 0x0
.long 0xbfc70000 // +0x061c: s_wait_kmcnt 0x0
.long 0xbefe00c1 // +0x0620: s_mov_b32 exec_lo, -1
.long 0xbfa00000 // +0x0624: s_branch mono_dq_convert_stage_end
