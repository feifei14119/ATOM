# gfx950 DeepSeek-V4.1-Flash：Mono kernel 与完整网络执行流程

分析日期：2026-11-11。代码基线：本地 ATOM 分支 `mn`，提交 `40c485c88af16e9163206d8f3ef86039ca51c4d6`。

本文根据当前代码的安装入口、运行器、模型拓扑、kernel 主体及 HI recipe 整理。拓扑已用仓库 fixture 和实际拓扑构造函数在 CPU 上核对；未加载模型、编译 GPU kernel 或执行 GPU 推理。支持条件表示代码中的准入条件，不等于本次重新验证过数值或性能。

## 1. 先区分三个层次

| 层次 | 本文含义 | 例子 |
|---|---|---|
| 网络 layer | 模型的一个 Transformer 层 | 主网络第 0～39 层；DSpark 另有 3 个 draft 层 |
| GPU kernel / launch | 一次 GPU 启动，拥有自己的 CTA 网格 | 常规路径的 K1、K2；HI 路径的一整个 layer kernel |
| stage / task | 同一个 GPU kernel 内的计算阶段及其工作分片 | WQKV、attention score、router、MoE down；某个 token/tile 的 task |

当前 gfx950 有两套主要 Mono 实现：

| 项目 | 常规 Mono | HI Mono |
|---|---|---|
| 每个主网络层 | 通常 K1 + K2，共 2 次 Mono launch | 整层 1 次 Mono launch |
| Attention 与 MoE | K1 做前投影，K2 做 attention 后半及 MoE | 同一个 layer kernel 完成两部分 |
| 压缩 KV | FULL 层在 K1/K2 之间调用现有 compressor | FULL 层融合在 layer kernel 内 |
| Engram | 在第 1、14 层前走现有 Engram 路径 | token-only 部分提前运行一个 ENGKV Mono，gate 部分融合到相应层 |
| 最后 norm / LM head | 走现有 runtime 的 norm/head | 使用单独的 verify-head Mono |
| DSpark | draft 的每层也是 K1 + K2 | CTX Mono + 3 个 draft-layer Mono + draft-head Mono |
| 运行入口 | `V41MonoDecodeRunner.forward` | `HiDecodeModel._hi_forward` → `HiLayers` |
| 主要源码 | `mono/kernels/`、`mono/runner.py` | `mono/hi/`、`mono/hi_*.py` |

这里的 `mono/` 指 `atom/models/deepseek_v41/mono/`。公共基础设施另在 `atom/mono/`。

**完整 40 层网络由多个 Mono launch 串联。每个 Mono 内的 stage 由编译器展开到该 kernel 中，不为每个 stage 再启动一个 GPU kernel。** 下文的 stage 箭头表示计算依赖；不同 CTA 可以按 mailbox 就绪情况重叠工作，不能把所有箭头都理解为全网格 barrier。

## 2. 模型怎样选择这条路径

~~~text
ModelRunner 加载 DeepseekV41RuntimeModel / DSpark drafter
  └─ registry.mono_decode_installers
      └─ dispatch.install_mono_decode
          ├─ gfx1250：另一套实现，本文不展开
          └─ gfx950：检查常规 Mono 配置
              ├─ HI 准入成立：安装 HiDecodeModel + HiDraftModel
              └─ 否则：安装 MonoDecodeModel + MonoDraftModel

每一次 forward：
  检查当前 step / shape 是否受支持
    ├─ 支持：执行相应 Mono 路径
    └─ 不支持：返回原有 runtime / 相应后备路径
~~~

安装点在 [model_runner.py](../atom/model_engine/model_runner.py) 的 `ModelRunner.__init__` 中、模型和 drafter 加载完成之后，具体映射在 [registry.py](../atom/models/registry.py)，决策在 [dispatch.py](../atom/models/deepseek_v41/mono/dispatch.py) 和 [hi_gate.py](../atom/models/deepseek_v41/mono/hi_gate.py)。HI 自动模式允许在不满足准入时回退；强制模式的拒绝行为应以 gate 的报错为准。

总开关是 `ATOM_MONO_ENABLE`；HI 选择使用 `ATOM_DSV41_MONO_HI=auto/1/0`，分别表示自动选择、要求 HI、关闭 HI。`ATOM_MONO_CHECK` 控制常规路径的分段参考检查。HI 是 high-interactivity Mono 的缩写。

常规 Mono 的主要约束见 [config.py](../atom/models/deepseek_v41/mono/config.py)：gfx950；TP 配置集合为 2/4/8，代码注释明确 TP2/4 有 GPU 运行记录，而 TP8 是编译/资源可容纳但原始服务路径存在限制；DP attention 另有 2-rank 路径。KV 支持 BF16/FP8，index cache 支持 FP8/FP4，单步最多 48 行。默认不让 side-stream compressor 与常驻 Mono 并发占用 CU。

HI 当前服务约束更窄：完整 MI355X（gfx950、256 CU）、TP4、无 DP attention、BF16 KV、FP4 index cache（preshuffle 或 mfma 布局）、128-token KV page、DSpark 5-token block、对应 Flash 模型几何、Engram UVA/overlap staging，最大 context bucket 为 1M。还会检查 TBO、KV transfer 等配置以及每种 shape 的实际构建结果。

两者主要服务 decode/DSpark verify。初次 prefill、图像输入和不满足 step 条件的情况不应计入本文的 Mono 主链。

