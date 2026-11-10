// Hand-written gfx1250 Mono scheduler. This is the launched GPU entry.
// 15 original test10 uint64 arguments occupy 120 kernarg bytes.
// Standard device C ABI: v0:v1=record, v2=task, v3=bid, v4=tid.
// Persistent caller state: s36:s37=record, s38=bid, s39=task, v40=tid.
// All are default callee-saved. s30:s31=return PC, s32=SP, s33=FP, s34=BP.
// build_asm_mono.py supplies resources/metadata from actual stage assembly.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.include "mono_resources.inc"
.text
.protected mono_asm_projection
.globl mono_asm_projection
.type mono_asm_projection,@function
.hidden mono_stage_slice
.hidden mono_stage_norm
.hidden mono_stage_wqkv
.p2align 8

.macro CALL_STAGE target
    v_mov_b32_e32 v0, s36
    v_mov_b32_e32 v1, s37
    v_mov_b32_e32 v2, s39
    v_mov_b32_e32 v3, s38
    v_mov_b32_e32 v4, v40
    s_getpc_b64 s[0:1]
    s_add_nc_u64 s[0:1], s[0:1], \target@rel64+4
    s_swappc_b64 s[30:31], s[0:1]
.endm

mono_asm_projection:
    s_mov_b64 s[36:37], s[0:1]
    v_mov_b32_e32 v40, v0
    // gfx1250 workgroup-id.x lowering, including clustered-dispatch encoding.
    // With an ordinary launch IB_STS2's cluster field is zero and bid=ttmp9.
    s_bfe_u32 s2, ttmp6, 0x4000c
    s_and_b32 s3, ttmp6, 15
    s_add_co_i32 s2, s2, 1
    s_getreg_b32 s4, hwreg(HW_REG_IB_STS2, 6, 4)
    s_mul_i32 s2, ttmp9, s2
    s_add_co_i32 s3, s3, s2
    s_cmp_eq_u32 s4, 0
    s_cselect_b32 s38, ttmp9, s3
    // gfx1250 has architected scratch backing; standard device functions use
    // s32 as the stack offset. The root owns no private frame.
    s_mov_b32 s32, 0
    s_mov_b32 s33, 0
    s_mov_b32 s34, 0

    // C1ReferencePlan: slice base=0,count=160, one task per owning CTA.
    s_mov_b32 s39, s38
    s_cmp_ge_u32 s39, 160
    s_cbranch_scc1 .Lnorm
    CALL_STAGE mono_stage_slice
.Lnorm:
    // norm base=168,count=1.
    s_cmp_lg_u32 s38, 168
    s_cbranch_scc1 .Lwqkv
    s_mov_b32 s39, 0
    CALL_STAGE mono_stage_norm
.Lwqkv:
    // wqkv base=176,count=112; wrap around the 256-CTA ring.
    s_sub_u32 s39, s38, 176
    s_and_b32 s39, s39, 255
    s_cmp_ge_u32 s39, 112
    s_cbranch_scc1 .Ldone
    CALL_STAGE mono_stage_wqkv
.Ldone:
    s_endpgm
.Lmono_end:
.size mono_asm_projection, .Lmono_end-mono_asm_projection

.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel mono_asm_projection
    .amdhsa_group_segment_fixed_size 14848
    .amdhsa_private_segment_fixed_size MONO_PRIVATE
    .amdhsa_kernarg_size 120
    .amdhsa_user_sgpr_count 2
    .amdhsa_user_sgpr_kernarg_segment_ptr 1
    .amdhsa_user_sgpr_kernarg_preload_length 0
    .amdhsa_user_sgpr_kernarg_preload_offset 0
    .amdhsa_wavefront_size32 1
    .amdhsa_uses_dynamic_stack 0
    .amdhsa_enable_private_segment MONO_SCRATCH_ENABLE
    .amdhsa_system_sgpr_workgroup_id_x 1
    .amdhsa_system_sgpr_workgroup_id_y 0
    .amdhsa_system_sgpr_workgroup_id_z 0
    .amdhsa_system_vgpr_workitem_id 0
    .amdhsa_next_free_vgpr MONO_VGPR
    .amdhsa_next_free_sgpr MONO_SGPR
    .amdhsa_reserve_vcc MONO_VCC
    .amdhsa_named_barrier_count 0
    .amdhsa_float_round_mode_32 0
    .amdhsa_float_round_mode_16_64 0
    .amdhsa_float_denorm_mode_32 3
    .amdhsa_float_denorm_mode_16_64 3
    .amdhsa_memory_ordered 1
    .amdhsa_forward_progress 1
.end_amdhsa_kernel
.include "mono_metadata.inc"
.section .note.GNU-stack,"",@progbits
