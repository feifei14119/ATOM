# 面向 ATOM 的调用点寄存器保持掩码

最终目标是把供应方 ASM 算子接入 ATOM Mono：**只约束目标算子调用处的跨调用状态，不给整个 Mono 及其内联算子施加很小的 VGPR 上限。** 本目录已经用真正的 `mono_kernel.cpp` 验证调用点 regmask；正式接入 ATOM 仍需要修改其 FlyDSL/LLVM 代码生成路径及供应方 ABI 适配。

## 1. 已经实现的机制

当前 `mono_kernel.cpp` 已删除 `amdgpu_num_vgpr(48)`。构建时对 `mono_kernel → stage_sub_device` 的唯一机器级调用，在寄存器分配前，把默认 `csr_amdgpu` 换成自定义 `CustomRegMask`：

```text
原掩码：普通 AMDGPU 设备函数 ABI
新掩码：保留原掩码的 SGPR、特殊寄存器等所有非 VGPR 位
        仅保留 v40–v47 对应的 VGPR 位及完整别名
```

对原掩码中其余 VGPR 的保持承诺予以取消。掩码只说明该调用的净效果：调用之前和之后的局部计算仍能使用其他 VGPR，其他调用点的掩码不变。

这里没有手写 `v_mov` 来绑定 C++ 变量。LLVM 根据调用掩码分配活跃区间，将 `tid` 放在 v40、`lane_bias` 放在 v41。调用后继续执行同一 CTA 0 的加法和发布逻辑；CTA 1 的 scale 与 CTA 2 的 relu 仍是主 kernel 的内联代码。

## 2. 当前原型的构建流程

```text
mono_kernel.cpp（无函数级 VGPR 上限）
    ↓ HIP 编译
mono_kernel.bc
    ↓ 删除没有被主 kernel 使用的 HIP assert/printf 等辅助函数
mono_kernel.codegen.ll
    ↓ 指令选择；暂停在 finalize-isel 之后、寄存器分配之前
mono_kernel.before_regmask.mir
    ↓ 只修改目标 SI_CALL 的 regmask
mono_kernel.callsite.mir
    ↓ 恢复 LLVM 后续优化、SGPR/VGPR 分配与代码生成
mono_kernel.s
    ↓ 汇编、与 stage_sub.co 静态链接
mono_kernel.co
    ↓ 同一个 mono_demo / 同一个 mono_kernel
三 CTA 完整流水线
```

实现：[callsite_regmask.py](callsite_regmask.py)。构建入口：[Makefile](Makefile)。实际 regmask 记录：[build/callsite_regmask.json](build/callsite_regmask.json)。

```bash
cd /home/feifei/repo/ATOM/mono_test2
make run

# 同一主调用方，改用高于原 48 上限的保持集合。
make BUILD=build_bank56 VGPR_FIRST=56 VGPR_COUNT=8 \
     STAGE_CO=build/stage_sub.co run
```

每次改变参数都记录在构建目录的 `regmask.config` 中，触发相应重编译。生成代码与原始供应方函数仍通过正常 ELF 设备链接结合，没有把供应方指令逐行替换到已生成的 Mono 二进制中。

## 3. 为什么必须包含寄存器别名

VGPR 的表示不只有 `$vgpr40`，还包括 16 位子寄存器和多寄存器元组，例如：

```text
$vgpr40
$vgpr40_lo16 / $vgpr40_hi16
$vgpr40_vgpr41
……
```

只有元组覆盖的所有 VGPR 都在允许集合内，才能把这个元组标记为保持。遗漏或错误地保留别名位，会造成不必要的 spill，或者让值通过元组绕过边界约束。

本原型从**正在使用的 llc 可执行文件**读取 `CSR_AMDGPU_RegMask`、寄存器描述表和名称表，按名称构造 MIR 的 `CustomRegMask`。没有使用另一个 LLVM 构建中的数字寄存器 ID。原始掩码包含 956 个物理寄存器名称/别名，收窄为 v40–v47 后为 280 个；这些数量包括 SGPR、只读特殊寄存器和别名，不是 GPR 个数。

这套读取方式依赖 ROCm 7.2 的 ELF 符号及 `MCRegisterDesc` 布局，**只用于当前原型**。脚本固定编译器提交 `7b800a19466229b8479a78de19143dc33c3ab9b5`，记录 llc SHA-256，遇到不匹配时拒绝；正式 ATOM 实现直接使用 LLVM 对象接口，不读取编译器自身的二进制。

