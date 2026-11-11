# step `body` kernel 各 stage 换成 asm 的寄存器预算与绑定设计

适用对象：`atom/models/deepseek_v41/mono/gfx1250/kernels/step.py` 的 `body`（214–216 行）层循环（267 行起）内的全部 stage。
数据来自 TR=48（`--layers 2`）的构建；表格由脚本生成，见文末“复现”。

## 结论

- **VGPR：** 必须用修复版 LLVM（`/app/llvm-upstream/build`，`SIISelLowering.cpp` 补丁，补丁文件在 `/app/ATOM/mono_test11/llvm_patch/`）编译，
  这时每个 stage 的 asm 可以使用 **v1 到 v(511 − keep V)**，约 444–480 个（见表 2；v0 = 线程号 t 是输入）。
  - 上限是 v511 而不是 v1023：256 线程的 CTA 每个 wave 最多 512 个 VGPR，声明到 v1023 会让 kernel 无法启动（mono_test11 实测）。
  - 实测在 40 个入口按 stage 同时 clobber v0–v(511 − keep V)：VGPR 512，spill 11 个，scratch 20 B，和只 clobber v0–v255 时相同，PASS。
  - 全部 clobber 到 v511、一个都不留时，scratch 从 20 B 涨到 520 B（spill 710 个），说明这个上限是实打实的。
  - FlyDSL 内置的 LLVM 和 `mono_test01/build/llvm-bin` 的 llc 没有打这个补丁，仍会静默丢掉 v256 以上的 clobber，只能用到 v255。
  - 使用 v256 以上的寄存器时，asm 文本要自己用 `s_set_vgpr_msb` 切换，并在退出前恢复成 0。
  - clobber 要逐个寄存器列出：`~{v[a:b]}` 这种区间写法在补丁里仍不生效。
- **SGPR：** 可用的物理 SGPR 是 s0–s29 和 s40–s105，共 96 个（s30–s39 留给 LLVM 的栈和返回地址）。
  - attention、indexer、Engram 段要保留的 SGPR 有 37–80 个，asm 可用 **41–59 个**（按 stage 不同，见表 2）。
  - front、MoE 段要保留 95–143 个，已经超过 96，原生 kernel 本来就把一部分 SGPR spill 到 VGPR lane。asm 统一给 **30 个（s0–s29）**，超出的部分由编译器 spill 到 VGPR lane，开销很小。
  - 实测把以上预算全部同时 clobber：相比只 clobber VGPR，`v_writelane` 多 38 条、`v_readlane` 多 105 条，平均每个入口约 6 条；VGPR、SGPR、scratch 不变，PASS。
  - 作对比，96 个 SGPR 全部 clobber 时 `v_readlane` 多 1056 条。所以 SGPR 不能全占。
- **绑定：** 沿用 stage_C（P2）的约定。`v0` = t；SGPR 输入从 s0 开始，先放 64 位指针对，再放 b、w、i32 标量和一个 flags 字；trace 期常量直接写进 asm 文本。
  - 直接指针模式下，`stage_crow`（38 个输入）和 `front_any`（59 个）的输入超过预算；`front_A`、`front_E2`、`stage_score_any`、`stage_select_any` 的输入虽在预算内，但留给 asm 的临时 SGPR 不到 8 个。
  - 这些 stage 改用 **表模式**：只传 `fp`、`Ly`、`b`、`w`、`flags` 共 6 个 SGPR，asm 自己用 `s_load_b64` 读指针表，和原生 `LazyC` 的做法一样。

## 1. stage 清单（tier 1 = WMMA/GEMM 计算密集，建议替换；tier 2 = 逐元素/控制/通信，可选）

