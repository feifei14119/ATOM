# 最小 Mono：普通设备函数调用与独立二进制链接

本目录只演示一条流程：将 ASM 编译成设备函数目标 `stage_sub.co`，将 Mono 调用方单独编译成 `mono_kernel.o`，通过 `ld.lld` 链接为 `mono_kernel.co`，最后由 HIP 加载、启动。

使用编译器默认的设备函数 ABI，不添加 VGPR/SGPR 上限，不修改 call-preserved regmask，不使用 inline asm 或二进制替换脚本。允许 `s_swappc_b64` / `s_setpc_b64`，也允许编译器按需使用 scratch。

## 构建和运行

环境：ROCm 7.2，gfx1100 / Radeon RX 7900 XTX。本机设备编号为 0。供应方汇编固定为 gfx1100，不能只修改 `-mcpu` 就移植到 gfx1250。

```bash
cd /home/feifei/repo/ATOM/mono_test0
make -j4
make run
make inspect  # 可选：输出汇编、反汇编和 ELF 信息
```

`make run DEVICE=0` 编译并运行一次，验证 4096 个元素的两个中间结果、最终结果和两个发布标记。`make clean` 删除默认构建目录。

## 最小调用链

```text
host: hipModuleLoad(mono_kernel.co)
    → hipModuleGetFunction("mono_kernel")
    → hipModuleLaunchCooperativeKernel：3 CTA × 128 threads

CTA 0: stage_sub_device(input, first, n, epoch)
           s_swappc_b64 → 独立 ASM：first = input - 1
                       ← s_setpc_b64
CTA 1: 等待 first → stage_scale：second = first * 2
CTA 2: 等待 second → stage_relu：output = max(second - 3, 0)
```

最终计算 `y[i] = max(2*x[i] - 5, 0)`。只有 `mono_kernel` 是可 launch 的 kernel；`stage_sub_device` 是 GPU 内部的普通 `__device__` 函数，调用它不会启动另一个 kernel。scale/relu 保持为独立头文件中的内联函数。

各 CTA 通过 global mailbox 和 acquire/release 标记通信。由于存在 CTA 间等待，host 保留 cooperative launch 与驻留容量检查。

主 kernel 有六个参数：`input, output, first, second, n, epoch`。本例不再包含用于验证跨调用寄存器的 lane_bias、额外加法或 sub_done 参数。

## 文件与二进制

| 文件 | 用途 |
| --- | --- |
| `mono_kernel.cpp` | 17 行主 kernel，包含一次普通外部设备函数调用 |
| `stages/sub_api.h` | 供应方函数声明，没有 C++ 实现 |
| `stages/sub_kernel.s` | 仅保留 `stage_sub_device` 的独立汇编；无 standalone kernel wrapper |
| `stages/scale.h`、`stages/relu.h` | 其余两个内联阶段 |
| `mono_abi.h`、`mailbox.h` | host/device 参数布局及 mailbox 同步 |
| `mono_demo.cpp` | 加载模块、启动和核对结果 |
| `Makefile` | 普通编译、链接、运行及可选反汇编 |

```text
stages/sub_kernel.s ── assembler ──────────→ stage_sub.co [ELF REL]
                                                      │
mono_kernel.cpp ── HIP RDC ─→ mono_kernel.bc            │
                                  │                   │
                              AMDGPU codegen          │
                                  ↓                   │
                            mono_kernel.o [ELF REL]   │
                                  └──── ld.lld ───────┘
                                           ↓
                                  mono_kernel.co [ELF DYN]
                                           ↓
                                      HIP 加载运行
```

`stage_sub.co` 的后缀是 `.co`，实际类型是可重定位目标 ELF REL，作用相当于 `.o`；最终可加载模块才是 ELF DYN。现成的 launchable `.hsaco` 不能仅改后缀就作为此处设备函数输入。

构建中的 `.bc` 是 HIP 分离编译的正常中间产物。整个过程没有暂停或修改 MIR，也没有修改编译器输出的指令。`make inspect` 生成的 `.s` 仅供阅读，不参与构建。

只持有已适配的供应方二进制时，可以在**新的构建目录**中执行：

```bash
make BUILD=build_receiver STAGE_CO=/absolute/path/stage_sub.co run
```

这条路径不依赖 `stages/sub_kernel.s`。更换供应方目标时使用新的 `BUILD` 或先清理，避免复用旧链接结果。

## 保存恢复与 ABI

调用方编译器按默认 ABI 处理参数和跨调用活跃值：可以使用 callee-saved 寄存器、重计算或 scratch spill/reload。此处不强制某一种保存策略，也不设置零 scratch 检查。

供应方 ASM 必须满足同一个设备函数 ABI。当前 `stage_sub_device` 已满足本例约定：参数使用 `v0:v7`，隐式参数指针位于 `s8:s9`，工作项标识位于 `v31`，返回地址位于 `s30:s31`，结尾用 `s_setpc_b64 s[30:31]` 返回。该函数包含 CTA barrier，因此生产者 CTA 的所有线程必须参与调用。

编译器不会反汇编外部 `.co` 来推断它破坏了哪些寄存器。若以后换成会覆盖 callee-saved 寄存器的 ASM，供应方仍须保存恢复这些寄存器，或先添加符合 ABI 的 wrapper。允许 scratch 不会自动修复供应方的 ABI 违规。

外部 ASM 的资源使用也必须被最终 descriptor 覆盖。本例供应方使用 32 VGPR、32 个编号 SGPR、零 private/LDS，已被本次编译的 Mono 资源覆盖；不能据此认为普通 ELF 链接器会自动推断任意新 ASM 的资源需求。

ABI 参考保留在 [中文译文](AMDGPU_DEVICE_FUNCTION_ABI.zh-CN.md) 和 [英文快照](AMDGPU_DEVICE_FUNCTION_ABI.en.rst)。

## 本机验证

2026-11-09，ROCm 7.2 / gfx1100：

- 从头编译和链接成功，GPU 核对 4096 个元素通过。
- 在没有供应方汇编/C++ 实现的临时接收目录中，仅使用 `stage_sub.co` 重新构建并运行通过。
- 供应方 292 字节函数体在清理前后、最终链接前后保持一致。
- 最终反汇编含一次 `s_swappc_b64` 和一次供应方 `s_setpc_b64`。
- 最终 metadata：VGPR 53、SGPR 36、固定 private 0，VGPR/SGPR spill count 均为 0。
- 当前 Mono 与供应方函数未生成 scratch load/store；这是本例编译结果，不是构建限制，也不代表运行时不分配 scratch 后备存储。`.uses_dynamic_stack` 为 true。
- 默认编译保留了 HIP 头文件带入的辅助函数，后端保守资源统计包含这些函数；本例不增加 IR 清理或资源修补步骤。

旧的 regmask 脚本、零 spill 检查、独立 probe、寄存器分组实验与旧构建产物已经移除。清理前的整个目录备份在 `/tmp/mono_test0-before-simplify-20261109.tar.gz`。
