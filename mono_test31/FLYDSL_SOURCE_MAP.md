# step.s 中全部 FlyDSL 片段的来源映射

本文覆盖 [step.s](/home/feifei/repo/ATOM/mono_test31/step.s) 中的全部 **43 个** `.flydsl.begin/end` 块，按汇编出现顺序列出它们对应 [原 step.py](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py) 的函数调用、行号和适配方式。

| 固定来源 | 行数 | SHA256 |
| --- | ---: | --- |
| step.s | 459 | `f6a49ddeb1dd984dfa97597b1ee83218e6c6f521b580cfc0292f5f78691f45d7` |
| step.py | 486 | `1ef733d1ed0664a3a0618e53e05d9779b44825686bcf6225373d0a64dbd9d7d1` |
| fragments.py | 186 | `b8b9ee335cbf67efcc15225e870f4d08cf796b8cd84fcf88b6208b288a2e741e` |

行号指当前源文件，不是展开后的 `step.generated.s` 或反汇编。源文件更新后需要重新核对。本文只做静态源码核对，没有构建 kernel、执行单测或启动 GPU。

## 1. 片段名与原函数名的关系

`.flydsl.function fragments.py:attention_A` 中的 `attention_A` 是本项目的阶段注册名，不是原 `step.py` 中名为 `attention_A` 的函数定义。原计算调用大多位于 `step.py` 的 **body 函数 L215–475**；实际计算 helper 定义在 attention/front/MoE 等其他文件。

例如：

```text
step.s 的片段名 kv_C
    → fragments.py 的 SPANS["kv_C"] = [(315, 316)]
    → step.py body 中的 stage_kv(c)、stage_C(c)
    → attention.py 中的实际函数定义
```

`fragments.py:generated_source` 为注册名构建 `adapted(...)`；`create_launcher` 再编译成 `step31_target_<name>` 或 `step31_draft_<name>`。预处理器把 native ASM 插回此块。最终阶段是内联展开，不能把文档中的 helper 调用理解为最终二进制保留设备函数调用。

来源分为三类：27 个按 `SPANS` 提取的阶段、14 个重写对应调用的 handoff 阶段、2 个 epoch 适配阶段。所有阶段还会附加公共上下文；表中来源区间仅列阶段主体，公共部分见第 4 节。

## 2. 全部 43 个片段，按 step.s 顺序

segment 列表示 `.flydsl.segment`：target/draft 为相应编译变体，both 可根据构建配置生成两套变体。epoch 标为 target，但在 draft-only launch 中也执行。

最后一列说明每个片段处理的数据、产出的结果或建立的同步依赖；执行条件及适配细节继续见第 3–5 节。

