# gfx1250 DS V4.1：以 ASM 编写 Mono step 主体

本例分析并改写 [step.py](../atom/models/deepseek_v41/mono/gfx1250/kernels/step.py) 的**调度主体**。ASM 负责入口、参数加载、指针表寻址、target/draft 的层循环、条件分支和阶段顺序；原 FlyDSL 计算阶段及同步 helper 用显式 `PSEUDO_FLYDSL` 伪调用表示。

基线：2026-11-11，本地 ATOM 提交 `a4fa4e095aa02db074a6c71a8eaeb03e53338a3d`。生成物的 manifest 另外记录实际读取源码的 SHA256。

**这不是已完成算子移植、能输出 token 的 kernel。** 可离线汇编为带 trap 占位的 code object，以检查真实 ASM 指令、descriptor、metadata 和 host kernarg 是否一致。没有实现 FlyDSL 调用 ABI，没有运行 GPU，没有加载模型，也没有修改原始 ATOM/AITER 代码。

## 文件与阅读顺序

| 文件 | 内容 |
|---|---|
| [step_asm.s](step_asm.s) | 主要示例：完整调度顺序和中文注释；建议首先阅读 |
| [pseudo_calls.inc](pseudo_calls.inc) | 伪调用、按需 scalar table load、counter address 和 handoff 宏 |
| [host_example.py](host_example.py) | 参考 AITER 的 module load / cluster launch；主要 host 步骤及详细注释 |
| [contract.py](contract.py) | 72-byte 显式 kernarg；从原源码提取表布局和 LDS 数值，不导入 GPU 模块 |
| [build_example.py](build_example.py) | 仅离线汇编/链接，生成常量、metadata、反汇编和 manifest |

## 1. 原始 step 的主链

gfx1250 这份代码包含的范围比 gfx950 每层 K1/K2 更大：

~~~text
tp_epoch_begin
  → target embedding / block_state
  → layer0 entry attention front
  → target layer0 … layer39
  → target head / 四卡 sampling / verification
       └─ draft context KV 工作交错在 sampling exchanges 中
  → draft metadata / anchor + noise block_state
  → draft0 entry attention front
  → draft layer0 … layer2
  → draft head / 四卡 Markov
  → tp_epoch_end
~~~

`step.build(part="all")` 可以把上述内容放在**一次 launch** 中。当前 [runner.py](../atom/models/deepseek_v41/mono/gfx1250/runner.py) 的 `prepare` / `launch` 实际使用：

~~~text
host 本步准备
  → launch(part="target")：target entry / 40 层 / target tail（含 CTX）
  → record verify-ready event
  → launch(part="draft")：draft entry / 3 层 / draft tail
~~~

这样 host 可等待第一个 launch 的 verdict，而第二个 launch 继续运行。本例支持 all/target/draft 三种编译配置。两次 launch 各执行一次 epoch begin/end；不能以“一个生成 step”为理由只推进一次 epoch。

## 2. 为什么需要两遍 front

原代码不是简单重复：

~~~text
attention front → attention body → FFN front → MoE
~~~

它将相邻层的 front 接起来：

~~~text
entry:
  attention_front(layer0)

layer Ly:
  A → kv → C → [index/compress/select] → D → E → F
  → TP1，输出 y1
  → hf=0: 本层 FFN front（mHC / norm / router）
  → MoE → combine → TP2，输出 y2
  → hf=1: 下一层 attention front
  → layer-end handoff
  → 可选 tap
~~~

最后一层的 hf=1 改为产生 target 的 `xh` 或 draft 的 `dh`，供 head 使用。`LKEYS[Ly]` 中的 `a*` 权重已经由 host 填为下一层 front 所需权重；ASM 再错误地读取 `LKEYS[Ly+1].a*` 会跳过一层。

