// HIP 风格解释性伪代码：逐段对应 step.s，不是可编译/可启动的 HIP kernel。
// ASM Lx-Ly 指当前 step.s 的源文件行号，不是展开后的指令编号。
// step.s SHA256: f6a49ddeb1dd984dfa97597b1ee83218e6c6f521b580cfc0292f5f78691f45d7
// STAGE(name, S) 表示 .flydsl.begin/end 中的 native ASM 被内联到此处；
// 它不是设备函数调用。阶段内部仍有条件、循环、同步和矩阵计算。
// STAGE 的传参由 PREP_STAGE 完成 (ASM L36-L48)：
// v[0:1]=record, v2=bid, v3=tid, v4=layer, v5=hf, v6=pi, v7=epoch。
// end/flags/npass/TRx/segment 是外层调度字段，不是上述函数接口的参数。

using u32 = unsigned int;
using u64 = unsigned long long;
enum Part { ALL = 0, TARGET_ONLY = 1, DRAFT_ONLY = 2 }; // STEP_PART：构建常量
enum Segment { TARGET = 0, DRAFT = 1 };               // s52：运行时状态

struct StageState {
    u64 record;          // s36:s37，原始 72-byte kernarg 区的地址
    u32 bid, tid;        // s38、v40，逻辑 CTA ID / CTA 内线程 ID
    u32 layer, epoch;    // s39、s48
    u32 hf, pi, npass;   // s49、s50、s51
    Segment segment;    // s52
    u32 end, flags, TRx; // s53、s54、s55
};

// 对应 LOAD_LAYER 宏 (ASM L50-L60)，并非额外计算阶段。
u64 load_layer64(StageState& S, u32 slot) {
    u64 fp = scalar_load_u64(S.record + 56);                 // ASM L51-L52
    u64 row = fp + LAYER_TABLE_OFFSET + S.layer * LAYER_ROW_BYTES; // ASM L53-L57
    return scalar_load_u64(row + slot);                     // ASM L58-L59
}

// 用硬件寄存器表达 clustered launch 的逻辑 CTA ID，不能直接假定 blockIdx.x。
u32 logical_cluster_cta_id() {                              // ASM L71-L78
    u32 width = ((ttmp6 >> 12) & 0xf) + 1;                  // ASM L71,L73
    u32 intra = ttmp6 & 0xf;                                // ASM L72
    u32 cluster_field = (IB_STS2 >> 6) & 0xf;                // ASM L74
    u32 clustered_id = ttmp9 * width + intra;                // ASM L75-L76
    return cluster_field == 0 ? ttmp9 : clustered_id;        // ASM L77-L78
}

// template / if constexpr 表达汇编 .if：构建时裁剪，不是 GPU 运行时分支。
// record 是硬件入口携带的 kernarg 地址的伪代码视图，不是新增的 HIP 参数。
template<Part STEP_PART, u32 TARGET_LAYERS, u32 DRAFT_LAYERS,
         u32 TARGET_ROWS, u32 DRAFT_ROWS>
