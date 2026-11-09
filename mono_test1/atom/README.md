# gfx1250 dq_convert：通过 inline asm `.long` 接入 Mono

这里按 `../stages/sub.h` 的方式，将 `dq_convert.original.s` 改为可嵌入 Mono 的指令片段，再在 C++ `asm volatile` 中声明固定输入和全部 clobber。调用方由 LLVM 正常分配寄存器；不限制整个函数的 VGPR/SGPR 数量，不改写 IR，也不使用设备函数 ABI。

已完成 gfx1250 汇编、真实 C++ 调用方编译、链接和静态检查。本机 GPU 为 gfx1100/gfx1036，**尚未进行 gfx1250 真机计算验证，也尚未修改生产 ATOM 的编译和调度代码**。

## 文件与生成流程

| 文件 | 用途 |
| --- | --- |
| `dq_convert.original.s` | 用户提供的原始独立 kernel，保持原样 |
| `dq_convert.inline.s` | 新的可汇编指令片段，含参数适配、等待、wave 判断和浮点模式恢复 |
| `dq_convert.inline.co` | 从新 `.s` 汇编得到的 AMDGPU ET_REL，用于提取指令 |
| `dq_convert.inline.words.inc` | 从上述 `.co` 的指定符号提取的 `.long` C++ 字符串 |
| `dq_convert_inline.h` | C++ inline 入口，固定输入约束与 clobber 都在这里 |
| `dq_convert_args.h` | 精确的 240 字节参数结构，附字段偏移检查 |
| `dq_convert.inline.disasm.txt` | 新片段的反汇编，方便核对 `.long` |
| `inline_contract.json` | 目标、寄存器、改写清单和字节摘要 |
| `prepare.py` / `Makefile` | 可复现地生成 `.s`、`.co`、`.inc` |
| `compile_check.cpp` / `verify.py` | 两次非末尾 inline 使用的编译检查与静态审计 |
| `verification.json` | 最近一次验证结果 |

```text
dq_convert.original.s
       │ prepare.py：检查原始摘要，适配入口/出口，重命名寄存器
       ▼
dq_convert.inline.s ── clang assembler ──► dq_convert.inline.co
                                                │ 提取完整符号机器码
                                                ▼
                                     dq_convert.inline.words.inc
                                                │ #include 到 asm volatile
                                                ▼
                                      dq_convert_inline.h
                                                │ 与调用方一起编译、分配寄存器
                                                ▼
                                      调用方 .o ──► Mono .co
```

`.long` 数据直接成为调用方 `.text` 中的可执行指令。**不把它逐行覆盖进已生成的 ATOM 二进制，也不把 `dq_convert.inline.co` 作为设备函数链接。** `build/caller.co` 的链接输入只有 `build/caller.o`。

新 `.s` 有 section、符号和 `.size`，可以独立汇编。它不带独立 kernel descriptor/HSA kernel metadata，因为该片段使用外层 Mono kernel 的资源和调度环境。这里的 `.co` 是提取用的可重定位目标，不能用 `hipModuleLaunchKernel` 单独启动，也不能作为普通设备函数调用。

## 汇编做了哪些改写

1. **保留计算和访存主体。** 原来是 292 条指令、1528 字节；删除末尾 `s_endpgm`，执行完直接继续外层 Mono。适配后完整片段 1604 字节；没有 `s_setpc`、`s_swappc` 或外部符号引用。
2. **参数来自 inline 输入。** `s[0:1]` 是普通 GPU 全局参数块地址，删除原 kernarg 指针高位截断。`v0` 直接接收 lane 编号，因此删除原来对 `v0` 的写操作。`s24` 直接接收 CTA 内 wave 编号。
3. **去掉物理网格依赖。** 将 TTMP 中提取的三个 block ID 替换为 0；每个 CTA 用自己的参数块和指针表示一个独立 tile。wave ID 不再读 TTMP。保持这些局部替换的字节长度，便于逐偏移核对。
4. **适配 256 线程的 Mono block。** 只有 `wave < 4` 执行原始的 128 线程计算；其余 wave 跳到片段末尾。片段内部没有 CTA barrier，外层仍需全 CTA 同步。
5. **将原来的 `s30–s38` 一一重命名到 `s40–s48`。** 同时改写源、目的和寄存器对，再由汇编器重新编码。这样避开 LLVM 可能用作栈/帧等状态的寄存器；不依赖 clobber 能保护编译器保留的栈寄存器。
6. **维护硬件状态。** 前后加入保守的 load/store/DS/KM/X/dependency 等待。用 `s5` 保存 MODE 低 8 位，片段内设为原 descriptor 的 `0xc0`，退出前恢复。这里只修改浮点舍入/denorm 字段，不改 gfx1250 VGPR bank 字段。原计算各段会暂时改 EXEC，并恢复完整 wave32 EXEC。

