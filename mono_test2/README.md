# Mono 主调用方：调用点 regmask 约束跨 ASM 调用状态

本目录直接使用 **`mono_kernel.cpp` 中的 `mono_kernel`** 演示普通设备函数调用、针对调用点的寄存器保持掩码，以及不使用 scratch 的跨调用上下文保留。默认构建、检查、运行全部针对这个主 Mono，没有第二个验证 kernel 参与。

供应方实现来自 `../mono_test/stages/sub_kernel.s`，独立编译为 `stage_sub.co`，与调用方链接为 `mono_kernel.co`。调用方没有 inline asm，也没有函数级 VGPR 上限。`callsite_regmask.py` 在寄存器分配前只收窄目标调用的保持掩码，LLVM 自动分配跨调用的线程编号和输入值。

**最终目标是 ATOM。** 实现机制、MIR 原型的限制及正式后端接入步骤见 [ATOM_CALLSITE_REGMASK.md](ATOM_CALLSITE_REGMASK.md)。当前已验证 gfx1100 主 Mono，尚未完成 gfx1250 ATOM 集成。

ABI 文档中文翻译见 [AMDGPU_DEVICE_FUNCTION_ABI.zh-CN.md](AMDGPU_DEVICE_FUNCTION_ABI.zh-CN.md)，[英文原文快照](AMDGPU_DEVICE_FUNCTION_ABI.en.rst) 可用于对照。

## 1. 构建和运行

环境：ROCm 7.2、clang 22.0.0git、gfx1100 / Radeon RX 7900 XTX。本机 HIP device 0 是这张 GPU。汇编固定为 gfx1100，修改 `-mcpu` 不能直接移植到 gfx1250。

```bash
cd /home/feifei/repo/ATOM/mono_test2
make -j4
make run DEVICE=0
```

`make` 和 `make run` 都包含静态检查；发现 private/scratch 或 VGPR/SGPR spill 时会失败，`make run` 不会继续 launch。

唯一的运行链是：

```text
mono_demo
  → hipModuleLoadData(mono_kernel.co)
  → hipModuleGetFunction("mono_kernel")
  → cooperative launch：3 CTA × 128 threads
      CTA 0：读取 lane_bias → 调用 stage_sub_device → 加上 lane_bias → 发布 first
      CTA 1：等待 first → 乘 2 → 发布 second
      CTA 2：等待 second → 减 3 并 ReLU → 输出
```

早期独立 `live_state_kernel` 的源码归档到 [history/](history/README.md)，不参与构建，原来的 `make run-live` 入口已移除。旧 build 目录中的独立验证二进制也不是当前运行输入。

## 2. 主 Mono 中实际改变了什么

调用方来自 `../mono_test/mono_kernel.cpp`。现在直接在其 CTA 0 分支加入调用前读取、调用后使用：

```cpp
extern "C" __global__
void mono_kernel(const float* input, float* output, Mailbox first,
                 Mailbox second, int n, unsigned epoch, unsigned* sub_done) {
  if (blockIdx.x == 0) {
    const unsigned tid = threadIdx.x;
    const float lane_bias = tid < static_cast<unsigned>(n)
                                ? static_cast<const volatile float*>(input)[tid]
                                : 0.0f;

    stage_sub_device(input, Mailbox{first.data, sub_done}, n, epoch);

    for (int i = tid; i < n; i += blockDim.x) {
      first.data[i] += lane_bias;
    }
    publish(first, epoch);
  } else if (blockIdx.x == 1) {
    stage_scale(first, second, n, epoch);
  } else if (blockIdx.x == 2) {
    stage_relu(second, output, n, epoch);
  }
}
```

完整代码见 [mono_kernel.cpp](mono_kernel.cpp)。`lane_bias` 是一次调用前的 volatile 读取；返回后的加法使用这次读取的结果。编译器不能把它改成在调用之后重新读取输入。

每个线程保存自己的 `input[threadIdx.x]`，并将它加到该线程负责的所有元素。当前计算公式因此为：

