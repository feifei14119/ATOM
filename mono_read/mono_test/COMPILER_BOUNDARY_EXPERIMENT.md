# 编译器可见的阶段边界与 VGPR/SGPR 保存预算

本实验已在 ROCm 7.2、Radeon RX 7900 XTX、gfx1100 / wave32 上编译并运行。它把[综合文档第 20 节](BINARY_STAGE_INTEGRATION.md#bounded-boundary-state)的“路线 B”实现为一个最小 LLVM 示例：**在寄存器分配之前声明边界 clobber，由 LLVM 安排跨边界的存活值，再由外层适配器保存一个固定的小集合。**

主体包含 LLVM 编译的地址计算、标量计算和向量计算；算子只从现有 `clobber_stage` 的 `.co` 中提取。两个算子都不是最后一步，都覆写 `v0–v255`、`s0–s105`、EXEC/VCC/SCC，仍能继续执行主体。最终使用普通 `s_branch`，没有设备函数 call/return。

## 1. 运行与文件入口

```bash
cd /home/feifei/repo/ATOM/mono_test
make run-boundary
```

`make boundary` 编译并静态检查，`make check-boundary` 只执行编译与静态检查；后两者不 launch GPU。每次检查都会重新生成两个有效配置和一个预算不足的负例。

| 文件 | 作用 |
| --- | --- |
| [compiler_boundary/caller.ll.in](compiler_boundary/caller.ll.in) | 可读的主体 LLVM IR，包含两个编译器可见的边界；算术值没有预先绑定物理寄存器 |
| [compiler_boundary/adapter.py](compiler_boundary/adapter.py) | `Bank` 统一定义保存集合、clobber、LDS 布局；`enter/leave` 生成保存与恢复 |
| [compiler_boundary/build.py](compiler_boundary/build.py) | 实例化 IR、调用 LLVM、插入原始二进制、更新资源、汇编链接及静态检查 |
| [compiler_boundary/audit.py](compiler_boundary/audit.py) | 拒绝 spill；对本例直线代码的最终 MIR 做寄存器活跃性检查 |
| [compiler_boundary/demo.cpp](compiler_boundary/demo.cpp) | 纯 host HIP module loader 与完整输出检查 |
| [clobber/stage_contract.json](clobber/stage_contract.json) | 沿用的供应方算子接口与资源契约 |

主体直接从 LLVM IR 开始，目的是让边界约束容易阅读，不依赖 ATOM、AITER 或 FlyDSL。host 由普通 `g++` 编译。

默认先从已有的 `clobber/stage.s` 构建供应方二进制，随后消费者只读取 `.co` 和接口 JSON。如果已经拿到符合本例接口的二进制，可以指定：

```bash
make -C compiler_boundary run STAGE=/absolute/path/to/stage.co
```

指定其他路径后，该文件不依赖供应方 `.s/.cpp/.h`。这仍要求匹配本例的算子接口；提取器不是任意 `.co` 的通用转换器。

主要产物位于 `build/compiler_boundary/`：

```text
s16_v8/                   较宽保存集合
s8_v8/                    较小保存集合
  caller.ll               展开 clobber 后的真实编译输入
  caller.s                LLVM 完成寄存器分配后的主体汇编
  caller.mir              后端资源分析阶段的机器 IR
  compile.log             编译诊断；成功时为空
  mono.s                  插入适配器和算子后的完整可汇编文件
  mono.o / mono.co        最终目标文件 / HIP 可加载 code object
  mono.disasm.s           最终反汇编，仅用于检查，不作为汇编输入
  metadata.txt            ELF 资源及重定位检查输出
  report.json             活跃寄存器、资源、原始字节与分支检查结果
rejected_s8_v4/           保留编译器输出及 rejection.json，不融合、不 launch
gpu.log                   真机结果
toolchain.txt             LLVM 版本
```

## 2. “编译器可见的边界”是什么

IR 中每个阶段入口使用 `asm sideeffect`。以较小配置为例，完整约束由脚本展开，概念上为：

```llvm
call void asm sideeffect "; MONO_BOUNDARY_0",
  "{s[0:1]},{s2},{v0},~{v8},...,~{v255},~{s8},...,~{s104},~{vcc},~{scc},~{memory}"
  (ptr addrspace(4) %kernarg, i32 %block_id, i32 %thread_id) #1

attributes #1 = { convergent noduplicate nounwind }
```

上面的省略式 **排除 `s32`，也不包含 `s105`**；实际完整列表见生成的 `caller.ll`。

各部分的职责是：

- `{s[0:1]},{s2},{v0}`：供应方入口的固定输入位置，由 LLVM 自动插入参数搬运。
- `~{v8}...`、SGPR clobber：告诉寄存器分配器，这些物理寄存器里的旧值不能直接跨边界使用。
- `~{vcc},~{scc}`：后继不能依赖边界前的旧条件标志；这里无需备份这两个标志。
- `sideeffect`、`~{memory}`：保留阶段，并让编译器知道它具有内存副作用。
- `convergent/noduplicate`：表达这个边界与参与线程有关且不应复制；**它们不会自动实现 CTA barrier 或证明全员参与**。实际同步由适配器完成，本例控制流保证完整 CTA 到达。

编译器看到的 clobber 是 **保存 → 算子 → 恢复 这一整个片段的净效果**。虽然算子会改写全部 GPR，适配器恢复小集合，因此小集合在编译器眼里仍然保持原值。若删掉适配器只插入算子，这份声明就是错误的。

示例特意让两个边界前后的值都有后续用途：

```text
加载 x；计算 live = 2*x + 3，sc = seed + block_id
边界 0：tmp1 = x - 1，随后覆写全部 GPR
计算 mid = live + tmp1，sc2 = sc + 1
边界 1：tmp2 = tmp1 - 1，随后覆写全部 GPR
out = mid + tmp2 + sc2
```

所以最终应为 `out[i] = 4*x[i] + seed + i/128 + 1`。LLVM 可以合法地推迟算术计算、提前消费某些输入，或搬移存活值；无需按源代码变量一一保存。

## 3. 如何约束 SGPR/VGPR

`Bank(sgprs=8, vgprs=8)` 定义较小配置：

```text
编译器可保留的普通集合：s0–s7、v0–v7
额外保护的后端保留寄存器：s32、s105
外层实际保存：10 个 SGPR + 8 个 VGPR
其他编号 GPR：声明为 clobber
```

本机 LLVM 在将 `s32/s105` 放入 clobber 时发出 reserved-register 警告。最终实现把它们从 clobber 中排除，并在适配器中一并保存、恢复；没有忽略警告。MIR 还显示 `s32` 为 `stackPtrOffsetReg`。这些编号属于本机后端约定，迁移 LLVM/架构时必须重新确认；构建会拒绝任何编译诊断。

这个约束作用于 **跨边界仍存活的值**。主体在边界前仍然可以用 `s8–s13` 做临时计算，并不要求整个 kernel 只出现低编号寄存器。

比较两份 `caller.s` 能直接看到 LLVM 的调整：

| 现象 | `s16_v8` | `s8_v8` |
| --- | --- | --- |
| 输出指针跨阶段的位置 | `s10:s11` | LLVM 插入 `s_mov_b64 s[6:7], s[10:11]` |
| `s3 += s13` | 边界 0 之后 | 移到边界 0 之前，提前消费 `s13` |
| private scratch / SGPR spill / VGPR spill | 全为 0 | 全为 0 |

这里对物理寄存器的搬移和调度来自 LLVM；生成器只指定入口参数、clobber 和适配器自身的寄存器。

较小配置的最终 MIR 检查得到以下普通 GPR live-out：

| 边界 | SGPR | VGPR |
| --- | --- | --- |
| 0 | `s0,s1,s2,s3,s6,s7` | `v0–v7` |
| 1 | `s3,s6,s7` | `v1,v2,v3,v4,v5,v7` |

适配器统一保存整个小集合，没有进一步压缩成各边界不同的最小清单。`report.json` 还列出 EXEC、MODE 和 M0 等隐式依赖：EXEC 重建为 full，当前供应方及适配器均不修改 MODE/M0；M0 来自后端 dealloc `sendmsg` 的隐式操作数。VCC/SCC 不在需要保留的 live-out 中。

### 预算过小会怎样

`Bank(sgprs=8, vgprs=4)` 将可跨边界保留的 VGPR 再缩为 `v0–v3`。本机编译结果为：

```text
.private_segment_fixed_size: 24
.vgpr_spill_count: 5
.sgpr_spill_count: 0
```

LLVM 用 scratch spill 满足寄存器约束。这不符合本实验的 scratch/spill 为 0 要求，所以 `require_no_spills()` 明确报 `boundary budget exceeded`；测试捕获这个预期拒绝，保留汇编与报告，不生成该配置的融合 `.co`。

因此，本方案是 **clobber 约束 + 资源门禁**，不能仅加 clobber 后就假设不会 spill。真实主体装不进预算时，应缩短存活区间、显式物化 context、在后继重算，或增大保存集合。

## 4. 全部 GPR 被覆盖之后，如何找到保存区

不能依赖某个 GPR 保留保存区地址。本例采用固定 LDS 地址和逻辑 wave 上下文恢复：

| LDS 区域 | 所有者 |
| --- | --- |
| `[0,512)` | 供应方算子工作区；算子会覆盖整个区域 |
| `[512,516)` | 外层 wave ticket counter |
| `[516,1024)` | 布局间隔，未使用 |
| `[1024, LDS_size)` | 128 个逻辑线程的固定寄存器备份 |

对 `s8_v8`，每线程备份 `18*4 = 72` 字节，整体 LDS 为 `1024 + 128*72 = 10240` 字节。为了代码简单，每个 SGPR 按线程重复保存；后续可改成每逻辑 wave 一份，但本例尚未做该优化。

`enter()`：

1. 等待之前的访存和寄存器生产完成。
2. 用入口 `v0` 的逻辑线程号计算 `1024 + tid*stride`。
3. 保存 `v0–v7` 和 SGPR 集合；适配器临时值使用集合外的 `v64/v65`。
4. 逻辑线程 0 清零 ticket，恢复 full EXEC，CTA barrier 后进入算子。

固定输入约束对应的参数搬运发生在 marker 前。若这些目标寄存器原本有活跃旧值，LLVM 必须先解决冲突；因此适配器可以在 marker 处保存分配完成的集合。它不在编译器不知情的情况下覆盖主体参数。

`leave()`：

1. 即使算子把 EXEC 清零，也先用标量指令恢复 full EXEC，并完成等待/barrier。
2. 每个 wave 的 lane 0 从 LDS 固定地址领取 ticket，得到 0–3 中一个唯一逻辑 wave 号。
3. 用 `v_mbcnt_lo_u32_b32` 重建 lane id，计算逻辑线程槽位。
4. 从该槽位恢复整个 VGPR/SGPR 集合，恢复后的 `v0` 是对应逻辑线程号；等待并 barrier 后执行 LLVM 生成的后继代码。

**这可能把完整逻辑 wave 上下文恢复到另一个物理 wave。** 本例无 scratch、无分歧掩码、无物理 wave 身份依赖，所有需继续使用的 GPR 状态完整迁移，lane 序号保持不变，所以允许这种置换。它不能用于必须恢复原物理 wave 身份或依赖未保存隐式状态的边界。若真实 ATOM 有这种要求，应另设稳定身份锚点或使用目标架构上验证过的恢复机制。

## 5. `.co` 如何接入

```text
caller.ll.in + Bank.clobbers
           ↓ LLVM opt 验证、llc -O2 寄存器分配
       caller.s / caller.mir
           ↓ 检查两个边界的活跃集合及 scratch/spill
           ↓ 用 enter + 原始算子机器码 + leave 替换 marker
       mono.s（完整 descriptor / metadata）
           ↓ clang++ -x assembler -c
       mono.o
           ↓ ld.lld -shared --no-undefined
       mono.co
           ↓ hipModuleLoad / hipModuleGetFunction / hipModuleLaunchKernel
       一次 launch 内完成两个算子和后续主体计算
```

沿用 `clobber/generate.py::extract()` 提取供应方符号。移除唯一末尾 `s_endpgm`，保留其前 **1560 字节原始机器码**，用 `.long` 嵌入两次；通过普通分支连接入口和恢复入口。静态检查确认两个副本逐字节相同，最终仅有一个 `s_endpgm`，共 4 条 `s_branch`，没有 `s_getpc_b64/s_swappc_b64/s_setpc_b64`。

LLVM 只编译了主体与净 clobber，所以融合器还必须更新最终 descriptor 和 metadata 的 LDS、SGPR 资源。最终仍为 `vgpr_count=256`、`sgpr_count=108`；后者包含 106 个编号 SGPR 及后端报告的 VCC 资源。**小保存集合不会消除供应方对全部 GPR 的资源需求。**

## 6. 验证结果与检查范围

| 配置 | 实际保存 | LDS / CTA | private / 线程 | 结果 |
| --- | --- | --- | --- | --- |
| `s16_v8` | 8 VGPR + 18 SGPR | 14336 B | 0 | 静态检查与 40 次 GPU launch 通过 |
| `s8_v8` | 8 VGPR + 10 SGPR | 10240 B | 0 | 静态检查与 40 次 GPU launch 通过 |
| `rejected_s8_v4` | 候选 4 VGPR + 10 SGPR | 未融合 | 24 B | 因产生 spill 而按预期拒绝 |

每个有效配置测试 `1/3/17/257` 个 CTA，每 CTA 128 线程，每个规模改变输入和 seed 重复 10 次。检查完整输入未改写、tmp1、tmp2、out、首尾 guard 和所有未 launch 区域。供应方 `.co` 也单独 launch 验证。

HIP occupancy API 对两个配置分别报告每 HIP multiprocessor 4/6 个活动 block；这是这两个 code object 的资源容量查询，**不是吞吐或延迟测试**。适配器有保守 NOP、等待、barrier 与重复的 SGPR 保存，本实验未测量性能。

活跃性检查使用 `llc -stop-after=amdgpu-resource-usage` 的 MIR，处于寄存器分配、调度、等待插入和分支松弛之后。检查器按显式/隐式 use-def 与寄存器 tuple 别名反向计算活跃集合，并拒绝集合外的边界 live-out。它只覆盖本例的**单基本块、完整 wave、无 private/无 lane spill** 形态，不支持任意 CFG、部分 lane 定义、循环或未知特殊寄存器。新增这些情况时需扩展分析，不能把当前脚本当作任意 ATOM 机器码的证明器。

本例的供应方也有明确约束：gfx1100/wave32/128 线程，固定入口 ABI、自包含机器码、无内部跳转或调用、一个末尾出口，LDS 不越界，MODE/M0 不变。接入其他算子需要重新确认这些契约及指令隐式效果。

## 7. 对 ATOM 的落地意义

这次实现证明了“增加编译器可见边界”可以直接影响寄存器分配，并与二进制算子的全 GPR 覆写兼容。对于 FlyDSL/MLIR 主体，可以在合适的 CTA 阶段交接处加入具有等价输入/副作用/clobber 的操作，并在 lowering 后让 LLVM 在寄存器分配前看到这些信息；不能等到最终汇编再单独补一个 marker。

实际接入还需把这里的 `Bank` 变成所选 ATOM 后端的边界 ABI，明确逻辑身份、同步参与者、所有特殊状态、算子入口与出口、LDS 保存区和所有跨阶段语义字段。继续保留 ATOM 现有 scratch/spill/驻留检查，再测 persistent grid 的跨 CTA 进度与真实模型结果。PR #2908 的 gfx1250 与本机 gfx1100 不同，不能直接复用这些寄存器编号、ISA 或资源数字。

这次没有修改 ATOM 的生产 Mono，也没有更改原有 `run`、`run-call`、`run-clobber` 实现；新增实验与它们并存。