ASM 中 `.Llayer` / `.Lfront_loop` 是真实分支和循环。为了展示简洁性，target/draft 共享一份 ASM 调度代码，通过 `s43` 和 `s45` 告知占位 adapter 当前 segment/shape。原 FlyDSL 按 segment trace 出各自的 body；未来实际设备算子仍需按 target/draft shape 分别适配，不能将 target 6 行实现当成 draft 5 行实现直接使用。

本例省略了原主体的 profiling 时间戳写入，以及 `iprefetch` 指令缓存预取调优；数据预取位置用伪调用标出。它展示计算与同步的控制结构，不代表保留了原 kernel 的性能。rank 仍是构建常量 `BUILD_RANK`，供未来的 TP/tail adapter 使用，不额外添加一个 host 参数。

## 3. 每层的完整条件路径

| 原始步骤 | ASM 中的位置 / 伪调用 |
|---|---|
| 下一层 Engram embedding quant | `engram_stage_engq` |
| WQKV 前投影与 latent 处理 | `attention_stage_A` |
| 下一层 Engram KV 投影 | `engram_stage_engkv` |
| KV norm/RoPE/ring，WQ_B/RoPE | `attention_stage_kv`、`attention_stage_C` |
| index query/head weights | `index_stage_iq`、`index_stage_iw` |
| compressor GEMM | `compressor_stage_cgemm` |
| index query quant，压缩行/ring | `index_stage_iquant`、`compressor_stage_crow/cring` |
| index score / 分层 top-k | `index_stage_score_any`、`.Lselect` |
| 稀疏 attention | `attention_stage_D` |
| WO_A / WO_B cluster | `attention_stage_E`、`attention_stage_F_cluster` |
| TP1 与列组发布 | `attention_tp_allreduce_1`、`step_gpub` |
| FFN front / 下一层 attention front | `front_any_with_x8pub` |
| 空闲 CTA 提前做 shared UG（宽批次） | `wait_x8_and_ug_shared_early` |
| expert union / UG / down | `moe_union_ug_down`，内部仍有 UG→down handoff |
| combine / TP2 / 列组发布 | `moe_combine_into_lds_payload`、`attention_tp_allreduce_2` |
| layer-end / tap | `HANDOFF LY_LAYER_END`、`draft_ctx_stage_tap1` |

`lflags` 分支保持原语义：

- bit1：有 compressor；bit2：ratio1。
- bit3：有 indexer；bit5：产生 candidate blocks；bit6：REINDEX。
- bit4：该迭代末尾写 DSpark tap。
- bit7：**下一层**有 Engram，在本迭代提前准备并由 hf=1 使用。

注意 tap 的迭代编号：此处 `Ly=36/37/38` 末尾导出数据，因为 hf=1 刚完成 layer37/38/39 的 attention front；不能机械改成在 Ly=37/38/39 导出同一个 `aRout`。

selection 的 pass 数是原来的两层树：普通 FULL/REINDEX 两次；candidate producer 再做两次 block selection，共四次。每个 pass 使用独立 `SELECT0 + pi*4` counter。

## 4. ASM 如何读取原参数

沿用 `body(recv0, recv1, recv2, recv3, cnt, st, scale, fp, tp)` 的逻辑参数，但**显式定义本示例自己的 kernarg 二进制布局**：

| 偏移 | 类型 / 内容 | 进入主体后的位置 |
|---:|---|---|
| 0 / 8 / 16 / 24 | 四个 receive buffer 地址 | 按需从 kernarg 重新读，应用 epoch parity |
| 32 | cnt 地址 | s38:s39 |
| 40 | st 地址 | s58:s59 |
| 48 | float scale | s57 的 32-bit bits |
| 52 | 4 字节 padding | 不读取 |
| 56 | fp 地址 | s34:s35 |
| 64 | tp 地址 | s36:s37 |

总计 72 字节、8-byte 对齐。`StepArgs`、descriptor、metadata 三处一致。host 不给 s34:s35 直接赋值：host 填 kernarg，硬件给 ASM kernarg 指针，ASM 再把 fp 加载到选定寄存器。

`fp` 继续使用现有 `StepTables.fptab`：