| # | 注册名 / segment | step.s 块行号 | step.py 主体来源 | 主要原函数及调用位置 | 作用说明 |
| ---: | --- | --- | --- | --- | --- |
| 1 | `epoch_begin` / target | [L84–88](/home/feifei/repo/ATOM/mono_test31/step.s:84) | 适配，对应 [L219](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:219)；定义 [L76–91](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:76) | `tp_epoch_begin`：调用 L219；定义 L76–91 | 读取当前 TP epoch，选择四个 rank 的当前接收半区，清零本 rank 的下一步半区；将 epoch 经 scheduler LDS 交给 ASM。 |
| 2 | `target_state` / target | [L109–113](/home/feifei/repo/ATOM/mono_test31/step.s:109) | [L229–234](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:229) | `CX.stage_block_state` L232–234 | 按 tids 读取每行 token 的 embedding，复制到 4 个残差流，并初始化 y=0、pre=(1,0,0,0)、post=0、comb=单位矩阵，建立 target 输入状态。 |
| 3 | `handoff_target_state` / target | [L114–118](/home/feifei/repo/ATOM/mono_test31/step.s:114) | 重写，对应 [L235](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:235) | `handoff` L235 | 让本 GPU 的所有 CTA 汇合，保证 target 初始状态可见后，入口 front 才开始读取。 |
| 4 | `target_front` / target | [L121–125](/home/feifei/repo/ATOM/mono_test31/step.s:121) | [L237](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:237) | `entry_front` L237；定义 L130–144，内部 `FS.front_any` L144 | 处理 target 初始残差状态，完成 attention 入口所需的混合、归一化和量化，生成 axn/x8/xs，并首次载入 LDS 残差，供 target 第 0 层使用。 |
| 5 | `handoff_target_front` / target | [L127–131](/home/feifei/repo/ATOM/mono_test31/step.s:127) | 重写，对应 [L238](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:238) | `handoff` L238 | 让所有 CTA 等待 front CTAs 完成 target 入口处理，再进入第 0 层 attention body。 |
| 6 | `draft_meta` / draft | [L141–145](/home/feifei/repo/ATOM/mono_test31/step.s:141) | [L257–259](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:257) | `CX.draft_meta` L257–259 | 根据 verdict 的接受数量、target rpos 和 dgeom，生成各 draft 行的 rpos_d、KV ring 写入位置 kvw_d 和 attention 窗口元数据 kmeta_d。 |
| 7 | `draft_state` / draft | [L147–151](/home/feifei/repo/ATOM/mono_test31/step.s:147) | [L260–262](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:260) | `CX.stage_block_state` L260–262 | 每个请求的第 0 行使用 anc token 的 embedding，其余行使用 noise 向量；初始化 4 个残差流及 pre/post/comb/y，建立 draft block 输入。 |
| 8 | `handoff_draft_state` / draft | [L152–156](/home/feifei/repo/ATOM/mono_test31/step.s:152) | 重写，对应 [L263](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:263) | `handoff` L263 | 汇合 draft metadata 和 block state 的写入，保证后续入口 front 及 draft 层可以读取准备好的状态。 |
| 9 | `draft_front` / draft | [L159–163](/home/feifei/repo/ATOM/mono_test31/step.s:159) | [L265](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:265) | `entry_front` L265；定义 L130–144，内部 `FS.front_any` L144 | 用 draft 入口表行的权重处理初始 block state，生成 draft 第 0 层的 attention 输入 axn/x8/xs，并首次载入其 LDS 残差状态。 |
| 10 | `handoff_draft_front` / draft | [L165–169](/home/feifei/repo/ATOM/mono_test31/step.s:165) | 重写，对应 [L266](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:266) | `handoff` L266 | 让所有 CTA 等待 draft 入口 front 完成，然后开始 draft 层循环。 |
| 11 | `layer_stamp_start` / both | [L177–181](/home/feifei/repo/ATOM/mono_test31/step.s:177) | [L300–303](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:300) | `stamp(0)` L301、`stamp(12)` L303；定义 L294–298 | 由 thread0 在第 0 层写时间戳槽 0、第 1 层写槽 12，用于测量层开始时间。 |
| 12 | `engq` / target | [L186–190](/home/feifei/repo/ATOM/mono_test31/step.s:186) | [L306](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:306) | `ES.stage_engq` L306 | 将预先准备的 Engram embedding engemb 量化为 MXFP8 eng8 和缩放码 engs，为后续 Engram KV 投影准备输入。 |
| 13 | `attention_A` / both | [L192–196](/home/feifei/repo/ATOM/mono_test31/step.s:192) | [L307–309](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:307) | `stage_A` L307；`pf_rows` L308–309 | 对量化输入 x8/xs 做首段 Q/KV 投影和归约，生成 qkv、量化 Q latent qr8/qrs 及归一化统计 ss；预取下一阶段的 wqb 权重。 |
| 14 | `handoff_A` / both | [L197–201](/home/feifei/repo/ATOM/mono_test31/step.s:197) | 重写，对应 [L310](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:310) | `handoff(lc,t,True)` L310 | 保证 A 产生的 Q/KV latent 和归一化统计对其他 CTA 可见，再进行 KV/C 与 indexer 计算。 |
| 15 | `engkv` / target | [L206–210](/home/feifei/repo/ATOM/mono_test31/step.s:206) | [L313–314](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:313) | `ES.stage_engkv` L313–314 | 将 eng8/engs 与 Engram 权重 engw/engws 做投影，生成 engkv 的分支 key 和共享 value，供下一层入口 attention front 的 Engram gate 使用。 |
| 16 | `kv_C` / both | [L212–216](/home/feifei/repo/ATOM/mono_test31/step.s:212) | [L315–316](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:315) | `stage_kv` L315；`stage_C` L316 | stage_kv 对 KV latent 做 RMSNorm、RoPE 和窗口 cache 写入；stage_C 用 wqb 展开 Q latent，完成归一化缩放及 RoPE，生成 attention query。 |
| 17 | `index_prepare` / target | [L221–225](/home/feifei/repo/ATOM/mono_test31/step.s:221) | [L320–328](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:320) | `IS.stage_iq` L322；`IS.stage_iw` L323；`CS.stage_cgemm` L328 | stage_iq 生成索引 query iq，stage_iw 生成各 head 的权重部分和 iwp；启用 compressor 时，stage_cgemm 将 axn 投影为值/门控分数的 cpart 部分和。 |
| 18 | `handoff_KV_C` / both | [L227–231](/home/feifei/repo/ATOM/mono_test31/step.s:227) | 重写，对应 [L329](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:329) | `handoff` L329 | 保证 KV cache、attention query 及可选 index/compressor 投影完成，后续量化或 attention 才读取；无 indexer 时也参与汇合。 |
| 19 | `index_quant` / target | [L236–240](/home/feifei/repo/ATOM/mono_test31/step.s:236) | [L332–344](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:332) | `IS.stage_iquant` L332–333；`CS.stage_crow` L343；`CS.stage_cring` L344 | 将 iq 量化为 FP8 iq_out/iqs_out，归约 iwp 并生成融合 query scale 的 iw_out；可选 crow 生成压缩 KV/索引行，cring 更新原始投影 ring。 |
| 20 | `handoff_quant` / target | [L241–245](/home/feifei/repo/ATOM/mono_test31/step.s:241) | 重写，对应 [L345](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:345) | `handoff` L345 | 保证索引 query/head 权重和可选压缩行、ring 更新可见，供 index scorer 读取。 |
| 21 | `index_score` / target | [L250–254](/home/feifei/repo/ATOM/mono_test31/step.s:250) | [L348–359](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:348) | `SC.stage_score_any` L359 | 计算 query 对可见索引 key 的多 head 加权评分并写 ilog，支持 FULL/REINDEX；candidate producer 还写 block 最大分数 ibmax。 |
| 22 | `handoff_score` / target | [L255–259](/home/feifei/repo/ATOM/mono_test31/step.s:255) | 重写，对应 [L360](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:360) | `handoff` L360 | 等待评分和可选 block 最大分数写完，使 selection 可以安全读取。 |
| 23 | `index_select` / target | [L268–272](/home/feifei/repo/ATOM/mono_test31/step.s:268) | [L363–365](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:363)；额外 [L348–358](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:348) | `TK.stage_select_any` L365；pmode/plev 在 L363–364 | 按 pi 的 mode/level 推进选择树；SEL/RX 最终写 top-512 行索引 isel/irow，BLK 最终写候选块 icand，供 attention 或后续 REINDEX 使用。 |
| 24 | `handoff_select` / target | [L273–277](/home/feifei/repo/ATOM/mono_test31/step.s:273) | 重写，对应 [L366](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:366) | `handoff` L366 | 发布当前 selection pass 的结果，保证下一层选择树或后续 attention 可以读取；每个 pi 使用不同 counter。 |
| 25 | `attention_D` / both | [L282–286](/home/feifei/repo/ATOM/mono_test31/step.s:282) | [L367–368](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:367) | `stage_D` L367；`pf_rows` L368 | 按窗口及选中索引读取 KV，计算 attention scores、softmax 和加权聚合，合并结果并量化为 o8/os_；预取输出投影 woa 权重。 |
| 26 | `handoff_D` / both | [L287–291](/home/feifei/repo/ATOM/mono_test31/step.s:287) | 重写，对应 [L369](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:369) | `handoff` L369 | 等待 attention 聚合和输出量化完成，使 E 阶段可以读取 o8/os_。 |
| 27 | `attention_E` / both | [L292–296](/home/feifei/repo/ATOM/mono_test31/step.s:292) | [L370–371](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:370) | `stage_E` L370；`pf_rows` L371 | 执行输出投影的 woa 部分，归约 K 分片并量化为 y8/ys；预取后续 wob 权重。 |
| 28 | `handoff_E` / both | [L297–301](/home/feifei/repo/ATOM/mono_test31/step.s:297) | 重写，对应 [L372](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:372) | `handoff` L372 | 保证 E 的归约/量化结果完成，供 F 的 wob 投影读取。 |
| 29 | `attention_F` / both | [L302–306](/home/feifei/repo/ATOM/mono_test31/step.s:302) | [L373–374](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:373) | `stage_F_cluster` L373；`gpu.barrier` L374 | 执行 wob 输出投影并合并本 GPU 的 K 分片，将 TP 部分结果写入 out 和每个 CTA 的 LDS payload；执行 CTA barrier，准备 TP1。 |
| 30 | `tp1` / both | [L307–311](/home/feifei/repo/ATOM/mono_test31/step.s:307) | [L375–377](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:375) | `tp_allreduce` L376；`gpub` L377（定义 L148–153） | 把 attention 输出部分结果做四 rank TP allreduce，结果写 y1/tpout，再发布 TP1 column-group counter，供 FFN front 按组等待。 |
| 31 | `front_wait` / both | [L327–331](/home/feifei/repo/ATOM/mono_test31/step.s:327) | [L385](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:385) | `gwait` L385；定义 L157–161 | hf0 等对应 column group 的 TP1 发布，hf1 等 TP2 发布；组内达到 16 个 TP CTA 后执行 CTA barrier，使 front 可以读取 y1/y2。 |
| 32 | `front` / both | [L332–336](/home/feifei/repo/ATOM/mono_test31/step.s:332) | [L387–422](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:387) | `FS.front_any` L422；局部 `fsel` L389–391、`x8pub` L415–421 | 复用 front 处理残差混合、归一化和量化：hf0 生成 FFN/MoE 输入与路由 ids/wts，并发布 X8；hf1 生成下一层 attention 输入或段末 head 输入，按需融合 Engram。 |
| 33 | `shared_early` / both | [L340–344](/home/feifei/repo/ATOM/mono_test31/step.s:340) | [L423–434](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:423) | `hx.wait_count` L429；`gpu.barrier` L430；`MS.ug_shared_early` L434 | 等待所有 front CTAs 发布 X8 后，利用 eligible idle CTAs 提前计算 shared expert 的 up/gate K 分片，写部分结果供 MoE 后续归约。 |
| 34 | `handoff_front` / both | [L349–353](/home/feifei/repo/ATOM/mono_test31/step.s:349) | 重写，对应 [L437](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:437) | `handoff` L437 | 在 hf0 汇合 FFN front 和 early shared 准备工作，保证路由、量化激活和相关部分结果对 MoE 可见。 |
| 35 | `moe` / both | [L354–358](/home/feifei/repo/ATOM/mono_test31/step.s:354) | [L438–445](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:438) | `MS.moe` L444；`gpu.barrier` L445 | 构建路由 expert 任务，执行 up/gate、激活与量化、down 投影及 shared expert 后续计算，将 expert 输出写入 mout，供 combine 使用。 |
| 36 | `handoff_moe_done` / both | [L359–363](/home/feifei/repo/ATOM/mono_test31/step.s:359) | 重写，对应 [L446](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:446) | `handoff` L446 | 等待 routed/shared expert 输出完成，使 combine 阶段可以读取并求和。 |
| 37 | `moe_combine_tp2` / both | [L364–368](/home/feifei/repo/ATOM/mono_test31/step.s:364) | [L448–450](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:448) | `MS.moe_combine` L448；`tp_allreduce` L449；`gpub` L450 | 合并已按路由权重加权的 expert 输出和 shared 输出，再做四 rank TP2 allreduce，结果写 y2/tp2out 并发布 TP2 group counter，供 hf1 attention front 读取。 |
| 38 | `handoff_layer_end` / both | [L373–377](/home/feifei/repo/ATOM/mono_test31/step.s:373) | 重写，对应 [L451](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:451) | `handoff` L451 | 在两遍 front 后让所有 CTA 汇合，保证本层及下一层输入准备工作完成，再进行 tap、层号递增或段尾处理。 |
| 39 | `tap` / target | [L382–386](/home/feifei/repo/ATOM/mono_test31/step.s:382) | [L454–456](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:454) | `CX.stage_tap1` L455–456 | 从相关 target 残差 aRout 的 4 个流取均值，量化到 aux8/auxs 的指定 tap 区，为 draft context KV 投影保存上下文输入。 |
| 40 | `layer_stamp_end` / both | [L388–392](/home/feifei/repo/ATOM/mono_test31/step.s:388) | [L457](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:457) | `stamp(18)` L457；定义 L294–298 | 由 thread0 写时间戳槽 18，记录当前层结束时间，配合开始时间戳分析耗时。 |
| 41 | `target_tail` / target | [L401–405](/home/feifei/repo/ATOM/mono_test31/step.s:401) | [L459–465](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:459) | `ST.target` L464–465；all 的同等工作位于 L248–251 | 从 target head 输入生成词表 logits，完成跨 rank 采样和草稿验证，写 outtok/verdict/anc；在通信过程中准备 draft context KV，并记录尾部时间戳。 |
| 42 | `draft_tail` / draft | [L414–418](/home/feifei/repo/ATOM/mono_test31/step.s:414) | [L467–472](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:467) | `ST.draft` L472 | 从 draft head 输入生成 dlog，执行 Markov 草稿采样，生成后续解码使用的 draft token，并维护 qlog/qids 等持续验证状态。 |
| 43 | `epoch_end` / target | [L421–425](/home/feifei/repo/ATOM/mono_test31/step.s:421) | 适配，对应 [L473](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:473)；定义 [L95–100](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:95) | `tp_epoch_end`：调用 L473；定义 L95–100 | 由 CTA0/thread0 把持久 tpep 更新为当前 epoch+1，使下一次 launch 切换通信半区。 |