| tier | stage | 定义 | step.py 调用 | 功能 |
|---|---|---|---|---|
| 1 | `stage_A` | `attention.py:180` | 307 | x·wqkv_aᵀ（MXFP8 WMMA，N=1792 K=5120，K 两半）+ 收尾：bf16 qkv、平方和 ss、q·qnw → MXFP8 qr8/qrs |
| 1 | `stage_C` | `attention.py:300` | 316 | qr8·wq_bᵀ（MXFP8 WMMA，K=1280 N=8192）× rstd + RoPE → q（P2 已替换） |
| 1 | `stage_D` | `attention.py:359` | 367 | 稀疏注意力：K/q 异步拷 LDS，S=q·Kᵀ（bf16 WMMA）、softmax、P·V，cluster 合并 + sink + 反 RoPE → o8/os |
| 1 | `stage_E` | `attention.py:556` | 370 | wo_a 分组低秩投影（MXFP8 WMMA，K=4096/4 切片）+ cluster 相加 → y8/ys |
| 1 | `stage_F_cluster` | `attention.py:612` | 373 | wo_b 2048→5120（MXFP8 WMMA，K/4 切片）+ cluster 相加 → out + LDS[r][20] |
| 1 | `stage_iq` | `index_query.py:46` | 322 | indexer wq_b（FP8 WMMA，K=1280 N=4096）× rstd + RoPE → iq |
| 1 | `stage_iw` | `index_query.py:79` | 323 | weights_proj（bf16 WMMA，K 切片）× axn → iwp 部分和 |
| 1 | `stage_cgemm` | `compressor.py:50` | 327-328 | compressor wkv_gate × axn（WMMA）→ cpart 部分和 |
| 1 | `stage_crow` | `compressor.py:116` | 343 | 压缩计划行：部分和归约、softmax 门控、norm/RoPE、投影（WMMA）→ main KV 行 + index 行 |
| 1 | `stage_score_any` | `index_score.py:53` | 359 | indexer 打分：iq_out·index 行（FP8 WMMA）× iw，ReLU 加权 → ilog（FULL/REINDEX） |
| 1 | `stage_engkv` | `engram.py:71` | 311-314 | engkv = eng8·engwᵀ（MXFP8 WMMA，N=25600 K=6144） |
| 1 | `front_any` | `front.py:506` | 422（hf 两遍）/ 144 | 整个 mHC front（A,B,|C,D,|E1,|E2，中间 3 个 cluster 屏障） |
| 1 | `front_B` | `front.py:240` | front.py 内 | R'·fn hi/lo → mHC mixes 部分和（bf16 WMMA） |
| 1 | `front_D` | `front.py:333` | front.py 内（hf=0） | 路由 logits 部分和（gate 320 列，WMMA） |
| 1 | `ug_shared_early` | `moe.py:559` | 434 | front 闲置 CTA 先算共享专家 UG 的 K 切片（FP8 WMMA） |
| 1 | `moe_ug` | `moe.py:421` | 443 → moe.py:819 | UG：FP4×MXFP8 WMMA（路由）/ FP8×MXFP8（共享），SwiGLU → MID（MXFP8） |
| 1 | `moe_dn` | `moe.py:694` | 443 → moe.py:825 | down 投影（FP4×MXFP8 WMMA）× 路由权重 → out 部分和 |
| 1 | `moe_dn_shared` | `moe.py:773` | 443 → moe.py:827 | 共享专家 down（FP8 WMMA） |
| 2 | `stage_kv` | `attention.py:255` | 315 | kv_norm(rstd·kvnw) + RoPE + QAT(e4m3 往返) → 写 KV ring（CTA 0..11） |
| 2 | `tp_allreduce` | `attention.py:653` | 376 / 449 | TP all-reduce：bf16 打包推给 3 个对端 + 轮询求和 → y1/y2（通信） |
| 2 | `stage_iquant` | `index_query.py:100` | 332 | iw 切片求和；iq 按 amax 量化 e4m3 → iq_out/iqs_out/iw_out |
| 2 | `stage_cring` | `compressor.py:241` | 344 | 本步原始投影写 7 槽 ring（kv fp32、score+ape） |
| 2 | `stage_select_any` | `topk.py:258` | 365 | 两级选择树上的精确 top-k（基数/计数选择，非 GEMM） |
| 2 | `stage_engq` | `engram.py:41` | 304-306 | Engram embedding → MXFP8 eng8/engs |
| 2 | `front_A` | `front.py:158` | front.py:520 内 | mHC post+pre（+Engram 门控） |
| 2 | `front_C` | `front.py:283` | front.py 内 | RMSNorm×nw → MXFP8 x8/xs（+bf16 axn） |
| 2 | `front_E1` | `front.py:356` | front.py 内（hf=0） | logits 归约 + sqrtsoftplus + 本地 top-6 |
| 2 | `front_E2` | `front.py:398` | front.py 内 | 候选合并 → ids/wts；下一子层 mHC 系数（Sinkhorn） |
| 2 | `moe_union` | `moe.py:238` | 443 → moe.py:817 | 专家并集 + pick 列表（排序网络，LDS） |
| 2 | `moe_dn_stage` | `moe.py:660` | 443 → moe.py:823 | MID 读入 LDS |
| 2 | `moe_combine` | `moe.py:386` | 447 | 6 个 pick + 共享相加 → LDS[r][20] |
| 2 | `stage_tap1` | `draft_ctx.py:213` | 455 | aRout 4 路均值 → MXFP8 aux8/auxs |
| 2 | `stage_block_state` | `draft_ctx.py:149` | 232 / 260 | embedding → 4 路初始状态 |

## 2. 寄存器预算（pre-RA liveness，48 行；keep = 跨 stage 必须保留，+N = 可重物化立即数）

