// gfx1100 / ROCm 7.2, wave32, ordinary HIP device-function ABI.
// Implements: output.data[i] = input[i] - 1; then publishes output.tag.
// All threads of the producer CTA must call this function (it uses s_barrier).
// Parameters: input v0:v1, output.data v2:v3, output.tag v4:v5,
//             n v6, epoch v7; implicit arguments s8:s9, workitem ID v31.
// Return address s30:s31. This is a device function, not a kernel entry.
	.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"
	.amdhsa_code_object_version 6
	.text
	.hidden	stage_sub_device                ; -- Begin function stage_sub_device
	.globl	stage_sub_device
	.p2align	2
	.type	stage_sub_device,@function
stage_sub_device:                       ; @stage_sub_device
; %bb.0:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)
	v_and_b32_e32 v10, 0x3ff, v31
	s_mov_b32 s1, exec_lo
	s_delay_alu instid0(VALU_DEP_1)
	v_cmpx_lt_i32_e64 v10, v6
	s_cbranch_execz .LBB5_3
; %bb.1:
	s_load_b32 s0, s[8:9], 0x0
	v_mov_b32_e32 v8, 0
	s_waitcnt lgkmcnt(0)
	s_cmp_lt_u32 s12, s0
	s_cselect_b32 s0, 12, 18
	s_delay_alu instid0(SALU_CYCLE_1)
	s_add_u32 s2, s8, s0
	s_addc_u32 s3, s9, 0
	global_load_u16 v11, v8, s[2:3]
	v_mov_b32_e32 v8, v10
	s_mov_b32 s2, 0
	.p2align	6
.LBB5_2:                                ; =>This Inner Loop Header: Depth=1
	s_delay_alu instid0(VALU_DEP_1) | instskip(NEXT) | instid1(VALU_DEP_1)
	v_ashrrev_i32_e32 v9, 31, v8
	v_lshlrev_b64 v[12:13], 2, v[8:9]
	s_delay_alu instid0(VALU_DEP_1) | instskip(NEXT) | instid1(VALU_DEP_1)
	v_add_co_u32 v14, vcc_lo, v0, v12
	v_add_co_ci_u32_e64 v15, null, v1, v13, vcc_lo
	v_add_co_u32 v12, s0, v2, v12
	s_delay_alu instid0(VALU_DEP_1) | instskip(SKIP_3) | instid1(VALU_DEP_1)
	v_add_co_ci_u32_e64 v13, null, v3, v13, s0
	flat_load_b32 v9, v[14:15]
	s_waitcnt vmcnt(0) lgkmcnt(0)
	v_dual_add_f32 v9, -1.0, v9 :: v_dual_add_nc_u32 v8, v8, v11
	v_cmp_ge_i32_e32 vcc_lo, v8, v6
	flat_store_b32 v[12:13], v9
	s_or_b32 s2, vcc_lo, s2
	s_delay_alu instid0(SALU_CYCLE_1)
	s_and_not1_b32 exec_lo, exec_lo, s2
	s_cbranch_execnz .LBB5_2
.LBB5_3:                                ; %Flow3
	s_or_b32 exec_lo, exec_lo, s1
	s_delay_alu instid0(SALU_CYCLE_1)
	s_mov_b32 s0, exec_lo
	s_waitcnt lgkmcnt(0)
	s_waitcnt_vscnt null, 0x0
	s_barrier
	buffer_gl0_inv
	v_cmpx_eq_u32_e32 0, v10
	s_cbranch_execz .LBB5_5
; %bb.4:
	flat_store_b32 v[4:5], v7
.LBB5_5:
	s_or_b32 exec_lo, exec_lo, s0
	s_waitcnt lgkmcnt(0)
	s_setpc_b64 s[30:31]
.Lfunc_end5:
	.size	stage_sub_device, .Lfunc_end5-stage_sub_device
                                        ; -- End function
	.set stage_sub_device.num_vgpr, 32
	.set stage_sub_device.num_agpr, 0
	.set stage_sub_device.numbered_sgpr, 32
	.set stage_sub_device.num_named_barrier, 0
	.set stage_sub_device.private_seg_size, 0
	.set stage_sub_device.uses_vcc, 1
	.set stage_sub_device.uses_flat_scratch, 0
	.set stage_sub_device.has_dyn_sized_stack, 0
	.set stage_sub_device.has_recursion, 0
	.set stage_sub_device.has_indirect_call, 0

// Retain compiler-style instruction prefetch padding.
	.text
	.p2alignl 7, 3214868480
	.fill 96, 4, 3214868480
	.section ".note.GNU-stack","",@progbits