## 3. 每个阶段保留的内容与外层条件

以下说明与表中注册名一一对应。外层 segment/layer/hf/pi 循环和注明的外层条件在 step.s；原片段内的条件继续由 FlyDSL 编译。

- **1. `epoch_begin`**：launch 入口；即使 draft 层数为 0 也执行。新增 scheduler LDS 交接见后文。
- **2. `target_state`**：target 入口，所有 CTA 进入。B=TR、W=1，aid 来自 tids。
- **3. `handoff_target_state`**：target 入口所有 CTA 参与；TARGET_STATE，hdev=False。
- **4. `target_front`**：外层 ASM L119–120 只让 bid<FRONT_CTAS 进入；使用 TENTRY_ROW。
- **5. `handoff_target_front`**：target 入口所有 CTA 参与；TARGET_FRONT，hdev=False。
- **6. `draft_meta`**：外层 ASM L139–140 只让 CTA0 进入；B=TRD/DSPARK_W、W=DSPARK_W。
- **7. `draft_state`**：draft 入口，aid 来自 anc，使用 anchor embedding/noise 建立 block state。
- **8. `handoff_draft_state`**：draft 入口所有 CTA 参与；DRAFT_STATE，hdev=False。
- **9. `draft_front`**：外层 ASM L157–158 只让 bid<FRONT_CTAS 进入；使用表行 NL+NDR 和 draft router 配置。
- **10. `handoff_draft_front`**：draft 入口所有 CTA 参与；DRAFT_FRONT，hdev=False。
- **11. `layer_stamp_start`**：保留内部 Ly==0/Ly==1 判断；stamp 内部仅 thread0 写。
- **12. `engq`**：外层 ASM L182–185 判断 target 且 lflags bit7。
- **13. `attention_A`**：包含 A 后的两次数据预取；不包含独立 handoff_A。
- **14. `handoff_A`**：所有当前层 CTA 参与；ATTN_A counter，hdev=True。
- **15. `engkv`**：外层 ASM L202–205 判断 target 且 bit7。
- **16. `kv_C`**：同一片段包含两个计算函数。
- **17. `index_prepare`**：外层判断 target 且 bit3；片段保留 hascomp(bit1)/r1(bit2) 和 compressor GEMM 条件。
- **18. `handoff_KV_C`**：始终执行，位于 indexer 条件之外；KV_C，hdev=True。
- **19. `index_quant`**：外层判断 target 且 bit3；片段保留 compressor rows/ring、bit1/bit2 条件。
- **20. `handoff_quant`**：仅 indexer 路径；INDEX_QUANT，hdev=True。
- **21. `index_score`**：外层 ASM L246–249 判断完整 64-bit ibat 非零；L348–358 构建 scorer 上下文及 REINDEX/iprod。
- **22. `handoff_score`**：score 后执行；SCORE，hdev=True。
- **23. `index_select`**：额外复制 L348–358 setup；pi 从 ASM 传入，片段不包含 L362 的 pi 循环。
- **24. `handoff_select`**：重写为 SELECT0+pi*4；每遍使用独立 counter，hdev=True。
- **25. `attention_D`**：包含 D 后的数据预取；不包含独立 handoff_D。
- **26. `handoff_D`**：ATTN_D，hdev=True。
- **27. `attention_E`**：包含 E 后的数据预取；不包含独立 handoff_E。
- **28. `handoff_E`**：ATTN_E，hdev=True。
- **29. `attention_F`**：包含 F 后的 CTA barrier；TP1 单独分片。
- **30. `tp1`**：L375 计算 par=Ly%2，结果送 y1，使用 TP1_GROUPS 发布。
- **31. `front_wait`**：外层仅 front CTAs 进入，hf0 等 TP1，hf1 等 TP2；按 column group 等待。
- **32. `front`**：外层仅 front CTAs 进入；内部保留 hf 指针选择、末层/tap/Engram 条件与 X8 callback。
- **33. `shared_early`**：ASM 外层仅 hf0 进入；原 L423 的构建条件和 L426 的 idle CTA 范围仍在片段内部。
- **34. `handoff_front`**：仅 hf0 路径，所有 CTA 参与；FRONT，hdev=True。
- **35. `moe`**：仅 hf0 路径；保留 LazyC shplane 及 MoE 参数构造。
- **36. `handoff_moe_done`**：仅 hf0 路径；MOE_DONE，hdev=True。
- **37. `moe_combine_tp2`**：仅 hf0 路径；额外插入 par=Ly%2（对应 L375），结果送 y2 并发布 TP2_GROUPS。
- **38. `handoff_layer_end`**：hf 两遍之后所有 CTA 参与；LAYER_END，hdev=True。
- **39. `tap`**：外层判断 target 且 bit4；片段 L454 计算 tap0=NL-4。
- **40. `layer_stamp_end`**：tap 之后写结束时间戳；stamp 内部仅 thread0 写。
- **41. `target_tail`**：实际提取 L459–465；包含 slot25 时间戳和 _ctxtab。all 且有 draft 时在 target 层后、draft 入口前执行。
- **42. `draft_tail`**：实际提取 L467–472；包含 slot26 时间戳；只在有 draft 层且 part!=target 时可达。
- **43. `epoch_end`**：每次 launch 末尾执行一次；内部 CTA0/thread0 推进 epoch。

