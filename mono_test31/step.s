// mono_test31: hand-written gfx1250 step.py scheduler, with real FlyDSL fragments.
// Preprocess this file with build.py; llvm-mc does not recognize .flydsl.*.
// Leaf CCC fragments retain their compiler-generated save/restore and scratch.
// Persistent state uses default AMDGPU callee-saved registers:
// s36:s37=kernarg, s38=CTA ID, s39=Ly, s48=epoch, s49=hf,
// s50=pi, s51=pass count, s52=segment(0 target/1 draft), s53=end,
// s54=lflags, s55=TRx, v40=thread ID. s32 is the device stack offset.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.include "constants.inc"
.include "resources.inc"
.text
.protected mono_step31
.globl mono_step31
.type mono_step31,@function
.p2align 8

// The expanded layer can exceed the signed-16-bit branch displacement.
// Long jumps use caller-saved s0:s1 and local rel64 relocations; no device call.
.macro STEP_JMP target
    s_getpc_b64 s[0:1]
    s_add_nc_u64 s[0:1], s[0:1], \target@rel64+4
    s_setpc_b64 s[0:1]
.endm

.macro STEP_CJMP condition, target
    .ifc \condition,scc0
        s_cbranch_scc1 .Lstep_skip\@
    .else
        s_cbranch_scc0 .Lstep_skip\@
    .endif
    STEP_JMP \target
.Lstep_skip\@:
.endm

.macro PREP_STAGE
    s_set_vgpr_msb 0
    v_mov_b32 v0, s36
    v_mov_b32 v1, s37
    v_mov_b32 v2, s38
    v_mov_b32 v3, v40
    v_mov_b32 v4, s39
    v_mov_b32 v5, s49
    v_mov_b32 v6, s50
    v_mov_b32 v7, s48
    s_waitcnt_depctr 0
    s_nop 7
.endm

.macro LOAD_LAYER dst, slot
    s_load_b64 s[0:1], s[36:37], 56
    s_wait_kmcnt 0
    s_mul_i32 s2, s39, LAYER_ROW_BYTES
    s_add_u32 s0, s0, LAYER_TABLE_OFFSET
    s_addc_u32 s1, s1, 0
    s_add_u32 s0, s0, s2
    s_addc_u32 s1, s1, 0
    s_load_b64 \dst, s[0:1], \slot
    s_wait_kmcnt 0
.endm

mono_step31:
    s_set_vgpr_msb 0
    s_mov_b64 s[36:37], s[0:1]
    v_mov_b32 v40, v0
    s_mov_b32 s32, 0
    s_mov_b32 s33, 0
    s_mov_b32 s34, 0
    s_mov_b64 s[30:31], 0
    // Same clustered-dispatch CTA ID decode as the original gfx1250 compiler.
    s_bfe_u32 s2, ttmp6, 0x4000c
    s_and_b32 s3, ttmp6, 15
    s_add_co_i32 s2, s2, 1
    s_getreg_b32 s4, hwreg(HW_REG_IB_STS2, 6, 4)
    s_mul_i32 s2, ttmp9, s2
    s_add_co_i32 s3, s3, s2
    s_cmp_eq_u32 s4, 0
    s_cselect_b32 s38, ttmp9, s3
    s_mov_b32 s39, 0
    s_mov_b32 s48, 0
    s_mov_b32 s49, 0
    s_mov_b32 s50, 0
    s_mov_b32 s52, 0
.flydsl.begin epoch_begin
    .flydsl.function fragments.py:epoch_begin
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    // Epoch output is in an appended, non-overlapping CTA-local LDS slot.
    v_mov_b32 v1, SCHED_LDS
    s_waitcnt_depctr 0
    s_nop 7
    ds_load_b32 v0, v1
    s_wait_dscnt 0
    v_readfirstlane_b32 s48, v0
    .if STEP_PART == 2
        .if DRAFT_LAYERS > 0
            STEP_JMP .Ldraft_entry
        .else
            STEP_JMP .Lepoch_end
        .endif
    .endif

.Ltarget_entry:
    s_mov_b32 s52, 0
    s_mov_b32 s39, 0
    s_mov_b32 s53, TARGET_LAYERS
    s_mov_b32 s55, TARGET_ROWS
.flydsl.begin target_state
    .flydsl.function fragments.py:target_state
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_target_state
    .flydsl.function fragments.py:handoff_target_state
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_ge_u32 s38, FRONT_CTAS
    STEP_CJMP scc1, .Ltarget_entry_join
.flydsl.begin target_front
    .flydsl.function fragments.py:target_front
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Ltarget_entry_join:
.flydsl.begin handoff_target_front
    .flydsl.function fragments.py:handoff_target_front
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    STEP_JMP .Llayer_check

