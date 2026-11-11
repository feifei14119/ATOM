// gfx1250 DeepSeek-V4.1-Flash：用 ASM 编写 step.py 的调度主体。
// 参照 step.build(TR, rank, NL=40, ndr=3, trd=5*B, part=...)。
// 真实 ASM：入口、显式参数加载、CTA ID、表寻址、条件分支、循环。
// 伪代码：PSEUDO_FLYDSL ...，包括原来的计算阶段和同步 helper。
// 本文件还不是能够推理的网络 kernel；只能生成带 trap 的语法检查 .co。
//
// 寄存器地图（为了阅读而选定的自定义调度约定，不是标准 device ABI）：
// s32:s33 kernarg; s34:s35 fp; s36:s37 tp; s38:s39 cnt;
// s40 全局 CTA ID; s41 epoch; s42 Ly; s43 segment(0 target/1 draft);
// s44 segment end; s45 当前 TR; s46 hf(0 FFN front/1 attention front);
// s47 lflags; s48:s49 当前 layer row; s50:s51 当前 layer counter base;
// s52:s53 tail counter base; s54 selection pass; s55 selection pass count;
// s56 receive parity byte offset; s57 softmax scale 的 f32 bits;
// s58:s59 timestamp buffer; v63 一维 threadIdx.x。
// s0:s31 / v0:v62 为本示例临时寄存器，SCC 每次调用后重新生成。
// 所有 PSEUDO_FLYDSL adapter 将来都要保存上述跨调用的调度值，或改此约定。
// 现在的代码没有“LLVM 已经自动实现寄存器保存”的假设。

.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.include "step_constants.inc"
.include "pseudo_calls.inc"
.text
.protected mono_step_asm_example
.globl mono_step_asm_example
.type mono_step_asm_example,@function
.p2align 8

mono_step_asm_example:
    // descriptor 只启用 kernarg_segment_ptr，关闭 kernarg preload：
    // s0:s1 是 kernarg 地址；一维 workitem ID 从 v0 取得。
    s_mov_b64 s[32:33], s[0:1]
    v_mov_b32 v63, v0
    s_load_b64 s[34:35], s[32:33], 56
    s_load_b64 s[36:37], s[32:33], 64
    s_load_b64 s[38:39], s[32:33], 32
    s_load_b64 s[58:59], s[32:33], 40
    s_load_b32 s57, s[32:33], 48
    s_wait_kmcnt 0

    // gfx1250 clustered dispatch 的 block_idx.x 解码。
    // cluster ID 在 ttmp9，ttmp6 包含 cluster 内位置/宽度；
    // 必须复现编译器的 clustered block ID，而不能总令 bid=ttmp9。
    // 此序列与本仓库 mono_test20 的 gfx1250 入口一致。
    s_bfe_u32 s2, ttmp6, 0x4000c
    s_and_b32 s3, ttmp6, 15
    s_add_co_i32 s2, s2, 1
    s_getreg_b32 s4, hwreg(HW_REG_IB_STS2, 6, 4)
    s_mul_i32 s2, ttmp9, s2
    s_add_co_i32 s3, s3, s2
    s_cmp_eq_u32 s4, 0
    s_cselect_b32 s40, ttmp9, s3

    s_add_u32 s52, s38, (TARGET_LAYERS + DRAFT_LAYERS) * LY_LAYER_BYTES
    s_addc_u32 s53, s39, 0

    // step.tp_epoch_begin：
    //   从 fp[tpep] 读取 epoch；
    //   各 CTA 合作清零本 rank receive buffer 的“另一半”，wait stores；
    //   recv[i] 的有效地址是 kernarg.recv[i] + (epoch&1)*RECV_HALF。
    // 返回 s0=epoch。只加载一个 scalar ep 不能替代另一半清零的工作。
    // helper 还以 fp[cyc] 绑定 timeout 报告的位置。
    PSEUDO_FLYDSL tp_epoch_begin
    s_mov_b32 s41, s0
    s_and_b32 s56, s41, 1
    s_mul_i32 s56, s56, RECV_HALF

    .if STEP_PART == 2
        // split draft 的前置条件：同 stream 的 target 已做 tail/CTX/verify。
        s_branch .Ldraft_entry
    .endif