## 4. 公共上下文并不只来自表中的主体行

生成逻辑位于 [fragments.py L107–148](/home/feifei/repo/ATOM/mono_test31/fragments.py:107)。一个阶段大致由以下部分拼成：

```text
参数/表/shape 的公共 prefix
    + 可选的 step.py L269–298 层上下文
    + 阶段主体（SPANS 提取或 handoff/epoch 适配）
    + hx.TOFLAG[0] = None
```

公共 prefix（fragments.py L110–135）包含：

| 片段中的准备工作 | 原 step.py 中的相关来源 |
| --- | --- |
| 从 record 读取 recv0..3、cnt/st/scale/fp/tp | 原 body 的参数 L215–216；record 是 ASM 版本的适配接口 |
| 按传入 epoch 重建 recv 半区地址 | 原 tp_epoch_begin L82/L91；epoch adapter 调用在 L219 |
| 登记 timeout 指针 TOFLAG | L218，退出清理对应 L474 |
| 重建 seg_kind/kind、FIRST_LY、TRx/Lx、DSUF、RNE/RTOPK | L221–223、L239–242、L268；形状由 target/draft 变体确定 |
| 取得 t/b/sm，计算 TCNT/lc | L228–231、L244–247、L269–274 |
| 生成 layer 的 LazyC/表字段和 stamp 局部函数 | 按需提取 L269–298；stamp 定义 L294–298 |