行数与并行 CTA 数不是一回事：

- `B`：请求数。
- `S`：本次处理的 token 行数。普通单 token decode 通常为 `S=B`。
- DSpark5 的 target verify 通常为 `S=6B`：一个 anchor 加五个 draft token。
- 对应 draft backbone 为 `5B` 行。
- gfx950 常驻 Mono 使用 256 CTA、每 CTA 512 threads、wave64，即每 CTA 8 waves；其定义在公共 [execution.py](../atom/mono/plan/execution.py) 和 HI 的 [target.py](../atom/models/deepseek_v41/mono/hi/target.py)。HI 目标每 CTA 使用一整个 CU 的 160 KiB LDS 预算。

## 3. 40 层的真实拓扑

下表全部使用 **从 0 开始的 layer ID**。基于 [fixture config.json](../tests/models/deepseek_v41/fixtures/config.json) 及 [config.py](../atom/models/deepseek_v41/config.py) 的 `build_attention_topology`。

模型几何：hidden=5120、mHC=4 个 residual streams、64 个 Q heads、head_dim=512、Q latent rank=1280、window=128、index top-k=512。主网络 routed experts=384、每 token 选 6 个；DSpark draft 为 128/3。

| Layer ID | 类型 | 压缩 ratio | compressed KV 来源 | top-k selection 来源 | candidates 来源 | 附加行为 |
|---|---|---:|---:|---:|---:|---|
| 0 | WINDOW | 0 | — | — | — | embedding 后首层 |
| 1 | WINDOW | 0 | — | — | — | Engram |
| 2 | FULL | 2 | 2 | 2 | — | 产生压缩 KV 和 selection |
| 3～7 | REUSE | 2 | 2 | 2 | — | 复用第 2 层的压缩结果及 selection |
| 8 | FULL | 2 | 8 | 8 | — | 新一组压缩源 |
| 9～13 | REUSE | 2 | 8 | 8 | — | 复用第 8 层 |
| 14 | FULL | 2 | 14 | 14 | — | Engram、新一组压缩源 |
| 15～19 | REUSE | 2 | 14 | 14 | — | 复用第 14 层 |
| 20 | FULL | 1 | 20 | 20 | 20 | 后半网络的 KV/candidate 源 |
| 21～23 | REUSE | 1 | 20 | 20 | 20 | 复用第 20 层 |
| 24 | REINDEX | 1 | 20 | 24 | 20 | 基于已有 KV/candidates 重新选 top-k |
| 25～27 | REUSE | 1 | 20 | 24 | 20 | 复用第 24 层的 selection |
| 28 | REINDEX | 1 | 20 | 28 | 20 | 重新选 top-k |
| 29～31 | REUSE | 1 | 20 | 28 | 20 | 复用第 28 层的 selection |
| 32 | REINDEX | 1 | 20 | 32 | 20 | 重新选 top-k |
| 33～35 | REUSE | 1 | 20 | 32 | 20 | 复用第 32 层的 selection |
| 36 | REINDEX | 1 | 20 | 36 | 20 | 重新选 top-k |
| 37～39 | REUSE | 1 | 20 | 36 | 20 | 同时为 DSpark 提供 3 处 aux taps |
| 40～42 | draft WINDOW | 0 | draft context | 无上述稀疏索引 | — | DSpark 的 3 个独立 draft 层 |

主网络合计：2 个 WINDOW、4 个 FULL、4 个 REINDEX、30 个 REUSE。逐层 JSON 见 [GFX950_DSV41_MONO_TOPOLOGY.json](GFX950_DSV41_MONO_TOPOLOGY.json)。

四种类型的差别：

- **WINDOW**：仅窗口 attention，无压缩分支。
- **FULL**：本层产生 compressed KV 和 index key，计算 index query/score/top-k，并做自己的 attention。
- **REINDEX**：复用 KV 源的 compressed KV/index key，使用本层 query 重新选 top-k；后半网络还使用第 20 层 candidates 缩小搜索范围。
- **REUSE**：复用相应源的 compressed KV 和 top-k，仍执行本层 Q/KV 投影、窗口 KV、attention、输出投影和 MoE。

因此，“复用”不表示跳过整个层，也不表示复用前一层 attention 输出。拓扑中的 encoder 0～19 / decoder 20～39 划分，也不表示这条 decode 路径只执行后 20 层；Mono 主循环实际遍历全部 40 层。

~~~mermaid
flowchart LR
    S2["L2: KV + selection"] --> C2["L3–L7"]
    S8["L8: KV + selection"] --> C8["L9–L13"]
    S14["L14: KV + selection"] --> C14["L15–L19"]
    S20["L20: KV + index keys + candidates"] --> C20["L21–L23: selection20"]
    S20 --> I24["L24: selection24 → L25–L27"]
    S20 --> I28["L28: selection28 → L29–L31"]
    S20 --> I32["L32: selection32 → L33–L35"]
    S20 --> I36["L36: selection36 → L37–L39"]
~~~

这个图表示 cache/selection 的共享关系；residual 主链仍按 0→1→…→39 执行。

## 4. 常规 Mono：所有 kernel 及完整主链

### 4.1 实际存在的四类入口