.Ltarget_entry:
    s_mov_b32 s43, 0
    s_mov_b32 s42, 0
    s_mov_b32 s44, TARGET_LAYERS
    s_mov_b32 s45, TARGET_ROWS
    // CX.stage_block_state(W=1, requests=TR)：
    // tids -> embedding -> dR 的四路副本；dy=0，pre=(1,0,0,0)，post=0，comb=I。
    PSEUDO_FLYDSL target_block_state
    TAIL_HANDOFF LY_TARGET_STATE
    s_cmp_ge_u32 s40, FRONT_CTAS
    s_cbranch_scc1 .Ltarget_entry_join
    s_mov_b32 s8, LY_TARGET_ENTRY_ROW
    // entry_front(row=44)：读该行 a* 权重；输出 x8/xs、attention gates；
    // 当前 residual 留在 LDS RKEEP，而不是每次 stage 全部写回显存。
    PSEUDO_FLYDSL entry_front_target
.Ltarget_entry_join:
    TAIL_HANDOFF LY_TARGET_FRONT
    s_branch .Llayer

.Ldraft_entry:
    s_mov_b32 s43, 1
    s_mov_b32 s42, TARGET_LAYERS
    s_mov_b32 s44, TARGET_LAYERS + DRAFT_LAYERS
    s_mov_b32 s45, DRAFT_ROWS
    s_cmp_lg_u32 s40, 0
    s_cbranch_scc1 .Ldraft_block
    // 仅 CTA0：verdict + dgeom -> kmeta_d / kvw_d / rpos_d。
    PSEUDO_FLYDSL draft_meta
.Ldraft_block:
    // anc embedding / noise -> draft block state；每请求 DSPARK_W=5 行。
    PSEUDO_FLYDSL draft_block_state
    TAIL_HANDOFF LY_DRAFT_STATE
    s_cmp_ge_u32 s40, FRONT_CTAS
    s_cbranch_scc1 .Ldraft_entry_join
    s_mov_b32 s8, TARGET_LAYERS + DRAFT_LAYERS
    // entry_front(row=43)，router shape=128 experts/top3。
    PSEUDO_FLYDSL entry_front_draft
.Ldraft_entry_join:
    TAIL_HANDOFF LY_DRAFT_FRONT

// ---------------------------------------------------------------- target / draft 的共有 layer 调度
.Llayer:
    // row = fp + 8*(len(FPTRS)+len(ATAB)) + Ly*8*len(LKEYS)。
    // c 并不是要从 host 逐 stage 构造的对象；它是这些表值、索引、LDS
    // 地址的视图。adapter 可用下面 LOAD_* 宏按需读取。
    s_mul_i32 s2, s42, LAYER_ROW_BYTES
    s_add_u32 s48, s34, LAYER_TABLE_OFFSET
    s_addc_u32 s49, s35, 0
    s_add_u32 s48, s48, s2
    s_addc_u32 s49, s49, 0
    s_lshl_b32 s2, s42, 8
    s_add_u32 s50, s38, s2
    s_addc_u32 s51, s39, 0
    LOAD_LAYER s[0:1], lflags
    s_mov_b32 s47, s0

    // 原代码的 lflags bit7 表示“下一层有 Engram”：
    // L0/L13 预备 L1/L14 的 Engram；gate 在下面 hf=1 的 front 使用。
    s_cmp_lg_u32 s43, 0
    s_cbranch_scc1 .Lstage_A
    s_bitcmp1_b32 s47, 7
    s_cbranch_scc0 .Lstage_A
    PSEUDO_FLYDSL engram_stage_engq
.Lstage_A:
    // 演示确切的按需参数加载：WQKV 权重来自本层，x8/xs 来自 ATAB。
    // 其余 c 值（qnw、kvnw、qkv/ss 等）由该设备 adapter 同样按需读取。
    LOAD_LAYER s[0:1], wqkv
    LOAD_LAYER s[2:3], wqkv_s
    LOAD_AT s[4:5], x8
    LOAD_AT s[6:7], xs
    // PSEUDO CALL attention.stage_A(c)，TRx=s45，scale=s57。
    // target/draft 是不同 shape；未来 adapter 按 s43 选择相应实现。
    PSEUDO_FLYDSL attention_stage_A
    PSEUDO_FLYDSL prefetch_wqb_rows
    HANDOFF LY_ATTN_A

    s_cmp_lg_u32 s43, 0
    s_cbranch_scc1 .Lkv_C
    s_bitcmp1_b32 s47, 7
    s_cbranch_scc0 .Lkv_C
    PSEUDO_FLYDSL engram_stage_engkv