当前浮点模式切换采用保守的原 descriptor 设置。这个 kernel 的主要浮点指令是 `v_cvt_pk_bf16_f32`；本地 LLVM 将其标为 `ReadsModeReg = 0`，因此该切换不代表已证明 BF16 转换必须依赖这些字段。这里保留显式切换和恢复，性能精简留待目标硬件验证。

生成器固定原始 `.s` 的 SHA-256 为 `4050f8e1eacf2463c98adeb8f2aeee2ca93e2792de3a43e58088cbd36a05a711`。更换供应方二进制后必须重新审计参数、寄存器和控制流；这不是任意 `.co` 的通用转换器。

## 编译器可见的边界

入口如下，完整定义见 `dq_convert_inline.h`：

```cpp
__device__ __forceinline__ __attribute__((convergent))
void stage_dq_convert_inline(const DqConvertArgs* args, unsigned linear_tid);
```

固定输入是直接写在约束字符串中的：

```cpp
: [args] "{s[0:1]}"(address), [lane] "{v0}"(lane), [wave] "{s24}"(wave)
```

没有在片段入口手写参数 `mov`。LLVM 可以直接安排输入，也可能在 asm 外生成必要的搬运；固定约束不保证调用方完全没有 `mov`。

| 资源 | 边界契约 |
| --- | --- |
| `s0:s1` | 只读输入：所有线程一致的全局参数地址 |
| `v0` | 只读输入：`linear_tid & 31` |
| `s24` | 只读输入：当前物理 CTA 内的 wave ID |
| `s2–s23`、`s25–s29`、`s40–s48` | 全部声明为 clobber；`s5` 包括在内 |
| `v4–v45` | 全部声明为 clobber |
| SCC、memory | 声明为 clobber |
| EXEC | 必须全 wave 进入；片段内部临时改变，返回时恢复全 wave |
| MODE 低 8 位 | 在 `.s` 中保存、设置、恢复 |
| VCC、M0、TTMP、`s30–s39` | 片段不改写 |
| LDS、scratch | 片段自身均为 0；调用方的分配由 LLVM 决定 |

寄存器 clobber **不会自动生成一套全寄存器 push/pop**。它告诉 LLVM：跨越该边界的活跃值不能继续依赖这些寄存器。LLVM 可以使用其他寄存器、搬运、重计算，压力高时也可能 spill。这里没有保证任意 ATOM 调用方都能做到 scratch 为 0。

固定输入不同时列入 clobber，因为改写后的片段确实不会写它们。如果将来修改片段写了这些寄存器，应同步改成合适的读写操作数/约束，不能只改 `.long`。

对 gfx1250 还需保证使用正确的 VGPR bank。当前 LLVM 的 `AMDGPULowerVGPREncoding` 在有 VGPR 输入的 inline asm 前恢复 bank 0；这里的 `v0` 输入使该边界可见。当前检查调用方只使用低编号 VGPR。生产调用方如使用 `v256+`，仍应在最终反汇编中核对 bank 切换，不能仅凭本例推断已覆盖该场景。

## 最小调用与参数

仅支持本次验证的 **gfx1250、wave32、一维 128 或 256 线程 CTA、完整 64×64 tile**。`linear_tid` 使用真实的 `threadIdx.x`。整个 CTA 必须在一致的控制流中调用，不能放在 `if (tid < 96)` 或其他只有部分 lane 参与的分支内。

参数块必须在 GPU 全局内存中、16 字节对齐、dispatch 期间保持不变；不能传线程私有栈上的结构地址。每个 CTA 的输入、输出和参数块应独立，以避免并发写同一个 tile。

在 host 构造参数，再复制到设备全局内存，例如：

```cpp
DqConvertArgs h{};               // 所有保留字段置零
h.ptr_dq_acc = device_packed_fp32; // 至少 4096 float，即 16 KiB
h.ptr_dq = device_bf16_bits;       // 至少 4096 uint16_t，即 8 KiB
h.Hs_dq_acc = 16384;
h.BAs_dq_acc = 16384;
h.Seqs_dq_acc = 256;             // 所有 stride 单位均为字节
h.Hs_dq = 8192;
h.BAs_dq = 8192;
h.Seqs_dq = 128;
h.seqlen_q = 64;
h.head_dim = 64;
h.max_seqlen_dq = 64;
// ptr_qseq/ptr_qseq_padded = nullptr，nsplit/split_stride = 0。
// hipMalloc 分配 device_args，并在 dispatch 前将 h 复制过去。
```