| stage | keep S | keep V | in S/V | out S/V | SGPR 无溢出余量 96−keepS | 推荐 asm SGPR 预算 | 输入 SGPR（直接模式） | asm 临时 SGPR | asm 可用 VGPR（修复版 LLVM） |
|---|---|---|---|---|---|---|---|---|---|
| `stage_A` | 38+58 | 18+15 | 1/1 | 9/3 | 58 | 58 | 22 | 36 | v1–v478（478） |
| `stage_C` | 50+57 | 25+15 | 2/0 | 1/0 | 46 | 46 | 21 | 25 | v1–v471（471） |
| `stage_D` | 43+57 | 24+15 | 7/1 | 3/3 | 53 | 53 | 30 | 23 | v1–v472（472） |
| `stage_E` | 43+57 | 22+15 | 5/2 | 0/6 | 53 | 53 | 16 | 37 | v1–v474（474） |
| `stage_F_cluster` | 40+57 | 16+15 | 6/7 | 1/0 | 56 | 56 | 14 | 42 | v1–v480（480） |
| `stage_iq` | 55+57 | 25+15 | 3/0 | 1/0 | 41 | 41 | 20 | 21 | v1–v471（471） |
| `stage_iw` | 51+57 | 25+15 | 5/0 | 0/0 | 45 | 45 | 8 | 37 | v1–v471（471） |
| `stage_cgemm` | 49+57 | 25+15 | 3/1 | 0/0 | 47 | 47 | 9 | 38 | v1–v471（471） |
| `stage_crow` | 68+57 | 25+15 | 2/2 | 1/2 | 28 | 30（超出部分溢出到 VGPR lane） | 38 | -8 → 表模式 24 | v1–v471（471） |
| `stage_score_any` | 70+57 | 26+15 | 9/0 | 3/4 | 26 | 30（超出部分溢出到 VGPR lane） | 24 | 6 → 表模式 24 | v1–v470（470） |
| `stage_engkv` | 47+57 | 19+15 | 1/0 | 0/0 | 49 | 49 | 12 | 37 | v1–v477（477） |
| `front_any` | 96+57 | 34+15 | 57/7 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 59 | -29 → 表模式 24 | v1–v462（462） |
| `front_B` | 142+57 | 52+15 | 5/13 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 8 | 22 | v1–v444（444） |
| `front_D` | 122+57 | 40+15 | 2/5 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 6 | 24 | v1–v456（456） |
| `ug_shared_early` | 96+57 | 34+15 | 2/19 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 10 | 20 | v1–v462（462） |
| `moe_ug` | 107+57 | 40+15 | 9/1 | 0/5 | ≤0 | 30（超出部分溢出到 VGPR lane） | 20 | 10 | v1–v456（456） |
| `moe_dn` | 101+57 | 39+15 | 4/4 | 1/4 | ≤0 | 30（超出部分溢出到 VGPR lane） | 8 | 22 | v1–v457（457） |
| `moe_dn_shared` | 97+57 | 34+15 | 5/9 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 10 | 20 | v1–v462（462） |
| `stage_kv` | 51+57 | 19+15 | 0/0 | 1/6 | 45 | 45 | 21 | 24 | v1–v477（477） |
| `tp_allreduce` | 44+57 | 21+15 | 0/0 | 0/0 | 52 | 52 | 16 | 36 | v1–v475（475） |
| `stage_iquant` | 52+57 | 26+15 | 1/0 | 0/0 | 44 | 44 | 12 | 32 | v1–v470（470） |
| `stage_cring` | 52+57 | 25+15 | 17/2 | 0/0 | 44 | 44 | 18 | 26 | v1–v471（471） |
| `stage_select_any` | 80+57 | 31+15 | 0/0 | 0/0 | 16 | 30（超出部分溢出到 VGPR lane） | 27 | 3 → 表模式 24 | v1–v465（465） |
| `stage_engq` | 37+58 | 16+15 | 1/1 | 0/0 | 59 | 59 | 8 | 51 | v1–v480（480） |
| `front_A` | 143+57 | 40+15 | 10/1 | 4/21 | ≤0 | 30（超出部分溢出到 VGPR lane） | 23 | 7 → 表模式 24 | v1–v456（456） |
| `front_C` | 124+57 | 44+15 | 19/8 | 0/1 | ≤0 | 30（超出部分溢出到 VGPR lane） | 13 | 17 | v1–v452（452） |
| `front_E1` | 117+57 | 40+15 | 5/2 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 10 | 20 | v1–v456（456） |
| `front_E2` | 96+57 | 34+15 | 21/6 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 23 | 7 → 表模式 24 | v1–v462（462） |
| `moe_union` | 113+57 | 35+15 | 5/2 | 3/6 | ≤0 | 30（超出部分溢出到 VGPR lane） | 5 | 25 | v1–v461（461） |
| `moe_dn_stage` | 105+57 | 43+15 | 1/7 | 0/0 | ≤0 | 30（超出部分溢出到 VGPR lane） | 6 | 24 | v1–v453（453） |
| `moe_combine` | 95+57 | 34+15 | 3/1 | 0/0 | 1 | 30（超出部分溢出到 VGPR lane） | 4 | 26 | v1–v462（462） |
| `stage_tap1` | 25+56 | 15+15 | 2/1 | 0/0 | 71 | 60 | 9 | 51 | v1–v481（481） |
| `stage_block_state` | 22+0 | 2+0 | 1/1 | 4/0 | 74 | 60 | 18 | 42 | v1–v509（509） |