```text
first[i]  = x[i] - 1 + x[i % 128]
second[i] = 2 * first[i]
y[i]      = max(second[i] - 3, 0)
          = max(2 * (x[i] + x[i % 128]) - 5, 0)
```

相比旧示例的 `max(2*x - 5, 0)`，新增的加法让跨调用值直接参与最终结果。它不是单独的诊断输出，也不是另一个 kernel 的测试。

### 为什么增加 `sub_done` 参数

原 `stage_sub_device` 在返回前就会发布传入的 mailbox tag。如果仍让它直接发布 `first.tag`，CTA 1 可能在 CTA 0 的后处理完成前读取 `first.data`，形成竞态。

当前流程是：

1. ASM 将 `input - 1` 写到 `first.data`，发布内部标记 `sub_done`。
2. 返回到同一个 CTA 0，完成 `first.data += lane_bias`。
3. `publish(first, epoch)` 执行 CTA barrier 和 release 发布。
4. CTA 1 acquire 等待正式的 `first.tag` 后再读取数据。

`sub_done` 是一个独立的 global 标记，保留原 ASM 的发布接口；CTA 1 不等待这个内部标记。所有 CTA 0 线程都调用 ASM，包括 n 小于 128 时没有有效元素的线程，满足内部 barrier 的参与要求。

主 kernel 的 host 参数新增了最后一个 `unsigned* sub_done`。host 已同步修改，分配 3 个 tag 并传入全部 7 个参数。显式参数共 64 字节，`sub_done` 位于偏移 56；当前总 kernarg 大小为 320 字节。旧的六参数 host 不能启动这个新接口。

## 3. 调用点约束，其他内联算子没有 48 VGPR 上限

当前源码和 LLVM IR 中均没有 `amdgpu_num_vgpr(48)` / `amdgpu-num-vgpr`。scale、relu 和 Mono 的局部计算不再受到该函数级上限限制。

构建脚本在 `mono_kernel` 唯一的 `SI_CALL @stage_sub_device` 上，将默认 `csr_amdgpu` 改为 `CustomRegMask`：

- VGPR：默认仅保持 v40–v47 及其完整子寄存器/元组别名。
- SGPR、只读特殊寄存器等：完整保留本机普通 ABI 掩码中的对应位。
- 其他调用点和函数的寄存器分配范围不变。

它限制的是需要在 VGPR 中直接跨调用保留的值。调用之前和返回之后的临时计算可以使用集合外的 VGPR。容量不足时 LLVM 仍可 spill，由构建门禁拒绝。

当前编译结果：

| 状态 | 默认位置 |
| --- | --- |
| CTA 内线程编号 tid | v40 |
| 调用前读取的 lane_bias | v41 |
| n / epoch | s34 / s35 |
| kernarg 指针 | s36:s37 |
| first.data / first.tag | s52:s53 / s54:s55 |

真实指令包括：

```asm
; 调用之前
flat_load_b32 v41, v[1:2] glc dlc
; ...参数准备...
s_swappc_b64 s[30:31], s[18:19]
; ...返回后加载 first.data...
v_dual_add_f32 v3, v41, v3 :: v_dual_add_nc_u32 v0, s1, v0
```

见 [build/mono_kernel.function.s](build/mono_kernel.function.s)。主函数没有 scratch 保存/恢复。调用点掩码和完整别名表记录在 [build/callsite_regmask.json](build/callsite_regmask.json)。

可用同一份主源码改为更高编号的保持集合：

```bash
make BUILD=build_bank56 VGPR_FIRST=56 VGPR_COUNT=8 \
     STAGE_CO=build/stage_sub.co run
```

这时 LLVM 使用 v56/v57，仍通过 160 次主 Mono launch，private/spill 均为 0。这验证了没有隐藏的函数级 48 上限，而不是声称真实 ATOM 算子已经完成性能优化。