~~~text
fp
 ├─ FPTRS：78 个 8-byte slots
 ├─ ATAB：38 个 8-byte slots
 └─ LKEYS rows：每行 71 个 8-byte slots
      row0…39：target layer
      row40…42：draft layer
      row43：draft entry front
      row44：target entry front
~~~

当前 layer row 起址：

~~~text
fp + 928 + Ly * 568
~~~

这些 slot 中既有指针，也有 `lflags/kring/ccap` 等以 64-bit slot 存放的数值。不要把每个 slot 都再解引用成指针。

`LOAD_FP` / `LOAD_AT` / `LOAD_LAYER` 对应原 `fptr/atab/ltab`。例如：

~~~asm
LOAD_LAYER s[0:1], wqkv
LOAD_LAYER s[2:3], wqkv_s
LOAD_AT    s[4:5], x8
LOAD_AT    s[6:7], xs
PSEUDO_FLYDSL attention_stage_A
~~~

这里只展示四项显式输入；A 的其他 buffer、norm weights、ss 等仍由 adapter 按表取出。`c` 原本是 trace-time Python dict/LazyC，不是运行时可以直接传指针的 C struct。本设计用 `fp + 当前 row + 循环值 + LDS offsets` 表示其视图，不要求 host 在每个 stage 调用前额外写一个 global 参数结构。

## 5. 寄存器与 LDS 如何保持

本例将少量调度状态固定在 `s32:s59` 和 `v63`，并在源文件开头列出每个寄存器含义。

**这只是 ASM 主体的自定义约定，不是编译器自动执行的约束。** 将来 adapter 必须保留这些值，或由 ASM 主体在调用前显式保存并在返回后恢复。若被调 ASM 会覆盖这些寄存器，仅仅写一行注释不能保证正确；需要实际的寄存器分配/保存方案。标准 device ABI 的 s32 等另有用途，不能直接套用本例地图。

伪调用返回时还必须恢复 EXEC；SCC/VCC 视为临时状态，主体在需要分支时重新比较。不能把 stage 内的 `s_endpgm` 当成返回。

LDS 则保持原来的生命周期：

| 区域 | 偏移 | 用途 |
|---|---:|---|
| TP payload | 0 | TP reduction payload，front 期间保留 |
| Front/MoE scratch | 4096 | 这些阶段自己的 LDS 工作区 |
| Residual keep | 294912 | front 之间保留四路 residual |

当前配置 `RKEEP + RK_BYTES = 315904` 字节，是例子动态 LDS 下界。生成器用原 attention/head/front/MoE 的公式取最大值，并同时考虑 target/draft 行数。不能把保存调度状态的额外 LDS 随意塞入这些已有区域。

当前 trap 壳的 64 VGPR / 60 SGPR / 0 private 仅说明**壳本身**。接入真实阶段后必须重新计算整个 kernel 的 VGPR/SGPR、private/stack、LDS、named barrier 以及 cluster 相关要求。不能拿壳的 descriptor 宣称最终 kernel 无 spill。

## 6. 为什么同步也保留为显式设备伪调用

`handoff` 本身就是原始 FlyDSL helper，因此也属于本例尚未导出的设备代码。其调用点、counter 地址、hdev 参数已明确写在 ASM。

原 `hx.handoff(hdev=True)` 的生产者 exchange store 使用 device scope；各 wave drain stores，CTA 同步，thread0 发布 counter 并等待 256 个 CTA，最后再 CTA 同步。`hdev=False` 还保留 release/acquire fence。

以下三种同步不能混用：

- CTA barrier：一个 CTA 的 8 个 wave。
- cluster barrier：16 个 CTA 的硬件 cluster；一些阶段使用其子组协作。
- device handoff / peer wait：256 个 CTA 或跨 GPU，使用 global counters / receive tags。

`gpub/gwait` 是列组级交接，front CTA 只等对应 16 个 TP CTA。把它们全部替换成 grid barrier 会改变原调度；只替换成 `s_barrier` 则无法保证正确性。