**怎么读这张表：**

- **keep S 超过 106：** keep S 是寄存器分配前的虚拟 SGPR 数（按 32 位计），表示同时活跃、需要放在 SGPR 里的值有多少，不是物理寄存器数。超过 96 的部分由分配器处理：spill 到 VGPR lane（`v_writelane`/`v_readlane`）、重新从指针表 `s_load`，或者重新计算。分配后的物理 ISA 上，跨 stage 实际占用的 SGPR 是：stage_A 31、stage_C 37、select_any 62、front_A 92、front_B 89、moe_ug 59、moe_combine 53。这些物理数字不区分条件分支路径，偏大，只能当上界。
- **keep V 和“asm 可用 VGPR”：** keep V 是必须跨 stage 保留的 VGPR 值的个数（含立即数），不是固定在哪几个寄存器上。asm 把低端的寄存器声明为 clobber 后，分配器会把这些值挪到没被 clobber 的高端，所以 asm 可用 VGPR = 512 − keep V − 1（v0 输入），即 v1 到 v(511 − keep V)。
- **前提：** 修复版 LLVM。用 FlyDSL 内置的 LLVM 时 v256 以上的 clobber 会被丢掉，这一列要改成 v1–v255。

## 3. 输入参数与寄存器绑定（直接指针模式；v0 = t）

### `stage_A`（tier 1，22 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT SMEM TR sm stx
- 绑定：`v0`=t；`s[0:1]`=qkv；`s[2:3]`=qkv_part；`s[4:5]`=qnw；`s[6:7]`=qr8；`s[8:9]`=qrs；`s[10:11]`=ss；`s[12:13]`=wqkv；`s[14:15]`=wqkv_s；`s[16:17]`=x8；`s[18:19]`=xs；`s20`=b；`s21`=w

### `stage_C`（tier 1，21 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT stx
- 绑定：`v0`=t；`s[0:1]`=qr8；`s[2:3]`=wqb；`s[4:5]`=qrs；`s[6:7]`=wqb_s；`s[8:9]`=ss；`s[10:11]`=q；`s[12:13]`=rpos；`s[14:15]`=rcos；`s[16:17]`=rsin；`s18`=b；`s19`=w；`s20`=wave mask（MT 决定）

### `stage_D`（tier 1，30 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：QV RPC TR o sm stx
- 绑定：`v0`=t；`s[0:1]`=aml；`s[2:3]`=apart；`s[4:5]`=kmeta；`s[6:7]`=knsel；`s[8:9]`=ksel；`s[10:11]`=kv；`s[12:13]`=o8；`s[14:15]`=os；`s[16:17]`=q；`s[18:19]`=rcos；`s[20:21]`=rpos；`s[22:23]`=rsin；`s[24:25]`=sink；`s26`=b；`s27`=w；`s28`=kring_off；`s29`=scale（f32）

### `stage_E`（tier 1，16 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT TR sm stx
- 绑定：`v0`=t；`s[0:1]`=o8；`s[2:3]`=os；`s[4:5]`=woa；`s[6:7]`=woa_s；`s[8:9]`=y8；`s[10:11]`=ypart；`s[12:13]`=ys；`s14`=b；`s15`=w

### `stage_F_cluster`（tier 1，14 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT TR sm
- 绑定：`v0`=t；`s[0:1]`=opart；`s[2:3]`=out；`s[4:5]`=wob；`s[6:7]`=wob_s；`s[8:9]`=y8；`s[10:11]`=ys；`s12`=b；`s13`=w

### `stage_iq`（tier 1，20 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT stx
- 绑定：`v0`=t；`s[0:1]`=iq；`s[2:3]`=iqw；`s[4:5]`=iqws；`s[6:7]`=qr8；`s[8:9]`=qrs；`s[10:11]`=rcos；`s[12:13]`=rpos；`s[14:15]`=rsin；`s[16:17]`=ss；`s18`=b；`s19`=w

### `stage_iw`（tier 1，8 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT stx
- 绑定：`v0`=t；`s[0:1]`=axn；`s[2:3]`=iwp；`s[4:5]`=iww；`s6`=b；`s7`=w

### `stage_cgemm`（tier 1，9 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT stx
- 绑定：`v0`=t；`s[0:1]`=axn；`s[2:3]`=cpart；`s[4:5]`=cwkv；`s6`=b；`s7`=w；`s8`=flags（bit 0:r1）

### `stage_crow`（tier 1，38 个 SGPR 输入 **（超出 s0–s29，建议表模式）**）

- trace 期常量（写入 asm 文本）：sm stx
- 绑定：`v0`=t；`s[0:1]`=btab；`s[2:3]`=cape；`s[4:5]`=cknw；`s[6:7]`=ckv；`s[8:9]`=cnw；`s[10:11]`=cpart；`s[12:13]`=cplan；`s[14:15]`=cplane；`s[16:17]`=cscore；`s[18:19]`=cstate；`s[20:21]`=cwk；`s[22:23]`=kv；`s[24:25]`=rcos；`s[26:27]`=rsin；`s[28:29]`=slots；`s40`=b；`s41`=w；`s42`=bstride；`s43`=ccap；`s44`=cmain；`s45`=cprow；`s46`=crpp；`s47`=flags（bit 0:r1）