| 入口 | 源码 / builder | 负责的工作 | 正常 forward 是否单独启动 |
|---|---|---|---|
| K1，`v41_attn_pre...` | [attn_pre.py](../atom/models/deepseek_v41/mono/kernels/attn_pre.py)，`build_attn_pre` | mHC 前接缝、norm、WQKV、Q/KV 后处理、index query 投影 | 是 |
| 合并 K2，`v41_layer_post...` | [layer_post.py](../atom/models/deepseek_v41/mono/kernels/layer_post.py)，`build_layer_post` | index selection、attention、输出投影、mHC/FFN norm、完整 MoE | 是 |
| 拆分 K2a，`v41_attn_post...` | [attn_post.py](../atom/models/deepseek_v41/mono/kernels/attn_post.py)，`build_attn_post` | K2 的 attention 半部 | 检查/拆分路径 |
| 拆分 K2b，`v41_moe...` | [moe.py](../atom/models/deepseek_v41/mono/kernels/moe.py)，`build_moe` | K2 的 MoE 半部 | 检查/拆分路径 |

`runner._bind` 令 `self.split_k2=self.check`。所以通常每层是 K1→K2；检查模式是 K1→K2a→K2b，并插入参考计算。四个 builder 不表示每层固定启动四个 kernel。

每种 row count、TP、KV/index 类型等可以生成不同二进制变体；不同 layer 也可能共享同一变体，启动时绑定不同权重/cache 指针。

### 4.2 从 token 到 logits

主调用链在 [runner.py](../atom/models/deepseek_v41/mono/runner.py) 的 `forward`、`_front`、`_layer_post`：

~~~text
MonoDecodeModel.forward
  └─ V41MonoDecodeRunner.forward
      ├─ 选择 S 对应的 build；开启本 step 的 mailbox
      ├─ model.embed(input_ids) → [1,S,5120]
      ├─ model.begin_forward；等待 Engram staging 完成
      ├─ write_step_meta：positions、ring 相对地址、key metadata、index walks
      ├─ SinglePassHCState.from_embeddings → 4 路 residual 状态
      │
      ├─ for layer = 0 ... 39:
      │   ├─ 若有 Engram：settle 上一层 pending → engram_forward
      │   ├─ _front → K1
      │   ├─ 若本层有 indexer：_compress_batch
      │   │   └─ FULL 层实际压缩；REINDEX 的 compressor=None，直接返回
      │   ├─ _layer_post → 合并 K2
      │   ├─ 若产生 candidates：组织后续 REINDEX 使用的 candidate block table
      │   └─ 用 res_ffn、gate/pre/post/comb、ffn_out 建立下一层状态
      │
      ├─ state.collapse → [S,5120]
      ├─ 需要时 gather token-parallel 输出
      └─ model.end_forward

原 runtime.compute_logits
  └─ final RMSNorm → LM head → logits → sampling / speculative verification
~~~

常规主网络一轮、每个 TP rank 通常有 **40×2=80 次主要 Mono launch**，还要加 embedding、Engram、compressor、metadata、最终 norm/head 等辅助工作。开启检查时通常有 120 次主要 Mono launch，并有参考 kernel；这些数字不是完整 GPU trace 的总 kernel 数。

### 4.3 K1 内部完整逻辑

实际主体在 `attn_pre.py::build_attn_pre` 返回的 `attn_pre`；stage 调度位于函数后半部。

| 顺序 / stage | 输入与计算 | 产物及后续使用 |
|---|---|---|
| `k1.slice / stage_slice` | 首层读取 embedding residual；其他层折叠上一层 pending MoE output，计算 mHC 的线性混合/统计；必要时写 DSpark tap | 本层 residual、混合后的 attention 输入、mHC 统计 |
| `k1.norm / stage_norm` | attention RMSNorm、量化 | BF16 `normed`；MXFP8 `X8` 和 E8M0 scale codes |
| `k1.wqkv_a / stage_wqkv` | `gemv_fp8_loads` 预取权重，`load_x8` 取量化输入；WQ_A 与 WKV 投影 | 每行 Q latent 1280 + KV 512，共 1792 列 |
| `k1.gate` | 根据 mHC 统计生成 attention 接缝的 pre/post/comb | attention 后 mHC 所需 gate |
| `k1.qkv` | Q latent norm/量化、KV norm、KV RoPE/窗口 ring 写入 | WQ_B 的量化输入，更新的窗口 KV |
| `k1.wq_b` | Q latent → 本 TP rank 的 Q heads，并做相应 RoPE | attention 的 Q |
| `stage_iq` | FULL/REINDEX 的 index-query 投影，交错在 WQ_B token loop 内 | index query |
| `k1.index_w / stage_iw` | index head weight 投影 | index score 的 head weights |
| `k1.index_quant` | index query 的 FP8/FP4 格式整理 | K2 indexer 的输入 |
| token-parallel 尾部（条件执行） | ring / normed 等跨 rank 数据整理 | 后续压缩与 attention 所需数据 |

`stage_wqkv` 对应的是前投影阶段；它不是一整个 attention，也不是整个网络层。WINDOW/REUSE 不需要的 index 投影分支不会执行。

gate 被放到部分投影后面是调度安排：norm/WQKV 不需要等待完整 gate 产出。它不改变 mHC 的数学依赖。

### 4.4 K1 与 K2 之间的压缩

`runner.forward` 在 K1 后调用 `block.attn._compress_batch(normed, cache, step, rope)`。只有 FULL 源层拥有 compressor；压缩工作还取决于本 step 的压缩计划。

它使用当前层 normed hidden 生成压缩 KV、相应索引 key，并写入模型 cache。ratio=2 的源层还维护压缩状态；ratio=1 的第 20 层为后半网络提供 KV。之后 K2 才读取这些数据执行选择及 attention。