这里的 `layer_stages` 是 SPANS 的全部键，排除 target_state/target_front/draft_meta/draft_state/draft_front/target_tail/draft_tail。它不是按名字模糊判断。handoff 和 epoch adapter 不提取 L269–298，使用公共 prefix 的地址准备。

entry/tail/epoch/handoff 不读取 layer row 来构造完整计算上下文，避免在零层或入口表行情况下错误地把入口当作 body 层。`PREP_STAGE`（step.s L36–48）在 native 展开时准备 record/bid/tid/layer/hf/pi/epoch；外层调度字段不是原 step.py 的新增函数参数。

## 5. 有额外提取或重写的阶段

### 5.1 index_score 与 index_select

注册表的 index_score 区间为 L348–359，实际生成拼接是：

```text
index_score = L348–358（setup） + L359（score 调用）
index_select = L348–358（再次构建 setup） + L363–365（mode/level/select）
```

两者的 setup 都包含 scorer 所需指针、lflags、isrx、ibmax/icand/lvl/iprod 等字段。**index_select 不仅对应 L363–365**，还复制了 L348–358；否则它无法依赖前一个片段的临时上下文。

L361–362 的 npass/pi 循环在 ASM L260–280 中实现，片段只接收当前 pi。handoff_select 是单独片段，对应 L366。