### `stage_score_any`（tier 1，24 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR sm stx
- 绑定：`v0`=t；`s[0:1]`=btab；`s[2:3]`=ibat；`s[4:5]`=ibmax；`s[6:7]`=ibound；`s[8:9]`=icand；`s[10:11]`=ilog；`s[12:13]`=iplane；`s[14:15]`=iq_out；`s[16:17]`=iw_out；`s18`=b；`s19`=w；`s20`=bstride；`s21`=ilw；`s22`=irpp；`s23`=flags（bit 0:iprod,1:isrx）

### `stage_engkv`（tier 1，12 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：MT sm stx
- 绑定：`v0`=t；`s[0:1]`=eng8；`s[2:3]`=engkv；`s[4:5]`=engs；`s[6:7]`=engw；`s[8:9]`=engws；`s10`=b；`s11`=w

### `front_any`（tier 1，59 个 SGPR 输入 **（超出 s0–s29，建议表模式）**）

- trace 期常量（写入 asm 文本）：TR hc_eps hdev ne norm_eps rk rms_eps sm topk stf
- 绑定：`v0`=t；`s[0:1]`=R；`s[2:3]`=Rout；`s[4:5]`=cand；`s[6:7]`=cands；`s[8:9]`=comb；`s[10:11]`=enggw；`s[12:13]`=engkv；`s[14:15]`=engpart；`s[16:17]`=fnh；`s[18:19]`=fnl；`s[20:21]`=gate；`s[22:23]`=gbias；`s[24:25]`=hbs；`s[26:27]`=hsc；`s[28:29]`=ids；`s[40:41]`=ncomb；`s[42:43]`=npost；`s[44:45]`=npre；`s[46:47]`=nw；`s[48:49]`=part；`s[50:51]`=plog；`s[52:53]`=post；`s[54:55]`=pre；`s[56:57]`=wts；`s[58:59]`=x8；`s[60:61]`=xn；`s[62:63]`=xs；`s[64:65]`=y；`s66`=b；`s67`=w；`s68`=flags（bit 0:eng,1:first,2:isffn,3:last,4:merge,5:xs32）

### `front_B`（tier 1，8 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：sm
- 绑定：`v0`=t；`s[0:1]`=fnh；`s[2:3]`=fnl；`s[4:5]`=part；`s6`=b；`s7`=w

### `front_D`（tier 1，6 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：ne sm topk
- 绑定：`v0`=t；`s[0:1]`=gate；`s[2:3]`=plog；`s4`=b；`s5`=w

### `ug_shared_early`（tier 1，10 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：NP sm topk
- 绑定：`v0`=t；`s[0:1]`=out；`s[2:3]`=shplane；`s[4:5]`=x8；`s[6:7]`=xs；`s8`=w；`s9`=bi

### `moe_ug`（tier 1，20 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：NP sm topk
- 绑定：`v0`=t；`s[0:1]`=mid8；`s[2:3]`=midc；`s[4:5]`=out；`s[6:7]`=s13；`s[8:9]`=shcnt；`s[10:11]`=shplane；`s[12:13]`=w13；`s[14:15]`=x8；`s[16:17]`=xs；`s18`=b；`s19`=w

### `moe_dn`（tier 1，8 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：NP sm topk
- 绑定：`v0`=t；`s[0:1]`=out；`s[2:3]`=s2；`s[4:5]`=w2；`s6`=b；`s7`=w

### `moe_dn_shared`（tier 1，10 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：NP dn8_bi dn8_nct sm topk
- 绑定：`v0`=t；`s[0:1]`=mid8；`s[2:3]`=midc；`s[4:5]`=out；`s[6:7]`=shplane；`s8`=b；`s9`=w

### `stage_kv`（tier 2，21 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR stx
- 绑定：`v0`=t；`s[0:1]`=kv；`s[2:3]`=kvn；`s[4:5]`=kvnw；`s[6:7]`=kvw；`s[8:9]`=qkv；`s[10:11]`=rcos；`s[12:13]`=rpos；`s[14:15]`=rsin；`s[16:17]`=ss；`s18`=b；`s19`=w；`s20`=kring_off

### `tp_allreduce`（tier 2，16 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR rank sm
- 绑定：`v0`=t；`s[0:1]`=tpout；`s[2:3]`=ytgt；`s[4:5]`=recv0；`s[6:7]`=recv1；`s[8:9]`=recv2；`s[10:11]`=recv3；`s12`=b；`s13`=w；`s14`=region；`s15`=tag

### `stage_iquant`（tier 2，12 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR stx
- 绑定：`v0`=t；`s[0:1]`=iq；`s[2:3]`=iq_out；`s[4:5]`=iqs_out；`s[6:7]`=iw_out；`s[8:9]`=iwp；`s10`=b；`s11`=w