因此常规路径的 FULL 层并非仅有两个 GPU launch：K1/K2 是两个主要 Mono，中间仍有现有 compressor 的工作。

### 4.5 合并 K2 内部完整逻辑

`layer_post.py` 的主体直接组合：

~~~python
run_attn_post(..., after_norm=publish_x, gates=False)
run_moe(..., before_ug=lambda: run_gates(...))
~~~

这是同一 GPU kernel 内生成代码的组合。按逻辑依赖展开如下：

| 阶段 | 内部工作 | 结果 |
|---|---|---|
| Indexer（FULL/REINDEX） | `run_indexer`：iscore → 分层选择/合并列表 → top-512；candidate 源还产生 top candidate blocks | attention 使用的 selection；跨层复用 selection/candidates |
| `k2a.attn_score` | 读取本层 Q；访问窗口 KV 和选中的 compressed KV；QK、分 split softmax | attention 分块统计/概率中间量 |
| `k2a.irq` | PV、分块结果归约、sink 处理、inverse RoPE、输出量化 | 输出投影输入 |
| `wo_a` | 分组低秩输出投影第一段 | WO_B 输入 |
| `wo_b` | 输出投影第二段，产生/推送 TP partial | attention output 的跨 rank 部分和 |
| `k2a.slice` | `stage_reduce` 合并 TP partial，并处理 attention→FFN 的 mHC 接缝 | FFN residual、混合输入/统计 |
| `k2a.norm` | FFN RMSNorm；`after_norm` 发布输入就绪 | MoE 可读取的 normed rows |
| MoE `xq` | 输入 MXFP8 量化 | routed/shared expert 的量化输入 |
| MoE `router` | hidden→384 expert scores | route scores |
| MoE `route` | score 变换、bias、top-6、权重归一化及 route scale | expert ID、权重、工作任务 |
| MoE `shared` | shared expert gate/up、带 limit 的 SwiGLU | shared intermediate |
| 延后的 `k2a.gate` | `before_ug` 回调运行 FFN mHC gate | 下一层所需 pre/post/comb |
| MoE `ug` | routed A8W4 gate/up、激活、mid requant；按队列/tile 调度 | routed intermediate |
| MoE `down` | routed down、按 route weight 合并 top-k、shared down、TP push | FFN 的 TP partial |
| MoE `reduce` | 合并各 rank partial | `ffn_out` |

candidate block 的当前配置为最多 top-2048 blocks，每 block 8 行；它与 attention 的 top-512 selected keys 是两个层次。源层 candidate table 被后续 REINDEX 使用。

合并 K2 把 gate 后移，允许 router/shared 与接缝中的其他工作交错。DP/token-parallel 路径还会包含输入 gather/push、candidate 等待等条件步骤。具体 schedule 的 task 分配以 build key 为准。

### 4.6 相邻层究竟传了什么

常规路径通过 [SinglePassHCState](../atom/model_ops/deepseek_v41/mhc.py) 传递：

~~~text
residual：上一次 post 尚未折叠时的四路 residual
pre_mix：下一次 collapse/pre 使用的 mixing
pending：待合入 residual 的 sublayer output，此处主要是 ffn_out
post_mix、combination：如何把 pending 和旧 residual 合成新 residual
~~~

一个 token 的逻辑 residual 为 BF16 `[4,5120]`；mHC mixing 有 pre 4、post 4、comb 4×4，共 24 个 FP32 值。张量的实际维度前还带 row/batch。

K2 不必把 FFN post 单独做成又一次 kernel。下一层 K1 的 slice 可以把它与本层的 mHC pre 一起处理。遇到 Engram 时先 settle；网络末尾由 collapse 完成收尾。

跨 K1/K2、跨 layer 的这些值保存在 global tensor/mailbox/cache 中。上一 kernel 的 VGPR/SGPR 不会自然延续成下一 kernel 的输入。

## 5. HI Mono：所有 kernel 与完整主链

### 5.1 实际接入的 kernel 家族

`HiPrograms.kernels()` 按 `layer/head/engkv/ctx/draft` 分类。展开实际用途如下：

| kernel 家族 | 主要 builder / recipe | 何时执行 |
|---|---|---|
| Target layer，`atom_v41_{kind}_..._r{S}` | `hi_compose._program` → `hi/v41/recipe.window_layer_blocks` | 每个主网络层一次；共 40 层 |
| Engram KV，`atom_v41_engkv_r{S}` | `recipe.engram_kv_stages` | layer 0 之前；一次处理第 1、14 层的 token-only 部分 |
| Verify head，`atom_v41_head...sample_race...` | `hi_compose._head_program` → `hi/v41/head.head_program` | layer 39 之后；整批或按请求拆分 |
| Draft context，`atom_v41_ctx_r{S}` | `hi/v41/draft.context_program` | target end-step 之后，准备 draft context KV |
| Draft layer 0 | `hi/v41/draft.stage_program(stage=0)` | 每轮 draft |
| Draft layer 1 | 同上，stage=1 | 接 draft layer 0 |
| Draft layer 2 | 同上，stage=2 | 接 draft layer 1 |
| Draft Markov head | `hi/v41/draft.head_program` | draft layer 2 之后，产生 draft token IDs |