.Lkv_C:
    // c.rpos/kmeta/kvw：target 使用原表，draft 使用 *_d。
    // c.ksel/knsel 必须使用本层 LKEYS，才能保留 selection-owner 共享关系。
    PSEUDO_FLYDSL attention_stage_kv
    PSEUDO_FLYDSL attention_stage_C
    s_cmp_lg_u32 s43, 0
    s_cbranch_scc1 .Lkv_C_join
    s_bitcmp1_b32 s47, 3
    s_cbranch_scc0 .Lkv_C_join
    PSEUDO_FLYDSL index_stage_iq
    PSEUDO_FLYDSL index_stage_iw
    s_bitcmp1_b32 s47, 1
    s_cbranch_scc0 .Lkv_C_join
    // bit2 区分 ratio1；此信息保留在 s47，adapter 读取。
    PSEUDO_FLYDSL compressor_stage_cgemm
.Lkv_C_join:
    HANDOFF LY_KV_C
    s_cmp_lg_u32 s43, 0
    s_cbranch_scc1 .Lstage_D
    s_bitcmp1_b32 s47, 3
    s_cbranch_scc0 .Lstage_D
    PSEUDO_FLYDSL index_stage_iquant
    s_bitcmp1_b32 s47, 1
    s_cbranch_scc0 .Liquant_join
    PSEUDO_FLYDSL compressor_stage_crow
    PSEUDO_FLYDSL compressor_stage_cring
.Liquant_join:
    HANDOFF LY_INDEX_QUANT
    // 某些 bring-up 表没有 scorer 输入；判断的是 64-bit ibat 指针。
    LOAD_LAYER s[0:1], ibat
    s_or_b32 s2, s0, s1
    s_cmp_eq_u32 s2, 0
    s_cbranch_scc1 .Lstage_D
    PSEUDO_FLYDSL index_stage_score_any
    HANDOFF LY_SCORE
    s_mov_b32 s54, 0
    s_mov_b32 s55, IDX_LEVELS
    s_bitcmp1_b32 s47, 6
    s_cbranch_scc1 .Lselect
    s_bitcmp1_b32 s47, 5
    s_cbranch_scc0 .Lselect
    s_mov_b32 s55, 2 * IDX_LEVELS
.Lselect:
    // s8=plev; s9=模式（示例约定：0 SEL / 1 BLK / 2 RX，adapter 映射 TK 常量）。
    s_and_b32 s8, s54, 1
    s_mov_b32 s9, 2
    s_bitcmp1_b32 s47, 6
    s_cbranch_scc1 .Lselect_call
    s_cmp_lt_u32 s54, IDX_LEVELS
    s_cselect_b32 s9, 0, 1
.Lselect_call:
    PSEUDO_FLYDSL topk_stage_select_any
    // 每个 pass 有独立 counter，不能反复等待同一个已完成的 counter。
    s_lshl_b32 s2, s54, 2
    s_add_u32 s2, s2, LY_SELECT0
    s_add_u32 s0, s50, s2
    s_addc_u32 s1, s51, 0
    s_mov_b32 s8, 1
    PSEUDO_FLYDSL device_handoff_256
    s_add_u32 s54, s54, 1
    s_cmp_lt_u32 s54, s55
    s_cbranch_scc1 .Lselect

.Lstage_D:
    PSEUDO_FLYDSL attention_stage_D
    PSEUDO_FLYDSL prefetch_woa_rows
    HANDOFF LY_ATTN_D
    PSEUDO_FLYDSL attention_stage_E
    PSEUDO_FLYDSL prefetch_wob_rows
    HANDOFF LY_ATTN_E
    // stage_F_cluster 内保留原 cluster 协作；不是把 256 CTA 全当独立块。
    PSEUDO_FLYDSL attention_stage_F_cluster
    PSEUDO_FLYDSL cta_barrier
    // TP1：region=(Ly&1)*2，tag=2*Ly+1，输出 fp[y1]。
    s_and_b32 s8, s42, 1
    s_lshl_b32 s8, s8, 1
    s_lshl_b32 s9, s42, 1
    s_add_u32 s9, s9, 1
    LOAD_FP s[0:1], y1
    PSEUDO_FLYDSL attention_tp_allreduce_1
    LAYER_COUNTER LY_TP1_GROUPS
    PSEUDO_FLYDSL step_gpub

