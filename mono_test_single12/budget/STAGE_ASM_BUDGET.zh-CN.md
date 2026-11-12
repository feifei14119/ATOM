# step `body` kernel 各 stage 换成 asm 的寄存器预算与绑定设计

适用对象：`atom/models/deepseek_v41/mono/gfx1250/kernels/step.py` 的 `body`（214–216 行）层循环（267 行起）内的全部 stage。

数据来自 `gprtool/`（2026-11-11）：TR=48、`--layers 2` 的构建，修复版 LLVM（`/app/llvm-upstream/build`）编译。寄存器数取自寄存器分配之后的 MIR（`llc -O2 -stop-before=prolog-epilog`），也就是分配器自己的活跃信息，不是分配前的估算。分析结论在 GPU 上做了运行时验证。工具用法见 `gprtool/README.zh-CN.md`，复现命令见文末。

## 结论

- **VGPR：** 17 个计算密集 stage 同时换成 asm 时，每个 asm 可用 **463–502 个 VGPR**，即 `v1–v255` 加上 `v257–v(511 − 保留数)`。
  - `v0` 是线程号 t，只读。
  - `v256` 存放编译器溢出 SGPR 的 lane，asm 不能碰。
  - 上限是 v511：声明到 v511 时 kernel 的 VGPR 数是 512，能正常运行并通过检查；声明到 v767 时 VGPR 数变成 768，启动报 `hipErrorLaunchOutOfResources`。原因是 256 线程的 CTA 必须放进一个 SIMD 的 VGPR 堆。v1023 可以编译，但无法启动。
- **SGPR：** 每个 asm 可用 **7–79 个 SGPR**（含可改写的输入），按 stage 差别很大（见表 2）。
  - 物理上可分配的是 s0–s101 和 s104，共 102 个。另外 wave32 下 `vcc_hi` 也是一个普通 SGPR，编译器会往里面放值。
  - 预留的是：s32（栈指针）、s102:s103（长跳转）、s105（EXEC 拷贝）、m0。旧版文档里"s30–s39 留给 LLVM"的说法是错的。
  - front、MoE 段 SGPR 很紧：`front_B` 第 2 次调用时，asm 只有自己的 7 个输入 SGPR（s0–s6）可用；`front_D` 有 24 个，`moe_ug` 有 36 个。
  - 约束：SGPR 溢出不能占用新的 VGPR。实测替换后承载 SGPR 溢出的仍只有 v256 一个寄存器，SGPR↔VGPR lane 指令数从 75 增加到 83（容差 16）。
- **asm 必须遵守的三条规则（不遵守会出错，都已实测）：**
  1. **用到的寄存器全部逐个声明为 clobber。** post-RA 调度器会把与 asm 没有寄存器依赖的 ALU 指令跨过 asm 移动，`sideeffect` 挡不住。在 MIR 里本来已经"死"了的寄存器，到最终 ISA 里可能在 asm 之后才被读。不声明就写，GPU 访存直接出错。区间写法 `~{v[a:b]}` 不生效，必须写成 `~{v1},~{v2},…`。
  2. **自己管理 VGPR MSB。** asm 没有 VGPR 操作数时，编译器不会在 asm 前把 MSB 复位，入口处的 bank 是任意的，写 `v5` 可能实际写到 `v261`。而且 asm 结束后编译器假定 MSB 没变。正确做法：
     ```
     s_getreg_b32  sT, hwreg(HW_REG_WAVE_MODE, 12, 8)   // 入口：保存 MODE[19:12]
     s_set_vgpr_msb 0x0                                  // 显式设置自己的 bank
     ...                                                 // 访问 v256+ 前 s_set_vgpr_msb 0x40 等
     s_setreg_b32  hwreg(HW_REG_WAVE_MODE, 12, 8), sT   // 出口：恢复
     s_nop 0                                             // 紧跟 MODE setreg 的 s_set_vgpr_msb 会被硬件丢弃
     ```
     即使只用 v0–v255 也要这样做：只写 v0–v255、不处理 MSB 的毒化实验同样崩溃。
  3. **`exec`、`m0`、v0，以及表 2 中没列为可 clobber 的 `vcc_lo`/`vcc_hi`/`scc`，退出时必须保持原值。**
