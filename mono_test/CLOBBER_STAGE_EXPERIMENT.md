# 非末尾 ASM 阶段覆盖全部通用寄存器：方案与真机实验

记录日期：2026-11-09。实验代码在 [clobber/](clobber/)，本机环境为 ROCm 7.2、RX 7900 XTX、gfx1100、wave32。

本报告的完整内容已合并到[二进制接入与跨阶段状态管理综合文档](BINARY_STAGE_INTEGRATION.md)第 9–18 节；第 19 节统一对照前后四种已实现方式。

## 1. 要解决的问题

目标是将 ASM `.co` 中的算子放入 Mono 的中间阶段：算子可能改写全部通用寄存器，执行后 Mono 还要继续计算，甚至再次进入 ASM 算子。

这不能仅靠把 call 改成 branch 解决。需要明确三个问题：

1. 后续仍需使用的值存在哪里？
2. 所有 GPR 都变了之后，怎样重新找到上下文和当前任务？
3. 如何在相同 wave/CTA 中继续执行，而不是由算子的 `s_endpgm` 提前结束？

本实验实现并比较：

| 版本 | 跨阶段状态处理 | 结果 |
| --- | --- | --- |
| `mono_unsafe` | 只保护安全继续执行所需的指针和编号，不保护活跃计算值 | 稳定复现错误，作为负对照 |
| `mono_preserve` | 保存、恢复活跃值和控制状态到每线程 private/scratch | 正确 |
| `mono_phase` | 阶段边界不保留 GPR 状态，从显式内存状态重建下一阶段 | 正确，private scratch 为 0 |

三个版本都没有 `s_getpc_b64`、`s_swappc_b64` 或 `s_setpc_b64`。每个 Mono 有两个 ASM 阶段和唯一的最终 `s_endpgm`。

## 2. 对 ATOM 的直接判断

### 2.1 推荐方向

对于当前 ATOM Mono，更适合继续推进 **阶段边界显式化 + 内存状态 + 少量保留 LDS 上下文** 的方向。

这意味着在阶段切换处结束寄存器中间值的生命周期，把真正需要传递的任务状态或结果放入约定的内存位置。下一阶段重新加载参数、逻辑线程编号和任务状态，允许前一个 ASM 阶段使用全部 GPR。

如果某些昂贵结果必须保留，也只保存这些活跃结果，不必因为算子覆盖了 256 个 VGPR，就保存全部 256 个 VGPR。

### 2.2 为什么 private/scratch 保存方案不能直接用于当前 ATOM

当前代码中有一个实际限制，而不仅是性能偏好：

- [atom/mono/runtime/widths.py](../atom/mono/runtime/widths.py) 的 `WidthBuilds._scratch_free()` 拒绝 private scratch 非零的构建。
- [DeepSeek v4.1 Mono runner](../atom/models/deepseek_v41/mono/runner.py) 确实使用了 `WidthBuilds`。
- 代码中的理由是：持久化 kernel 需要所有相关 CTA 驻留，private scratch 的分配可能导致部分 CTA 先运行并等待其余 CTA。

因此，`mono_preserve` 的实验成功证明状态能够恢复，但不意味着它可以绕过当前 ATOM 的检查直接使用。

这里的 **private scratch** 是 ELF metadata 中的 `.private_segment_fixed_size`。ATOM 参数里名为 `scratch` 的显式全局工作缓冲区是另一回事；把阶段结果放入后者，不等于启用编译器的 private scratch。

### 2.3 ATOM 已有合适的概念边界，但还需要接入工作

[layer_post.py](../atom/models/deepseek_v41/mono/kernels/layer_post.py) 在同一 CTA 上依次执行 `run_attn_post()` 和 `run_moe()`，使用 LDS union，并在阶段间使用 barrier。这提供了设计显式阶段接口的起点。

但它当前的 `ca`、`cb`、参数和临时量是编译器管理的值，不能默认认为这些值在一个破坏全部 GPR 的二进制块之后仍然有效。真正接入时，需要把跨边界值转为显式上下文，或让编译器/后端正确处理该边界的破坏集合。