主层的 kind 包括首层 window、带 Engram 的 window、compressed consumer、KV+index source、index-only source 等。相同 kind/width 的多层可共享 kernel 程序，指针表则按 layer 分别绑定。

当前 `HiPrograms` 的安装配置要求带 Engram 的完整 40 层 HI 链。不要把 `hi_plan.py` 中曾描述的可选 33 层覆盖理解为当前服务必定执行“33 层 HI + 7 层常规”。

### 5.2 一次 target verify 的启动顺序

~~~mermaid
flowchart TD
    E["Embedding + begin_forward + staging join"] --> B["begin-step bridge：metadata / ring / residual streams"]
    B --> G["ENGKV Mono：L1 和 L14 的 token-only 部分"]
    G --> L0["Layer 0 Mono"]
    L0 --> L1["Layer 1 Mono，含 Engram gate"]
    L1 --> LS["Layer 2 … 13 Mono"]
    LS --> L14["Layer 14 Mono，含 Engram gate"]
    L14 --> LT["Layer 15 … 39 Mono"]
    LT --> H["Verify-head Mono：fold / norm / LM head / 选 token"]
    H --> X["end-step bridge：cache export / taps / collapse"]
    X --> C["CTX Mono：更新 3 个 draft 层的 context KV"]
    C --> P["post-verify：比较 draft 与 target / commit"]
    P --> D["下一轮 DSpark draft 与 target verify"]
~~~

调用栈：

~~~text
HiDecodeModel.forward
  └─ _hi_forward
      ├─ embed / model.begin_forward / staging.join
      ├─ hook.begin_step
      │   ├─ hi_bridge._begin_step_kernel  [辅助 Triton kernel]
      │   ├─ 必要的 band/live-row 元数据整理
      │   └─ _engram_launch → ENGKV Mono
      ├─ for spec in model.topology:
      │   └─ hook.layer(spec.layer_id, rows)
      │       ├─ programs[key].launch(table, buffers, layer=i)
      │       └─ 最后一层后：head_program.launch，一次或多个请求分片
      ├─ hook.end_step
      │   ├─ hi_bridge._end_step_kernel  [辅助 Triton kernel]
      │   ├─ _ctx_after_target → CTX Mono
      │   └─ 符合 verify 条件时 pv.launch → post-verify helper
      └─ collapse_view / model.end_forward

ModelRunner.compute_head → 读取本 forward 已计算的 HI head 输出
~~~

源码：[hi_dispatch.py](../atom/models/deepseek_v41/mono/hi_dispatch.py)、[hi_runner.py](../atom/models/deepseek_v41/mono/hi_runner.py)、[hi_bridge.py](../atom/models/deepseek_v41/mono/hi_bridge.py)。

典型单请求 verify、每个 TP rank 的主要 Mono launch 数为 **1 ENGKV + 40 layers + 1 head + 1 CTX = 43**。仍要加 embedding、begin/end-step、post-verify 等辅助 kernel。多请求的 split head、draft 分组和后备形状会改变数量。

### 5.3 一个 HI layer 的完整逻辑

主 recipe 在 [hi/v41/recipe.py](../atom/models/deepseek_v41/mono/hi/v41/recipe.py) 的 `window_layer_blocks`。名字保留了 window，但该函数已覆盖所有 layer 类型。

~~~text
mHC seam A / hca
  ├─ 首层：embedding streams
  ├─ 中间层：折叠上一层 MoE 输出 / TP partial
  └─ Engram 层：hca0 fold → Engram gate → hca mixing
    ↓
attn_norm → 量化输入 xa（source 层还提供 BF16 xab）
    ├─ wq_a：5120 → 1280
    ├─ wkv：5120 → 512
    └─ FULL：Compressor → compressed KV / index key / compress state
    ↓
q_norm / kv_norm
    ├─ FULL / REINDEX：Indexer → score / candidates / top-k / sel_store
    └─ wq_b → 本 rank 的 Q heads
    ↓
KVPrep（RoPE）
    ↓
MLAWindowAttn 或 MLASparseAttn（window + selected compressed KV）
    ↓
RingWrite
    ↓
wo_a → wo_b → TP attention partial
    ↓
mHC seam F / hcf：attention post + FFN pre、residual/gates
    ↓
ffn_norm → xf（MXFP8）及需要的 BF16/统计
    ↓
MoERouter：384 scores → top-6 IDs / weights
    ↓
shared expert + routed MoE：gate/up → SwiGLU → down → weighted combine
    ↓
推送本 rank MoE partial
    ├─ chain 内：交给下一层 / head 接着处理
    ├─ chain 尾或需要完整输出：reduce / store ffn_out
    └─ 部分 sharded 调度：hcz 在本层尾提前完成下一层 fold + LIN
~~~

以下分支必须一起理解：

1. **FULL 的 Compressor**：WKV/WGATE dots、pool/归一化/RoPE、写 compressed cache；ratio=2 维护可用于 speculative rejection 的多槽 state。其 dots 依赖 attn_norm，可被安排在 WQ_A/WKV 前后。
2. **Indexer**：index WQ_B、head weight dot、query FP4 packing；FULL 还接新 index key；随后 score、top-k、`sel_store`。candidate source 生成候选 block/bitmap，REINDEX 在候选范围重新评分。
3. **Attention**：WINDOW 只读窗口；source 和 consumer 使用稀疏 attention。source 可读本次 launch 的 channel，consumer 从前层留下的 cache/selection 读取。
4. **MoEExperts**：shared 可融合在专家 block 内；对应 `sh_ug/rt/ug/sh_down/down/combine` 等阶段，具体是否独立取决于 schedule。未融合时出现独立 `se_gu/se_d`。是否有 own/dsum/finish、最终 store 由 TP reduce 和 chain 模式决定。
5. **调度变形**：norm 可以融合进消费它的 Linear；`moe_route_early` 会调整 index/comp、MoE、gate 和 LDS 驻留次序。上述是完整数学依赖，不承诺每个构建有同名的一一对应 stage。