- **绑定：** `v0` = t（只读）；SGPR 输入从 s0 开始，64 位指针按偶数对齐优先放，然后是 32 位标量。SGPR 输入以 tied output 形式声明（`={s0},…,{s0}`），所以 asm 可以改写它们。trace 期常量（MT、TR、sm、w 等）直接写进 asm 文本。

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
| 1 | `front_B` | `front.py:240` | front.py 内 | R'·fn hi/lo → mHC mixes 部分和（bf16 WMMA） |
| 1 | `front_D` | `front.py:333` | front.py 内（hf=0） | 路由 logits 部分和（gate 320 列，WMMA） |
| 1 | `ug_shared_early` | `moe.py:559` | 434 | front 闲置 CTA 先算共享专家 UG 的 K 切片（FP8 WMMA） |
| 1 | `moe_ug` | `moe.py:421` | 443 → moe.py:819 | UG：FP4×MXFP8 WMMA（路由）/ FP8×MXFP8（共享），SwiGLU → MID（MXFP8） |
| 1 | `moe_dn` | `moe.py:694` | 443 → moe.py:825 | down 投影（FP4×MXFP8 WMMA）× 路由权重 → out 部分和 |
| 1 | `moe_dn_shared` | `moe.py:773` | 443 → moe.py:827 | 共享专家 down（FP8 WMMA） |
| 2 | `front_any` | `front.py:506` | 422（hf 两遍）/ 144 | 整个 mHC front（A,B,\|C,D,\|E1,\|E2，中间 3 个 cluster 屏障）；按子步骤 B、D 替换 |
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

## 2. 寄存器预算（tier 1 的 17 个 stage 同时替换成 asm）

`gprtool contract`：每个 tier 1 stage 的调用都换成一条 inline asm，输入按第 3 节绑定，其余 clobber 按本表声明。表中数字来自最终构建：VGPR 512 个，VGPR scratch 指令 9 条（只溢出线程号 t：存 1 次，在 8 个 stage 入口读回），SGPR↔VGPR lane 指令 83 条（替换但不声明 clobber 时是 75 条），承载 SGPR 溢出的仍只有 v256。

| stage | 跨 asm 保留 V / S | 保留窗口 V / S | 最终构建跨 asm 活跃 V / S | asm 可用 VGPR | asm 可用 SGPR（含输入） | 可 clobber 的特殊寄存器 |
|---|---|---|---|---|---|---|
| `stage_A` | 17 / 35 | 18 / 35 | 15 / 26 | **493**：`v[1:255] v[257:494]` | **67**：`s[0:31] s[33:67]` | `vcc_lo` `scc` |
| `stage_engkv` | 14 / 36 | 15 / 36 | 12 / 28 | **496**：`v[1:255] v[257:497]` | **66**：`s[0:31] s[33:66]` | `vcc_lo` `scc` |
| `stage_C` | 15 / 33 | 16 / 33 | 13 / 29 | **495**：`v[1:255] v[257:496]` | **69**：`s[0:31] s[33:69]` | `vcc_lo` |
| `stage_iq` | 15 / 33 | 16 / 39 | 13 / 29 | **495**：`v[1:255] v[257:496]` | **63**：`s[0:31] s[33:63]` | `vcc_lo` |
| `stage_iw` | 15 / 29 | 16 / 35 | 13 / 25 | **495**：`v[1:255] v[257:496]` | **67**：`s[0:31] s[33:67]` | `vcc_lo` |
| `stage_cgemm` | 15 / 27 | 16 / 33 | 13 / 23 | **495**：`v[1:255] v[257:496]` | **69**：`s[0:31] s[33:69]` | `vcc_lo` `scc` |
| `stage_crow` | 17 / 42 | 18 / 48 | 14 / 41 | **493**：`v[1:255] v[257:494]` | **54**：`s[0:31] s[33:54]` | `vcc_lo` `scc` |
| `stage_score_any` | 14 / 52 | 15 / 64 | 12 / 48 | **496**：`v[1:255] v[257:497]` | **38**：`s[0:31] s[33:38]` | `vcc_lo` `scc` |
| `stage_D` | 16 / 26 | 17 / 32 | 14 / 21 | **494**：`v[1:255] v[257:495]` | **70**：`s[0:31] s[33:70]` | `vcc_lo` `scc` |
| `stage_E` | 22 / 31 | 23 / 37 | 20 / 26 | **488**：`v[1:255] v[257:489]` | **65**：`s[0:31] s[33:65]` | `vcc_lo` `scc` |
| `stage_F_cluster` | 14 / 23 | 15 / 23 | 12 / 18 | **496**：`v[1:255] v[257:497]` | **79**：`s[0:31] s[33:79]` | `vcc_lo` `scc` |
| `front_B`（第 1 次） | 8 / 37 | 9 / 43 | 8 / 31 | **502**：`v[1:255] v[257:503]` | **59**：`s[0:31] s[33:59]` | `vcc_hi` |
| `front_B`（第 2 次） | 47 / 87 | 48 / 95 | 45 / 86 | **463**：`v[1:255] v[257:464]` | **7**：`s[0:6]` | 无 |
| `front_D` | 40 / 72 | 41 / 78 | 37 / 71 | **470**：`v[1:255] v[257:471]` | **24**：`s[0:23]` | `vcc_lo` `scc` |
| `ug_shared_early` | 33 / 47 | 34 / 59 | 30 / 46 | **477**：`v[1:255] v[257:478]` | **43**：`s[0:31] s[33:43]` | `vcc_lo` `scc` |
| `moe_ug` | 34 / 60 | 35 / 66 | 32 / 59 | **476**：`v[1:255] v[257:477]` | **36**：`s[0:31] s[33:36]` | `vcc_lo` `scc` |
| `moe_dn` | 33 / 54 | 34 / 60 | 31 / 53 | **477**：`v[1:255] v[257:478]` | **42**：`s[0:31] s[33:42]` | `vcc_lo` `scc` |
| `moe_dn_shared` | 33 / 48 | 34 / 60 | 30 / 47 | **477**：`v[1:255] v[257:478]` | **42**：`s[0:31] s[33:42]` | `vcc_lo` `scc` |

