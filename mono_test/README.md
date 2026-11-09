# 无 call/return 的二进制阶段融合

二进制接入方式及两种跨阶段状态管理方法的完整原理、ABI、构建命令、验证记录与性能边界，见
[Mono kernel 二进制阶段接入与跨阶段状态管理](BINARY_STAGE_INTEGRATION.md)。

如何通过固定跨 ASM 边界的活跃状态、只保存少量寄存器，见
[边界约束与实现步骤](BINARY_STAGE_INTEGRATION.md#bounded-boundary-state)。该节明确区分现有实验与后续接入方案。

该约束的可运行 LLVM 示例见[编译器可见边界实验](COMPILER_BOUNDARY_EXPERIMENT.md)。
运行 `make run-boundary`，可比较两种 SGPR 保存预算、检查过小 VGPR 预算触发的 spill 拒绝，
并验证两个全 GPR 覆写的非末尾二进制阶段。较小配置只保存 8 VGPR + 10 SGPR，private scratch 为 0。

下一步使用真实 AITER gfx1250 `.co` 的详细方案见
[gfx1250 AITER 接入步骤](GFX1250_AITER_INTEGRATION_PLAN.md)：选择最小的 BF16 转换 kernel，
替换 PR #2908 target-6 K1 的 WQKV 输出舍入子步骤，列出参数、布局、TTMP 入口适配和完整验证步骤。
算子侧产物已放在 [atom/](atom/README.md)：原版完整汇编、适配版汇编和新的
[dq_convert.mono.co](atom/dq_convert.mono.co)。运行 `make -C atom` 可复现编译与静态检查；
真实 ATOM 主体接入与 gfx1250 真机验证尚待执行。

ATOM PR #2908 的 K1/K2 算子、不同宽度的实现入口及融合边界，见
[PR #2908 Mono kernel 集成算子清单](PR_2908_MONO_OPERATORS.md)。

针对“非末尾 ASM 阶段覆盖全部通用寄存器”的后续实验，见
[全寄存器覆盖与阶段状态恢复](CLOBBER_STAGE_EXPERIMENT.md)。运行 `make run-clobber`
可复现负对照、private 上下文保存及 private-scratch-free 阶段重建三种情况。

当前默认构建从 GPU 二进制中取出 `stage_sub_device`，在最终汇编前将它嵌入
Mono 的 CTA 0 路径。最终 `mono_kernel` 没有 `s_getpc_b64`、`s_swappc_b64`
或 `s_setpc_b64`；减法阶段不需要 C++ 实现或 LLVM IR。

本例的 `stage_sub` 是 CTA 0 的最后一步，因此用一条 `s_branch` 进入减法指令，
完成后直接接 Mono 的 `s_endpgm`，不需要返回跳转。入口 branch 跳过对齐填充，
避免线程额外执行 NOP；CTA 分派和阶段内部循环仍使用普通条件分支。

## 为什么普通设备链接不够

普通 `.o + .o → .hsaco` 静态链接会解析函数地址，但不会自动将已经生成的
机器码函数内联。它会保留函数地址计算、`s_swappc_b64` 和 `s_setpc_b64`。
原方案仍可用 `make run-call` 运行，产物为 `build/mono_kernel_call.hsaco`。

此外，本机 LLVM 汇编器不支持直接用 `s_branch` 引用另一个目标文件中的
未定义标签。因此默认方案是在 **最终汇编前** 合并阶段，使跳转与标签处于
同一汇编单元内，而不是把 call 简单改为跨目标文件的 branch。

## 默认构建流程

```text
mono_kernel.cpp + sub_api.h + scale.h + relu.h
                  ↓ 编译器准备参数寄存器，生成含外部调用的中间汇编
          mono_kernel_call.s ─────────┐
                                     ├─ fuse_sub.py → mono_kernel.s
供应方的 stage_sub.o ────────────────┘                        ↓ 汇编、链接
（或由 sub_kernel.s 汇编生成）                        mono_kernel.hsaco
```

`fuse_sub.py` 做以下几件事：

1. 用 ELF 符号的地址和大小定位 `stage_sub_device`，读取实际机器指令。
2. 校验 gfx1100、固定资源契约、无重定位、内部跳转范围及单一末尾返回。
3. 删除调用方的函数地址计算，将 `s_swappc_b64` 改为普通 `s_branch`，嵌入阶段机器码。
4. 去掉阶段最后的 `s_setpc_b64`，顺序执行调用方已有的 `s_endpgm`。
5. 保留 Mono 的 descriptor、metadata 和保守资源配置，再汇编、链接。

最终汇编用 `.long` 保存阶段的原始指令字，后面附带反汇编注释。
这不会重新翻译减法算法，也不会重新分配阶段内部的寄存器。
已验证当前 `stage_sub.o` 的函数返回之前 **288 字节机器码完整保留**，
内部相对分支的距离也不变；原返回指令的位置由 4 字节 `s_endpgm` 接替。
没有被使用的 HIP 运行库函数体不带入最终汇编。

这是针对当前 ROCm 7.2 / gfx1100 / wave32 示例的有限二进制融合器，
不是通用的反编译或任意 kernel 内联工具。编译器改变调用位置的指令布局，
或输入函数不符合约定时，脚本会报错，需要重新检查适配。

## 接口与适用范围

`stages/sub_api.h` 只有声明，没有减法实现：

```cpp
extern "C" __device__ void stage_sub_device(
    const float* input, Mailbox output, int n, unsigned epoch);
```

`Mailbox` 是两个 64 位指针 `data`、`tag`，按值传递。
当前机器码使用 HIP 默认设备函数 ABI：显式参数在 `v0:v7`，工作项标识在
`v31`，隐式参数指针在 `s8:s9`，CTA x 标识在 `s12`。
生产者 CTA 的全部线程参与调用，写完数据后用块内 barrier 和 agent release
原子 store 发布 epoch。

优先交付 `build/stage_sub.o` 这样的 ELF `REL` 设备函数目标。使用方需要
符号表、资源信息以及双方约定的 ABI，但不需要任何减法实现源码。
当前脚本也能读取保留相同函数、符号及资源信息的自包含 ELF code object；
不能因此推断普通只含 `__global__` kernel 入口的 `.hsaco` 都能融合。
独立 kernel 的 ABI、终止语义、重定位、LDS 和内部调用可能完全不同。

资源约定包括 32 VGPR、32 个编号 SGPR、无 AGPR、无 scratch、无递归或内部调用。
脚本只接受当前阶段使用的指令集合及内部条件分支。当前调用点必须是 CTA 0
的最后一步，紧接 kernel 结束；不能把任意中间调用都当作这种尾部路径处理。

## 本机运行

依赖 ROCm 7.2、C++17 编译器、make 和 Python 3 标准库，无需 ATOM、AITER、
FlyDSL 或额外 Python 包。

```bash
cd /home/feifei/repo/ATOM/mono_test
make run
```

默认从 `stages/sub_kernel.s` 汇编出 `build/stage_sub.o`，然后进行二进制融合。
`stages/sub.cpp`、`stages/sub.h`、`stages/add.h` 不在这条构建路径的依赖中。

供应方直接给了 `.o` 时：

```bash
make -B run STAGE_SUB_OBJECT=/absolute/vendor/stage_sub.o
```

此路径也不需要减法 `.s`。`-B` 确保切换输入二进制时重新构建。
本例已在新目录中仅放调用方源码、接口声明、融合脚本和供应方 `.o`，
没有 `sub.cpp`、`sub.h` 或任何输入汇编文件，从零构建和运行通过。
构建过程中生成调用方及最终汇编，这是本地中间产物。

可分别执行：

```bash
make stage-sub-object  # 生成供应方可交付的二进制
make asm               # 生成最终融合汇编 build/mono_kernel.s
make kernel            # 汇编并链接默认 Mono code object
make check-branches    # 反汇编并断言无 getpc/swappc/setpc
make run-call          # 保留的普通设备函数链接版本，供对照
```

最终汇编和链接的实际命令：

```bash
python3 fuse_sub.py \
  --caller build/mono_kernel_call.s --stage build/stage_sub.o \
  --output build/mono_kernel.s --llvm-bin /opt/rocm/llvm/bin
/opt/rocm/llvm/bin/clang++ --target=amdgcn-amd-amdhsa -mcpu=gfx1100 \
  -x assembler -c build/mono_kernel.s -o build/mono_kernel.o
/opt/rocm/llvm/bin/ld.lld -shared --no-undefined \
  build/mono_kernel.o -o build/mono_kernel.hsaco
```

最终这一步不再链接 `stage_sub.o`，因为其指令已经嵌入 Mono。

## 验证结果与性能边界

本机 RX 7900 XTX 的实际指令检查结果（普通调用版本合计调用者和 sub 函数）：

| 指令 | 普通设备函数链接 | 默认融合版本 |
| --- | ---: | ---: |
| `s_getpc_b64` | 1 | 0 |
| `s_swappc_b64` | 1 | 0 |
| `s_setpc_b64` | 1 | 0 |

完整 GPU 运行结果：

```text
GPU 0: Radeon RX 7900 XTX (gfx1100), wave size 32
PASS: mono_kernel has no getpc/swappc/setpc instructions
PASS: 32 epochs x 4096 elements; 1 kernel launch per epoch, 3 CTAs x 128 threads
Formula: y = max(2*x - 5, 0)
```

当前只验证了机器码结构和功能正确性，未进行性能计时。
**消除 call/return 并不等于恢复源码内联的全部优化。** 参数寄存器搬运仍保留，
Mono 仍采用编译器对外部函数的保守资源配置（53 VGPR / 36 SGPR 等），
阶段内部的寄存器分配和指令调度也已固定。因此不能只据这些指令数宣称性能
与源码内联相同或必然更快。

如果进一步要求跨阶段寄存器分配、消除参数搬运或跨阶段调度，需要供应方提供
可优化的 LLVM IR/bitcode，或双方约定可参数化的汇编片段接口。仅凭任意已经
生成的机器码，不存在等同源码内联效果的通用编译选项。

## Mono 的执行与文件

一次 cooperative launch 启动 3 个 CTA，每个 CTA 128 线程：

```text
CTA 0: a[i] = x[i] - 1         → 发布 mailbox 1
CTA 1: 等待 mailbox 1，b=a*2  → 发布 mailbox 2
CTA 2: 等待 mailbox 2，y=max(b-3,0)
```

host 仍由普通 C++ 编译器构建，读取 `.hsaco` 后使用 `hipModuleLoadData`、
`hipModuleGetFunction("mono_kernel")` 和 `hipModuleLaunchCooperativeKernel`。
cooperative launch 保证这个小 grid 的驻留条件，消费者使用 acquire 读取标签。
最终 code object 只有 `mono_kernel` 一个可启动入口。

```text
mono_kernel.cpp             调用方源码，生成中间调用序列
stages/sub_api.h             仅有设备接口声明
stages/sub_kernel.s          可选的供应方汇编输入
fuse_sub.py                  有限的二进制阶段融合器
build/stage_sub.o            无需源码即可交付的 GPU 设备函数
build/mono_kernel_call.s     编译器中间汇编，仍含外部调用
build/mono_kernel.s          最终融合汇编，无 call/return
build/mono_kernel.disasm.txt 最终机器码的可读反汇编
build/mono_kernel.hsaco      默认融合目标
build/mono_kernel_call.hsaco 普通设备函数链接对照目标
```

`make run-sub` 保留独立减法 kernel 的 36 组校验；`make sub-asm` /
`make sub-code-object` 保留独立减法汇编实验。`make sub-object` 是早期从
`sub.cpp` / `sub.h` 生成历史 `build/sub.o` 的可选实验，与默认构建无关。

ATOM PR #2908 的相关 Mono 路径主要在源码/IR 层融合。本例为了演示只交付
机器码的场景，采用汇编前拼接；两者可达到相似的分支控制流，但优化能力不同。