.Ldraft_entry:
    s_mov_b32 s52, 1
    s_mov_b32 s39, TARGET_LAYERS
    s_mov_b32 s53, TARGET_LAYERS + DRAFT_LAYERS
    s_mov_b32 s55, DRAFT_ROWS
    s_cmp_lg_u32 s38, 0
    STEP_CJMP scc1, .Ldraft_block
.flydsl.begin draft_meta
    .flydsl.function fragments.py:draft_meta
    .flydsl.segment draft
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Ldraft_block:
.flydsl.begin draft_state
    .flydsl.function fragments.py:draft_state
    .flydsl.segment draft
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_draft_state
    .flydsl.function fragments.py:handoff_draft_state
    .flydsl.segment draft
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_ge_u32 s38, FRONT_CTAS
    STEP_CJMP scc1, .Ldraft_entry_join
.flydsl.begin draft_front
    .flydsl.function fragments.py:draft_front
    .flydsl.segment draft
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Ldraft_entry_join:
.flydsl.begin handoff_draft_front
    .flydsl.function fragments.py:handoff_draft_front
    .flydsl.segment draft
    .flydsl.abi leaf-ccc-inline
.flydsl.end

.Llayer_check:
    s_cmp_lt_u32 s39, s53
    STEP_CJMP scc0, .Lsegment_tail
.Llayer:
    LOAD_LAYER s[0:1], LK_lflags
    s_mov_b32 s54, s0
.flydsl.begin layer_stamp_start
    .flydsl.function fragments.py:layer_stamp_start
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_lg_u32 s52, 0
    STEP_CJMP scc1, .LA
    s_bitcmp1_b32 s54, 7
    STEP_CJMP scc0, .LA
.flydsl.begin engq
    .flydsl.function fragments.py:engq
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.LA:
.flydsl.begin attention_A
    .flydsl.function fragments.py:attention_A
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_A
    .flydsl.function fragments.py:handoff_A
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_lg_u32 s52, 0
    STEP_CJMP scc1, .Lkv
    s_bitcmp1_b32 s54, 7
    STEP_CJMP scc0, .Lkv
.flydsl.begin engkv
    .flydsl.function fragments.py:engkv
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Lkv:
.flydsl.begin kv_C
    .flydsl.function fragments.py:kv_C
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_lg_u32 s52, 0
    STEP_CJMP scc1, .Lkv_join
    s_bitcmp1_b32 s54, 3
    STEP_CJMP scc0, .Lkv_join
.flydsl.begin index_prepare
    .flydsl.function fragments.py:index_prepare
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Lkv_join:
.flydsl.begin handoff_KV_C
    .flydsl.function fragments.py:handoff_KV_C
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_lg_u32 s52, 0
    STEP_CJMP scc1, .LD
    s_bitcmp1_b32 s54, 3
    STEP_CJMP scc0, .LD
.flydsl.begin index_quant
    .flydsl.function fragments.py:index_quant
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_quant
    .flydsl.function fragments.py:handoff_quant
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    LOAD_LAYER s[2:3], LK_ibat
    s_or_b32 s0, s2, s3
    s_cmp_eq_u32 s0, 0
    STEP_CJMP scc1, .LD
.flydsl.begin index_score
    .flydsl.function fragments.py:index_score
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_score
    .flydsl.function fragments.py:handoff_score
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_mov_b32 s50, 0
    s_mov_b32 s51, IDX_LEVELS
    s_bitcmp1_b32 s54, 6
    STEP_CJMP scc1, .Lselect
    s_bitcmp1_b32 s54, 5
    STEP_CJMP scc0, .Lselect
    s_mov_b32 s51, 2 * IDX_LEVELS
.Lselect:
.flydsl.begin index_select
    .flydsl.function fragments.py:index_select
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_select
    .flydsl.function fragments.py:handoff_select
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_add_u32 s50, s50, 1
    s_cmp_lt_u32 s50, s51
    STEP_CJMP scc1, .Lselect
.LD:
.flydsl.begin attention_D
    .flydsl.function fragments.py:attention_D
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_D
    .flydsl.function fragments.py:handoff_D
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin attention_E
    .flydsl.function fragments.py:attention_E
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_E
    .flydsl.function fragments.py:handoff_E
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin attention_F
    .flydsl.function fragments.py:attention_F
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin tp1
    .flydsl.function fragments.py:tp1
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end

    s_mov_b32 s49, 0
