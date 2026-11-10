// Standalone gfx1100 assembly, derived from ROCm 7.2 compiler output.
// Opaque device-stage implementation; no HIP/C++ implementation is required.
// Define SUB_DEVICE_ONLY=1 to emit only the linkable device function.
// By default, sub_kernel also adapts the kernel ABI for standalone testing:
//   extern "C" __global__ void sub_kernel(
//       const float* input, Mailbox output, int n, unsigned epoch) {
//     stage_sub_device(input, output, n, epoch);
//   }
// Standalone sub_kernel launch: exactly one CTA, as indexing is block-local.
// In Mono, only the producer CTA calls stage_sub_device.
// Explicit kernarg layout: input=0, output.data=8, output.tag=16, n=24,
// epoch=28. Hidden launch arguments start at 32 (total allocation: 288 bytes).
// This is an editable assembly snapshot, independent of sub.cpp / sub.h.
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
	.ifndef SUB_DEVICE_ONLY
	.text
	.protected	sub_kernel              ; -- Begin function sub_kernel
	.globl	sub_kernel
	.p2align	8
	.type	sub_kernel,@function
sub_kernel:                             ; @sub_kernel
// kernarg pointer arrives in s[0:1]; workgroup id x in s15; workitem id in v0.
// Move explicit args to v0:v7, implicit-arg pointer to s[8:9], thread id to v31.
; %bb.0:
	s_load_b256 s[16:23], s[0:1], 0x0
	v_mov_b32_e32 v31, v0
	s_add_u32 s8, s0, 32
	s_addc_u32 s9, s1, 0
	s_mov_b32 s12, s15
	s_getpc_b64 s[0:1]
	s_add_u32 s0, s0, stage_sub_device@rel32@lo+4
	s_addc_u32 s1, s1, stage_sub_device@rel32@hi+12
	s_mov_b32 s32, 0
	s_waitcnt lgkmcnt(0)
	v_dual_mov_b32 v0, s16 :: v_dual_mov_b32 v1, s17
	v_dual_mov_b32 v2, s18 :: v_dual_mov_b32 v3, s19
	v_dual_mov_b32 v4, s20 :: v_dual_mov_b32 v5, s21
	v_dual_mov_b32 v6, s22 :: v_dual_mov_b32 v7, s23
	s_swappc_b64 s[30:31], s[0:1]
	s_endpgm
	.section	.rodata,"a",@progbits
	.p2align	6, 0x0
	.amdhsa_kernel sub_kernel
		.amdhsa_group_segment_fixed_size 0
		.amdhsa_private_segment_fixed_size 0
		.amdhsa_kernarg_size 288
		.amdhsa_user_sgpr_count 15
		.amdhsa_user_sgpr_dispatch_ptr 0
		.amdhsa_user_sgpr_queue_ptr 0
		.amdhsa_user_sgpr_kernarg_segment_ptr 1
		.amdhsa_user_sgpr_dispatch_id 0
		.amdhsa_user_sgpr_private_segment_size 0
		.amdhsa_wavefront_size32 1
		.amdhsa_uses_dynamic_stack 0
		.amdhsa_enable_private_segment 0
		.amdhsa_system_sgpr_workgroup_id_x 1
		.amdhsa_system_sgpr_workgroup_id_y 0
		.amdhsa_system_sgpr_workgroup_id_z 0
		.amdhsa_system_sgpr_workgroup_info 0
		.amdhsa_system_vgpr_workitem_id 0
		.amdhsa_next_free_vgpr 32
		.amdhsa_next_free_sgpr 33
		.amdhsa_reserve_vcc 1
		.amdhsa_float_round_mode_32 0
		.amdhsa_float_round_mode_16_64 0
		.amdhsa_float_denorm_mode_32 3
		.amdhsa_float_denorm_mode_16_64 3
		.amdhsa_dx10_clamp 1
		.amdhsa_ieee_mode 1
		.amdhsa_fp16_overflow 0
		.amdhsa_workgroup_processor_mode 1
		.amdhsa_memory_ordered 1
		.amdhsa_forward_progress 1
		.amdhsa_shared_vgpr_count 0
		.amdhsa_inst_pref_size 1
		.amdhsa_exception_fp_ieee_invalid_op 0
		.amdhsa_exception_fp_denorm_src 0
		.amdhsa_exception_fp_ieee_div_zero 0
		.amdhsa_exception_fp_ieee_overflow 0
		.amdhsa_exception_fp_ieee_underflow 0
		.amdhsa_exception_fp_ieee_inexact 0
		.amdhsa_exception_int_div_zero 0
	.end_amdhsa_kernel
	.text