// ---------------------------------------------------------------- 两遍 front，只保留一份调度代码
    s_mov_b32 s46, 0
.Lfront_loop:
    // 只有前 96 CTA 运行 front；所有选择都是 CTA-uniform。
    // 当前层 attention front 已在上一层 hf=1（或 entry_front）完成。
    // hf=0 执行“本层 FFN front”；hf=1 执行“下一层 attention front”。
    s_cmp_ge_u32 s40, FRONT_CTAS
    s_cbranch_scc1 .Lfront_idle
    // 两个偏移 128/192 都需要 literal，不能塞入同一条 s_cselect。
    s_mov_b32 s2, LY_TP1_GROUPS
    s_mov_b32 s3, LY_TP2_GROUPS
    s_cmp_eq_u32 s46, 0
    s_cselect_b32 s2, s2, s3
    s_add_u32 s0, s50, s2
    s_addc_u32 s1, s51, 0
    // gwait 等待本列组的 16 个 TP CTA，不是等待全设备。
    PSEUDO_FLYDSL step_gwait
    // 必须按 hf 切换：
    // hf=0: y1 / f* / nw / fx8 / fxs，merge=1、isffn=1、xs32=0。
    // hf=1: y2 / a* / anw / x8 / xs，merge=0、isffn=0、xs32=1。
    // ltab[Ly].a* 是 host 填入的下一层权重；勿再额外把 Ly+1 取两次。
    // hf=1 且是 segment 尾：xn 写 xh(target) 或 tp[dh](draft)。
    // rk=LDS+RKEEP；sm=LDS+FRONT_LDS。不可覆盖 LDS0 的 TP payload。
    // first=false（entry 已准备 residual）。
    // last=(hf==1 && (Ly==39 || 36<=Ly<=38))，与 step.py 一致。
    // target 且 hf=1 且 bit7 时融合 Engram gate。
    // callback x8pub：宽批次 FFN front 的 stage_C 后发布 LY_X8_PUB。
    PSEUDO_FLYDSL front_any_with_x8pub
.Lfront_idle:
    s_cmp_lg_u32 s46, 0
    s_cbranch_scc1 .Lfront_next
    // 原 sh_early：ceil(TRx/16)>=3。窄批次不执行此分支。
    s_cmp_le_u32 s45, 32
    s_cbranch_scc1 .Lmoe
    s_cmp_lt_u32 s40, FRONT_CTAS
    s_cbranch_scc1 .Lmoe
    s_add_u32 s2, s45, 15
    s_lshr_b32 s2, s2, 4
    s_mul_i32 s2, s2, 18 * 2
    s_add_u32 s2, s2, FRONT_CTAS
    s_cmp_ge_u32 s40, s2
    s_cbranch_scc1 .Lmoe
    // front 的空闲 CTA：等 X8_PUB 达到96，CTA barrier，然后 shared UG。
    LAYER_COUNTER LY_X8_PUB
    PSEUDO_FLYDSL wait_x8_and_ug_shared_early
.Lmoe:
    HANDOFF LY_FRONT
    LAYER_COUNTER LY_MOE_UG
    // adapter 还取 lc+SHARED_DOWN；内部 UG→down handoff 不能删除。
    // target: TR*6 picks / 384 experts；draft: TRD*3 / 128。
    PSEUDO_FLYDSL moe_union_ug_down
    PSEUDO_FLYDSL cta_barrier
    HANDOFF LY_MOE_DONE
    PSEUDO_FLYDSL moe_combine_into_lds_payload
    // TP2：region=(Ly&1)*2+1，tag=2*Ly+2，输出 fp[y2]。
    s_and_b32 s8, s42, 1
    s_lshl_b32 s8, s8, 1
    s_add_u32 s8, s8, 1
    s_lshl_b32 s9, s42, 1
    s_add_u32 s9, s9, 2
    LOAD_FP s[0:1], y2
    PSEUDO_FLYDSL attention_tp_allreduce_2
    LAYER_COUNTER LY_TP2_GROUPS
    PSEUDO_FLYDSL step_gpub