## 4. 真实运行和边界检查

2026-11-09，本机 gfx1100 / RX 7900 XTX：

| 配置 | 跨调用 tid / lane_bias | metadata VGPR / SGPR | private | VGPR/SGPR spill | 结果 |
| --- | --- | --- | ---: | --- | --- |
| 调用点仅保持 v40–v47 | v40 / v41 | 42 / 58 | 0 | 0 / 0 | 160 次主 Mono launch 全部通过 |
| 调用点仅保持 v56–v63 | v56 / v57 | 58 / 58 | 0 | 0 / 0 | 160 次主 Mono launch 全部通过 |
| 调用点仅保持 v40 | 预算不足 | 不作为可运行版本 | 16 字节 | 检查拒绝 | 没有 launch |

两组成功配置均覆盖 n=1、31、128、257、4096，各 32 次；每次 3 CTA × 128 threads，检查两个中间 mailbox、最终结果、3 个 tag 和未使用尾部。

v56/v57 的结果证明原函数级 48 上限已经移除。当前 scale/relu 本身很简单，这个结果不声称已经做过高寄存器压力的真实 ATOM 算子性能测试。

默认最终 VGPR 数从旧构建的 53 变为 42，与去掉未使用 HIP 辅助函数后的模块级资源估计有关，不是“regmask 一定降低整个 kernel 寄存器数量”的性能结论。硬件仍按最终 kernel descriptor 分配资源，调用点约束不会让每个算子获得独立 launch 配置。

运行日志与证据：

- [build/main.log](build/main.log)：默认主 Mono。
- [build/bank56.log](build/bank56.log)：同一主 Mono 使用 v56–v63。
- [build/rejected_bank1.log](build/rejected_bank1.log)：单 VGPR 预算被拒绝。
- [build/mono_kernel.function.s](build/mono_kernel.function.s)：默认主函数汇编。
- [build/link_check.json](build/link_check.json)：链接和零 spill 检查。

零 scratch 仍然是一条构建门禁。regmask 让编译器知道寄存器会被破坏，但不会自动保证任意多的跨调用状态都能装进 8 个 VGPR。

## 5. 原型遇到的 MIR 序列化问题

本机原样导出的 MIR，直接恢复编译也有问题，与修改 regmask 无关：

1. wave32 的 `S_CBRANCH_VCCNZ/Z` 打印 `implicit $vcc_lo`，MIR parser 却要求 `$vcc`。原型保留真实的 VCC_LO 依赖，另加 `implicit undef $vcc` 满足解析要求。
2. 恢复编译后丢失入口用户 SGPR 数，descriptor 从 13 变成 8，而机器指令仍从 s13 读取 workgroup ID。未修正的版本实际出现 mailbox tag 错误。原型从直接编译的基线保留 `.amdhsa_user_sgpr_count=13`。
3. 恢复路径引用但未定义 `amdgpu.max_num_named_barrier`。当前 gfx1100 和已验证的叶函数都不使用 named barrier，原型显式补 0。

脚本先做一次**不修改调用掩码的 MIR 往返**，要求生成的主函数指令文本与直接编译结果完全一致；校正入口 descriptor 后，再应用目标调用掩码。保持变化的是真实寄存器分配结果，不能把基线的 VGPR/SGPR 数或 scratch 大小强行套到新结果上。

还显式合并供应方的已知 VGPR/SGPR 资源。原型锁定 `stage_sub_device` 的 292 字节函数 SHA-256，要求其 private/AGPR/named-barrier 为 0；它不是任意 `.co` 的自动 ABI 或资源推导器。

**这些兼容处理不应搬进 ATOM 正式编译链。** 正式实现应在同一个 LLVM 编译进程内改变 MachineInstr 的 regmask，不导出再恢复 MIR；这样无需从 ELF 提取编译器表，也不会丢失 MachineFunctionInfo。

## 6. ATOM 正式接入的位置

PR #2908 中的 `atom/mono/runtime/compile.py` 负责 compile-only、提取已生成的 `gpu.binary` 和读取资源。到读取 `.co` 时，寄存器分配已经完成，无法再让 regmask 指导编译器保护上下文。

正式变更应进入 FlyDSL 使用 LLVM TargetMachine 生成 AMDGPU 代码的路径：