HI 把这些 block 的 `stages(sc)` 展开成一个 `Program`。最终只有一个 `@flyc.kernel`；不存在每个 block 都重新 launch 的过程。

### 5.4 HI 怎样把 40 个独立 launch 连成一条链

HI 有三类关键跨层状态：

| 状态 | 内容 | 后继消费者 |
|---|---|---|
| residual 与 mHC gates | `r_f`、`gate_f` 等，逻辑 residual 为 `[S,4,5120]`；gate 每行 24 个值 | 下一层 seam A 或最终 head |
| TP peer partial | `moe.part`、相关确认/归约区域；部分模式还有 `lin_n` | 下一层入口或上一层尾部的接续处理 |
| 模型持久 cache | window rings、compressed KV、index keys、selection、candidate bitmap、压缩状态 | 对应拓扑中的本层及后续层 |

常见 chain 方式：

~~~text
Layer i:
  attention → FFN norm → MoE
  每个 TP rank 把 MoE partial 推送到 peer region
  输出 residual + mHC gates
       ↓ 下一次 kernel launch
Layer i+1:
  seam A 读取上次 launch 的 partial
  TP 求和 + mHC post + 本层 pre
  → 本层 attention 输入
~~~

在 `RESIDUAL=sharded` 时，部分 residual 只保存本 rank 的 `5120/TP` 列，离开 chain、Engram 或 tap 等需要全量时再 gather。另一个重要调度 `SHARD_SEAM_A=end` 会将下一层的 fold + LIN 放到前一层末尾 `hcz`，下一层使用已准备好的结果继续 norm/mixing。不能一概说“所有归约都发生在下一层开头”。

最终 verify head 也可以成为 chain 的消费者，直接 fold 最后一层推送的 MoE partial。若 head 按请求拆分，最后一层可能作为 chain tail 先形成完整输出，再由各 head 分片读取。

这些传递通过预绑定的 global buffer/peer region 和指针表完成。指针表预先组织权重与缓冲区地址；每个 launch 使用 step、layer tag 区分本轮数据，并复用 arena。它不是把所有层寄存器状态一直保留在 GPU 上。

HI 源码中 `scratch` / `priv` 也用作显式申请的工作缓冲区名字。不能仅凭参数名将其等同于 AMDGPU 编译器的 private-segment scratch spill。

## 6. Engram、verify head、CTX、draft 的内部流程

### 6.1 Engram

主网络第 1、14 层有 Engram。

常规路径在相应层 K1 之前调用现有 `engram_forward`，先 settle pending residual。

HI 将它拆成两部分：

~~~text
提前的 ENGKV Mono：
  token/history/hash lookup
  → enc / gather
  → Engram WKV
  → KV 整理
  → store 两个 Engram 层各自的 eng.kv

第 1 或 14 层的 Mono：
  当前 residual fold
  → 使用提前得到的 eng.kv 做依赖 hidden 的 gate
  → Engram 更新后的 residual
  → 本层 attention 的 mHC mixing / norm
~~~

源码入口：`recipe.engram_kv_stages`、[engram_io.py](../atom/models/deepseek_v41/mono/hi/v41/engram_io.py)、[Engram block](../atom/models/deepseek_v41/mono/hi/blocks/gfx950/engram.py)。ENGKV 按 look/enc/gath/wkv/kvx/store 交错两个层的工作。它能提前，是因为这部分依赖 token/history，不依赖第 1/14 层的实时 hidden；gate 必须等各层自己的 hidden。

Engram 的 KV 与 attention 的 KV cache 是不同数据，不应因名字相同混为一谈。

### 6.2 Verify head

HI head 的基本依赖：

~~~text
最后一层 MoE partial / output
  → mHC fold + collapse
  → final RMSNorm
  → 按 TP 分片的 vocab projection（vocab=129280）
  → rank 间合并候选 / token 选择
  → token IDs、必要的 score 信息
~~~

当前 `hi_compose._head_program` 实际传入 `sample=True, race=True`，支持准入范围内的 temperature/top-p 路径；不能仅据 `head.py` 旧的 greedy 描述认为它只有 argmax。对不能由该 head 表示的请求，runtime 仍有 logits 后备机制。

实际 hook 把 head 作为最后一层之后的独立 Mono。recipe 虽有把 head 放入 layer 的构建接口，但不能据此把当前服务图画成“layer39 已包含 head”。

### 6.3 CTX：target 怎么给 draft 提供上下文

DSpark 读取主网络第 37/38/39 层的 aux taps。HI end-step bridge 将需要的 tap 数据交给现有 aux storage，随后 CTX Mono 完成：

~~~text
3 处 target taps
  → cx_q：拼接/量化
  → cx_proj：main_proj
  → cx_ag：需要时按 TP gather
  → cx_mnorm：main norm / 量化
  → cx_wkv0、cx_wkv1、cx_wkv2：三个 draft 层各自的 context KV 投影
  → cx_kvn0/1/2：KV norm
  → cx_kvp0/1/2：RoPE
  → cx_st0/1/2：写 draft context rings