**怎么读这张表：**

- **跨 asm 保留：** 替换后、不声明 clobber 时（R0），寄存器分配器在这个 asm 之后仍要用的物理寄存器个数，不含预留寄存器、v0 和 asm 的输出。这是物理寄存器数，不会超过硬件数量。15 个左右的 VGPR 是整个 kernel 都在用的立即数常量，理论上可以重算，但实测把它们排除出窗口后，编译器选择溢出到 scratch（130 条指令），所以窗口里保留了它们。
- **保留窗口：** asm 不能碰的寄存器，即编译器跨 asm 存放值的地方：VGPR 是 v256 加上 v511 往下的若干个，SGPR 是 s104 和 s101 往下的若干个。窗口按"保留数 + 余量"搜索得到，余量尽量为 0，只在不加余量会导致新溢出的点保留。最终 VGPR 余量全部为 0（窗口 = 保留数 + v256），SGPR 在部分点保留了 +6 或 +12（`front_B` 第 2 次调用是 +8，因为再大就要占用输入寄存器）。
- **最终构建跨 asm 活跃：** 按本表声明 clobber 后，编译器实际跨 asm 保留的个数，都不超过窗口。
- **asm 可用：** 除窗口、预留寄存器、v0 以外的所有寄存器。SGPR 一列包含 asm 的输入寄存器（可改写）。`vcc_hi` 能否 clobber 单独列出。
- **适用范围：** 这是 17 个 stage **同时**替换时的数字。只替换其中一部分时，`gprtool contract --replace …` 会重新求解，结果通常更宽松。

**tier 2 和未替换 stage 的参考：** 下表是原生 kernel（不替换任何 stage）在每个 stage 入口和出口的活跃寄存器数（分配后 MIR，不含预留寄存器）。以后要替换其中某个 stage，用 `gprtool contract --replace <stage> …` 求解。