这个供应方 kernel 的 FP32 输入不是普通行优先 64×64。若期望输出对应 `X[r*64+c]`，输入应按以下方式打包：

```cpp
unsigned sr = 16*(r/16) + 8*((c/16)%2) + r%8;
unsigned sc = 32*(c/32) + 16*((r/8)%2) + c%16;
packed_fp32[sr*64+sc] = X[r*64+c];
```

输出为行优先的 4096 个 BF16 位模式。静态验证检查了这个打包公式和汇编 load/store 地址公式的一一对应；转换结果、NaN/Inf/边界值仍需在 gfx1250 上与原 kernel 比较。

调用方的阶段边界示意：

```cpp
// 整个 CTA 的前序步骤先写好自己的 packed_fp32。
__threadfence_block();
__syncthreads();
stage_dq_convert_inline(device_args_for_this_cta, threadIdx.x);
__threadfence_block();
__syncthreads();
// 后续步骤在这里读取 BF16 输出并继续执行。
```

片段内的 wait 只等待本 wave 的操作，`"memory"` 是编译器边界，它们都不能代替 CTA barrier。跨 CTA 发布结果时，仍要沿用 ATOM 的 mailbox、release/acquire 和 epoch/tag 协议；上面的 block fence 不能代替跨 CTA 同步。

## 编译和核对

```bash
cd /home/feifei/repo/ATOM/mono_test1/atom
make
make check
```

也可以直接编译新 `.s`：

```bash
/opt/rocm/llvm/bin/clang++ --target=amdgcn-amd-amdhsa \
  -mcpu=gfx1250 -x assembler -c dq_convert.inline.s -o dq_convert.inline.co
```

正常修改流程是编辑 `prepare.py`，运行 `make` 重新生成 `.s/.co/.inc`，同步审计 `.h` 的约束，然后运行 `make check`。不要仅手工修改 `.s` 后继续使用旧的 `.inc`。

本次使用 ROCm 7.2 / AMD clang 22。检查内容包括：

- 原 `.s` 重新汇编的指令字节与原注释一致；改写主体只包含明确的入口补丁、退出删除和 SGPR 重命名。
- 所有被写的 GPR 都在 clobber 中，固定输入确实只读；EXEC/浮点模式在参与 wave 路径恢复，跳过路径不改动它们。
- 提取的片段无 relocation；内部条件分支准确落到片段末尾，`.inc` 字节与 `.co` 完全一致。
- 同一个真实 C++ 调用方中连续使用两次 header；最终 `.co` 的两处指令字节与片段完全一致且按 64 字节对齐。
- 检查 LLVM IR 的固定输入和 clobber、最终 HSA metadata 与 kernel descriptor；没有 IR/descriptor 补丁。
- 编译检查的结果为 **46 VGPR、49 SGPR、LDS 0、scratch 0、VGPR/SGPR spill 0**，没有 PC 调用/返回指令。46/49 是该检查调用方的资源统计，不是对整个 ATOM Mono 的上限。

`build/caller.boundary.txt` 去掉长 `.long` 列表，便于观察 LLVM 的边界分配。例如本次编译将跨边界的状态放在 `v1–v3`、`s36–s39`，这些位置不在 clobber 中。`build/caller.ll` 仅用于检查普通编译产物，没有对其编辑。

## 对接 ATOM 的下一层

这个 `.h` 可直接用于 HIP/C++ Mono 调用方。PR #2908 的 Mono 主体经 FlyDSL/MLIR 生成，Python 文件不能直接 `#include` C++ header。实际接入时，需要在 **寄存器分配之前** 发出等价的 LLVM inline asm：相同 `.long`、3 个固定输入、完整 clobber、side-effect/convergent 属性及内存副作用。

为选中的阶段准备 CTA 独立的全局参数和 packed tile，并在一致控制流中执行边界。若将它用于 `stage_wqkv` 的 BF16 舍入实验，它只替代相应的转换子步骤，不能替代 WQKV GEMM；少量有效元素必须填入完整 tile，其余位置初始化，输出再转换成后续步骤期望的表示。

在 `gpu.binary` 已经生成后再替换机器码，无法让 LLVM 根据上述 clobber 安排活跃值。新阶段还可能改变寄存器压力及常驻 CTA 数量，因此要重查完整 Mono 的 descriptor、scratch/spill、occupancy，以及 PR 中的 residency 检查。当前小调用方的零 scratch 结果不等于通过了 ATOM 的这些条件。

相关 PR：<https://github.com/ROCm/ATOM/pull/2908>。