### 5.2 moe_combine_tp2

主体提取 L448–450，另在前面补上：

```python
par = Ly % 2  # 来源对应 step.py L375
```

因为不能依赖 tp1 片段中的临时 par 跨片段存活。它不是复制 tp1 计算，只重建 parity 后执行 combine/TP2/gpub。

### 5.3 所有 handoff 阶段

handoff 不是从 SPANS 直接切片，生成器按 counter 名重写调用，见 [fragments.py L93–98](/home/feifei/repo/ATOM/mono_test31/fragments.py:93)。下面列出完整生成形式和原调用行：

| 片段 | 生成的主体 | 原 step.py |
| --- | --- | --- |
| `handoff_target_state` | `handoff(TCNT + i64(LY.TARGET_STATE), t, False)` | [L235](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:235) |
| `handoff_target_front` | `handoff(TCNT + i64(LY.TARGET_FRONT), t, False)` | [L238](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:238) |
| `handoff_draft_state` | `handoff(TCNT + i64(LY.DRAFT_STATE), t, False)` | [L263](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:263) |
| `handoff_draft_front` | `handoff(TCNT + i64(LY.DRAFT_FRONT), t, False)` | [L266](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:266) |
| `handoff_A` | `handoff(lc + i64(LY.ATTN_A), t, True)` | [L310](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:310) |
| `handoff_KV_C` | `handoff(lc + i64(LY.KV_C), t, True)` | [L329](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:329) |
| `handoff_quant` | `handoff(lc + i64(LY.INDEX_QUANT), t, True)` | [L345](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:345) |
| `handoff_score` | `handoff(lc + i64(LY.SCORE), t, True)` | [L360](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:360) |
| `handoff_select` | `handoff(lc + i64(LY.SELECT0) + i64(pi) * 4, t, True)` | [L366](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:366) |
| `handoff_D` | `handoff(lc + i64(LY.ATTN_D), t, True)` | [L369](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:369) |
| `handoff_E` | `handoff(lc + i64(LY.ATTN_E), t, True)` | [L372](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:372) |
| `handoff_front` | `handoff(lc + i64(LY.FRONT), t, True)` | [L437](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:437) |
| `handoff_moe_done` | `handoff(lc + i64(LY.MOE_DONE), t, True)` | [L446](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:446) |
| `handoff_layer_end` | `handoff(lc + i64(LY.LAYER_END), t, True)` | [L451](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:451) |