| 插入点 | 入口活跃 V / S | 出口活跃 V / S | 贯穿 stage V / S | 其中立即数常量 V / S |
|---|---|---|---|---|
| `stage_block_state` | 2 / 16 | 1 / 20 | 1 / 16 | 0 / 0 |
| `front_A`（第 1 次） | 19 / 48 | 22 / 41 | 3 / 36 | 0 / 0 |
| `front_any`（第 1 次） | 17 / 48 | 0 / 10 | 0 / 10 | 0 / 0 |
| `front_B`（第 1 次） | 23 / 40 | 9 / 35 | 9 / 35 | 0 / 0 |
| `front_C`（第 1 次） | 9 / 35 | 5 / 23 | 5 / 23 | 0 / 0 |
| `front_E2`（第 1 次） | 5 / 23 | 0 / 10 | 0 / 10 | 0 / 0 |
| `stage_engq` | 17 / 27 | 16 / 27 | 16 / 27 | 15 / 7 |
| `stage_A` | 19 / 30 | 22 / 33 | 19 / 27 | 15 / 7 |
| `stage_engkv` | 19 / 32 | 19 / 31 | 19 / 31 | 15 / 6 |
| `stage_kv` | 19 / 35 | 25 / 36 | 19 / 35 | 15 / 6 |
| `stage_C` | 25 / 36 | 25 / 35 | 25 / 34 | 15 / 6 |
| `stage_iq` | 25 / 41 | 25 / 40 | 25 / 39 | 15 / 6 |
| `stage_iw` | 25 / 40 | 25 / 35 | 25 / 35 | 15 / 6 |
| `stage_cgemm` | 26 / 35 | 25 / 33 | 25 / 33 | 15 / 6 |
| `stage_iquant` | 26 / 36 | 26 / 36 | 26 / 36 | 15 / 6 |
| `stage_crow` | 27 / 54 | 27 / 53 | 25 / 52 | 15 / 6 |
| `stage_cring` | 27 / 53 | 25 / 36 | 25 / 36 | 15 / 6 |
| `stage_score_any` | 26 / 60 | 30 / 53 | 26 / 51 | 15 / 6 |
| `stage_select_any` | 31 / 60 | 31 / 60 | 31 / 60 | 15 / 6 |
| `stage_D` | 25 / 34 | 26 / 26 | 24 / 25 | 15 / 6 |
| `stage_E` | 24 / 30 | 27 / 25 | 22 / 25 | 15 / 6 |
| `stage_F_cluster` | 23 / 28 | 16 / 23 | 16 / 22 | 15 / 6 |
| `tp_allreduce`（第 1 次） | 21 / 26 | 21 / 26 | 21 / 26 | 15 / 6 |
| `front_any`（第 2 次） | 59 / 100 | 34 / 44 | 34 / 44 | 15 / 6 |
| `front_A`（第 2 次） | 59 / 100 | 62 / 94 | 40 / 90 | 15 / 6 |
| `front_B`（第 2 次） | 65 / 94 | 52 / 89 | 52 / 89 | 15 / 6 |
| `front_C`（第 2 次） | 52 / 89 | 45 / 72 | 44 / 72 | 15 / 6 |
| `front_D` | 45 / 72 | 40 / 70 | 40 / 70 | 15 / 6 |
| `front_E1` | 42 / 70 | 40 / 65 | 40 / 65 | 15 / 6 |
| `front_E2`（第 2 次） | 40 / 65 | 34 / 44 | 34 / 44 | 15 / 6 |
| `ug_shared_early` | 53 / 46 | 34 / 44 | 34 / 44 | 15 / 6 |
| `moe_union` | 36 / 66 | 41 / 64 | 35 / 61 | 15 / 6 |
| `moe_ug` | 41 / 64 | 45 / 55 | 40 / 55 | 15 / 6 |
| `moe_dn_stage` | 48 / 54 | 43 / 53 | 43 / 53 | 15 / 6 |
| `moe_dn` | 43 / 53 | 43 / 49 | 39 / 49 | 15 / 6 |
| `moe_dn_shared` | 43 / 49 | 34 / 45 | 34 / 45 | 15 / 6 |
| `moe_combine` | 35 / 45 | 34 / 43 | 34 / 43 | 15 / 6 |
| `tp_allreduce`（第 2 次） | 34 / 43 | 34 / 43 | 34 / 43 | 15 / 6 |
| `stage_tap1` | 16 / 18 | 15 / 17 | 15 / 17 | 15 / 6 |

原生 kernel 的预留寄存器是 s32、s102、s103、s105、v256、v257（两个 SGPR 溢出 lane），溢出为 SGPR→lane 58 条、lane→SGPR 64 条、VGPR scratch 存 4 条、取 11 条。

## 3. 输入参数与寄存器绑定

由 `gprtool` 的 replace 构建生成（`build/gpr/c_r0/bind.json`）。`v0` 只读；SGPR 是 tied 输入，asm 可以改写。trace 期常量写进 asm 文本。

