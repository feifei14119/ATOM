# ATOM PR #2908：Mono kernel 集成算子清单

本文按实际 runner → build → device stage 调用链，列出 PR #2908 中 Mono kernel 集成的计算、量化、数据整理和通信操作，并标出不同执行路径的实现入口。

- PR：[ROCm/ATOM #2908](https://github.com/ROCm/ATOM/pull/2908)，标题为 `feat(dsv41): add gfx1250 mono backend, enabled by default for 1/2/8-request decode`。
- 阅读日期：2026-11-09。
- 源码版本：PR head **`7c925f72b22ee6a815fd6d63734bbcff5fa72a08`**。下文源码链接全部固定到这一 commit；PR 后续更新可能改变清单。
- PR 的新增后端目录为 `atom/models/deepseek_v41/mono/gfx1250/`，它复用 `atom/models/deepseek_v41/mono/kernels/` 和 `atom/mono/` 中的部分代码。
- 本地工作树当前 commit 为 `1d37f866`，没有上述 `gfx1250` 目录。因此本次直接读取 PR 源码快照，不能把本地通用 Mono 的文件名和行号当成 PR 新后端的实现入口。

这里的“算子”按计算语义拆分。**一行不代表一个单独 launch 的 kernel，也不代表一个独立 `.co`。** 多个算子常常在同一个 `stage_*` 中完成；同一算子也可能分为多个生产者和消费者任务。下面的函数是源码层组合进 K1/K2 的设备代码。

## 1. 实际启用范围与 kernel 入口

默认部署约束是 **gfx1250、TP=4、BF16 KV cache、FP8 index cache、固定 5 个 draft token 的 DSpark**。target 验证阶段每个请求有 6 行，draft 每个请求有 5 行。入口只将 1、2、8 请求对应的宽度路由到 Mono；其他宽度仍走原模型路径。依据：[配置][config]、[target dispatch][dispatch.MonoDecodeModel.forward]、[draft dispatch][dispatch.MonoDraftModel.block_backbone]。

| 路径 | 逻辑行数 | K1 实际 builder | K2 实际 builder | 索引器 |
| --- | --- | --- | --- | --- |
| target，1/2 请求 | 6 / 12 | [dspark_dynamic_k1.py::build_dspark_k1][dynamic_k1.build_dspark_k1] | [dspark_dynamic_index_down.py::build_dspark_down][dynamic_k2.build_dspark_down] | 依据 layer 类型启用 |
| target，8 请求 | 48 | [dspark_wide_accum_k1.py::build_dspark_k1][wide_k1.build_dspark_k1] | [dspark_mhtjstest_native_k2.py::build_dspark_down][wide_k2.build_dspark_down] | 依据 layer 类型启用 |
| draft，1/2 请求 | 5 / 10 | [dspark_k1.py::build_dspark_k1][draft_k1.build_dspark_k1] | [dspark_index_down.py::build_dspark_down][draft_k2.build_dspark_down] | 关闭 |
| draft，8 请求 | 40，内部补到 48 | 与 target 48 行相同的 builder | 与 target 48 行相同的 builder | 关闭 |

构建分流见 [target `_rows_build`][runner.V41MonoDecodeRunner._rows_build] 和 [draft `_rows_build`][draft_runner.DraftMonoRunner._rows_build]。40 行 draft 将第 39 行复制到补齐行，计算完成后截取真实结果，见 [draft `backbone`][draft_runner.DraftMonoRunner.backbone]。

每层主要有 **K1、K2 两个融合 launch**。K2 内包含通常称为 K2a 的注意力后处理部分和 K2b 的 MoE 部分。此 gfx1250 配置拒绝 `ATOM_MONO_CHECK/DEBUG/TIMELINE`；代码中保留的 split-K2 分支不属于默认可用路径。不要把 K2a/K2b 理解成 K2 在 GPU 上再次 launch 的两个 kernel。

这些入口使用 256 个 CTA、每 CTA 256 个物理线程，物理 wave 为 wave32。部分 stage 用逻辑 wave64 的编号与归约顺序，不能据此把整个后端视为 wave64。

## 2. 一层计算的总体关系

```text
上一层的 residual、pending MoE output、mHC gates
    │
    ▼
K1：mHC residual/collapse/mix → attention RMSNorm/量化
    → WQKV_A → Q/KV norm、KV RoPE/QAT/cache write
    → WQ_B + query RoPE
    → [按 layer 类型] index query projection / head weight / FP8 quant
    同时生成 attention 子层所需的 mHC gates
    │
    ├── kernel 外：compressor、index key 写入（有需要的层）
    ▼
K2： [按 layer 类型] index score → token Top-K / candidate-block Top-K
    → sparse/window attention：QK、softmax、PV、split merge、sink
    → inverse RoPE + FP8 quant → WO_A → quant → WO_B
    → TP attention all-reduce → FFN mHC residual/collapse/mix/norm
    → router / expert Top-K / shared expert / routed expert / combine
    → TP MoE all-reduce
    同时生成 FFN 子层所需的 mHC gates
    │
    ▼
下一层 K1 消化 pending MoE output，或 kernel 外最终 collapse
```

这是**数据依赖图**。CTA 的阶段次序、预取和任务分配允许重叠；不能把每个箭头理解成全 grid 同步。阶段间通过 global mailbox、LDS、ready flag 和 peer buffer 交接。

## 3. K1：attention 前处理的全部算子

表中以 target 6/12 行实现为主要入口；48 行和 draft 的差异在第 6 节列出。

| 编号 | 算子 / 子操作 | 输入、输出与含义 | 实现入口 |
| --- | --- | --- | --- |
| K1-01 | 延迟 mHC post + residual combination | `pending` 子层输出乘 `post_in`，旧的 4 路 residual 按 `comb_in` 混合，得到 BF16 `res_out`；仅 `fold=True` 执行 | [slice_loads / slice_row][common_pre.slice_row]，由 [stage_tile][dynamic_mhc.stage_tile] 使用 |
| K1-02 | mHC pre collapse | 4 路 residual 按 `pre_in` 加权，得到 hidden=5120 的子层输入 `LIN` | [stage_tile][dynamic_mhc.stage_tile]；draft 为 [stage_slice][draft_k1.stage_slice] |
| K1-03 | mHC mix projection | residual 与 `hc_fn` 做投影，生成 pre/post/comb 所需的 24 个 mix 分量的部分和 | [stage_tile][dynamic_mhc.stage_tile] |
| K1-04 | 平方和与跨 slice 归约 | residual 平方和供 mHC gate 的归一化；collapse 后输入平方和供 attention RMSNorm；48/6/12 行版将后者发布到 `mhc_sq` | [stage_tile][dynamic_mhc.stage_tile]、[norm_square_total][dynamic_mhc.norm_square_total]、[stage_gate_c1][gate.stage_gate_c1] |
| K1-05 | mHC gate 归一化、仿射、sigmoid、Sinkhorn | mix 乘 reciprocal RMS，再施加 `hc_scale/hc_base`；pre/post 经 sigmoid，comb 经指数及迭代行列归一化，写出 `pre_out/post_out/comb_out` | [stage_gate_c1][gate.stage_gate_c1] |
| K1-06 | Attention RMSNorm | 对 `LIN` 做 RMSNorm，乘 `attn_w`，按 BF16 舍入；需要 compressor/indexer 的层同时写 `normed/NB` | [stage_norm][dynamic_k1.stage_norm] |
| K1-07 | Attention 输入 group-32 FP8 量化 | 每 32 元素统计 amax，生成 power-of-two scale code，量化为 FP8 数据和 scale，写 `X8/X8S` | [stage_norm][dynamic_k1.stage_norm] |
| K1-08 | 合并的 WQKV_A 线性投影 | FP8 路径计算 Q latent 和 KV latent；Q latent 为 1280 维，KV 为 512 维，合计 1792 个输出；写 `QKV` | [stage_wqkv][dynamic_k1.stage_wqkv] |
| K1-09 | Q latent RMSNorm + MXFP8 量化 | 读取 Q latent、乘 `qn_w`，产生第二级 query projection 使用的 `QX8/QX8S`；需要时另写 `qr_out/qrs_out` | [stage_qkv][dynamic_k1.stage_qkv] |
| K1-10 | KV RMSNorm | 对 KV latent 做归一化，乘 `kvn_w`，得到 BF16 值 | [stage_qkv][dynamic_k1.stage_qkv] |
| K1-11 | KV RoPE | 对 KV 尾部 64 维做 GPT-J 风格成对旋转 | [stage_qkv][dynamic_k1.stage_qkv] |
| K1-12 | KV FP8 QAT + window ring 写入 | group-32 量化到 FP8 再反量化，并将所得值存入 BF16 window KV ring；默认 cache 的存储类型仍是 BF16 | [stage_qkv][dynamic_k1.stage_qkv] |
| K1-13 | WQ_B query 投影 + RoPE | Q latent 投影到当前 TP rank 的 query heads，再对每个 head 的尾部做 RoPE，写 BF16 `q_out` | [stage_wqb / qprojection][dynamic_k1.qprojection] |
| K1-14 | Indexer query 投影 + RoPE | 使用 indexer 的 query 权重投影 Q latent，对 index query 的旋转维度做 RoPE，写 `IQ` | [stage_iq / qprojection][dynamic_k1.stage_iq]；仅 `feeds_index=True` |
| K1-15 | Indexer head-weight projection | BF16 `normed` 与 `iw_w` 做点积，为每个 index head 生成一个权重，写 `IW` | [stage_iw][dynamic_k1.stage_iw] |
| K1-16 | Indexer query FP8 量化 + 权重缩放 | 对每个 index head 的 128 维 query 量化，写 `iq_out/iqs_out`；head weight 乘 query scale 和固定因子后写 `iw_out` | [stage_iquant_c1][index_query.stage_iquant_c1]；48 行为 [stage_iquant4][wide_k1.stage_iquant4] |
| K1-17 | DSpark auxiliary tap | 在指定层取 4 路 residual 的均值并写给 drafter；仅 `aux=True` | [stage_tile][dynamic_mhc.stage_tile] / [slice_input][common_pre.slice_input] |

`fold` 的判定见 [runner `_layer_keys`][runner.V41MonoDecodeRunner._layer_keys]：第一层以及经过 Engram、已 settle 的层不再折叠上一子层输出。`feeds_index` 对应 FULL/REINDEX 层；draft 的 K1 不生成 indexer 输入，见 [draft `_layer_keys`][draft_runner.DraftMonoRunner._layer_keys]。

Q/KV 的低秩投影结构不是通常的三个独立 Q、K、V GEMM。这里首先得到 Q latent 与共享 KV row，再展开 Q heads；后续 attention 从该 KV pool 读取 K/V 数据。模型维度见 [dims.py][dims]。

## 4. K2 前半：indexer、attention、输出投影与 FFN 接口

### 4.1 Indexer：稀疏选择

| 编号 | 算子 / 子操作 | 输入、输出与含义 | 实现入口 |
| --- | --- | --- | --- |
| K2-I01 | FP8 index query × cached index key | 对每个 index head 计算 query-key dot product，应用 key scale、ReLU，再按 head weight 求和，写 `ilog` | [score_one_chunk][index.score_one_chunk]、[stage_iscore][index.stage_iscore]；48 行对应 [CT2 score_one_chunk][ct2.score_one_chunk] |
| K2-I02 | Candidate block score reduction | 每 8 个 key 的分数取最大值，写 `ibmax`；包括无效位置与末尾 block 的处理 | [score_one_chunk][index.score_one_chunk]；仅 `iprod != 0` |
| K2-I03 | Token Top-K / 多层 Top-K merge | 逐段选择，再按 tree 合并成每 token 的 top-512 selected keys | [run_indexer][index.run_indexer] → [_run_tree][index._run_tree] → [stage_ilist][index.stage_ilist] → [lds_topk][topk.lds_topk] |
| K2-I04 | Candidate-block Top-K / 多层 merge | 对 block maxima 选择 top-2048 candidate blocks，供后续 REINDEX 层使用 | 同上，`kind="blk"`；仅 candidate-producing layer |
| K2-I05 | Selected row / KV pool row 映射与发布 | 将选中的逻辑 index 转为 attention 读取的物理 pool row，写 `isel/irow`，发布 `IRDY`；block 结果写 `icout` | [stage_ilist][index.stage_ilist]、[_final][index._final]、[共用 _selected_rows][common_index._selected_rows] |

48 行入口使用 `dspark_ct2_index_attention.py` 内同类函数，包含长上下文的 score task 和 Top-K 实现调整，见 [CT2 run_indexer][ct2.run_indexer]、[CT2 stage_ilist][ct2.stage_ilist]。其中还有直接接受较短列表的分支，因此不能把“多层 Top-K”理解成每个 token 总会运行固定层数。

K2 仅在 `index_bound_max > 0` 且 `iact != 0` 时执行上述 indexer。普通 window/reuse 层依照元数据读取窗口或已有 selection；draft 的 `index_bound_max=0`，整个 indexer 被关闭。

### 4.2 Sparse/window attention

| 编号 | 算子 / 子操作 | 输入、输出与含义 | 6/12 行及窄 draft | 48 行 |
| --- | --- | --- | --- | --- |
| K2-A01 | Window / selected KV gather | 解析窗口及 selected key 的 pool row，读取 KV 数据，涉及 global→LDS 拷贝 | [stage_attn_score][attention.stage_attn_score]、[stage_attn_pv][attention.stage_attn_pv] | [P1A stage_fused][p1a.stage_fused] |
| K2-A02 | QK dot product + scale/mask | BF16 Q/K 矩阵乘、QK scale、无效位置屏蔽 | [score_split][attention.score_split] | [stage_fused][p1a.stage_fused] |
| K2-A03 | Softmax 统计与概率 | 分段 max、exp、sum；窄路径写 `AM/AL/AP`，P1A 在同一阶段进行在线 softmax | [score_split][attention.score_split] | [stage_fused][p1a.stage_fused] |
| K2-A04 | P×V、split 合并与 sink | 对概率和值做乘加，合并各 split，并把 attention sink 加入最终归一化 | [stage_attn_pv / pv_stats][attention.stage_attn_pv] | [stage_fused][p1a.stage_fused] 产 partial O/m/l；[stage_irq_p1a][p1a.stage_irq_p1a] 合并并处理 sink |
| K2-A05 | Attention output inverse RoPE | 对输出 head 尾部施加逆旋转 | [irq_group][common_post.irq_group]，由 `stage_attn_irq` 调用 | [raw_irq_group][raw_irq.raw_irq_group]，由 `stage_irq_p1a` 调用 |
| K2-A06 | Attention output group-32 FP8 量化 | 逆旋转后计算 amax/scale，写 `XO/XOS`，供 WO_A 使用 | [irq_group][common_post.irq_group] | [raw_irq_group][raw_irq.raw_irq_group] |

48 行路径中的 **P1A** 将 QK + online softmax + PV 合在 `stage_fused` 内，每个 token 分为 5 个 key split；后续 `stage_irq_p1a` 合并这 5 份结果。它不是在 Mono 外调用另一个 FlashAttention kernel。

### 4.3 输出投影、TP 归约、FFN mHC

| 编号 | 算子 / 子操作 | 输入、输出与含义 | 实现入口 |
| --- | --- | --- | --- |
| K2-P01 | WO_A grouped projection | 每组 attention heads 的输出做 FP8 线性投影，写低秩中间结果 | [stage_woa][wo.stage_woa]；48 行 [native run_wo][native_wo.run_wo] |
| K2-P02 | WO_A output BF16 舍入 + FP8 量化 | 生成 WO_B 读取的 `X8B/X8BS` | [stage_woa][wo.stage_woa]；48 行 [woa_finish][native_wo.woa_finish] |
| K2-P03 | WO_B projection + peer push | 投影回 hidden=5120，得到当前 rank 的部分结果并发布到各 rank 的 attention peer region | [stage_wob][wo.stage_wob]、[wob_push][wo.wob_push]；48 行 [native run_wo][native_wo.run_wo] |
| K2-P04 | Attention TP all-reduce | 按 rank 顺序累加 attention partials，以 BF16 结果供下一个 mHC 使用 | [reduce_attn_pair][wo.reduce_attn_pair]；48 行 [reduce_attn_pair_packed][split.reduce_attn_pair_packed] |
| K2-P05 | FFN mHC post/residual + pre collapse + mix projection | 将 attention 输出折叠进 residual，再得到 FFN 输入及其 mHC mix/square partials；数学子操作对应 K1-01～04 | [dynamic run_seam][seam.run_seam] → [stage_tile][dynamic_mhc.stage_tile]；48 行 [split run_seam][split.run_seam] |
| K2-P06 | FFN RMSNorm + MoE 输入发布 | FFN 输入归一化、乘 `ffn_w`，写 `normed` 并发布 `XRDY` | [dynamic run_seam][seam.run_seam] 使用 [stage_norm][dynamic_k1.stage_norm]；48 行 [finish_pair][split.finish_pair] |
| K2-P07 | FFN mHC gates | mix 归一化、pre/post sigmoid、comb Sinkhorn，写 FFN 的 `pre/post/comb` | [run_seam_gates][seam.run_seam_gates] → [stage_gate_c1][gate.stage_gate_c1]；48 行复用相同 gate 运算 |

Attention 的 all-reduce 分布在 producer 的 peer push 和 consumer 的 sum 中。单独看到 `reduce=False` 的 builder 参数，**不能推断 K2 没有 all-reduce**：默认 `seam=True` 会在 FFN seam 内完成归约；`reduce=True` 是另一个将归约结果单独输出的探测分支。

## 5. K2 后半：MoE 的全部算子

target 使用 **384 个 routed experts、top-6**；draft 使用 **128 个 routed experts、top-3**。两者都有 shared expert，routed/shared 中间维度都按 TP 分片。依据：[通用 MoE 定义][common_moe]、[draft 初始化][draft_runner.DraftMonoRunner.__init__]。

| 编号 | 算子 / 子操作 | 输入、输出与含义 | 实现入口 |
| --- | --- | --- | --- |
| K2-M01 | MoE 输入 group-32 MXFP8 量化 | `normed` 同时供 routed/shared expert 使用，产生 `X8/X8S/X8RDY` | 窄路径 [stage_xq / xq_quant][front.stage_xq]；48 行提前合入 FFN seam 的 [finish_pair][split.finish_pair] |
| K2-M02 | Router linear projection | BF16 `normed × gate_w`，分 K 计算 expert logits，写 `LOGIT` | [stage_router][front.stage_router]；48 行由 [router_unit][native_front.router_unit] 调用 |
| K2-M03 | Router partial reduction + sqrt-softplus + bias | 合并 K partials、BF16 舍入、计算 `sqrt(softplus(logit))`；加 correction bias 作为选择分数 | [stage_route][front.stage_route]、[_score][common_moe._score] |
| K2-M04 | Expert Top-K + 权重归一化 | 选 top-6/3 expert；用未加 bias 的得分归一化并乘 routed scaling factor 1.5；写 `ROUTE` 的 expert id 与 weight | [stage_route][front.stage_route] |
| K2-M05 | Expert union / token 分组与排序表 | 根据各 token 的 top-k，构造本批活跃 expert 集合 U、每个 expert 的 token/pick 列表、偏移及 tile 表 | [load_route][union.load_route]；内部使用 bitmask/popcount/prefix 与 pick placement |
| K2-M06 | 按 expert gather 量化输入 | 从 `X8/X8S` 收集当前 expert 对应 token 的输入，放入 LDS，供 W13 计算 | [gather_x8r][ug.gather_x8r]；48 行 [native gather][native_ug.gather] |
| K2-M07 | Routed expert W13：gate/up 双投影 | MXFP4 权重 × MXFP8 输入，计算 gate 与 up；合并 K slices | [stage_ug][ug.stage_ug]、[ug_pair_matrix][ug.ug_pair_matrix]；48 行 [native run_ug][native_ug.run_ug] |
| K2-M08 | Routed activation：clamp + SiLU × up | gate 上界裁剪、up 双边裁剪，再做 SiLU 与逐元素乘法、BF16 舍入 | [ug_epilogue][ug.ug_epilogue]；48 行 [native epilogue][native_ug.epilogue] |
| K2-M09 | Routed intermediate MXFP8 量化 | 对上一步结果做 group-32 量化，按 expert/pick 布局写 `MID/MIDS` 并发布 ready | 同一 [ug_epilogue][ug.ug_epilogue] / [native epilogue][native_ug.epilogue] |
| K2-M10 | Routed expert W2/down projection | MXFP4 权重 × MXFP8 intermediate，生成各 expert 对 hidden 的贡献 | 窄 target [stage_down][dynamic_down.stage_down]；窄 draft [stage_down][down.stage_down]；48 行 [routed_columns][round_down.routed_columns] |
| K2-M11 | Routing-weight 乘法与 token combine | 每个 expert 输出乘相应 route weight、按约定 BF16 舍入，再按 token 的 top-k 顺序累加 | 窄路径 [down_store][down.down_store] 写贡献，target 用 [bulk_finish][column_down.bulk_finish]、draft 用 [down_combine][down.down_combine] 合并；48 行 [compute_tile][round_down.compute_tile] + [bulk_finish][round_down.bulk_finish] |
| K2-M12 | Shared expert gate/up 双投影 | FP8 权重 × 量化输入，计算 shared gate/up；shared expert 不经过 routed Top-K | [stage_shared][front.stage_shared]；48 行 [shared_unit][native_front.shared_unit] 调用它 |
| K2-M13 | Shared activation：clamp + SiLU × up | gate/up BF16 舍入、带 limit 的 SiLU×up，写 BF16 `SMID` | [stage_shared][front.stage_shared]、[_silu_mul][common_moe._silu_mul] |
| K2-M14 | Shared intermediate FP8 量化 | 量化 `SMID`，写 `SMQ/SMC` | [smid_quant][front.smid_quant] |
| K2-M15 | Shared down projection | FP8 shared W2 × shared intermediate，得到 shared output | [down_shared][down.down_shared] |
| K2-M16 | Routed + shared combine 与 peer push | 合并 routed 累加结果和 shared 输出，BF16 舍入，写每个 rank 的 FFN peer region | 窄 target [bulk_finish][column_down.bulk_finish]；窄 draft [down_combine][down.down_combine]；48 行 [bulk_finish][round_down.bulk_finish] |
| K2-M17 | MoE TP all-reduce | 等待各 rank 的 FFN partials，按 rank 顺序求和，FP32 累加后写 BF16 `out/ffn_out` | [stage_reduce][down.stage_reduce]；48 行 [stage_reduce_packed][round_down.stage_reduce_packed] |

这张表把 routed/shared 两个分支拆开描述，不代表它们严格先后执行。例如 48 行 front 会让部分 CTA 先做 shared expert，再执行 router；down 也会先计算 shared down，以覆盖等待 routed intermediate 的时间。

此处的 **expert Top-K** 与第 4.1 节的 **index Top-K** 不同：前者选择 MoE experts，后者选择 attention keys/candidate blocks。

## 6. 同一算子在不同宽度下的实现对照

以下路径均相对于 `atom/models/deepseek_v41/mono/gfx1250/kernels/`。

| 计算组 | target 6/12 行 | target 48 行及 padded draft 48 行 | draft 5/10 行 |
| --- | --- | --- | --- |
| K1 mHC residual/collapse/mix | `dspark_dynamic_mhc.py::stage_tile` | `dspark_mhc_dataflow_sv.py::stage_tile` | `dspark_k1.py::stage_slice` |
| K1 norm/WQKV/QKV | `dspark_dynamic_k1.py` 内同名 stage | `dspark_wide_accum_k1.py` 内同名 stage | `dspark_k1.py` 内同名 stage |
| K1 WQ_B / index query projection | `stage_wqb/stage_iq → qprojection` | `dspark_wide_accum.py::project`，通过 `wide_project` 别名调用 | `stage_wqb → qprojection`；不含 index query |
| K1 index weight / quant | `stage_iw` / `stage_iquant` | `stage_iw_unit` / `stage_iquant4` | 关闭 |
| K2 index score / select | `dspark_index_attention.py` | `dspark_ct2_index_attention.py`；draft 关闭 | 关闭 |
| Attention QK/softmax/PV | `dspark_attention.py::stage_attn_score/stage_attn_irq` | `p1a_attention.py::stage_fused/stage_irq_p1a` | `dspark_attention.py` |
| IRQ / inverse RoPE + quant | 通用 `mono/kernels/attn_post.py::irq_group` | `dspark_mhtjstest_raw_irq.py::raw_irq_group` | 与窄 target 相同 |
| WO_A/WO_B | `dspark_wo.py::run_wo` | `dspark_mhtjstest_native_wo.py::run_wo` | `dspark_wo.py::run_wo` |
| Attention reduce + FFN seam | `dspark_dynamic_seam.py::run_seam` | `dspark_mhtjstest_split.py::run_seam/finish_pair` | `dspark_seam.py::run_seam` |
| MoE input quant | `dspark_moe_front.py::stage_xq` | `dspark_mhtjstest_split.py::finish_pair` | 与窄 target 相同 |
| Router/route/shared | `dspark_moe_front.py::run_moe_front` | `dspark_mhtjstest_native_front.py::run_moe_front`，复用 router/route/shared device stage | 与窄 target 相同 |
| Routed UG/activation/quant | `dspark_ug.py::run_ug` | `dspark_mhtjstest_native_ug.py::run_ug` | `dspark_ug.py::run_ug` |
| Routed down/combine/TP reduce | `dspark_dynamic_column_down.py::run_down` | `dspark_mhtjstest_round_column_down.py::run_down` | `dspark_down.py::run_down` |

两个容易按文件名判断错的地方：

1. `dspark_wide_accum_k1.py` 里仍定义 `stage_wqb/stage_iq/qprojection`，但其实际 wide builder 使用的是 [wide_project][wide_project.project]。查符号定义不能代替查 builder 的调用点。
2. `reference_*` 并非全部未使用。例如 [reference_gate.py][gate] 的 gate stage、[reference_multirow_projection.py][projection] 的投影 helper、[reference_topk.py][topk] 的 Top-K 都被活跃路径复用；反过来，这些文件的独立测试 builder 并不因此成为每层新增的 launch。

## 7. 同步、数据移动与可选分支

这些也是替换 ASM 二进制时需要接住的工作，但应与模型数学算子区分。

| 项目 | 位置 / 行为 | 默认状态 |
| --- | --- | --- |
| Device mailbox poll/put、epoch tag | [reference_sync.py][sync]；生产者写数据，按作用域发布，消费者等待对应 epoch | 启用 |
| CTA barrier、LDS union 复用 | 各 K1/K2 builder 与 stage 中的 `gpu.barrier()`；确保本 CTA 上前一阶段对共享 LDS 的使用已结束 | 启用；不是全 grid barrier |
| 阶段参数暂存/重建 | K2 的 `late_meta` 在 LDS 保存指针/标量，`late_pointer/restore_late` 按阶段取回 | 启用；这是显式保存语义上下文，不是任意寄存器保护 |
| TDM/global→LDS 拷贝与量化 layout 变换 | P1A、native WO/UG/down、FP8/MXFP4 helper 中 | 算子内部启用；不是额外模型层 |
| 动态 UG/down 任务分配 | route table、UG queue、down arrival rank 等 | 随路径/shape 启用 |
| Token-parallel gather / reduce-scatter / query-cache 复制 | K1 的 `*_dsts`、`run_gather`、peer rows 等 | 本 PR 默认 target 将阈值设为 `max_rows+1`，draft 固定关闭，不能算默认执行的 all-gather |
| Expert-parallel / DP-attention 路由 | 通用 helper 中保留相关分支 | gfx1250 配置拒绝 EP/DP-attention，不计为此后端默认算子 |
| FP4 index scoring / FP8 KV storage | 共用源码内有分支 | 默认要求 FP8 index、BF16 KV，不计为默认路径 |
| `ATOM_DSV41_GFX1250_SLICE_MOE=1` | 48 行 K2 以 [run_slice_moe][slice_moe.run_slice_moe] 将 routed UG 与 down 的 K128 slice 合在任务中，之后沿用 combine/reduce | 默认关闭；计算语义仍是 K2-M07～11/16～17，不是新增模型算子 |
| 调试时间戳/中间值 dump | `dspark_stamps.py` 及 builder 的 debug 分支 | 默认关闭；不作为模型算子统计 |

runner 仍能构建若干非默认宽度，源码也有 `target42` 等替代阶段。比如 dynamic K2 在 36/42 行选择 `dspark_target42_attention.py::stage_attn_irq`，但顶层 dispatch 对应的 3～7 请求宽度走 native，因此不能把这个分支标成默认启用。

部分文件头仍写着 `External trial` 或 `Full MoE not present`。本清单以最终调用链为准：runner 实际给 K2 builder 传入 `seam=True, gates=True, front=True, ug=True, down=True`，完整 MoE 已在同一 K2 中。

## 8. 仍在 K1/K2 外执行的操作

PR 修改了这些模块或 runner 调用了它们，并不代表它们也被编进 K1/K2。

| 操作 | 位置 / 证据 | 与 Mono 的边界 |
| --- | --- | --- |
| Embedding lookup | [target forward][runner.V41MonoDecodeRunner.forward]、[draft backbone][draft_runner.DraftMonoRunner.backbone] | 进入每层 K1 之前 |
| DSpark noise embedding / 初始 block state / 补行 | draft 的 `_noise_embedding`、`build_block_state`、replicate | draft K1 之前 |
| Engram lookup/forward 与其之前的 residual settle | target 的 `block.engram_forward` / `state.settle()` | 对应层 K1 之前 |
| Compressor projection 与 cache compression | [attention `_compress_batch`][model_attention.Attention._compress_batch]：`compressor.project`、`cache.compress` | K1 与 K2 之间 |
| Indexer key projection/写入 | `_compress_batch` 中的 `indexer.write_keys` | 在 K1/K2 外；已融合的是 index **query**、head weight、score/select，不是整个 indexer 生命周期 |
| Step/window/index 元数据准备 | `write_step_meta` / `write_draft_step_meta` | 在 K1/K2 launch 之前 |
| Candidate block-table 构建 | target forward 的 `candidate_block_table(...)` | candidate-producing layer 的 K2 之后 |
| Step mailbox 清零与跨 rank fence | [dspark_step_begin.py][step_begin]、`mailboxes.begin_step()` | 单独的 step-begin launch；不属于每层 K1/K2 |
| 最后一层 residual collapse | target/draft 的 `state.collapse()` | 最后一个 K2 之后；中间层的 pending post 通常由下一 K1 折叠 |
| Draft 最终 norm | `draft.mtp[-1].norm(hidden)` | draft 最后 K2/collapse 之后 |
| LM head/logits 与 sampling/DSpark verify 后处理 | [compute_logits][dispatch.MonoDecodeModel.compute_logits] 转发原模型；sampling 在模型 runner 层 | 不在 K1/K2 内 |
| 权重 shuffle/repack/bind | [dspark_weights.py][weights] 及 native weight helper | 构建准备工作，不是每层 Mono 内的运行时算子 |

## 9. 面向 ASM `.co` 替换时的使用方式

这份清单可以作为替换范围的索引，但**不能直接将表中每一行当成独立二进制替换点**。例如 `stage_qkv` 包含 Q norm/quant、KV norm/RoPE/QAT 和 cache write；`finish_pair` 同时完成 FFN norm、MoE input quant 和 ready 发布；替换其中一个数学算子时，仍需保留其余语义。

优先从实际 builder 的 stage 调用点确定边界，再为待替换块记录：输入输出地址与 layout、量化格式和 scale、CTA/task 映射、LDS 占用、mailbox/tag/peer 发布、需要跨阶段存活的状态。算子输出正确但未发布对应 ready，消费者仍会等待。

现有寄存器覆盖与状态重建实验另见 [BINARY_STAGE_INTEGRATION.md](BINARY_STAGE_INTEGRATION.md)。本文只做 PR 源码清点，未在本机 gfx1100 上编译或验证 gfx1250 模型 kernel，也不将 PR 中的性能注释当成本次实测结果。

<!-- 固定 commit 的源码引用定义；由源码 AST 核对函数名和行号。 -->

[attention.score_split]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_attention.py#L76
[attention.stage_attn_pv]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_attention.py#L290
[attention.stage_attn_score]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_attention.py#L114
[column_down.bulk_finish]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_column_down.py#L181
[common_index._selected_rows]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/index_score.py#L338
[common_moe]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/moe.py#L1
[common_moe._score]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/moe.py#L352
[common_moe._silu_mul]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/moe.py#L599
[common_post.irq_group]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/attn_post.py#L270
[common_pre.slice_input]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/attn_pre.py#L317
[common_pre.slice_row]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/attn_pre.py#L364
[config]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_config.py#L1
[ct2.run_indexer]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ct2_index_attention.py#L547
[ct2.score_one_chunk]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ct2_index_attention.py#L235
[ct2.stage_ilist]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ct2_index_attention.py#L316
[dims]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/kernels/dims.py#L1
[dispatch.MonoDecodeModel.compute_logits]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_dispatch.py#L80
[dispatch.MonoDecodeModel.forward]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_dispatch.py#L68
[dispatch.MonoDraftModel.block_backbone]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_dispatch.py#L110
[down.down_combine]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_down.py#L218
[down.down_shared]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_down.py#L138
[down.down_store]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_down.py#L124
[down.stage_down]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_down.py#L314
[down.stage_reduce]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_down.py#L274
[draft_k1.build_dspark_k1]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_k1.py#L543
[draft_k1.stage_slice]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_k1.py#L64
[draft_k2.build_dspark_down]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_down.py#L24
[draft_runner.DraftMonoRunner.__init__]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_draft_runner.py#L55
[draft_runner.DraftMonoRunner._layer_keys]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_draft_runner.py#L101
[draft_runner.DraftMonoRunner._rows_build]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_draft_runner.py#L115
[draft_runner.DraftMonoRunner.backbone]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_draft_runner.py#L151
[dynamic_down.stage_down]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_column_down.py#L12
[dynamic_k1.build_dspark_k1]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L533
[dynamic_k1.qprojection]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L152
[dynamic_k1.stage_iq]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L183
[dynamic_k1.stage_iw]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L394
[dynamic_k1.stage_norm]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L196
[dynamic_k1.stage_qkv]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L269
[dynamic_k1.stage_wqkv]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L141
[dynamic_k2.build_dspark_down]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_index_down.py#L24
[dynamic_mhc.norm_square_total]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_mhc.py#L116
[dynamic_mhc.stage_tile]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_mhc.py#L37
[front.smid_quant]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_moe_front.py#L189
[front.stage_route]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_moe_front.py#L272
[front.stage_router]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_moe_front.py#L125
[front.stage_shared]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_moe_front.py#L334
[front.stage_xq]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_moe_front.py#L67
[gate]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_gate.py#L1
[gate.stage_gate_c1]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_gate.py#L34
[index._final]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_attention.py#L395
[index._run_tree]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_attention.py#L521
[index.run_indexer]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_attention.py#L461
[index.score_one_chunk]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_attention.py#L217
[index.stage_ilist]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_attention.py#L295
[index.stage_iscore]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_index_attention.py#L265
[index_query.stage_iquant_c1]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_index_query.py#L73
[model_attention.Attention._compress_batch]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/attention.py#L301
[native_front.router_unit]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_front.py#L69
[native_front.shared_unit]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_front.py#L51
[native_ug.epilogue]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_ug.py#L53
[native_ug.gather]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_ug.py#L14
[native_ug.run_ug]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_ug.py#L98
[native_wo.run_wo]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_wo.py#L132
[native_wo.woa_finish]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_wo.py#L104
[p1a.stage_fused]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/p1a_attention.py#L68
[p1a.stage_irq_p1a]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/p1a_attention.py#L202
[projection]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_multirow_projection.py#L1
[raw_irq.raw_irq_group]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_raw_irq.py#L3
[round_down.bulk_finish]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_round_column_down.py#L318
[round_down.compute_tile]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_round_column_down.py#L171
[round_down.routed_columns]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_round_column_down.py#L262
[round_down.stage_reduce_packed]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_round_column_down.py#L399
[runner.V41MonoDecodeRunner._layer_keys]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runner.py#L398
[runner.V41MonoDecodeRunner._rows_build]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runner.py#L436
[runner.V41MonoDecodeRunner.forward]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runner.py#L568
[seam.run_seam]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_seam.py#L170
[seam.run_seam_gates]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_seam.py#L200
[slice_moe.run_slice_moe]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_slice_moe.py#L286
[split.finish_pair]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_split.py#L23
[split.reduce_attn_pair_packed]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_split.py#L84
[split.run_seam]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_split.py#L130
[step_begin]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_step_begin.py#L1
[sync]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_sync.py#L1
[topk]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_topk.py#L1
[topk.lds_topk]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_topk.py#L96
[ug.gather_x8r]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ug.py#L198
[ug.stage_ug]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ug.py#L219
[ug.ug_epilogue]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ug.py#L240
[ug.ug_pair_matrix]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_ug.py#L66
[union.load_route]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_union.py#L21
[weights]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_weights.py#L1
[wide_k1.build_dspark_k1]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wide_accum_k1.py#L716
[wide_k1.stage_iquant4]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wide_accum_k1.py#L609
[wide_k2.build_dspark_down]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_k2.py#L46
[wide_project.project]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wide_accum.py#L29
[wo.reduce_attn_pair]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wo.py#L169
[wo.stage_woa]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wo.py#L188
[wo.stage_wob]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wo.py#L152
[wo.wob_push]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_wo.py#L125