原 L310 写 `handoff(lc,t,True)`，生成器写 `lc+LY.ATTN_A`，其中 ATTN_A=0。其他 counter 名与原调用逐一对应。True/False 选择内存顺序方案；两者默认都是当前 GPU 上 256 个 CTA 的 device-wide handoff。

### 5.4 epoch_begin / epoch_end

生成的 epoch_begin 主体为：

```python
recv, tep = tp_epoch_begin([recv0, recv1, recv2, recv3], fp, rank)  # 原调用 L219
if t == 0:
    hx.lstore(fx.Int32(SCHED_LDS), tep)  # ASM 适配新增：交接 epoch
gpu.barrier()  # ASM 适配新增：CTA barrier
```

`gpu.barrier()` 让本 CTA 的线程在 LDS 交接后汇合。`tp_epoch_begin` 本身仍是原 step.py L76–91 的函数。随后 step.s L89–95 读取 SCHED_LDS 到 s48。新增 LDS 交接和 CTA barrier 不属于原 L219 的单行调用。

生成的 epoch_end 主体为：

```python
tp_epoch_end(fp, tep)  # 原调用 L473；函数定义 L95–100
```

两者都固定编译 target adapter，由 `build.py:variants` 特殊处理，因此不会因 part=draft 而被删掉。

### 5.5 target_tail 的实际提取与执行位置

**实际提取的是 L459–465，而不是 L248–251。** 这段来自原 `part=target` 的尾部，包含 slot25 时间戳和 `ST.target(...,ctx=_ctxtab(fp,NDR),T=TR)`。

原 all 模式的同等工作在进入 draft segment 时执行 L248–251，直接使用 ctxtab；all 且 draft 层数>0 时，_ctxtab 同样返回 ctxtab。ASM 将这两种构建共用的 tail 放在 L401–405，通过 L400 的构建条件及 L407–411 的后续跳转保持顺序：

```text
target 层结束 → target_tail →（all 且有 draft）draft_entry → draft 层
```

part=all 且没有 draft 层时没有 target_tail；part=target 时有 target_tail。draft-only 不会在此调用 target_tail。

## 6. 主要原函数的定义位置

上一张表给的是 **step.py 的调用位置**。下面给出本项目主要函数的 **实际定义位置**，以便继续查看计算实现；没有展开这些函数内部的完整调用链。