| stage | 绑定 | 输入 SGPR 数 |
|---|---|---|
| `stage_A` | `qkv=s[0:1]` `qkv_part=s[2:3]` `qnw=s[4:5]` `qr8=s[6:7]` `qrs=s[8:9]` `ss=s[10:11]` `wqkv=s[12:13]` `wqkv_s=s[14:15]` `x8=s[16:17]` `xs=s[18:19]` `b=s20` `t=v0` | 21 |
| `stage_engkv` | `eng8=s[0:1]` `engkv=s[2:3]` `engs=s[4:5]` `engw=s[6:7]` `engws=s[8:9]` `b=s10` `t=v0` | 11 |
| `stage_C` | `q=s[0:1]` `qr8=s[2:3]` `qrs=s[4:5]` `rcos=s[6:7]` `rpos=s[8:9]` `rsin=s[10:11]` `ss=s[12:13]` `wqb=s[14:15]` `wqb_s=s[16:17]` `b=s18` `t=v0` | 19 |
| `stage_iq` | `iq=s[0:1]` `iqw=s[2:3]` `iqws=s[4:5]` `qr8=s[6:7]` `qrs=s[8:9]` `rcos=s[10:11]` `rpos=s[12:13]` `rsin=s[14:15]` `ss=s[16:17]` `b=s18` `t=v0` | 19 |
| `stage_iw` | `axn=s[0:1]` `iwp=s[2:3]` `iww=s[4:5]` `b=s6` `t=v0` | 7 |
| `stage_cgemm` | `axn=s[0:1]` `cpart=s[2:3]` `cwkv=s[4:5]` `b=s6` `r1=s7` `t=v0` | 8 |
| `stage_crow` | `btab=s[0:1]` `cape=s[2:3]` `cknw=s[4:5]` `ckv=s[6:7]` `cnw=s[8:9]` `cpart=s[10:11]` `cplan=s[12:13]` `cplane=s[14:15]` `cscore=s[16:17]` `cstate=s[18:19]` `cwk=s[20:21]` `kv=s[22:23]` `rcos=s[24:25]` `rsin=s[26:27]` `slots=s[28:29]` `b=s30` `bstride=s31` `ccap=s33` `cmain=s34` `cprow=s35` `crpp=s36` `r1=s37` `t=v0`（跳过预留的 s32） | 37 |
| `stage_score_any` | `btab=s[0:1]` `ibat=s[2:3]` `ibmax=s[4:5]` `ibound=s[6:7]` `icand=s[8:9]` `ilog=s[10:11]` `iplane=s[12:13]` `iq_out=s[14:15]` `iw_out=s[16:17]` `b=s18` `bstride=s19` `ilw=s20` `iprod=s21` `irpp=s22` `isrx=s23` `t=v0` | 24 |
| `stage_D` | `aml=s[0:1]` `apart=s[2:3]` `kmeta=s[4:5]` `knsel=s[6:7]` `ksel=s[8:9]` `kv=s[10:11]` `o8=s[12:13]` `os=s[14:15]` `q=s[16:17]` `rcos=s[18:19]` `rpos=s[20:21]` `rsin=s[22:23]` `sink=s[24:25]` `b=s26` `kring_off=s27` `scale=s28` `t=v0` | 29 |
| `stage_E` | `o8=s[0:1]` `os=s[2:3]` `woa=s[4:5]` `woa_s=s[6:7]` `y8=s[8:9]` `ypart=s[10:11]` `ys=s[12:13]` `b=s14` `t=v0` | 15 |
| `stage_F_cluster` | `opart=s[0:1]` `out=s[2:3]` `wob=s[4:5]` `wob_s=s[6:7]` `y8=s[8:9]` `ys=s[10:11]` `b=s12` `t=v0` | 13 |
| `front_B` | `fnh=s[0:1]` `fnl=s[2:3]` `part=s[4:5]` `b=s6` `t=v0` | 7 |
| `front_D` | `gate=s[0:1]` `plog=s[2:3]` `b=s4` `t=v0` | 5 |
| `ug_shared_early` | `out=s[0:1]` `shplane=s[2:3]` `x8=s[4:5]` `xs=s[6:7]` `bi=s8` `t=v0` | 9 |
| `moe_ug` | `mid8=s[0:1]` `midc=s[2:3]` `out=s[4:5]` `s13=s[6:7]` `shcnt=s[8:9]` `shplane=s[10:11]` `w13=s[12:13]` `x8=s[14:15]` `xs=s[16:17]` `b=s18` `t=v0` | 19 |
| `moe_dn` | `out=s[0:1]` `s2=s[2:3]` `w2=s[4:5]` `b=s6` `t=v0` | 7 |
| `moe_dn_shared` | `mid8=s[0:1]` `midc=s[2:3]` `out=s[4:5]` `shplane=s[6:7]` `b=s8` `t=v0` | 9 |