[execution.py](../atom/mono/plan/execution.py) 当前描述的是 MI355X、256 个 CTA、每 CTA 512 个线程、wave64 的模型。本文真机验证是 gfx1100、每 CTA 128 个线程、wave32。这里验证的是机制，尚未完成 MI355X 或实际 ATOM 算子的接入。

## 3. 供应方确实交付独立 ASM `.co`

[clobber/stage.s](clobber/stage.s) 是一个有 descriptor 和 metadata、可单独通过 HIP module 启动的汇编 kernel。它生成：

```text
build/clobber/stage.co
```

它的计算本身很简单：

```text
dst[blockIdx.x * 128 + threadIdx.x] = src[...] - 1
```

为了覆盖问题的关键条件，这个算子还会：

- 使用并覆盖自己的完整 512 字节 LDS 区域，包含块内 barrier。
- 在计算、存储完成之后，将 `v0–v255` 全部写为 0。
- 将 `s0–s105` 全部写为 0。
- 将 `VCC_LO`、`EXEC_LO` 和 `SCC` 改为 0。
- 最后执行独立 kernel 的 `s_endpgm`。

这覆盖了本机可用的全部编号 VGPR 和 SGPR。它不等于覆盖 GPU 所有特殊硬件状态；实验没有改写 FP MODE、trap 状态等所有特殊寄存器。

[stage_contract.json](clobber/stage_contract.json) 记录接口，包括架构、wave/block 大小、参数位置、内存占用、破坏集合和出口条件。它不是算子实现源码。

消费方 [generate.py](clobber/generate.py) 只读取 `.co` 和契约，按 ELF 符号取出函数机器码，移除末尾的 4 字节 `s_endpgm`，将保留的 1560 字节放到 Mono 中。每个版本放入两份，在相应位置用普通 branch 转入后继代码。

三种版本共包含六份相同的算子体。[verify.py](clobber/verify.py) 检查六份机器码字节均与供应方一致，还检查覆盖每个 GPR 的指令确实存在。

## 4. 不是尾部特例：完整测试流水线

每次 Mono launch 执行下面的流水线，同一个 `.co` 被使用两次：

```mermaid
flowchart LR
    A[Mono 前段：生成活跃状态] --> B[ASM 1：tmp1 = x - 1；覆盖全部 GPR]
    B --> C[恢复或重建状态；Mono 中段继续计算]
    C --> D[ASM 2：tmp2 = tmp1 - 1；覆盖全部 GPR]
    D --> E[恢复或重建状态；Mono 后段写出结果]
```

具体计算为：

```text
前段：live = 2*x + 3，scalar = blockIdx.x + 17
ASM 1：tmp1 = x - 1
中段：live += tmp1，scalar += 1
ASM 2：tmp2 = tmp1 - 1
后段：out = tmp2 + live + scalar

最终：out = 4*x + blockIdx.x + 18
```

`live` 和 `scalar` 在保存/恢复方案中分别放在 `v8` 和 `s8`，两个 ASM 阶段都会覆盖它们。另设 VCC、SCC 状态，检查后继代码看到的状态；EXEC 必须重新变为完整 wave，才能继续加载和同步。

测试 kernel 的参数是六个指针：`x`、`tmp1`、`tmp2`、`out`、`state`、`flags`。前两个指针直接对应 ASM 1 的参数；将 kernarg 指针前移 8 字节后，前两个参数就变成 `tmp1`、`tmp2`，对应 ASM 2。

本例因此也明确演示了：分支进入独立 kernel 的代码时，需要由外层准备它原本期待的入口寄存器和参数布局。原 descriptor 不会因为 branch 而自动生效。

## 5. 方案 A：保存并恢复活跃上下文

### 5.1 保存什么

`mono_preserve` 使用每线程 private 内存，固定分配 64 字节，实际使用下面 36 字节：

| 每线程字节偏移 | 保存内容 |
| --- | --- |
| 0、4 | 原始 Mono kernarg 指针 |
| 8 | 原逻辑 `threadIdx.x` |
| 12 | `blockIdx.x` |
| 16 | 活跃 VGPR `v8` |
| 20 | 活跃 SGPR `s8` |
| 24 | `VCC_LO` |
| 28 | 通过 `s_cselect` 捕获的 SCC |
| 32 | 原 `EXEC_LO` |