本原型暂停/恢复 MIR，依赖当前 ROCm 7.2 的内部表示。正式接入 ATOM 应在 LLVM 编译进程内设置 MachineInstr regmask，避免本原型所需的 MIR 解析和入口 descriptor 兼容处理，详见 [接入说明](ATOM_CALLSITE_REGMASK.md)。

## 4. ASM 二进制如何编译与链接

[stages/sub_kernel.s](stages/sub_kernel.s) 与原文件逐字节相同，没有 `sub.cpp` 或 `sub.h` 参与构建。此 ASM 已经包含符合设备函数 ABI 的 `stage_sub_device`，没有额外插入保存 wrapper。

| 文件 | ELF 类型 | 用途 |
| --- | --- | --- |
| `build/stage_sub.co` | ET_REL | 可重定位的 ASM 函数目标，作为链接输入 |
| `build/mono_kernel.o` | ET_REL | Mono 调用方机器码，链接前 stage 符号尚未解析 |
| `build/mono_kernel.co` | ET_DYN | 最终 HSA 模块，由 HIP 加载，launch mono_kernel |

`stage_sub.co` 本质上是通常命名为 `.o` 的链接目标。`.co` 后缀不让它变成可单独 launch 的 kernel。定义 `SUB_DEVICE_ONLY=1` 后，ASM 只输出设备函数，不输出独立 `sub_kernel` wrapper、descriptor 和 kernel metadata。

关键命令由 [Makefile](Makefile) 实现：

```bash
mkdir -p build

/opt/rocm/llvm/bin/clang++ \
  --target=amdgcn-amd-amdhsa -mcpu=gfx1100 \
  -x assembler -Wa,-defsym,SUB_DEVICE_ONLY=1 \
  -c stages/sub_kernel.s -o build/stage_sub.co

/opt/rocm/llvm/bin/clang++ \
  -x hip -std=c++17 -O2 --offload-arch=gfx1100 \
  --offload-device-only -fgpu-rdc \
  -c mono_kernel.cpp -o build/mono_kernel.bc

# 在寄存器分配前修改目标调用掩码，再继续 LLVM 代码生成。
python3 callsite_regmask.py \
  --bitcode build/mono_kernel.bc --stage build/stage_sub.co \
  --output build/mono_kernel.s --vgpr-first 40 --vgpr-count 8

/opt/rocm/llvm/bin/clang++ \
  --target=amdgcn-amd-amdhsa -mcpu=gfx1100 \
  -x assembler -c build/mono_kernel.s -o build/mono_kernel.o

/opt/rocm/llvm/bin/ld.lld -shared --no-undefined \
  build/mono_kernel.o build/stage_sub.co -o build/mono_kernel.co
```

GPU 在一次 launch 内，通过 `s_swappc_b64` 调用 stage，stage 通过 `s_setpc_b64 s[30:31]` 返回。没有子 kernel launch，没有对最终二进制做逐行替换。

接收方只拿到二进制时，可使用新构建目录：

```bash
make BUILD=build_receiver STAGE_CO=/absolute/path/stage_sub.co run
```

此路径不依赖供应方 ASM/C++ 实现。`make stage` 才明确要求从本地汇编生成供应方目标。

## 5. 验证结果

2026-11-09，本机 RX 7900 XTX / gfx1100 的当前主 Mono：

| 项目 | 结果 |
| --- | --- |
| 唯一 launchable kernel | mono_kernel |
| GPU 验证 | n=1、31、128、257、4096，各 32 次，共 160 次 Mono launch |
| 每次 launch | 3 CTA × 128 threads |
| 验证内容 | 两个 mailbox 的中间值、最终 ReLU 输出、3 个 tag、有效区间之外未写入的尾部 |
| 调用控制流 | 1 个 swappc、1 个 stage setpc，调用之后仍有 CTA 0 计算 |
| lane_bias 跨调用位置 | v41 |
| tid 跨调用位置 | v40 |
| 固定 private / LDS | 0 / 0 |
| VGPR / SGPR spill count | 0 / 0 |
| metadata VGPR / SGPR count | 42 / 58 |
| HIP 驻留容量 | 768 CTA，满足 3 CTA 的示例要求 |
| stage 函数机器码 | 292 字节，链接前后逐字节一致 |
| 最终链接 | 无未解析符号，无剩余重定位 |