输入 SGPR 多的 stage（`stage_crow` 37 个、`stage_D` 29 个、`stage_score_any` 24 个）也可以改用第 4 节的表模式，把输入压到 6–9 个，多出来的 SGPR 给 asm 当临时寄存器。

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

读出来的指针放在 asm 自己的临时 SGPR 里，按需重读，不跨 stage 保留。

## 5. 替换时的其它约束

1. **trace 期常量要做成多份文本：** `TR`/`MT`/`RPC`/`QV`/`NP`/`topk`/`ne` 在 target 段和 draft 段不同（TR 与 TRD，FS.NE/TOPK 与 DRAFT_NE/TOPK）。同一个 stage 在两个段各需要一份 asm 文本，或者把这些量改成 SGPR 输入。
2. **输入和 clobber：** inline asm 的输入寄存器不能同时出现在 clobber 列表里（编译器按 early-clobber 处理）。要改写输入，就把它声明为 tied output（本工具对 SGPR 输入就是这样做的）。v0（t）整个 kernel 都要用，必须只读。
3. **LDS 约定：** asm 只能使用本 stage 的 LDS 区域，以下跨 stage 的 LDS 状态不能破坏：
   - TP payload `[TR][20] f32`，LDS 0..4095：F 或 combine 写入，tp_allreduce 读取，front 不得覆盖；
   - `RKEEP`（294912 起）：两个 front 之间保留的残差流；
   - front 和 MoE 的工作区从 `FRONT_LDS`（4096）开始；moe_union 写入的并集和 pick 列表要保留到 ug、dn 用完；moe_dn_stage 读入 LDS 的 MID 由 moe_dn 读取。
4. **同步留在哪里：** handoff、`gpub`/`gwait`、`pf_rows`、`iprefetch` 在调用处，不属于 stage，保持不动。stage 内部的 `cluster_sync`（A、D、E、F、front 子步骤之间）要在 asm 里自己实现。front 若按子步骤 B、D 分别替换，子步骤之间的 cluster 屏障仍在 Python 侧。
5. **退出前的等待：** LLVM 的 waitcnt pass 看不到 asm 内部的 store，asm 退出前必须执行 `s_wait_xcnt 0` 和 `s_wait_storecnt 0`（stage_C 已这样做）。如果 asm 内部有 LDS 写，后面 Python 代码可能直接读，这时还要加 `s_wait_dscnt 0`。
6. **hazard：** 规则同 stage_C 的 README：WMMA → VALU 之间 4 个 `v_nop`；TRANS 指令（`v_rcp`/`v_rsq`/`v_exp`…）之后如果紧接着读它的结果，要插 `v_nop`。
7. **长跳转寄存器：** 替换成空 asm 时代码很小，编译器不会预留 s102:s103；换成真实 asm 后代码变大，会重新预留（原生 kernel 就预留了）。本表已按预留处理，asm 不要用 s102、s103。

## 6. 方法与验证

`gprtool/gprtool.py` 的四个子命令（细节见 `gprtool/README.zh-CN.md`）：

- **analyze：** 在每个 stage 调用前后插一条不带操作数的 inline asm 标记，所以寄存器分配和原生 kernel 完全相同（VGPR 364，溢出条数一致）。FlyDSL 把 bitcode 交给修复版 llc，工具用同一条 llc 命令加 `-stop-before=prolog-epilog` 取分配后的 MIR，从每个基本块的 `liveins`（带 lane mask）往回推，得到每个标记处的活跃物理寄存器。
  - 早期版本的标记带一个 VGPR 输入，会扰动分配（VGPR scratch 读取从 11 条变成 69 条），已经改掉。