这里保存的是跨阶段活跃状态，不是所有被破坏的寄存器。为保持实验简单，uniform 的 SGPR 和标志也按每线程重复保存；实际实现可考虑每 wave 只存一份。

当前保存集合由 `clobber/generate.py::save_private()` 手工指定：外层汇编也是本脚本生成的，因此可以逐项确认后续使用。`s9` 保存的是进入保存流程时捕获的 SCC，不是原 `s9` 的独立活跃值。当前没有自动分析 ATOM 或任意调用方二进制的寄存器活跃性，也没有求出最小保存集合。将这一手工约定推广为明确的阶段 ABI，见[综合文档第 20 节](BINARY_STAGE_INTEGRATION.md#bounded-boundary-state)。

### 5.2 全部 GPR 都坏了，怎样找到保存区

在 gfx1100 上，恢复入口先执行：

```asm
s_mov_b32 exec_lo, -1
s_mov_b64 s[10:11], src_private_base
v_mov_b32 v20, 0
v_mov_b32 v21, s11
; 使用 v[20:21] 指向的 private aperture 地址读取上下文
```

`src_private_base` 是硬件提供的 special source，不依赖某个通用寄存器跨阶段保留。每线程 private 地址相同，但对应各线程自己的保存区。

因此，这条恢复路径不需要在 ASM 中保留一个 GPR 作为指针锚点。前提是 private 内存及相关硬件状态仍按约定可用，ASM 没有破坏保存区。

### 5.3 前提与成本

本例以完整 wave、完整 128 线程 CTA 进入阶段边界。恢复入口先启用整个 wave，是这个约定下的操作，不能直接推广到任意分歧控制流、部分有效线程或提前退出的 kernel。

当前算子 private scratch 为 0，因此不会占用本实验的保存区。若算子自身使用 private 内存，必须把上下文放在不重叠的范围，并正确扩大最终 private segment；仅修改 metadata 并不会自动隔离两个使用者。

保存/恢复 36 字节意味着每个阶段边界每线程有 72 字节逻辑 private 读写，两次边界为 144 字节，还不计其他访存。真实成本与缓存、调度和活跃状态规模有关。本实验没有进行性能计时。

这个方案适合验证正确性或需要保留原线程状态的场合，但当前 ATOM 的 private-scratch-free 检查不接受它。

## 6. 方案 B：阶段边界从内存重建，private scratch 为 0

### 6.1 不保存寄存器身份

`mono_phase` 不要求 `v8`、`s8` 等寄存器内容跨 ASM 存活：

- 计算的 `live` 放到显式全局 `state` 数组。
- `tmp1`、`tmp2` 本来就是阶段间的全局内存结果。
- 标量调度值从 CTA 编号和当前阶段重新计算。
- VCC/SCC 是边界之外不再活跃的状态，按后继阶段需要重新建立，而非恢复旧硬件标志。

这要求从程序语义上划清阶段边界。不是在现有任意机器指令位置插入一个算子，然后期待周围的寄存器自动恢复。

### 6.2 在 LDS 保留最小 CTA 上下文

供应方使用 LDS `[0, 512)`。外层在其后保留 32 字节，使最终 LDS 为 544 字节：

| LDS 字节偏移 | 内容 |
| --- | --- |
| 512、516 | 原始 Mono kernarg 指针 |
| 520 | CTA 编号 |
| 524 | 阶段重建时使用的 wave ticket 计数器 |
| 528–543 | 当前未使用的保留空间 |

这些是整个 CTA 的 uniform 信息，任意 wave 都能从固定 LDS 偏移读取，不需要先知道自己原来的 wave 编号。

算子必须遵守自己的 LDS 使用范围。这里的 metadata 和契约用于布局，并不是为二进制提供了内存隔离；一个越界写 LDS 的算子仍能破坏外层上下文。

### 6.3 丢失线程编号后如何继续

外层无需恢复原来的物理 wave 对应关系。它可以在完整 CTA 边界重新分配逻辑工作编号：

1. 用标量指令恢复完整 EXEC，等待访存，执行 CTA barrier。
2. 重置 LDS 中的计数器，并用 barrier 确保所有 wave 完成重置。
3. 每个 wave 的 lane 0 执行一次 `ds_add_rtn_u32`，取得唯一 ticket 0、1、2 或 3。
4. 用 `v_mbcnt_lo_u32_b32` 重新得到硬件 lane id。
5. 构造新的 `logical_tid = ticket * 32 + lane_id`。
6. 从 LDS 固定偏移读回 kernarg 指针和 CTA 编号。
7. 按新的逻辑编号读取 `state` 和任务输入，继续下一阶段。

所有 128 个逻辑编号仍然恰好各出现一次，但它们不保证继续落在原来的物理 wave 上。这就是该方案可以不保留任何 GPR 编号锚点的原因。

如果某个算子依赖“必须由之前同一个物理 lane 持有的未落内存结果”，就不能直接采用这个协议。必须先把这些结果转为可按逻辑任务编号读取的内存状态，或使用其他保存方案。

### 6.4 与 ATOM 的关系

该思路与 ATOM 的“同一个 CTA 在不同阶段重新领取任务”的结构比较接近。实际接入时，保留的上下文还可能包含层号、rank、调度队列位置、mailbox tag 和指针等，32 字节只是本实验的大小。

当前 ATOM 的执行模型将 LDS 预算设为 160 KiB。不能假设还有空闲空间；应由统一的 LDS allocator 在算子 scratch union 之外分配上下文，检查最终最大占用。必要时改变算子分块或布局。

在 MI355X/wave64 上还需要重新实现 lane id、逻辑 wave 编号、入口寄存器映射以及资源计算。本文没有把 gfx1100 代码直接移植到该设备。

## 7. 对照结果

实际运行覆盖 1、3、17 个 CTA，每个 CTA 128 线程，每种规模 5 轮不同输入。每个正确版本共 15 次 Mono launch，每次包含两个非末尾二进制阶段。

检查内容包括两个算子中间输出、Mono 中段状态、最终输出、两次边界后的标志/标量状态以及有效区间外的保护数据。

```text
PASS: standalone supplier .co, 17 CTAs x 128 threads

mono_unsafe:
EXPECTED FAILURE reproduced: 26863 value mismatches, 80640 state mismatches

mono_preserve:
PASS: 15 launches, two non-tail binary stages per launch;
      intermediates/output/state/guards verified

mono_phase:
PASS: 15 launches, two non-tail binary stages per launch;
      intermediates/output/state/guards verified
```

资源 metadata 和实际反汇编检查：

| 版本 | private 字节/线程 | LDS 字节/CTA | VGPR | metadata SGPR 数 | PC call/return |
| --- | ---: | ---: | ---: | ---: | --- |
| `mono_unsafe` | 64 | 512 | 256 | 108 | 无 |
| `mono_preserve` | 64 | 512 | 256 | 108 | 无 |
| `mono_phase` | 0 | 544 | 256 | 108 | 无 |

负对照也保留了指针和编号的恢复机制，避免测试变成无效地址访问；它只故意不保护活跃值和标志。负对照出错是测试期望，整个 harness 在确认错误被复现、另两种方法正确后返回成功。

`mono_preserve` 检查保存/恢复的标志；`mono_phase` 检查重建后的标志，二者含义不同。

还在一个全新目录中仅提供接收方脚本、host、ABI/契约和 `vendor.co`，没有供应方 `.s`，从零构建和运行了相同测试，结果通过。

这些实验只使用 CTA 内的同步，没有证明大型持久化 grid 的跨 CTA 等待和驻留条件。测试使用普通 module launch；实际 ATOM 的驻留和进度保证仍须单独满足。

## 8. 如何复现

```bash
cd /home/feifei/repo/ATOM/mono_test
make run-clobber
```

只构建或检查机器码：

```bash
make clobber
make check-clobber
```

使用外部交付的、满足本实验契约的 `.co`：

```bash
make -B run-clobber CLOBBER_STAGE=/absolute/vendor/stage.co
```

该命令仍使用本实验的 `stage_contract.json`；不能把任意 `.co` 代入就认为它符合接口。

主要文件：

| 文件 | 作用 |
| --- | --- |
| [clobber/stage.s](clobber/stage.s) | 供应方独立 ASM kernel，包含全 GPR 覆盖操作 |
| [clobber/stage_contract.json](clobber/stage_contract.json) | 供应方/接收方约定 |
| [clobber/generate.py](clobber/generate.py) | 从 `.co` 提取机器码，生成三种非末尾接入方式 |
| [clobber/abi.py](clobber/abi.py) | 本实验的 gfx1100 kernel descriptor 和 metadata 模板 |
| [clobber/demo.cpp](clobber/demo.cpp) | 独立算子验证、负对照、两个正确版本的完整结果检查 |
| [clobber/verify.py](clobber/verify.py) | 机器码、出口和资源检查 |
| `build/clobber/stage.co` | 实际供应方 code object |
| `build/clobber/mono.s` | 生成的完整融合汇编 |
| `build/clobber/mono.co` | 三个实验 kernel 的 code object |
| `build/clobber/report.json` | 静态验证和资源报告 |

## 9. 接入真实 ASM 算子需要的契约

除了参数类型，一个可融合的算子至少需要约定：

- 目标架构、wave 大小、CTA 线程数、逻辑任务与原 kernel 网格的映射。
- 入口所需的 kernarg、dispatch/implicit 参数、工作项/CTA 编号及其他寄存器。
- VGPR、SGPR、AGPR 和特殊状态的破坏范围；FP MODE 等是否恢复或需要外层重建。
- LDS、private 和显式全局工作区的占用与生命周期，哪些内存区域属于外层上下文。
- 所有出口如何到达后继阶段，是否存在提前终止、内部调用、重定位和 PC 相对数据。
- barrier 的参与线程、退出时 EXEC 条件、未完成的访存/矩阵指令及发布协议。

当前提取器仅接受这个没有内部跳转/调用、单一末尾出口、自包含的测试算子。真实大算子的多个出口、常量池、重定位、长分支和资源上限需要进一步处理。

如果必须保留原线程身份，又不能使用 private scratch，一个可选方向是与供应方约定极小的保留寄存器或其他稳定锚点，再访问显式的 wave 上下文。若连这种契约、保留内存区和阶段边界都不能约定，就无法保证任意现成 `.co` 可以安全嵌入 Mono。

## 10. 性能边界与下一步

本次未做性能计时。适配代码使用了保守的等待和 `s_nop` 间隔，测试算子还故意写满整个寄存器文件，因此不适合据此给真实算子做性能排名。

已证明的是：**即使算子覆盖全部 GPR，也可以在一次 kernel launch 内继续执行后续阶段，同时不使用 PC call/return。** 代价转移为状态保存、内存重载、barrier、任务重新编号及资源预留。

针对 ATOM，合理的推进顺序是先选择一个现有 CTA barrier 边界和一个小算子，明确全局状态及保留 LDS 上下文，形成 MI355X 版本的阶段 ABI；再接入供应方 `.co`，检查资源和跨 CTA 进度，最后测量性能。不能仅把本实验的直接分支拼接应用到任意算子内部。

## 11. 后续方案：固定跨 ASM 边界的活跃状态

约束为：**进入 ASM 前，后续仍需使用、且尚未存入显式内存或安排重建的旧值，只能位于事先约定的一小组边界寄存器中。** 主体其他临时寄存器可以自由使用，但其旧值不能跨这个边界继续被依赖。ASM 仍可以改写全部 GPR；外层只保存并恢复这组状态。

完整的边界 ABI 示例、状态完备性规则、保存与参数准备的顺序、恢复起点、两条实现路线及检查方法，已写入[综合文档第 20 节](BINARY_STAGE_INTEGRATION.md#bounded-boundary-state)。

与当前实验的关系：`mono_preserve` 已展示手工控制的小保存集合，`mono_phase` 已展示 private 为 0 的内存状态重建。新增的 [compiler_boundary 实验](COMPILER_BOUNDARY_EXPERIMENT.md) 已统一保存集合与 LDS offset，通过编译器可见 clobber 让 LLVM 安排存活值，并验证 8 VGPR + 10 SGPR 的小保存集合可承受两个全 GPR 覆写阶段。运行 `make run-boundary` 可复现；原有三个 clobber 版本保持不变。新检查器仅覆盖本例直线 MIR，通用边界 ABI、复杂 CFG 分析和真实 ATOM 接入仍需补齐。