### `stage_cring`（tier 2，18 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：stx
- 绑定：`v0`=t；`s[0:1]`=cape；`s[2:3]`=ckv；`s[4:5]`=cpart；`s[6:7]`=cscore；`s[8:9]`=cstate；`s[10:11]`=slots；`s[12:13]`=wplan；`s14`=b；`s15`=w；`s16`=wcap；`s17`=flags（bit 0:r1）

### `stage_select_any`（tier 2，27 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR sm stx nlev
- 绑定：`v0`=t；`s[0:1]`=btab；`s[2:3]`=ibat；`s[4:5]`=ibmax；`s[6:7]`=ibound；`s[8:9]`=icand；`s[10:11]`=ilog；`s[12:13]`=irow；`s[14:15]`=isel；`s[16:17]`=lvl；`s18`=b；`s19`=w；`s20`=bstride；`s21`=cprow；`s22`=ilw；`s23`=imain；`s24`=irpp；`s25`=lev；`s26`=mode

### `stage_engq`（tier 2，8 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR stx
- 绑定：`v0`=t；`s[0:1]`=eng8；`s[2:3]`=engemb；`s[4:5]`=engs；`s6`=b；`s7`=w

### `front_A`（tier 2，23 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：TR hdev rk sm
- 绑定：`v0`=t；`s[0:1]`=R；`s[2:3]`=Rout；`s[4:5]`=comb；`s[6:7]`=enggw；`s[8:9]`=engkv；`s[10:11]`=engpart；`s[12:13]`=part；`s[14:15]`=post；`s[16:17]`=pre；`s[18:19]`=y；`s20`=b；`s21`=w；`s22`=flags（bit 0:eng,1:first,2:last）

### `front_C`（tier 2，13 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：hdev norm_eps sm
- 绑定：`v0`=t；`s[0:1]`=nw；`s[2:3]`=part；`s[4:5]`=x8；`s[6:7]`=xn；`s[8:9]`=xs；`s10`=b；`s11`=w；`s12`=flags（bit 0:xs32）

### `front_E1`（tier 2，10 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：ne topk
- 绑定：`v0`=t；`s[0:1]`=cand；`s[2:3]`=cands；`s[4:5]`=gbias；`s[6:7]`=plog；`s8`=b；`s9`=w

### `front_E2`（tier 2，23 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：hc_eps hdev ne rms_eps sm topk
- 绑定：`v0`=t；`s[0:1]`=cand；`s[2:3]`=cands；`s[4:5]`=hbs；`s[6:7]`=hsc；`s[8:9]`=ids；`s[10:11]`=ncomb；`s[12:13]`=npost；`s[14:15]`=npre；`s[16:17]`=part；`s[18:19]`=wts；`s20`=b；`s21`=w；`s22`=flags（bit 0:merge）

### `moe_union`（tier 2，5 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：NP sm topk
- 绑定：`v0`=t；`s[0:1]`=ids；`s[2:3]`=wts；`s4`=w

### `moe_dn_stage`（tier 2，6 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：NP sm topk
- 绑定：`v0`=t；`s[0:1]`=mid8；`s[2:3]`=midc；`s4`=b；`s5`=w

### `moe_combine`（tier 2，4 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：topk TR sm_out
- 绑定：`v0`=t；`s[0:1]`=out；`s2`=b；`s3`=w

### `stage_tap1`（tier 2，9 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：T
- 绑定：`v0`=t；`s[0:1]`=aux8；`s[2:3]`=auxs；`s[4:5]`=src；`s6`=b；`s7`=w；`s8`=j

### `stage_block_state`（tier 2，18 个 SGPR 输入）

- trace 期常量（写入 asm 文本）：B W
- 绑定：`v0`=t；`s[0:1]`=R；`s[2:3]`=aid；`s[4:5]`=comb；`s[6:7]`=emb；`s[8:9]`=noise；`s[10:11]`=post；`s[12:13]`=pre；`s[14:15]`=y；`s16`=b；`s17`=w

## 4. 表模式（输入 SGPR 太多的 stage）

原生 kernel 的指针本来就不常驻 SGPR，每次使用都从 `fp` 指针表重新 `s_load_b64`（`fptr` / `atab` / `ltab`，step.py:71/181/168）。asm 也可以照做：

| 寄存器 | 内容 |
|---|---|
| `v0` | t |
| `s[0:1]` | fp（kernel 参数） |
| `s2` | Ly（层号，`scf.for` 的归纳变量） |
| `s3` | b |
| `s4` | w |
| `s5` | flags（r1 / isrx / iprod / isf / first / last / eng / merge / xs32 等，按 stage 定义 bit） |
| `s[6:7]`、`s[8:9]` … | 表里没有、要在调用处算出的值（见下） |

表内地址（FPTRS 78 项，ATAB 38 项，LKEYS 71 项）：

