# Mono：用 C++ inline asm 的 .long 嵌入二进制阶段

本目录复现 `../mono_test0` 的相同主 kernel、六参数接口与三 CTA 流程。差别在于减一阶段：其机器码通过 **C++ inline asm 的 `.long` 指令字**进入主 kernel，在 LLVM 寄存器分配之前就带有输入和 clobber 约束。

```text
CTA 0：inline asm / .long → first = input - 1 → 发布 first
CTA 1：等待 first → stage_scale → second = first * 2 → 发布 second
CTA 2：等待 second → stage_relu → output = max(second - 3, 0)
```

最终公式仍为 `y[i] = max(2*x[i] - 5, 0)`。scale/relu 保持原来的 C++ 内联阶段。host、参数布局和 mailbox 代码从 `mono_test0` 直接复制。

## 构建与运行

使用 ROCm 7.2 和 gfx1100 / Radeon RX 7900 XTX，本机设备编号为 0。

```bash
cd /home/feifei/repo/ATOM/mono_test1
make -j4
make run
make check
```

- `make run`：一次 cooperative launch，3 CTA × 128 threads，核对 4096 个元素的两个中间值、最终结果和两个发布标记。
- `make check`：生成汇编/反汇编，验证真实 inline asm 输入与 clobber、完整指令字节和无设备调用返回。
- `make inspect`：只生成可阅读的 LLVM IR、汇编、反汇编和 ELF 信息。
- `make clean`：删除构建目录。

## 从哪里阅读

| 文件 | 内容 |
| --- | --- |
| [mono_kernel.cpp](mono_kernel.cpp) | 与 mono_test0 相同的三 CTA 分派，减一改为 stage_sub_inline |
| [stages/sub.h](stages/sub.h) | **核心实现**：固定寄存器输入、真实 asm volatile、`.long` include 和 clobber |
| [build/sub_words.inc](build/sub_words.inc) | `.long 0x...` 的 C++ 字符串字面量，每行注释对应指令 |
| [stages/sub_kernel.s](stages/sub_kernel.s) | mono_test0 原始设备函数汇编的副本，机器指令未改写 |
| [stages/scale.h](stages/scale.h)、[stages/relu.h](stages/relu.h) | 乘二和 ReLU 阶段 |
| [embed_sub.py](embed_sub.py) | 从 `.co` 取出固定函数，移除唯一末尾 return，生成 `.long` 字符串 |
| [Makefile](Makefile) | 编译、嵌入、链接流程 |
| [build/mono_kernel.ll](build/mono_kernel.ll) | 寄存器分配前的 asm sideeffect 及全部约束 |
| [build/mono_kernel.disasm.txt](build/mono_kernel.disasm.txt) | 最终主 kernel 的实际指令 |

## `.long` 实际如何嵌入

```text
stages/sub_kernel.s
    → assembler → build/stage_sub.co（ELF REL）
    → embed_sub.py → build/sub_words.inc（288 B 的机器指令字）
                             ↓ #include 到 asm volatile 内
mono_kernel.cpp + stages/sub.h + scale.h + relu.h
    → HIP / LLVM IR（这里已经有 .long 和固定寄存器约束）
    → 正常寄存器分配与代码生成 → mono_kernel.o
    → ld.lld → mono_kernel.co
```

最终链接只传 `mono_kernel.o`。`stage_sub.co` 用作构建时的机器码输入，不作为链接输入，也不作为运行时调用目标。没有事后修改 Mono 汇编或二进制的步骤；`make inspect` 产生的 `.s` 仅供阅读。

核心写法在 `stages/sub.h` 中：

```cpp
asm volatile(
    "s_branch 1f\n"
    ".p2align 6\n"
    "1:\n"
#include "sub_words.inc"   // 多个相邻的 ".long 0x...\n" 字符串
    "s_waitcnt vmcnt(0) lgkmcnt(0)\n"
    "s_waitcnt_vscnt null, 0\n"
    "s_waitcnt_depctr 0\n"
    :
    : /* 固定寄存器输入，完整列表见源文件 */
    : /* 实际被覆盖的寄存器，以及 memory */);
```

这些 `.long` 被汇编到主 kernel 的可执行 `.text` 中。GPU 按机器指令执行它们；它们不是运行时读取的数据表。

从供应方 292 B 函数中仅去掉最后 4 B 的 `s_setpc_b64 s[30:31]`，保留其余 288 B，包括内部短分支和对齐 NOP。外层直接分支跳过对齐填充，使 payload 仍按 64 B 对齐；末尾等待输出写入完成，随后直接继续编译器生成的代码。本示例 CTA 0 的下一步是结束该 CTA，CTA 1/2 继续消费 mailbox。

