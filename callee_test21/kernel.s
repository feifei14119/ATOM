// gfx1100 / wave32. The launched kernel is entirely hand-written ASM.
// Three explicit pointer arguments: input a, input b, output records.
// One workgroup of 1..32 threads; thread ID is initially in v0.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"
.amdhsa_code_object_version 6
.text
.protected asm_flydsl_demo
.globl asm_flydsl_demo
.type asm_flydsl_demo,@function
.p2align 8
asm_flydsl_demo:
    s_load_b64 s[4:5], s[0:1], 0
    s_load_b64 s[6:7], s[0:1], 8
    s_load_b64 s[8:9], s[0:1], 16
    v_mov_b32_e32 v8, v0
    s_nop 7
    v_lshlrev_b32_e32 v9, 2, v8
    v_mul_lo_u32 v10, 48, v8
    s_waitcnt lgkmcnt(0)
    s_nop 7
    global_load_b32 v0, v9, s[4:5]
    global_load_b32 v1, v9, s[6:7]
    s_waitcnt vmcnt(0)

    // Live state outside the authorized fragment register pool.
    v_mov_b32_e32 v15, 0x12345678
    s_mov_b32 s12, 0x2468ace0
    s_mov_b32 vcc_lo, 0x5a5a5a5a
    s_getreg_b32 s13, hwreg(HW_REG_MODE)
    s_cmp_eq_u32 s12, s12

.flydsl.begin arithmetic_0
    .flydsl.function expressions.py:mul_add
    .flydsl.in f32 a = v0
    .flydsl.in f32 b = v1
    .flydsl.out f32 c = v2
    .flydsl.temp vgpr = v[32:35]
.flydsl.end

    // Capture SCC before any subsequent scalar arithmetic changes it.
    s_cselect_b32 s14, 1, 0
    s_getreg_b32 s15, hwreg(HW_REG_MODE)
    v_mov_b32_e32 v11, s12
    v_mov_b32_e32 v12, s14
    v_mov_b32_e32 v13, vcc_lo
    v_mov_b32_e32 v14, exec_lo
    v_mov_b32_e32 v16, s13
    v_mov_b32_e32 v17, s15
    v_mov_b32_e32 v18, 0x76543210
    s_nop 7
    // Record: a, b, c, VGPR guard, SGPR guard, SCC, VCC, EXEC,
    //         MODE before/after, lane ID, final guard.
    global_store_b32 v10, v0, s[8:9] offset:0
    global_store_b32 v10, v1, s[8:9] offset:4
    global_store_b32 v10, v2, s[8:9] offset:8
    global_store_b32 v10, v15, s[8:9] offset:12
    global_store_b32 v10, v11, s[8:9] offset:16
    global_store_b32 v10, v12, s[8:9] offset:20
    global_store_b32 v10, v13, s[8:9] offset:24
    global_store_b32 v10, v14, s[8:9] offset:28
    global_store_b32 v10, v16, s[8:9] offset:32
    global_store_b32 v10, v17, s[8:9] offset:36
    global_store_b32 v10, v8, s[8:9] offset:40
    global_store_b32 v10, v18, s[8:9] offset:44
    s_waitcnt_vscnt null, 0
    s_endpgm
.Lkernel_end:
.size asm_flydsl_demo, .Lkernel_end-asm_flydsl_demo
// End-of-code prefetch padding, outside the function's declared size.
.p2alignl 7, 0xbf9f0000
.fill 96, 4, 0xbf9f0000

.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel asm_flydsl_demo
    .amdhsa_group_segment_fixed_size 0
    .amdhsa_private_segment_fixed_size 0
    .amdhsa_kernarg_size 24
    .amdhsa_user_sgpr_count 2
    .amdhsa_user_sgpr_kernarg_segment_ptr 1
    .amdhsa_wavefront_size32 1
    .amdhsa_uses_dynamic_stack 0
    .amdhsa_enable_private_segment 0
    .amdhsa_system_sgpr_workgroup_id_x 0
    .amdhsa_system_sgpr_workgroup_id_y 0
    .amdhsa_system_sgpr_workgroup_id_z 0
    .amdhsa_system_vgpr_workitem_id 0
    // Covers the explicitly authorized v32-v35 pool and all hand-written code.
    .amdhsa_next_free_vgpr 36
    .amdhsa_next_free_sgpr 16
    .amdhsa_reserve_vcc 1
    .amdhsa_float_round_mode_32 0
    .amdhsa_float_round_mode_16_64 0
    .amdhsa_float_denorm_mode_32 3
    .amdhsa_float_denorm_mode_16_64 3
    .amdhsa_dx10_clamp 0
    .amdhsa_ieee_mode 1
    .amdhsa_workgroup_processor_mode 1
    .amdhsa_memory_ordered 1
    .amdhsa_forward_progress 1
.end_amdhsa_kernel

.amdgpu_metadata
---
amdhsa.version: [1, 2]
amdhsa.target: amdgcn-amd-amdhsa--gfx1100
amdhsa.kernels:
  - .name: asm_flydsl_demo
    .symbol: asm_flydsl_demo.kd
    .kernarg_segment_size: 24
    .kernarg_segment_align: 8
    .group_segment_fixed_size: 0
    .private_segment_fixed_size: 0
    .wavefront_size: 32
    .sgpr_count: 18
    .vgpr_count: 36
    .max_flat_workgroup_size: 32
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
    .args:
      - .name: input_a
        .offset: 0
        .size: 8
        .value_kind: global_buffer
        .address_space: global
      - .name: input_b
        .offset: 8
        .size: 8
        .value_kind: global_buffer
        .address_space: global
      - .name: records
        .offset: 16
        .size: 8
        .value_kind: global_buffer
        .address_space: global
...
.end_amdgpu_metadata
.section .note.GNU-stack,"",@progbits