.Lfront_next:
    s_add_u32 s46, s46, 1
    s_cmp_lt_u32 s46, 2
    s_cbranch_scc1 .Lfront_loop
    HANDOFF LY_LAYER_END

    s_cmp_lg_u32 s43, 0
    s_cbranch_scc1 .Llayer_next
    s_bitcmp1_b32 s47, 4
    s_cbranch_scc0 .Llayer_next
    s_sub_u32 s8, s42, TARGET_LAYERS - 4
    // Ly=36/37/38 的末尾刚做完下一层 attention front，
    // 所以这里导出的正是 Layer37/38/39 输入的 residual taps。
    // 应在下一轮 front 改写 aRout 前读出。
    PSEUDO_FLYDSL draft_ctx_stage_tap1
.Llayer_next:
    s_add_u32 s42, s42, 1
    s_cmp_lt_u32 s42, s44
    s_cbranch_scc1 .Llayer

// ---------------------------------------------------------------- segment tail
    s_cmp_lg_u32 s43, 0
    s_cbranch_scc1 .Ldraft_tail
    // tail.target 整体留为伪调用。内部必须包含：
    // HEAD handoff → vocab head → HEAD_DONE → 4-rank sample/verify
    // → VERIFY_DONE。CTX 的 main_proj/KV/ring 部分交错在 sampling exchanges。
    // 不能在 host 重新单独 launch CTX 而声称仍保持原来的调度。
    PSEUDO_FLYDSL tail_target_with_context
    .if STEP_PART == 1
        s_branch .Lepoch_end
    .else
        s_branch .Ldraft_entry
    .endif
.Ldraft_tail:
    // draft head → DRAFT_HEAD_DONE → 4-rank Markov → mids/qlog/qids。
    PSEUDO_FLYDSL tail_draft_markov
.Lepoch_end:
    // 仅 CTA0/thread0 写 fp[tpep]=epoch+1；发生在最后 handoff 后。
    // split 模式中 target 和 draft 各有一次 epoch_begin/end，不能偷偷合并。
    s_mov_b32 s8, s41
    PSEUDO_FLYDSL tp_epoch_end
    s_endpgm
.Lend:
.size mono_step_asm_example, .Lend-mono_step_asm_example

// 语法检查对象的 descriptor；真实集成要汇总所有 stage 的资源再重建。
// 固定 LDS=0，host shared_mem 传全量动态 LDS。
// 因为所有伪调用是 trap，以下 64 VGPR / 60 SGPR / 0 private 只描述这个壳。
.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel mono_step_asm_example
    .amdhsa_group_segment_fixed_size 0
    .amdhsa_private_segment_fixed_size 0
    .amdhsa_kernarg_size 72
    .amdhsa_user_sgpr_count 2
    .amdhsa_user_sgpr_kernarg_segment_ptr 1
    .amdhsa_user_sgpr_kernarg_preload_length 0
    .amdhsa_user_sgpr_kernarg_preload_offset 0
    .amdhsa_wavefront_size32 1
    .amdhsa_enable_private_segment 0
    .amdhsa_uses_dynamic_stack 0
    .amdhsa_system_sgpr_workgroup_id_x 1
    .amdhsa_system_sgpr_workgroup_id_y 0
    .amdhsa_system_sgpr_workgroup_id_z 0
    .amdhsa_system_vgpr_workitem_id 0
    .amdhsa_next_free_vgpr 64
    .amdhsa_next_free_sgpr 60
    .amdhsa_reserve_vcc 0
    .amdhsa_named_barrier_count 0
    .amdhsa_float_round_mode_32 0
    .amdhsa_float_round_mode_16_64 0
    .amdhsa_float_denorm_mode_32 3
    .amdhsa_float_denorm_mode_16_64 3
    .amdhsa_memory_ordered 1
    .amdhsa_forward_progress 1
.end_amdhsa_kernel
.include "step_metadata.inc"
.section .note.GNU-stack,"",@progbits