- `fptr(name)` = `fp + FPTRS.index(name)·8`，例：cpart 432、axn 272、fx8 112、x8 552；
- `atab(name)` = `fp + (78 + ATAB.index(name))·8`，例：kv 688、x8 624、ss 776（ss 还要加 `Ly·SS_LAYER_F32·4`）；
- `ltab(Ly, name)` = `fp + 928 + Ly·568 + LKEYS.index(name)·8`。asm 先算一次 `s_mul_i32 sX, s2, 568`，例：rcos 216、rsin 224、cnw 304、cape 312、cwk 320、cknw 328、cplan 336、ccap 352、cmain 368、crpp 376、cprow 384、cplane 392、ckv 400、cscore 408、cstate 416、btab 424、bstride 432、slots 440。`ccap` 这类 i32 取 64 位表项的低 32 位。

调用处要额外算好再传入的值：

- `front_any`：`xn`（最后一层改写到 `xh` 或 tp 表里的 `dh`）放 `s[6:7]`；`lc = cnt + Ly·LCB` 放 `s[8:9]`，给 `x8pub` 的计数器用。`fsel`/`lsel` 和 `x8`/`xs` 的二选一由 asm 根据 flags 里的 isf 位自己完成。
- `tp_allreduce`：`tep & 1` 放 `s6`（`recv` 要加 `(tep&1)·RECV_HALF`）；`region`、`tag` 放 `s7`、`s8`。
- `stage_select_any`：`lev`、`mode` 放 `s6`、`s7`。
- `stage_crow`、`stage_score_any`：不需要额外值。

读出来的指针放在 asm 自己的临时 SGPR 里（预算内），按需重读，不跨 stage 保留。表模式每个 stage 只需要 6–9 个输入 SGPR。

## 5. 替换时的其它约束

1. **trace 期常量要做成多份文本：** `TR`/`MT`/`RPC`/`QV`/`NP`/`topk`/`ne` 在 target 段和 draft 段不同（TR 与 TRD，FS.NE/TOPK 与 DRAFT_NE/TOPK）。同一个 stage 在两个段各需要一份 asm 文本，或者把这些量改成 SGPR 输入。
2. **不能改写输入寄存器：** inline asm 的输入寄存器不能出现在 clobber 列表里。要改写就先拷到临时寄存器，或者声明为 tied output。stage_C 的片段没有改写任何输入。
3. **LDS 约定：** asm 只能使用本 stage 的 LDS 区域，以下跨 stage 的 LDS 状态不能破坏：
   - TP payload `[TR][20] f32`，LDS 0..4095：F 或 combine 写入，tp_allreduce 读取，front 不得覆盖；
   - `RKEEP`（294912 起）：两个 front 之间保留的残差流；
   - front 和 MoE 的工作区从 `FRONT_LDS`（4096）开始；moe_union 写入的并集和 pick 列表要保留到 ug、dn 用完；moe_dn_stage 读入 LDS 的 MID 由 moe_dn 读取。
4. **同步留在哪里：** handoff、`gpub`/`gwait`、`pf_rows`、`iprefetch` 在调用处，不属于 stage，保持不动。stage 内部的 `cluster_sync`（A、D、E、F、front 子步骤之间）要在 asm 里自己实现。front 若按子步骤 B、D 分别替换，子步骤之间的 cluster 屏障仍在 Python 侧。
5. **退出前的等待：** LLVM 的 waitcnt pass 看不到 asm 内部的 store，asm 退出前必须执行 `s_wait_xcnt 0` 和 `s_wait_storecnt 0`（stage_C 已这样做）。如果 asm 内部有 LDS 写，后面 Python 代码可能直接读，这时还要加 `s_wait_dscnt 0`。
6. **hazard：** 规则同 stage_C 的 README：WMMA → VALU 之间 4 个 `v_nop`；TRANS 指令（`v_rcp`/`v_rsq`/`v_exp`…）之后如果紧接着读它的结果，要插 `v_nop`。

## 6. 方法与误差

- **keep / in / out：** 在每个 stage 调用前后插空 inline asm 标记（`budget/probe_build.py`），取 FlyDSL 的 LLVM IR，用 `opt -O3` 和 `llc -O3 -mcpu=gfx1250 -stop-before=greedy` 得到寄存器分配前的 MIR，再用 `budget/liveness.py` 按 32 位 lane 计算活跃区间。
  - keep = 进入时活跃 ∩ 离开时活跃，即跨 stage 必须保留的寄存器；
  - in = 进入时活跃 − 离开时活跃，即 stage 消耗的输入；out 反过来，是 stage 产生的输出；
  - +N 是 `s_mov`/`v_mov` 立即数，可以重新物化，不计入保留成本。
- **误差：**
  - 这是寄存器分配前的数字。独立运行的 llc 得到 336 个 VGPR，FlyDSL 带标记构建得到 364 个，二者有出入，表里的数字只能当近似。
  - 物理 ISA 上的活跃分析（`isa_liveness.py`）不区分路径，相关条件分支下的定义和使用会被高估，只能作为上界：attention 段 V 70–87、front/MoE 段 V 37–116。
  - 最终以 clobber 实测为准，见下表。

