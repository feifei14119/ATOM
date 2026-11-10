// gfx1100 / wave32. CUSTOM low-context ABI: callable only through the patched
// SI_CALL regmask in callsite_regmask.py, NOT an ordinary default-ABI function.
// Arguments unchanged: bias v0, input v1:v2, record v3:v4, tx/ty/bx/by v5-v8;
// packed thread ID v31, workgroup IDs s12/s13; result v0; return PC s30:s31.
// Preserves the standard-ABI subset v40-v47, v56-v63, s30-s39 and special state.
// Body really overwrites v64-v255 and s40-s105. No save/restore is needed.
// EXEC, MODE, VCC, s30:s31, s32 and s33/s34 remain unchanged.
	.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"
	.amdhsa_code_object_version 6
	.text
	.globl stage_probe_lowctx
	.hidden stage_probe_lowctx
	.p2align 2
	.type stage_probe_lowctx,@function
stage_probe_lowctx:
.Lpayload_begin:
// Conservative boundaries/dependency waits keep this teaching example simple.
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)
	s_waitcnt_vscnt null, 0
	s_waitcnt_depctr 0
// Actual overwrite of EVERY numbered GPR in the requested ranges.
// v_mov affects only active lanes; inactive lanes and EXEC stay untouched.
	.irp r, 64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255
	v_mov_b32_e32 v\r, 0xdeadbeef
	.endr
	.irp r, 40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105
	s_mov_b32 s\r, 0xbaadf00d
	.endr
	s_waitcnt_depctr 0
	v_mov_b32_e32 v10, v1
	v_mov_b32_e32 v11, v2
	s_waitcnt_depctr 0
	global_load_b32 v9, v[10:11], off
	v_and_b32_e32 v12, 0x3ff, v31
	v_bfe_u32 v13, v31, 10, 10
	v_mov_b32_e32 v14, s12
	v_mov_b32_e32 v15, s13
	s_xor_b32 s0, s12, s13
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
// Change input memory so the caller cannot reload its original live snapshot.
	v_xor_b32_e32 v17, 0x9e3779b9, v9
	s_waitcnt_depctr 0
	global_store_b32 v[10:11], v17, off
// result = ((loaded ^ 0x13579bdf) + bias + tx + (ty<<8)
//           + (bx<<16) + (by<<24)) ^ (implicit_bx ^ implicit_by).
	v_xor_b32_e32 v16, 0x13579bdf, v9
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v0, v16
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v5, v16
	v_lshlrev_b32_e32 v17, 8, v6
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v17, v16
	v_lshlrev_b32_e32 v17, 16, v7
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v17, v16
	v_lshlrev_b32_e32 v17, 24, v8
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v17, v16
	s_waitcnt_depctr 0
	v_xor_b32_e32 v16, s0, v16
	v_mov_b32_e32 v10, v3
	v_mov_b32_e32 v11, v4
	s_waitcnt_depctr 0
// Record each argument separately, not just a checksum of all arguments.
	global_store_b32 v[10:11], v0, off offset:0
	global_store_b32 v[10:11], v9, off offset:4
	global_store_b32 v[10:11], v5, off offset:8
	global_store_b32 v[10:11], v6, off offset:12
	global_store_b32 v[10:11], v7, off offset:16
	global_store_b32 v[10:11], v8, off offset:20
	global_store_b32 v[10:11], v12, off offset:24
	global_store_b32 v[10:11], v13, off offset:28
	global_store_b32 v[10:11], v14, off offset:32
	global_store_b32 v[10:11], v15, off offset:36
	global_store_b32 v[10:11], v16, off offset:40
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v0, v16
	s_waitcnt_depctr 0
.Lpayload_end:
	s_setpc_b64 s[30:31]
.Lstage_end:
	.size stage_probe_lowctx, .Lstage_end-stage_probe_lowctx
	.set stage_probe_lowctx.payload_offset, .Lpayload_begin-stage_probe_lowctx
	.set stage_probe_lowctx.payload_size, .Lpayload_end-.Lpayload_begin
	.set stage_probe_lowctx.num_vgpr, 256
	.set stage_probe_lowctx.num_agpr, 0
	.set stage_probe_lowctx.numbered_sgpr, 106
	.set stage_probe_lowctx.num_named_barrier, 0
	.set stage_probe_lowctx.private_seg_size, 0
	.set stage_probe_lowctx.uses_vcc, 0
	.set stage_probe_lowctx.uses_flat_scratch, 0
	.set stage_probe_lowctx.has_dyn_sized_stack, 0
	.set stage_probe_lowctx.has_recursion, 0
	.set stage_probe_lowctx.has_indirect_call, 0
	.section ".note.GNU-stack","",@progbits