```text
ATOM stage：声明需要替换的算子边界
    ↓
FlyDSL / MLIR：生成真实的外部设备函数调用
    ↓
LLVM IR：保留调用、参数、内存副作用和参与线程语义
    ↓
AMDGPU call lowering / MachineFunction pass
    在该调用上设置定制 regmask
    ↓
LLVM 寄存器分配及代码生成
    ↓
链接 ASM 适配函数，生成最终 .co
    ↓
ATOM 资源检查、occupancy 检查与真实算子正确性验证
```

不能仅在 Python `@traced` helper、普通 barrier、plan 记录或 kernel metadata 上加一个字段，就得到这个编译器边界。它必须在 LLVM 寄存器分配之前成为真实调用及其机器寄存器掩码。

### 6.1 调用点的标识

可使用每个边界独有的外部符号，例如 `atom_mono_dq_convert_bank8`，或者在 LLVM 调用上携带由自定义 lowering 识别的契约标记。按 Mono 函数和目标调用精确匹配，不修改所有普通设备调用的 `CSR_AMDGPU_RegMask`。

不一定需要新增 LLVM calling convention 枚举。参数和返回地址可以继续沿用普通设备函数布局，只在选中的 MachineInstr 上设置新的保持掩码。

如果适配函数只履行这个较小的保持契约，它就不是任意普通 ABI 调用方都可直接使用的通用函数。必须确保所有到该入口的调用都携带匹配契约，避免其他调用方继续依赖完整的默认 callee-saved 集合。

### 6.2 修改掩码

下面是机制伪代码，不是已经编译进 ATOM 的补丁：

```cpp
// Only the selected Mono stage call.
uint32_t* mask = MF.allocateRegMask();
copyDefaultCallMask(mask, CallMI);

for (MCRegister r : allPhysicalRegisters(TRI)) {
  if (isVGPRViewOrTuple(r) && !allCoveredVGPRsInBank(r, bank))
    clearPreservedBit(mask, r);
}

CallMI.regMaskOperand().setRegMask(mask);
```

新掩码内存必须随 MachineFunction 存活，不能指向局部临时数组。别名判定使用目标的寄存器信息与子寄存器关系，而非把 gfx1100 的名字或编号硬编码到 gfx1250。

插入位置必须早于第一次 SGPR/VGPR 分配，并考虑 IPRA / register-usage propagation 是否会再次覆盖调用掩码。若改变掩码时已建立活跃性分析，需正确失效并重建；更简单的是在相关分析建立前完成。

本原型只收窄 VGPR，SGPR 和特殊状态掩码保持原样。之后可以另设 SGPR 边界集合，但必须保留返回地址、栈/帧管理及其他后端保留状态的有效契约，不能简单清掉所有 SGPR 位。

### 6.3 供应方 ASM 的责任

regmask 表达的是“适配器 + ASM + 恢复”的净效果。它不会禁止 ASM 写入某个寄存器。

- ASM 不改写保持集合时，可让活跃值直接留在寄存器中。
- ASM 会改写保持集合时，适配器仍需保存并恢复，可选择 LDS 以避免 private scratch。
- ASM 覆盖全部 GPR 时，还要解决返回地址、执行掩码、保存区定位和 wave/lane 身份的恢复。

当前 gfx1100 `stage_sub_device` 已符合普通 ABI，所以验证不需要额外保存层。先前选定的 gfx1250 AITER `dq_convert` 会覆盖 v40/v41、s30/s31、s32 等状态，不能直接把本原型的 regmask 套上去就跳入原 `.co`。

### 6.4 ATOM 的验收条件

保留 PR #2908 的资源门禁：scratch 为 0、VGPR spill 为 0；SGPR spill 只允许其既有特定 K2 例外。按最终 `.co` 查询真实 HIP occupancy，256-thread block 的总驻留容量仍需满足 256 CTA。

此外检查目标调用前后的实际活跃集合、完整调用链的寄存器/LDS/栈资源、全员参与和同步协议。选择小 bank 可能导致 spill，需要缩短活跃区间、显式 context 化或增大 bank；不要通过放宽现有门禁隐藏这种失败。

## 7. 当前完成范围

已完成：同一个 `mono_kernel.cpp` 的调用点 regmask 实验、无全函数 VGPR 上限、两种 bank 的 gfx1100 真机验证、零 spill 拒绝路径、正常设备函数链接。

尚未完成：在 ATOM 所用 FlyDSL/LLVM 构建中加入正式 pass、把目标 gfx1250 stage 降成匹配调用、完成 AITER 二进制 ABI 适配、gfx1250 真机正确性和性能测试。本机没有 gfx1250 GPU，当前结果不能替代这些验证。