跨 CTA 的 global 发布/读取还要保留作用域及 cache 可见性；不能以 scalar table load 的实现去轮询可变 counter。保留 timeout/cyc 报告，并确保所有参与的 CTA/cluster 可以常驻，否则全网格自旋可能等待永远无法被调度的生产者。

## 7. Host 主要步骤

[host_example.py](host_example.py) 直接引用 [AITER asm_utils.py](../../aiter/aiter/ops/asm/asm_utils.py) 的真实接口：

~~~text
原 ATOM 模型、TP4、cache、StepTables、peer mappings 准备
  → 选择 rank/TR/part 对应的最终 .co
  → get_function：hipModuleLoad + hipModuleGetFunction，准备阶段缓存
  → 原本的本步更新、Engram staging join、cnt 清零一次
  → StepArgs 打包九个逻辑参数
  → current_raw_stream
  → launch_co_cluster
       grid=(256,1,1)
       block=(256,1,1)
       cluster_dim=(16,1,1)
       shared_mem=本例计算的动态 LDS
  → 同 stream 消费 outtok/verdict/mids，或用 event 跨 stream
~~~

AITER 内部使用 `hipDrvLaunchKernelEx` 和 `hipLaunchAttributeClusterDimension`。不能将其换成缺少 cluster 属性的普通 launch，然后期待原 cluster 阶段保持行为。

所有 TP ranks 应各自提交工作，不可等待 rank0 完成后才启动 rank1。peer 地址必须是**在当前进程已映射、当前 GPU 可访问**的 VA；不能仅把另一个进程的 `tensor.data_ptr()` 数值发过来就使用。

保留 StepTables / scratch / cache / peer owner 的生命周期。不要每步清零 `tpep`、probability draft 的 `qlog/qids` 等持久状态。split target/draft 之间不再次清 cnt；原 kernel 负责 receive parity。

## 8. 离线检查

从任意目录执行：

~~~bash
python3 -B /home/feifei/repo/ATOM/mono_test21/build_example.py
python3 -B /home/feifei/repo/ATOM/mono_test21/host_example.py
~~~

默认构建 rank0、target 6 行 / draft 5 行、part=all。也可以查看 split 和宽批次配置：

~~~bash
python3 -B /home/feifei/repo/ATOM/mono_test21/build_example.py --part target
python3 -B /home/feifei/repo/ATOM/mono_test21/build_example.py --part draft
python3 -B /home/feifei/repo/ATOM/mono_test21/build_example.py --rows 48 --rank 3
~~~

每个配置输出到自己的 `build/{part}_r{rank}_t{rows}/`：

- `step_constants.inc`：从原代码提取的 table/counter 偏移。
- `step_metadata.inc`：host-visible kernel metadata。
- `step.syntax.o`：可重定位汇编目标。
- `step.syntax.co`：链接后的语法检查 code object。
- `step.disasm.txt` / `step.notes.txt`：反汇编和 metadata/symbols。
- `manifest.json`：配置、源码摘要、资源下界及“未实现算子”的标记。

伪调用被明确编译为 `s_trap 2; s_endpgm`，而不是空实现。host 的 `load_ready_kernel` / `launch_prepared` 会拒绝这种产物；它们的后半段展示真正接好后如何调用 AITER。不要通过手动更改 manifest 来执行占位代码。

下一步真正接入时，需要落实的是这些伪调用的设备代码及资源/上下文契约；主体的循环、分支、参数入口与 host launch 接缝已经具体化在本目录。

本次检查结果：all/target/draft 的 rank0、TR=6 构建，以及 all 的 rank3、TR=48 构建均通过本机 ROCm LLVM 的离线汇编和链接；Python 语法、kernarg 的实际 bytes/offset 和占位产物拒绝执行路径已做 CPU 检查。尚未验证 HIP module load、真实设备阶段调用、驻留/cluster 行为、数值结果或性能。