__global__ void mono_step31_pseudocode(u64 record) {
    StageState S;                                          // ASM L62-L69
    S.record = record;                                     // ASM L64
    S.tid = threadIdx.x;                                   // ASM L65，入口 v0 -> v40
    initialize_ccc_stack_state_to_zero();                   // ASM L66-L69
    S.bid = logical_cluster_cta_id();                      // ASM L71-L78
    S.layer = 0;                                           // ASM L79
    S.epoch = 0;                                           // ASM L80
    S.hf = 0;                                              // ASM L81
    S.pi = 0;                                              // ASM L82
    S.segment = TARGET;                                    // ASM L83

    STAGE(epoch_begin, S);                                 // ASM L84-L88
    // epoch_begin 将 epoch 写入当前 CTA 的 scheduler LDS，然后 CTA barrier。
    S.epoch = readfirstlane(load_lds_u32(SCHED_LDS));        // ASM L89-L95
    if constexpr (STEP_PART == DRAFT_ONLY) {                // ASM L96-L102
        if constexpr (DRAFT_LAYERS > 0) goto draft_entry;    // ASM L97-L98
        else goto epoch_end;                               // ASM L99-L100
    }

target_entry:                                              // ASM L104
    S.segment = TARGET;                                    // ASM L105
    S.layer = 0;                                           // ASM L106
    S.end = TARGET_LAYERS;                                  // ASM L107
    S.TRx = TARGET_ROWS;                                    // ASM L108
    STAGE(target_state, S);                                // ASM L109-L113
    STAGE(handoff_target_state, S);                        // ASM L114-L118，全设备 handoff
    if (S.bid < FRONT_CTAS) {                              // ASM L119-L120，反向写成执行条件
        STAGE(target_front, S);                            // ASM L121-L125，入口 attention front
    }
    STAGE(handoff_target_front, S);                        // ASM L127-L131，所有 CTA 参与
    goto layer_check;                                      // ASM L132，跳过 draft_entry

draft_entry:                                               // ASM L134
    S.segment = DRAFT;                                     // ASM L135
    S.layer = TARGET_LAYERS;                                // ASM L136，使用全表的绝对层号
    S.end = TARGET_LAYERS + DRAFT_LAYERS;                    // ASM L137
    S.TRx = DRAFT_ROWS;                                     // ASM L138
    if (S.bid == 0) {                                      // ASM L139-L140
        STAGE(draft_meta, S);                              // ASM L141-L145，CTA 0 内部再分配线程工作
    }
    STAGE(draft_state, S);                                 // ASM L147-L151
    STAGE(handoff_draft_state, S);                         // ASM L152-L156
    if (S.bid < FRONT_CTAS) {                              // ASM L157-L158
        STAGE(draft_front, S);                             // ASM L159-L163
    }
    STAGE(handoff_draft_front, S);                         // ASM L165-L169
    // target/draft entry 都不重置 hf/pi；保持原汇编的持久状态。

layer_check:                                               // ASM L171
    // 等价地用 while 表达入口检查及末尾的回边；层数为 0 时直接进尾部。
    while (S.layer < S.end) {                              // ASM L172-L174,L394-L395
        S.flags = u32(load_layer64(S, LK_lflags));          // ASM L175-L176，只取加载值的低 32 位
        STAGE(layer_stamp_start, S);                       // ASM L177-L181

        if (S.segment == TARGET && (S.flags & (1u << 7))) { // ASM L182-L185
            STAGE(engq, S);                                // ASM L186-L190，下一层 Engram 的 embedding 量化
        }
        STAGE(attention_A, S);                             // ASM L192-L196，含原 A 后的权重预取
        STAGE(handoff_A, S);                               // ASM L197-L201
        if (S.segment == TARGET && (S.flags & (1u << 7))) { // ASM L202-L205
            STAGE(engkv, S);                               // ASM L206-L210，生成 Engram KV
        }
        STAGE(kv_C, S);                                    // ASM L212-L216，KV 和 C 两个原阶段

        if (S.segment == TARGET && (S.flags & (1u << 3))) { // ASM L217-L220
            STAGE(index_prepare, S);                       // ASM L221-L225，IQ/IW；内部按 bit1/2 做 compressor
        }
        STAGE(handoff_KV_C, S);                            // ASM L227-L231，在 indexer 条件之外

        if (S.segment == TARGET && (S.flags & (1u << 3))) { // ASM L232-L235
            STAGE(index_quant, S);                         // ASM L236-L240，量化及可选 crow/cring
            STAGE(handoff_quant, S);                       // ASM L241-L245
            if (load_layer64(S, LK_ibat) != 0) {            // ASM L246-L249，检查完整 64-bit 指针
                STAGE(index_score, S);                     // ASM L250-L254
                STAGE(handoff_score, S);                   // ASM L255-L259
                S.pi = 0;                                 // ASM L260
                S.npass = IDX_LEVELS;                      // ASM L261，当前构建常量为 2
                if (!(S.flags & (1u << 6)) &&              // ASM L262-L263，REINDEX 优先，保持两遍
                     (S.flags & (1u << 5))) {              // ASM L264-L265，非 REINDEX 的 candidate producer
                    S.npass = 2 * IDX_LEVELS;              // ASM L266，即四遍
                }
                do {                                      // ASM L267，首遍无条件进入
                    STAGE(index_select, S);                // ASM L268-L272，内部用 pi 算 mode/level
                    STAGE(handoff_select, S);              // ASM L273-L277，每遍使用独立 counter
                    ++S.pi;                               // ASM L278
                } while (S.pi < S.npass);                  // ASM L279-L280
            }
        }

        STAGE(attention_D, S);                             // ASM L282-L286
        STAGE(handoff_D, S);                               // ASM L287-L291
        STAGE(attention_E, S);                             // ASM L292-L296
        STAGE(handoff_E, S);                               // ASM L297-L301
        STAGE(attention_F, S);                             // ASM L302-L306
        STAGE(tp1, S);                                     // ASM L307-L311，含 TP allreduce 和分组发布

        S.hf = 0;                                         // ASM L313
        do {                                              // ASM L314
            if (S.hf == 0) {                              // ASM L315-L316
                prefetch_instruction_windows_4KiB(7);      // ASM L317-L323，0/4096/.../24576 的 PC-relative 请求
            }
            if (S.bid < FRONT_CTAS) {                      // ASM L325-L326
                STAGE(front_wait, S);                      // ASM L327-L331，hf0 等 TP1，hf1 等 TP2
                STAGE(front, S);                           // ASM L332-L336，hf0 FFN front；hf1 attention front
            }
            if (S.hf == 0) {                              // ASM L338-L339
                // 此处所有 CTA 进入；片段内部才选择 early shared 的空闲 CTA。
                STAGE(shared_early, S);                    // ASM L340-L344
                prefetch_instruction_windows_4KiB(4);      // ASM L345-L348
                STAGE(handoff_front, S);                   // ASM L349-L353，所有 CTA 汇合
                STAGE(moe, S);                             // ASM L354-L358，内部包含 CTA barrier
                STAGE(handoff_moe_done, S);                // ASM L359-L363
                STAGE(moe_combine_tp2, S);                  // ASM L364-L368，combine + TP2 + 分组发布
            }
            ++S.hf;                                       // ASM L370
        } while (S.hf < 2);                                // ASM L371-L372，循环后 hf=2

        STAGE(handoff_layer_end, S);                       // ASM L373-L377
        if (S.segment == TARGET && (S.flags & (1u << 4))) { // ASM L378-L381
            STAGE(tap, S);                                 // ASM L382-L386，保存 draft 需要的 context
        }
        STAGE(layer_stamp_end, S);                         // ASM L388-L392，tap 后没有新增 handoff
        ++S.layer;                                        // ASM L393
        // ASM L394-L395 直接回 .Llayer，不重复入口 .Llayer_check；while 合并两次检查。
    }

segment_tail:                                              // ASM L397
    if (S.segment == DRAFT) goto draft_tail;                // ASM L398-L399
    if constexpr (STEP_PART == TARGET_ONLY || DRAFT_LAYERS > 0) { // ASM L400-L406
        STAGE(target_tail, S);                             // ASM L401-L405，head/sampling/verification
    }
    if constexpr (STEP_PART == ALL && DRAFT_LAYERS > 0) {   // ASM L407-L411
        goto draft_entry;                                  // ASM L408，同一 launch 继续 draft 段
    } else {
        goto epoch_end;                                    // ASM L410
    }

draft_tail:                                                // ASM L412
    if constexpr (DRAFT_LAYERS > 0 && STEP_PART != TARGET_ONLY) { // ASM L413-L419
        STAGE(draft_tail, S);                              // ASM L414-L418
    }

epoch_end:                                                 // ASM L420
    STAGE(epoch_end, S);                                   // ASM L421-L425，每次 launch 恰有一次
    return;                                                // ASM L426，s_endpgm
}

// ASM L427-L430 是函数尺寸/填充；L432-L459 是 descriptor/metadata，非运行时流程。
// 启动约定为 256 CTAs × 256 threads，wave32，cluster=(16,1,1)。
// kernarg=72 bytes (ASM L437)；LDS 由 host 传入 (ASM L435 固定 LDS=0)。