.Lfront:
    s_cmp_lg_u32 s49, 0
    STEP_CJMP scc1, .Lfront_dispatch
    s_prefetch_inst_pc_rel 0, null, 31
    s_prefetch_inst_pc_rel 4096, null, 31
    s_prefetch_inst_pc_rel 8192, null, 31
    s_prefetch_inst_pc_rel 12288, null, 31
    s_prefetch_inst_pc_rel 16384, null, 31
    s_prefetch_inst_pc_rel 20480, null, 31
    s_prefetch_inst_pc_rel 24576, null, 31
.Lfront_dispatch:
    s_cmp_ge_u32 s38, FRONT_CTAS
    STEP_CJMP scc1, .Lfront_idle
.flydsl.begin front_wait
    .flydsl.function fragments.py:front_wait
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin front
    .flydsl.function fragments.py:front
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Lfront_idle:
    s_cmp_lg_u32 s49, 0
    STEP_CJMP scc1, .Lfront_next
.flydsl.begin shared_early
    .flydsl.function fragments.py:shared_early
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_prefetch_inst_pc_rel 0, null, 31
    s_prefetch_inst_pc_rel 4096, null, 31
    s_prefetch_inst_pc_rel 8192, null, 31
    s_prefetch_inst_pc_rel 12288, null, 31
.flydsl.begin handoff_front
    .flydsl.function fragments.py:handoff_front
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin moe
    .flydsl.function fragments.py:moe
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin handoff_moe_done
    .flydsl.function fragments.py:handoff_moe_done
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.flydsl.begin moe_combine_tp2
    .flydsl.function fragments.py:moe_combine_tp2
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Lfront_next:
    s_add_u32 s49, s49, 1
    s_cmp_lt_u32 s49, 2
    STEP_CJMP scc1, .Lfront
.flydsl.begin handoff_layer_end
    .flydsl.function fragments.py:handoff_layer_end
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_cmp_lg_u32 s52, 0
    STEP_CJMP scc1, .Llayer_next
    s_bitcmp1_b32 s54, 4
    STEP_CJMP scc0, .Llayer_next
.flydsl.begin tap
    .flydsl.function fragments.py:tap
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
.Llayer_next:
.flydsl.begin layer_stamp_end
    .flydsl.function fragments.py:layer_stamp_end
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_add_u32 s39, s39, 1
    s_cmp_lt_u32 s39, s53
    STEP_CJMP scc1, .Llayer

.Lsegment_tail:
    s_cmp_lg_u32 s52, 0
    STEP_CJMP scc1, .Ldraft_tail
    .if STEP_PART == 1 || DRAFT_LAYERS > 0
.flydsl.begin target_tail
    .flydsl.function fragments.py:target_tail
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    .endif
    .if STEP_PART == 0 && DRAFT_LAYERS > 0
        STEP_JMP .Ldraft_entry
    .else
        STEP_JMP .Lepoch_end
    .endif
.Ldraft_tail:
    .if DRAFT_LAYERS > 0 && STEP_PART != 1
.flydsl.begin draft_tail
    .flydsl.function fragments.py:draft_tail
    .flydsl.segment draft
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    .endif
.Lepoch_end:
.flydsl.begin epoch_end
    .flydsl.function fragments.py:epoch_end
    .flydsl.segment target
    .flydsl.abi leaf-ccc-inline
.flydsl.end
    s_endpgm
.Lstep_end:
.size mono_step31, .Lstep_end-mono_step31
.p2alignl 7, 0xbf9f0000
.fill 96, 4, 0xbf9f0000

.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel mono_step31
    .amdhsa_group_segment_fixed_size 0
    .amdhsa_private_segment_fixed_size STEP_PRIVATE
    .amdhsa_kernarg_size 72
    .amdhsa_user_sgpr_count 2
    .amdhsa_user_sgpr_kernarg_segment_ptr 1
    .amdhsa_user_sgpr_kernarg_preload_length 0
    .amdhsa_user_sgpr_kernarg_preload_offset 0
    .amdhsa_wavefront_size32 1
    .amdhsa_enable_private_segment STEP_SCRATCH
    .amdhsa_uses_dynamic_stack 0
    .amdhsa_system_sgpr_workgroup_id_x 1
    .amdhsa_system_vgpr_workitem_id 0
    .amdhsa_next_free_vgpr STEP_VGPR
    .amdhsa_next_free_sgpr STEP_SGPR
    .amdhsa_reserve_vcc STEP_VCC
    .amdhsa_named_barrier_count STEP_NAMED_BARRIERS
    .amdhsa_float_round_mode_32 0
    .amdhsa_float_round_mode_16_64 0
    .amdhsa_float_denorm_mode_32 3
    .amdhsa_float_denorm_mode_16_64 3
    .amdhsa_memory_ordered 1
    .amdhsa_forward_progress 1
.end_amdhsa_kernel
.include "metadata.inc"
.section .note.GNU-stack,"",@progbits