## 编译器可见的边界

原始指令字使用固定物理寄存器，因此必须明确描述其输入：

| 输入 | 寄存器 |
| --- | --- |
| input 指针 | v0:v1 |
| first.data 指针 | v2:v3 |
| first.tag 指针 | v4:v5 |
| n / epoch | v6 / v7 |
| threadIdx.x | v31 |
| 隐式 launch 参数指针 | s8:s9 |
| blockIdx.x | s12，本次在 CTA 0 分支中被优化为 0 |

这版 Clang 的 C++ 局部寄存器变量只接受 `v0`、`s8` 等单寄存器名，不接受 `v[0:1]`。**不能把一个 uint64 直接绑定到 v0 并假定 v1 也会填入。** 本例将每个指针拆成两个 uint32，分别绑定 low/high；生成的 IR 有 12 个明确的 i32 输入。

对本固定供应方，净 clobber 为：

```text
s0–s3
v8–v15
VCC、SCC、memory
```

其余输入寄存器保持原值。原体自己保存并恢复 EXEC，因此整个区域净效果不破坏 EXEC。它包含 CTA barrier，必须在 CTA 一致的控制流中由全部线程到达，不能把调用放在 `if (tid < n)` 内；n 小于 CTA 大小时的掩码由原体内部处理。

`asm volatile` 防止有副作用的区域被删除；生成的 IR call 带 `convergent`；`memory` 描述间接访问的 input/mailbox 内存。LLVM 根据这些约束分配调用方寄存器，并自然统计硬编码输入与 clobber 所需的资源。本例不需要手动修补 descriptor/metadata。

这里没有完整现场快照，也没有默认 device-call ABI 的 callee-saved 保存 wrapper。`.long` 本身不会保护任何寄存器：本例能成立，是因为已核对固定供应方的真实寄存器读写，并把净效果准确交给编译器。以后换成会破坏所有寄存器的 ASM，必须重新设计保存层和约束，不能直接沿用本表。

## 与 mono_test0 的对照

| 项目 | mono_test0 | mono_test1 |
| --- | --- | --- |
| 减一入口 | 普通外部设备函数调用 | 带约束的 inline asm |
| 二进制使用方式 | 链接 stage_sub.co | 将函数体编码为 `.long` |
| 最终链接输入 | caller.o + stage_sub.co | 只有 caller.o |
| 编译器依据 | 默认设备函数 ABI | 固定输入 + clobber |
| 阶段入口/出口 | PC call/return | 直接分支 + 顺序继续 |
| 函数级 VGPR/SGPR 上限 | 无 | 无 |
| scale/relu、计算公式、host 接口 | 相同 | 相同 |

本例不强制零 scratch，也不对其他内联阶段添加寄存器上限。当前生成的主 kernel 恰好不需要 scratch；不能据此推断大型 ATOM Mono 同样不需要。

如果供应方仅提供已审计的 `.co`，可以在新的构建目录使用：

```bash
make BUILD=build_receiver STAGE_CO=/absolute/path/stage_sub.co run
```

这条依赖路径只读取供应方二进制，不要求本地 `sub_kernel.s`。更换供应方路径时使用新 BUILD 或先 clean。提取器固定验证函数 SHA，因此不接受未经重新审计的任意 `.co`。

## 已完成的验证

2026-11-09，ROCm 7.2 / gfx1100：

- 默认 `make run` 验证 4096 元素通过。
- 额外临时 host 使用同一份主 `mono_kernel.co` 验证 n=1、31、128、257，全部通过；临时源码和可执行文件未保留。不同大小可以通过修改 `mono_abi.h` 的 kElements 后重新构建复现。
- 实际 LLVM IR 包含完整 `.long`、12 个 i32 输入、clobber 和 convergent 属性。
- 最终可执行主函数中恰好包含一份 288 B payload，与供应方去掉末尾 return 后逐字节一致。
- 主 kernel 无 `s_getpc_b64`、`s_swappc_b64`、`s_setpc_b64`，无外部 stage_sub_device 符号及未解析重定位。
- 最终资源：VGPR 32、SGPR 26、LDS/private 0，VGPR/SGPR spill count 均为 0。

记录见 [静态结果](build/verification.json) 和 [本次实机结果](build/gpu_verification.json)。这些结果证明本例的编写、编译与执行流程；没有做性能对比，也没有在本目录接入真实 ATOM 算子。