| 在 step.py 中的名字 | 实际定义文件与行号 |
| --- | --- |
| `tp_epoch_begin` | [step.py L76–91](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:76) |
| `tp_epoch_end` | [step.py L95–100](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:95) |
| `entry_front` | [step.py L130–144](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:130) |
| `gpub` | [step.py L148–153](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:148) |
| `gwait` | [step.py L157–161](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:157) |
| `stamp（body 内局部函数）` | [step.py L294–298](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:294) |
| `fsel（front 内局部函数）` | [step.py L389–391](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:389) |
| `x8pub（front callback）` | [step.py L415–421](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:415) |
| `fptr` | [step.py L71–73](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:71) |
| `ltab` | [step.py L168–172](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:168) |
| `atab` | [step.py L181–186](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:181) |
| `lsel` | [step.py L175–178](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:175) |
| `cwith` | [step.py L126–127](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:126) |
| `LazyC` | [step.py L103–123](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:103) |
| `_ctxtab` | [step.py L164–165](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:164) |
| `iprefetch` | [step.py L189–193](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/step.py:189) |
| `stage_A` | [attention.py L180–250](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:180) |
| `stage_kv` | [attention.py L255–295](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:255) |
| `stage_C` | [attention.py L300–330](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:300) |
| `stage_D` | [attention.py L359–551](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:359) |
| `stage_E` | [attention.py L556–607](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:556) |
| `stage_F_cluster` | [attention.py L612–648](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:612) |
| `tp_allreduce` | [attention.py L653–696](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:653) |
| `pf_rows` | [attention.py L168–175](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/attention.py:168) |
| `handoff（经 attention 导入）` | [device.py L327–344](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/device.py:327) |
| `hx.wait_count` | [device.py L317–323](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/device.py:317) |
| `CX.stage_block_state` | [draft_ctx.py L149–174](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/draft_ctx.py:149) |
| `CX.draft_meta` | [draft_ctx.py L178–209](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/draft_ctx.py:178) |
| `CX.stage_tap1` | [draft_ctx.py L213–237](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/draft_ctx.py:213) |
| `ES.stage_engq` | [engram.py L41–61](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/engram.py:41) |
| `ES.stage_engkv` | [engram.py L71–122](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/engram.py:71) |
| `IS.stage_iq` | [index_query.py L46–75](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/index_query.py:46) |
| `IS.stage_iw` | [index_query.py L79–96](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/index_query.py:79) |
| `IS.stage_iquant` | [index_query.py L100–124](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/index_query.py:100) |
| `CS.stage_cgemm` | [compressor.py L50–69](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/compressor.py:50) |
| `CS.stage_crow` | [compressor.py L116–237](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/compressor.py:116) |
| `CS.stage_cring` | [compressor.py L241–260](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/compressor.py:241) |
| `SC.stage_score_any` | [index_score.py L53–168](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/index_score.py:53) |
| `TK.stage_select_any` | [topk.py L258–320](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/topk.py:258) |
| `FS.front_any` | [front.py L506–526](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/front.py:506) |
| `MS.ug_shared_early` | [moe.py L559–603](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/moe.py:559) |
| `MS.moe` | [moe.py L813–828](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/moe.py:813) |
| `MS.moe_combine` | [moe.py L386–403](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/moe.py:386) |
| `ST.target` | [tail.py L72–85](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/tail.py:72) |
| `ST.draft` | [tail.py L89–96](/home/feifei/repo/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels/tail.py:89) |

## 7. 由 ASM 接管，因而不在片段主体里的控制流

| 原 step.py | step.s 对应位置 |
| --- | --- |
| L220–223：segment 展开/类型 | L96–108、L134–138、L397–419；ASM segment=0/1，与原 kind=1/4 不同 |
| L267：layer 循环 | L171–174、L393–395 |
| L304–305 / L311–312：Engram 条件 | L182–185 / L202–205 |
| L317–319 / L330–331：indexer 外层条件 | L217–220 / L232–235 |
| L346：ibat 非空条件 | L246–249 |
| L361–362：selection 遍数和 pi 循环 | L260–280；mode/level 仍在 index_select |
| L379：hf 两遍循环 | L313–314、L370–372 |
| L380–381 / L436：front/MoE 指令预取 | L315–323 / L345–348；它们是纯 ASM，不是遗漏的 FlyDSL 块 |
| L384 / L386：front CTA 选择 | L325–326 |
| L435：仅 hf0 执行 MoE/TP2 | L338–339 |
| L452–453：tap 条件 | L378–381 |
| L458 / L466：target/draft tail 条件 | L400–419；build.py 还按可达性选择是否编译 |

每个 block 在主文件中出现一次，不等于运行时只执行一次：layer 阶段会逐层重复，front 会按 hf 重复，selection 会按 pi 重复。`.segment both` 的 block 在某些配置中还会展开两套 native 变体；有些不可达 block 在预处理时删除。

## 8. 本次核对范围

静态核对 step.s 中 43 个块的名称、行号、segment、function 引用，与 fragments.py 的 SPANS / handoff / epoch 注册全集一致；所有源码区间和函数定义链接以当前文件为依据。

这份文档描述源码映射和适配设计，不表示完整展开、LLVM 编译或 gfx1250 运行结果已经验证。相关整体说明见 [STEP_EXPLAINED.md](/home/feifei/repo/ATOM/mono_test31/STEP_EXPLAINED.md)，body 伪代码见 [step_py_pseudocode.hip.cpp](/home/feifei/repo/ATOM/mono_test31/step_py_pseudocode.hip.cpp)。