~~~

这些都是 **一个 CTX Mono 内部的阶段**。其入口在 [hi/v41/draft.py](../atom/models/deepseek_v41/mono/hi/v41/draft.py) 的 `context_blocks/context_program`，运行在 `hi_draft._ctx_after_target`。

常规路径也保留 target taps，但 context write 使用原有 DSpark 组织方式；普通 K1/K2 本身不包含 HI 的 CTX Mono。

### 6.4 三层 DSpark draft 与 draft head

DSpark 从 anchor token embedding 和 noise embedding 构造 block 输入，一次提出五个候选 token。

常规路径 [draft_runner.py](../atom/models/deepseek_v41/mono/draft_runner.py)：

~~~text
anchor/noise → build_block_state + draft metadata
  → draft0 K1 → draft0 K2
  → draft1 K1 → draft1 K2
  → draft2 K1 → draft2 K2
  → collapse → 最后 draft norm
  → 原有 head_and_sample / Markov head
  → 五个 draft IDs
~~~

HI 路径 [hi_draft.py](../atom/models/deepseek_v41/mono/hi_draft.py)：

~~~text
draft-begin helper：anchor/noise residual、positions、slots、step
  → Draft layer 0 Mono
  → Draft layer 1 Mono
  → Draft layer 2 Mono
  → Draft-head Mono：最后 MoE fold / collapse → mtp.2.norm → MarkovHead
  → mk.ids
~~~

三个 HI draft layer 复用主层 recipe，但有这些差别：

- routed experts/top-k 为 128/3。
- 使用 `MLABlockAttn`，读取 target 经 CTX 生成的历史 context，并允许 draft block 内的双向 attention。
- 移除主网络 recipe 的 `RingWrite`；context KV 的写入由 CTX 管理。
- draft 的 residual 使用 replicated 布局，partial 格式采用该 draft chain 自己的配置。
- draft head 使用 target LM head 权重及 Markov tables；其结果已经是 IDs，`HiDraftModel.head_and_sample` 读取这些结果。

通常是 3+1=4 个主要 draft Mono。对于较宽、多请求形状，planner 可分组或按请求拆分；并非所有 batch 都固定只有四次 launch。

## 7. 完整生成循环：target 与 draft 如何接起来

~~~mermaid
flowchart TD
    P["初始 prefill：现有 runtime 建 cache / context"] --> A["获得 anchor 和 draft 所需上下文"]
    A --> D["DSpark：anchor + noise → 3 层 draft → Markov head"]
    D --> V["Target verify：anchor + 5 个 draft，共 6 行/请求"]
    V --> T["40 个 target layer + target head"]
    T --> C["更新 target cache / taps / draft context"]
    C --> R["比较 target 与 draft：确定接受前缀和下一 anchor"]
    R --> U["提交有效状态，推进 position / request metadata"]
    U --> D
    R --> O["将已接受 token 交给服务层，检查停止条件"]
~~~

图的环可以从一次 target 完成后的 CTX/anchor 处开始理解。具体首次调用的 bootstrap 由 drafter/runtime 处理；初始 prefill 不被强行归入 Mono。

HI 将更多步骤收入 target graph：

1. Target 的 40 层和 head 在 graph 内产生验证 token。
2. end-step 导出 ring/taps/hidden，CTX 为 draft 写 context KV。
3. [post_verify.py](../atom/models/deepseek_v41/mono/round/post_verify.py) 比较 target IDs 与 draft IDs，计算接受长度和下一 anchor，并提交可接受的 Engram cursor 状态。
4. [device_round.py](../atom/models/deepseek_v41/mono/round/device_round.py) 在准入成立时使用设备端 verdict 推进下一轮位置，基本关系为 `next_position = previous_start + 1 + accepted_drafts + row_offset`。
5. [HiRound](../atom/models/deepseek_v41/mono/round/__init__.py) 统一决定 FORWARD/LEAN/DEVICE 服务方式，metadata builder、ModelRunner 和 scheduler 继续负责请求生命周期与停止条件。

Speculative verify 会计算随后可能被拒绝的行。能否读取某个 cache entry 必须由已提交位置、slot、bound、压缩 state 等元数据决定，不能把“已经写到显存”理解为“已经被接受”。

这不是 GPU 上一个永久运行、自动生成全部 token 的单 kernel；host/framework 仍组织多次 launch 或 graph replay，以及请求调度、结果消费。

## 8. CTA、kernel、TP 三层同步

| 范围 | 主要机制 | 作用 |
|---|---|---|
| 单个 CTA 内 | LDS、wait、CTA barrier；HI emitter 对相邻 LDS 使用阶段安排 barrier | 同步 8 个 waves，安全复用 LDS |
| 同一 Mono 的不同 CTA | mailbox/channel 的数据、ready flags、计数/任务队列 | 某一 tile/row 就绪后消费者继续，避免每个 stage 都全局同步 |
| 同 GPU 不同 Mono launch | 当前 stream 的顺序；graph 保留依赖；global tensor/cache 传递 | K1→compress→K2、layer i→layer i+1 |
| TP rank / GPU 之间 | peer memory、发布/等待协议、partial reduce/gather、launch tag/parity | attention/MoE TP 通信，防止新 launch 覆盖旧 launch 尚未消费的区域 |