- **verify（GPU）：** 在 78 个标记处把分析判为"死"的寄存器全部写成 `0xDEAD0000 + n`，同时逐个声明为 clobber，再和 golden 对比。
  - 结果：25967 次 VGPR 写、4423 次 SGPR 写；kernel 自检通过，相对 golden 的 rel L2 为 xh 0.034、aRout 0.041、kv_rows 0.127，在噪声范围内（不毒化的运行对 golden：xh/aRout 0.02–0.06，kv_rows 0.10–0.20）。
  - 负对照：在 `stage_E` 入口把 26 个活跃 VGPR 也一起毒化，GPU 访存出错（rc −6）。
  - 这个过程中发现了结论里的规则 1 和规则 2：不声明 clobber 时有 16 个点出错（post-RA 调度跨 asm 移动了指令），声明了但不处理 MSB 时 v0–v255 的毒化也出错。
- **contract：** 17 个 tier 1 stage 同时换成 asm（输入按第 3 节绑定），先编译一次不声明 clobber 的版本（R0），取每个 asm 之后仍活跃的物理寄存器个数作为保留数。然后按"保留数 + 余量"把窗口放在寄存器堆顶部，其余全部声明 clobber，搜索最小余量。判据有三条：
  1. 承载 SGPR 溢出的 WWM VGPR 不能多于 R0（硬约束）；
  2. SGPR↔lane 指令数不超过 R0 + 16；
  3. VGPR scratch 指令数不超过 R0 + 16。

  搜索顺序是先找全局 SGPR 余量（结果 12），再找全局 VGPR 余量（结果 2），最后逐点尝试收回余量（VGPR 全部收回到 0）。共编译 58 次，约 15 分钟。
  - 窗口直接取 R0 中跨 asm 的那组寄存器反而更差（SGPR lane 指令 109 条，还多占一个 WWM VGPR），因为贪心分配器不会照搬 R0 的解。
  - 不加余量时 SGPR 溢出会多 40 条左右，主要出现在原生代码区：SGPR 的分配本来就接近饱和，原生 kernel 也在溢出到 lane。
- **limit（GPU）：** 在 `stage_E` 入口声明 clobber v1–v(n−1)。n=512 时 VGPR 数为 512，通过；n=768 时 VGPR 数为 768，`hipErrorLaunchOutOfResources`。n=1024 没来得及跑：GPU 驱动卡死了，测试进程停在 D 状态，需要管理员复位。

旧版本文档用的是寄存器分配前的虚拟寄存器估算（keepS 会超过 106），已被本表取代。修复版和未修复版 LLVM 处理 v256 以上 clobber 的对比如下（最小用例 `build/budget/clob_test/c.ll` 声明 `~{v100},~{v255},~{v256},~{v300},~{v511},~{v700},~{v1023}`）：

- `/app/llvm-upstream/build/bin/llc`（LLVM 24.0.0git，带 `SIISelLowering.cpp` 补丁，补丁文件在 `/app/ATOM/mono_test11/llvm_patch/`）：7 个 clobber 全部保留。
- `mono_test01/build/llvm-bin/llc` 和 FlyDSL 内置 LLVM（未打补丁）：只剩 v100 和 v255，v256 以上被静默丢掉。

| 40 个入口同时 clobber（修复版 LLVM） | VGPR | VGPR spill | scratch B | scratch st/ld | 指令数 |
|---|---|---|---|---|---|
| 只插标记 | 364 | 4 | 20 | 4/11 | 26793 |
| v0–v255 | 364 | 11 | 20 | 9/63 | 27763 |
| v0–v447 | 512 | 11 | 20 | 9/63 | 27756 |
| v0–v511（一个都不留） | 512 | 710 | 520 | 360/797 | 29097 |

## 复现

```bash
cd /app/ATOM/mono_test_single12
python3 gprtool/gprtool.py analyze            # 原生 kernel 的活跃寄存器 -> build/gpr/analyze.json（约 20 s）
python3 gprtool/gprtool.py contract           # 17 个 stage 替换后的预算 -> build/gpr/contract.json（约 15 min）
HIP_VISIBLE_DEVICES=1 python3 gprtool/gprtool.py verify   # GPU 毒化验证 -> build/gpr/verify.json（约 2 min）
HIP_VISIBLE_DEVICES=1 python3 gprtool/gprtool.py limit    # 可声明的 VGPR 上限 -> build/gpr/limit.json
python3 gprtool/report.py > build/gpr/report.md          # 本文表 2、表 3 的 markdown
```