| 构建（40 个入口同时 clobber） | VGPR | SGPR | scratch B | writelane | readlane | scratch st/ld | 指令数 |
|---|---|---|---|---|---|---|---|
| 只插标记 | 364 | 105 | 20 | 58 | 68 | 4/11 | 26690 |
| v0–v255 | 364 | 105 | 20 | 58 | 68 | 9/63 | 27650 |
| v0–v255 + s0–s15 | 364 | 105 | 20 | 76 | 140 | 9/63 | 27720 |
| v0–v255 + s0–s29 | 364 | 105 | 20 | 94 | 122 | 9/63 | 27714 |
| v0–v255 + s40–s71 | 364 | 105 | 20 | 99 | 148 | 9/63 | 27893 |
| **v0–v255 + 表 2 推荐预算（逐 stage）** | 364 | 105 | 20 | 96 | 173 | 9/63 | 27886 |
| v0–v255 + 全部 96 个 SGPR | 368 | 106 | 20 | 335 | 1124 | 9/64 | 29448 |

以上构建全部通过 mono 检查（`build/budget/result48_*.json`）。

以上几行用的是 FlyDSL 内置的 LLVM（v256 以上的 clobber 不生效）。

**v256 以上的 clobber：修复版和未修复版对比（2026-11-11）**

最小用例 `build/budget/clob_test/c.ll` 声明了 `~{v100},~{v255},~{v256},~{v300},~{v511},~{v700},~{v1023}`。经 `finalize-isel` 之后：

- `/app/llvm-upstream/build/bin/llc`（LLVM 24.0.0git，带补丁）：7 个 clobber 全部保留为 implicit-def。
- `mono_test01/build/llvm-bin/llc`（AMD LLVM 23.0.0git，未打补丁）：只剩 `$vgpr100` 和 `$vgpr255`。FlyDSL 内置的 LLVM 表现相同：clobber 扩到 v1023，ISA 也和 v255 时完全一样。

mono 带标记构建，修复版 LLVM（`PYTHONPATH=/app/flydsl_overlay`，`FLYDSL_COMPILE_LLVM_DIR=/app/llvm-upstream/build`，`FLYDSL_COMPILE_LLVM_HANDOFF=llvm`）：

| 40 个入口同时 clobber | VGPR | VGPR spill | scratch B | scratch st/ld | 指令数 |
|---|---|---|---|---|---|
| 只插标记 | 364 | 4 | 20 | 4/11 | 26793 |
| v0–v255 | 364 | 11 | 20 | 9/63 | 27763 |
| v0–v447 | 512 | 11 | 20 | 9/63 | 27756 |
| **逐 stage v0–v(511 − keep V)（表 2）** | 512 | 11 | 20 | 9/63 | 27759 |
| v0–v511（一个都不留） | 512 | 710 | 520 | 360/797 | 29097 |

全部 PASS（运行内检查：数值有限，同一次运行内重复执行逐位一致）。digest 每次运行都会变，内置 LLVM 下也是这样，所以不做跨构建比较。

## 复现

```bash
cd /app/ATOM/mono_test_single12
# 带标记构建（PROBE_CLOBBER=v|vs，PROBE_SGPRS=a-b，PROBE_SGPR_MAP=build/budget/sgpr_map.json）
FLYDSL_RUNTIME_ENABLE_CACHE=0 FLYDSL_DUMP_IR=1 FLYDSL_DUMP_DIR=$PWD/build/budget/dump48 PYTHONPATH=/app/ATOM \
  python3 budget/probe_build.py --layers 2 --repeat 1 --out build/budget/result48.json
# 用修复版 LLVM 做 v256 以上的 clobber 实测（PROBE_VMAX=n，或 PROBE_VGPR_MAP=build/budget/vgpr_map.json 逐 stage）
PYTHONPATH=/app/flydsl_overlay:/app/ATOM FLYDSL_COMPILE_LLVM_DIR=/app/llvm-upstream/build FLYDSL_COMPILE_LLVM_HANDOFF=llvm \
  FLYDSL_RUNTIME_ENABLE_CACHE=0 FLYDSL_DUMP_IR=1 FLYDSL_DUMP_DIR=$PWD/build/budget/dump48_fix_vmap \
  PROBE_VGPR_MAP=build/budget/vgpr_map.json python3 budget/probe_build.py --layers 2 --repeat 1 --out build/budget/result48_fix_vmap.json
# 寄存器分配前的 liveness（pre48.mir 由 opt/llc 从 dump48 的 21_llvm_ir.ll 生成）
python3 budget/liveness.py build/budget/pre48.mir --json build/budget/live48.json
# 各 stage 读取的字典 key，以及本文的表格
python3 budget/stage_inputs.py --json build/budget/stage_inputs.json
python3 budget/bind_design.py build/budget/stage_inputs.json build/budget/live48.json > build/budget/bind_tables.md
```