host 检查未经过 ReLU 截断的中间值，避免错误被最终的零值掩盖。全员调用和后处理后的正式发布也覆盖了 n 小于一个 wave 或 CTA 的情况。

检查入口为 [checks/check_link.py](checks/check_link.py)。它检查 ELF、函数字节、实际 call/return、零 private/spill、主函数调用前的加载和调用后的 callee-saved VGPR 使用。后者是针对本例单个调用的检查，不是通用 CFG 活跃性证明，也不是任意供应方的完整 ABI 验证器。

主运行日志：[build/main.log](build/main.log)。静态结果：[build/link_check.json](build/link_check.json)。供应方函数仍由同一个 `stage_sub.co` 提供；只交付二进制的接收方还需带上本目录 `callsite_regmask.py` 作为当前编译流程的一部分。

同一份主 Mono 的调用点集合缩为仅 v40 时，生成 16 字节 private，构建门禁拒绝，没有 launch，见 [build/rejected_bank1.log](build/rejected_bank1.log)。

`.uses_dynamic_stack` 仍为 true，是当前 RDC 外部调用的保守描述。当前 stage 是 private 为 0 的已知叶函数；不能推广为任意外部函数都无需额外栈资源。

## 6. 换成任意 ASM 时仍需满足的契约

此处的零 scratch 成立，因为指定的 `stage_sub_device` 已遵循当前普通设备函数 ABI：它不破坏 callee-saved GPR、返回地址或栈指针，并在返回时恢复 EXEC。当前入口仍使用 v0:v7 传递显式参数、v31 提供工作项标识、s8:s9 提供隐式参数指针、s12 提供 blockIdx.x、s30:s31 提供返回地址。

若以后换成会覆盖 callee-saved 寄存器的 ASM，仍需独立适配层履行保持约定。可以显式使用 LDS 保存/恢复，从而避免 private scratch，但编译器不会自动将这些保存改成 LDS。全部 GPR 都被覆盖时，还必须设计保存区和线程身份的恢复起点。

增加普通调用、允许符号链接，都不会自动修复供应方的 ABI 违规，也不会自动推导任意外部 ASM 的寄存器/LDS/栈资源。当前实验没有修改实际 ATOM 算子，也没有在 gfx1250 上运行。

## 7. 文件入口

- [mono_kernel.cpp](mono_kernel.cpp)：真正的主调用方，无函数级 VGPR 上限。
- [mono_demo.cpp](mono_demo.cpp)：唯一当前 host，加载主 Mono 并验证流水线。
- [stages/sub_api.h](stages/sub_api.h)：设备函数声明。
- [stages/sub_kernel.s](stages/sub_kernel.s)：独立 ASM 供应方。
- [Makefile](Makefile)：编译、链接、检查、运行。
- [callsite_regmask.py](callsite_regmask.py)：寄存器分配前的调用点掩码原型。
- [ATOM_CALLSITE_REGMASK.md](ATOM_CALLSITE_REGMASK.md)：面向 ATOM 的正式接入位置和当前限制。
- [build/mono_kernel.ll](build/mono_kernel.ll)：主调用方的编译 IR，不含函数级 VGPR 数量属性。
- [build/mono_kernel.function.s](build/mono_kernel.function.s)：只包含主函数的编译器汇编。
- [build/mono_kernel.disasm.txt](build/mono_kernel.disasm.txt)：最终主 Mono 与 stage 的反汇编。
- [history/README.md](history/README.md)：早期独立验证的归档说明。

原供应方汇编 SHA-256：`8324383579034da17323b5a09d720f41f9ed22ffa673a1ddc9d0da0d91b9ae28`。stage 函数字节 SHA-256：`040b7830b48375bd886e11e41256c3df26bc62a7f6b6bc8c4f0d1d6bc19bef87`。