常规路径的基础设施在 [device/sync.py](../atom/mono/device/sync.py)、[device/ranks.py](../atom/mono/device/ranks.py)、[runtime/mailboxes.py](../atom/mono/runtime/mailboxes.py)。

HI 在 [plan/program.py](../atom/models/deepseek_v41/mono/hi/plan/program.py) 声明 channels/regions/依赖，运行时绑定共享 arena 与 peer group，再由 emitter 生成生产/等待代码。内部 `_end_step(peers)` 还有 CPU 端翻转 peer phase 的用途，应与真正发射 `hi_bridge._end_step_kernel` 的方法区分。

HI 中 ENGKV=41、CTX=42、draft=43～46 等常量是同步/launch 标签；它们不是新的主网络 layer ID，也不能直接用最大标签推算 kernel 总数。

## 9. 编译和参数组织：这些 stage 如何成为一个 Mono

常规路径：

~~~text
模型拓扑、权重格式、S、TP
  → AttnPreBuild / LayerPostBuild 等 build key
  → build_attn_pre / build_layer_post
  → FlyDSL trace/JIT 编译包含所有相关 stage 的 kernel
  → KernelAbi.pack 按入口参数顺序组织实际地址/值
  → runner._run_compiled 在当前 stream 启动
~~~

HI 路径：

~~~text
hi_plan + hi/v41/recipe + schedules + Scenario
  → Block.stages(sc)
  → moe_route_early 等 schedule 变换
  → Program：stage、task、channel、region、LDS/peer 需求
  → MonoKernel(Program)
      → hi/emit/kernel.build
          → 一个 mono(step, layer, table, scratch, priv)
          → _emit_stages 在编译期展开各个 stage
      → FlyDSL/LLVM 编译 + 资源检查
  → table(pointers)：预绑定本层权重、cache、状态和 peer 地址
  → MonoKernel.launch(table, buffers, layer, stream)
~~~

见 [hi/emit/kernel.py](../atom/models/deepseek_v41/mono/hi/emit/kernel.py)、[hi/runtime/kernel.py](../atom/models/deepseek_v41/mono/hi/runtime/kernel.py)、[hi/emit/compile.py](../atom/models/deepseek_v41/mono/hi/emit/compile.py)。

HI 会检查编译产物的 VGPR/SGPR、LDS、private segment、scratch 指令等资源；部分构建显式允许 SGPR spill 到 VGPR lane，仍拒绝相应不满足内存 spill 规则的产物。因此不能把“具有资源检查”简化成“绝对不发生任何 GPR spill”。

当前原生代码的上述 stage 是 FlyDSL 内部组合/展开。我们之前在 `mono_test00/01/10/30` 讨论的外部 ASM device function 或 inline-asm 接入，是另一层集成实验；不能把它们当作当前所有 layer 默认采用的调用方式。

## 10. 继续阅读代码的顺序

| 要回答的问题 | 建议先看 |
|---|---|
| 安装了哪套 Mono | [dispatch.py](../atom/models/deepseek_v41/mono/dispatch.py)，[hi_gate.py](../atom/models/deepseek_v41/mono/hi_gate.py) |
| 40 层如何遍历 | 常规 [runner.py](../atom/models/deepseek_v41/mono/runner.py) 的 forward；HI [hi_dispatch.py](../atom/models/deepseek_v41/mono/hi_dispatch.py) 的 _hi_forward |
| 哪些层共享 KV/top-k | [config.py](../atom/models/deepseek_v41/config.py) 的 build_attention_topology |
| K1 主体和 WQKV | [kernels/attn_pre.py](../atom/models/deepseek_v41/mono/kernels/attn_pre.py) |
| K2 如何合并 attention 和 MoE | [kernels/layer_post.py](../atom/models/deepseek_v41/mono/kernels/layer_post.py)，随后读 attn_post.py / moe.py |
| 单个 HI layer 包含哪些算子 | [hi/v41/recipe.py](../atom/models/deepseek_v41/mono/hi/v41/recipe.py) 的 window_layer_blocks |
| 不同类型 layer 如何实例化 | [hi_compose.py](../atom/models/deepseek_v41/mono/hi_compose.py) 的 _program |
| HI 实际发射哪些 kernel | [hi_runner.py](../atom/models/deepseek_v41/mono/hi_runner.py) 的 begin_step / layer / end_step |
| HI 各算子的设备实现 | [hi/blocks/gfx950](../atom/models/deepseek_v41/mono/hi/blocks/gfx950)，[hi/device/gfx950](../atom/models/deepseek_v41/mono/hi/device/gfx950) |
| target/draft 如何串联 | [hi_draft.py](../atom/models/deepseek_v41/mono/hi_draft.py)，[hi/v41/draft.py](../atom/models/deepseek_v41/mono/hi/v41/draft.py)，[round](../atom/models/deepseek_v41/mono/round) |
| 资源/布局/同步如何进入最终 kernel | [hi/plan/program.py](../atom/models/deepseek_v41/mono/hi/plan/program.py)，[hi/emit/kernel.py](../atom/models/deepseek_v41/mono/hi/emit/kernel.py) |

注意仓库历史文字与当前实现有差异：recipe 中曾写的 12-row 上限、K2b 尚不支持的状态、可选 33 层 HI、greedy-only head，均不能替代当前 gate、runner 和 builder。本文以这一提交的实际调用路径为准；更改模型配置或 schedule 后，需要重新核对拓扑、资源准入和 launch 划分。