.Lfunc_end6:
	.size	sub_kernel, .Lfunc_end6-sub_kernel
                                        ; -- End function
	.set sub_kernel.num_vgpr, max(32, stage_sub_device.num_vgpr)
	.set sub_kernel.num_agpr, max(0, stage_sub_device.num_agpr)
	.set sub_kernel.numbered_sgpr, max(33, stage_sub_device.numbered_sgpr)
	.set sub_kernel.num_named_barrier, max(0, stage_sub_device.num_named_barrier)
	.set sub_kernel.private_seg_size, 0+max(stage_sub_device.private_seg_size)
	.set sub_kernel.uses_vcc, or(1, stage_sub_device.uses_vcc)
	.set sub_kernel.uses_flat_scratch, or(0, stage_sub_device.uses_flat_scratch)
	.set sub_kernel.has_dyn_sized_stack, or(0, stage_sub_device.has_dyn_sized_stack)
	.set sub_kernel.has_recursion, or(0, stage_sub_device.has_recursion)
	.set sub_kernel.has_indirect_call, or(0, stage_sub_device.has_indirect_call)
	.endif

// Retain compiler-style end-of-text padding for instruction prefetch.
	.text
	.p2alignl 7, 3214868480
	.fill 96, 4, 3214868480
	.section ".note.GNU-stack","",@progbits

// The assembler encodes this YAML as the AMDGPU metadata ELF note.
	.ifndef SUB_DEVICE_ONLY
	.amdgpu_metadata
---
amdhsa.kernels:
  - .args:
      - .address_space:  global
        .offset:         0
        .size:           8
        .value_kind:     global_buffer
      - .offset:         8
        .size:           16
        .value_kind:     by_value
      - .offset:         24
        .size:           4
        .value_kind:     by_value
      - .offset:         28
        .size:           4
        .value_kind:     by_value
      - .offset:         32
        .size:           4
        .value_kind:     hidden_block_count_x
      - .offset:         36
        .size:           4
        .value_kind:     hidden_block_count_y
      - .offset:         40
        .size:           4
        .value_kind:     hidden_block_count_z
      - .offset:         44
        .size:           2
        .value_kind:     hidden_group_size_x
      - .offset:         46
        .size:           2
        .value_kind:     hidden_group_size_y
      - .offset:         48
        .size:           2
        .value_kind:     hidden_group_size_z
      - .offset:         50
        .size:           2
        .value_kind:     hidden_remainder_x
      - .offset:         52
        .size:           2
        .value_kind:     hidden_remainder_y
      - .offset:         54
        .size:           2
        .value_kind:     hidden_remainder_z
      - .offset:         72
        .size:           8
        .value_kind:     hidden_global_offset_x
      - .offset:         80
        .size:           8
        .value_kind:     hidden_global_offset_y
      - .offset:         88
        .size:           8
        .value_kind:     hidden_global_offset_z
      - .offset:         96
        .size:           2
        .value_kind:     hidden_grid_dims
    .group_segment_fixed_size: 0
    .kernarg_segment_align: 8
    .kernarg_segment_size: 288
    .language:       OpenCL C
    .language_version:
      - 2
      - 0
    .max_flat_workgroup_size: 1024
    .name:           sub_kernel
    .private_segment_fixed_size: 0
    .sgpr_count:     35
    .sgpr_spill_count: 0
    .symbol:         sub_kernel.kd
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
    .vgpr_count:     32
    .vgpr_spill_count: 0
    .wavefront_size: 32
    .workgroup_processor_mode: 1
amdhsa.target:   amdgcn-amd-amdhsa--gfx1100
amdhsa.version:
  - 1
  - 2
...

	.end_amdgpu_metadata
	.endif
