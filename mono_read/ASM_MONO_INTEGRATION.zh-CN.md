# ATOM Mono 接入 ASM：mono_test00 / mono_test01 / mono_test10 实现对照

本文按 2026-11-10 工作区中的实际代码整理。目标是把供应方 ASM 接入 FlyDSL 编写的 ATOM Mono，让算子前后的 Mono 代码继续使用正确的上下文。三个目录分别为：

- [mono_test00](../mono_test00/README.md)：**标准设备 ABI 包装器，编译成 bitcode，通过 FlyDSL `ffi + link_extern` 接入**。目录原名为 `mono_test20`，现在统一使用 `mono_test00`。
- [mono_test01](../mono_test01/README.md)：**独立 ASM 设备函数，修改调用点的 call-preserved regmask，再进行机器码链接**。
- [mono_test10](../mono_test10/README.md)：**将 ASM 指令编码为 `.long`，直接放进 Mono 的 inline asm，声明固定输入和完整 clobber**。

三者的 Mono 主体均由 FlyDSL 编写。`00` 中的 HIP/C++ 仅用于设备包装函数，`01` 的独立 `.co` 是设备函数目标，`10` 的 `.co` 用来提取指令。

**验证记录的来源：** 当前三个目录的 README 均已记录 gfx1250 实机 A/B 通过结果。本文的运行数据摘自这些记录。本地当前没有相应的最新 `build/result.json`，只有 `00` 的早期离线产物以及旧静态检查记录；本文不将它们当作新一轮实机测试的原始报告。本次整理没有重新编译或运行 GPU。旧 `VALIDATION.json` / `STATIC_CHECKS.json` 中的“未运行”是早期检查状态。

## 1. 三种方案测试的是同一段计算

共同基线来自 [mono_test_origin](../mono_test_origin/README.md)，保留的 ATOM PR #2908 来源提交是 `7c925f72b22ee6a815fd6d63734bbcff5fa72a08`。

| 配置 | 当前值 |
| --- | --- |
| GPU / 物理 wave | gfx1250 / wave32 |
| C：并发 token 数 | **1，单 token** |
| 网格 | 256 CTA，每 CTA 256 线程，即 8 个物理 wave |
| 主体 | `build_projection_asm()` 内的 `projection()` |
| 基线阶段 | slice → RMSNorm/FP8 → WQKV |
| WQKV 输出 | 112 个 task，每 task 16 个值，共 1792 个值 |
| 供应方 | `fmha_bwd_hd64_dq_convert_bf16`，FP32→BF16 转换和 tile 布局整理 |
| 实际替换位置 | WQKV 矩阵乘和 FP32 累加之后的 `bf16_round(total)` |

**这里没有用 dq_convert 替换整个 WQKV GEMM。** 三者保留相同的 WMMA 和八路 FP32 累加，只替换舍入步骤。`feeds_index=True` 用于输出 normed/NB 供校验，没有增加 indexer，也不运行整个网络。

```text
原始路径：
slice → RMSNorm/FP8 → WQKV WMMA → FP32 累加 → bf16_round → 发布 QKV

三种 ASM 路径：
slice → RMSNorm/FP8 → 同样的 WMMA → 同样的 FP32 累加
    → 写本 task 的 packed FP32 tile
    → wait + 全 CTA barrier
    → 通过 00 / 01 / 10 的边界执行 dq_convert
    → wait + 全 CTA barrier
    → 读取 BF16 输出，转为 FP32 表示
    → 使用原 task、tid、输出地址和 mailbox 上下文发布 QKV
```

每 task 分配 16 KiB FP32 输入、8 KiB BF16 输出、240 字节参数记录，以及输入/输出 tile 两侧各 256 字节 guard。16 个有效结果位于逻辑 64×64 tile 的第 0 行、第 0～15 列，其余位置也参与转换和校验。

这意味着每 16 个有效结果会转换 4096 个元素，且增加中间 global memory 读写。因此三个版本首先验证接入流程与正确性，不能直接用它们推断替换真实 WQKV 的性能收益。

## 2. 一张表看清区别

| 比较项 | mono_test00 | mono_test01 | mono_test10 |
| --- | --- | --- | --- |
| Mono 看到的边界 | 普通设备函数 call | 设备函数 call，自定义保持集合 | LLVM inline asm |
| 算子机器码所在位置 | 独立 wrapper 函数内部 | 独立 ASM 函数内部 | Mono 函数内部 |
| 参数入口 | 标准 ABI：`uint64 + uint32` | 标准参数布局：`ptr + i32` | 固定输入：s0:s1、v0、s24 |
| 寄存器保护依据 | 默认 ABI；wrapper 内部有 clobber | 调用点 `CustomRegMask` | 片段完整 clobber |
| 谁保护 Mono 的活跃值 | LLVM 按默认 ABI 安排 | LLVM 按自定义 regmask 安排 | LLVM 按 inline asm 约束安排 |
| 谁履行 callee 的保持责任 | 编译器生成 wrapper 保存恢复 | ASM 不写承诺保持的寄存器 | 没有独立 callee ABI 边界 |
| 是否有真实 call/return | 有 | 有 | 该 ASM 边界没有 |
| `.long/.inc` | 有，在 C++ wrapper 内 | 无 | 有，直接嵌入 Mono |
| 核心链接对象 | wrapper 的 `.bc` | 调用方 `.o` + ASM `.co` | 无独立算子目标链接，内嵌指令 |
| 是否显式调用 `llc` | 否 | 是 | 否 |
| 是否修改 MIR/regmask | 否 | 是，在寄存器分配之前 | 否 |
| 是否限制整个 Mono 的 GPR 数量 | 否 | 否 | 否 |
| 是否保证零 scratch | 否 | 否 | 否 |
| 构建接入 | FlyDSL 原生 FFI/bitcode 链接 | 临时编译 hook + LLVM/MIR 流程 | FlyDSL 正常 inline asm 编译 |

“编译器自动处理”有不同含义：`00` 是默认 ABI 的 caller 管理与 wrapper 保存恢复；`01` 是 caller 按缩小的保持集合分配/溢出；`10` 是避免让活跃值被 inline 片段覆盖。它们不意味着编译器自动理解任意黑盒机器码。

## 3. 共同的参数和 ASM 适配

### 3.1 参数从哪里来

host 初始化 112 个 `DqConvertArgs`，组成 GPU global memory 参数表。表地址作为修改后 Mono 的第 15 个参数 `dq_args` 传入，原有 14 个参数顺序不变。

`stage_wqkv_asm()` 按下式获得当前 task 的记录：

```text
record = dq_args + task * 240
```

参数结构见 [dq_convert_args.h](../mono_test00/asm/dq_convert_args.h)。关键字段如下，所有 stride 都以字节计：

| 偏移 | 内容 | 本单测设置 |
| --- | --- | --- |
| 0x00 | FP32 输入地址 | 本 task 的 packed 输入 tile |
| 0x10 | BF16 输出地址 | 本 task 的输出 tile |
| 0x20 / 0x30 | 输入 head / batch stride | 16384 / 16384 |
| 0x40 | 输入 row stride | 256 |
| 0x50 / 0x60 | 输出 head / batch stride | 8192 / 8192 |
| 0x70 | 输出 row stride | 128 |
| 0x80 / 0x90 / 0xc0 | seqlen / head_dim / max_seqlen | 64 / 64 / 64 |

其余字段按当前单 tile 场景初始化，保留字段清零。供应方从这个记录中读取实际数据指针和尺寸，不能将 Mono 自身的 HSA kernarg 布局直接当作供应方参数布局。

### 3.2 三种边界最终都准备相同的供应方输入

| 供应方片段的入口寄存器 | 内容 |
| --- | --- |
| s0:s1 | wave 内一致的 `record` 地址 |
| v0 | `linear_tid & 31`，物理 wave 内 lane |
| s24 | `readfirstlane(linear_tid) >> 5`，CTA 内物理 wave 编号 |

Mono 的物理 CTA 编号与供应方逻辑 tile 坐标不是同一个概念。当前每个参数记录描述一个独立 tile，适配代码把供应方所用的逻辑 block/head/batch 坐标设为 0，不再直接读取原始 TTMP dispatch 坐标。

所有 8 个 wave 都到达边界；供应方内部让 wave 4～7 跳过转换，wave 0～3 完成 tile。边界必须处于约定的 full EXEC / 全 CTA 路径，不能放进 `tid < 16` 分支。

### 3.3 从独立 GPU kernel 适配成内部步骤

三者均保留 `asm/dq_convert.original.s`，另存适配后的 `.s`，由 `asm/prepare.py` 可复现生成。主要改动包括：

1. 移除独立 launch 的 kernel descriptor/metadata，生成内部代码符号。
2. 准备参数记录地址、lane 和 wave，替换原始入口和 TTMP 依赖。
3. 原 s30～s38 改为 s40～s48，避开返回地址及栈相关寄存器。
4. 保存/恢复所修改的 MODE 低 8 位，按 full wave32 契约恢复 EXEC。
5. 为片段边界加入所需等待，去除结束整个 kernel 的 `s_endpgm`。
6. `00/10` 片段结束后顺序继续；`01` 使用返回地址进行设备函数返回。

当前适配不改写 VCC、M0、TTMP、s30～s39 或 gfx1250 VGPR bank 位。不能据此认为任意 ASM 都能覆盖这些特殊状态；换供应方时需要重新确认执行契约。

## 4. mono_test00：标准 ABI wrapper bitcode + FFI

### 4.1 编译与链接流程

```text
asm/dq_convert.original.s
    ↓ prepare.py 适配，保留原件
asm/dq_convert.inline.s
    ↓ Clang 汇编为 ET_REL 目标
build/asm/dq_convert.inline.co
    ↓ 提取完整符号，检查字节、大小、对齐和无重定位
build/asm/dq_convert.inline.words.inc
    ↓ #include 到 inline asm，给出固定输入和完整 clobber
asm/dq_convert_inline.h
    ↓ forceinline 到普通设备包装函数
asm/dq_wrapper.cpp
    ↓ Clang -emit-llvm；opt 清理无用函数
build/wrapper/dq_wrapper.bc
    ↓ FlyDSL link_extern，在机器码生成之前链接
Mono IR + wrapper IR
    ↓ 正常 LLVM 后端代码生成
build/ffi/kernel.co：Mono 函数 + 独立 wrapper 函数
```

这里的 `.bc` 是真正的 LLVM 函数定义，内部包含 opaque inline asm 字符串。它没有把 `.co` 改后缀，也没有把机器码还原成可优化的算子 IR。

### 4.2 调用链与接口

```text
projection()
  → stage_wqkv_asm(matrix, task, ops, dq_args)
    → invoke_dq_convert(record, tid)                 dq_ffi.py
      → ffi("mono_dq_convert_wrapper", ...)
        → llvm.call @mono_dq_convert_wrapper(i64, i32)
          → 编译器生成的 wrapper 保存代码
          → 准备供应方 s0:s1 / v0 / s24
          → .long 片段
          → 编译器生成的恢复与 return
```

[dq_wrapper.cpp](../mono_test00/asm/dq_wrapper.cpp) 的实际函数为：

```cpp
extern "C" __device__ __attribute__((noinline, convergent))
void mono_dq_convert_wrapper(std::uint64_t args_address,
                             std::uint32_t linear_tid) {
  stage_dq_convert_inline(
      reinterpret_cast<const DqConvertArgs*>(args_address), linear_tid);
}
```

[dq_ffi.py](../mono_test00/mono1250/kernels/dq_ffi.py) 使用：

```python
stage = link_extern(
    ffi("mono_dq_convert_wrapper", ["uint64", "uint32"],
        "void", is_pure=False),
    bitcode_path=str(BITCODE),
)
```

包装器保持 `noinline`，因此保留真实设备函数边界。当前 FFI 没有 convergence 参数，`invoke_dq_convert()` 在 IR 构建阶段给刚生成的 call 补上 `convergent`，函数定义也带有该属性。这里没有修改 MIR 或后端编译流程。

### 4.3 保存恢复与寄存器约束

[dq_convert_inline.h](../mono_test00/asm/dq_convert_inline.h) 声明的固定输入是 `{s[0:1]}`、`{v0}`、`{s24}`；污染集合是：

```text
SGPR：s2～s23、s25～s29、s40～s48
VGPR：v4～v45
其他：SCC、memory
```

固定输入在片段中只读，不重复列为 clobber。片段改变 EXEC/MODE 后按契约恢复。`memory` 是编译器的内存副作用约束，实际硬件等待和 CTA 同步由相应代码执行。

- **Mono 调用方：** 编译器按默认 ABI 安排跨调用活跃值，可以使用保持寄存器、搬运、重算或 scratch。
- **wrapper：** 编译器看得到内部 clobber，为会被改写的 callee-saved 寄存器生成保存恢复。
- **片段：** 自己负责特殊状态和入口/出口适配，不手写通用 GPR 的 ABI 保存恢复。

当前片段会改写默认保持集合中的 v40～v45 和 s48。早期 Clang 22 的独立 wrapper 汇编显示：v40～v45 保存到 scratch，s48 暂存到 v3 的 lane 0，另有保护非活动 lane 的操作；private frame 为 32 字节/线程。这是包装器离线观察，最终 Mono 的资源另见第 7 节。

该方案与 `callee_test00` 使用相同的标准设备调用基础，但 `callee_test00` 手写被调 ASM 的 ABI 保存恢复；这里通过 wrapper 内的 clobber 让编译器生成。只写一个外部 `__device__` 声明而直接链接不守 ABI 的黑盒 `.co`，不能得到同样的保护。

## 5. mono_test01：独立 ASM + 调用点 regmask

### 5.1 编译与链接流程

```text
原始 ASM → 适配入口、重命名寄存器、普通设备返回
    ↓
asm/dq_convert.lowctx.s → build/asm/dq_convert.lowctx.co
                                              │
FlyDSL Mono → 外部 llvm.func 声明 + llvm.call    │
    ↓ device_codegen.py 临时编译 hook           │
正常 lowering，末尾 format=llvm → caller.bc     │
    ↓ opt 清理                                 │
caller.codegen.ll                              │
    ↓ llc -stop-after=finalize-isel             │
caller.before_regmask.mir                       │
    ↓ callsite_regmask.py 修改目标 SI_CALL      │
caller.lowctx.mir                               │
    ↓ llc -start-after=finalize-isel             │
寄存器分配 / 调度 → caller.lowctx.s             │
    ↓ Clang 汇编                               │
caller.lowctx.o ───────── ld.lld 链接 ──────────┘
    ↓
build/lowctx/kernel.co → 放入 gpu.binary → 普通 FlyDSL launcher
```

`llc` 是 LLVM 的后端工具，可读取 LLVM IR 或 MIR，完成指令选择、寄存器分配、调度及代码输出。这里使用它暂停并继续后端流水线；修改 regmask 的是 Python 脚本，按修改后的约束生成代码的是 LLVM。

MIR 中修改的是目标 `SI_CALL` 的保持掩码，不是在最终机器码中插入调用或覆盖指令。链接也是构建时的 ELF 链接，没有 GPU 运行时动态解析算子。

### 5.2 实际参数传递

[dq_device.py](../mono_test01/mono1250/kernels/dq_device.py) 生成外部 `llvm.func @mono_dq_convert_lowctx(!llvm.ptr, i32)` 和真实 call。对应 [C++ 对照声明](../mono_test01/asm/dq_convert_api.h) 为：

```cpp
extern "C" __device__ __attribute__((noinline, convergent))
void mono_dq_convert_lowctx(const DqConvertArgs* args, unsigned linear_tid);
```

当前目标下，此签名使用 v0:v1 传指针、v2 传 linear_tid，s30:s31 持有返回地址；构建脚本核对 `SI_CALL` 的实际参数寄存器。独立 ASM 入口用 `v_readfirstlane_b32` 把地址转到 s0:s1，并计算供应方的 lane/wave。

参数布局沿用普通设备 ABI，**寄存器保持承诺已经是自定义 ABI**。单独的 C++ 声明不会缩小保持集合，必须配套调用点处理。

### 5.3 “限制在 v64/s40 以内”到底指什么

[callsite_regmask.py](../mono_test01/callsite_regmask.py) 从默认保持掩码中删除涉及 v≥64 或 s≥40 的保持位，包括半寄存器和 tuple 别名，保留默认非 GPR 位。最终保留的普通编号 GPR 是：

| 类型 | 自定义调用点承诺保持的寄存器 |
| --- | --- |
| VGPR | v40～v47、v56～v63，共 16 个 |
| SGPR | s30～s39，共 10 个 |

它不是把全部 v0～v63/s0～s39 都变成 callee-saved，也不是让整个 Mono 只能用 64 个 VGPR / 40 个 SGPR。高寄存器仍能用于其他阶段以及调用前后的计算，只是不能依赖该调用保留它们的原值。

s30:s31 为返回地址，s32/s33/s34 涉及 SP/FP/BP，不能把上述 10 个 SGPR 都当成可自由放业务上下文的空间。放不下的跨调用活跃值仍由 LLVM 搬运、重算或 spill。

为履行这个保持承诺，供应方作如下映射：

```text
原 s30～s38 → s40～s48
原 v40～v45 → v64～v69
```

适配后的算子不改写承诺保持的 GPR，因而无需为它们增加 callee 保存恢复，也不需要 callee private 栈帧。其 MODE 仍在 s5 中保存并恢复，最后执行 `s_setpc_b64 s[30:31]`。gfx1250 反汇编也会使用 `s_set_pc_i64`，调用对应 `s_swap_pc_i64` / `s_swappc_b64`。

### 5.4 资源与工具链依赖

独立 ASM 资源下限为 70 个 VGPR、49 个编号 SGPR，LDS/private 为 0。FlyDSL 调用侧有一个空 inline asm：

```text
asm("", clobber = v69, s48)
```

它用于让 LLVM 把供应方最高寄存器计入资源需求，**不是调用保持掩码，也不是寄存器数量上限**。当前 `-amdgpu-assume-external-call-stack-size=0` 以这个具体 callee 确认无栈帧为前提，不能照搬给任意外部函数。

当前实现固定 LLVM 提交 `d177931e65e6057dca59f1c5b95e643d29876db3`，并适配 FlyDSL 0.4.1 的编译入口。所选工具链缺少 `llc` 时，[build_llc.py](../mono_test01/build_llc.py) 用目录内同提交的 `llvm/tools/llc` 源码和已安装的匹配头文件/静态库构建它；不下载、不改写系统编译器。缺少必要开发库会报告错误。

流程包含未修改掩码的 MIR 往返校验，要求指令、机器码、重定位与 descriptor 一致；还有 wave32 VCC 隐式操作数兼容处理，以及恢复 MIR 序列化丢失的 user-SGPR count、补齐零 named-barrier 资源符号。最终 VGPR/SGPR/private 计数来自自定义流水线，不复制基线计数。

这是一套工具链相关的 MIR 原型。生产化更适合在 LLVM 进程内实现寄存器分配前的 pass。没有把 `callee_test01` 的单基本块活跃性检查器直接套在复杂 Mono CFG 上，也没有复制其故意污染全部高寄存器的测试指令。

## 6. mono_test10：直接 inline .long + clobber

### 6.1 编译和调用链

```text
asm/dq_convert.original.s → asm/dq_convert.inline.s
    ↓ Clang 汇编
build/asm/dq_convert.inline.co（ET_REL）
    ↓ 提取完整符号，验证无重定位
dq_convert.inline.words.inc + .bin + inline_contract.json
    ↓ Python load_fragment() 读取 .inc
projection()
  → stage_wqkv_asm()
    → invoke_dq_convert(record, tid)                 dq_inline.py
      → llvm.inline_asm(固定输入, .long 文本, clobber)
        ↓ FlyDSL 正常 LLVM 编译
build/inline/kernel.co：片段直接位于 Mono 函数内部
```

[dq_inline.py](../mono_test10/mono1250/kernels/dq_inline.py) 使用与 `00` 的 wrapper 内部相同的三个固定输入和 78 个 GPR clobber，另加 SCC/memory。Mono 本身就能看到这一边界的污染集合。

`.inc` 内容是 `.long 0x...` 的文本，最终汇编时这些 32 位数成为 Mono `.text` 中的机器指令。它没有在运行时逐条复制指令，也没有改写已经生成的 Mono 二进制；用于提取的 `.co` 不参与独立设备函数链接。

目录中保留的 C++ `.h` 是接口对照，实际 FlyDSL 路径由 Python 读取 `.inc` 并构造 LLVM inline asm，不是由 Mono `#include` C++ 头文件。

### 6.2 如何保护跨边界上下文

LLVM 在寄存器分配前看到 clobber，不能让需要跨片段存活的值未经保护地留在被覆盖的寄存器里。它可以选择其他寄存器、搬运、重算或 scratch spill/reload，因此无需再对整个 Mono 设置 VGPR/SGPR 数量上限。

这不要求先确定“Mono 当前活跃了哪些物理寄存器”，再用脚本逐个保存。需要准确提供的是片段自身的输入、输出、副作用和写寄存器集合，调用者活跃性由编译器分析。

边界本身没有 device call/return；片段通过局部跳转和顺序执行衔接。为保持 64 字节对齐，文本前有 `s_branch` 跳过对齐填充。边界周围仍可能出现参数搬运或 spill，不能把“没有 swap-PC”理解成“完全没有额外指令”。

`.long` 对 LLVM 的优化和指令调度是不透明的。其内部依赖、等待及特殊状态必须正确适配；完整 clobber 不能替代这些责任。更大的片段或多个嵌入点还可能增加代码体积及寄存器压力。

## 7. 当前已有运行记录与资源比较

下表摘自三个目录当前 README 的 gfx1250 设备 0 运行记录，环境记载为 ROCm 7.16、AMD Clang 23.0.0git（`d177931e65e6`）；`01/10` 明确记载 FlyDSL 0.4.1。这里没有重新读取目标机报告或运行基准。

| 项目 | native 基线 | 00：FFI wrapper | 01：lowctx | 10：inline |
| --- | --- | --- | --- | --- |
| VGPR | 126 | 126 | 257 | 126 |
| SGPR | 68 | 70 | 108 | 68 |
| scratch，字节/线程 | 0 | 32 | 16 | 0 |
| 报告的 VGPR / SGPR spill | 0 / 0 | 0 / 0 | 1 / 16 | 0 / 0 |
| LDS，字节/CTA | 14848 | 14848 | 14848 | 14848 |
| 驻留容量，CTA/CU | 4 | 4 | 1 | 4 |
| 整卡驻留容量 | 1024 | 1024 | 256 | 1024 |
| 默认 9 组 A/B | 作为对应基线 | 记录通过 | 记录通过 | 记录通过 |

这些数值是 README 记录的最终资源口径，不能解释成调用方业务变量的数量；`01` 的 257 VGPR 也不等于供应方片段单独使用 257 个寄存器。

需要区分三个概念：

1. **scratch 与 spill 计数不同。** `00` 的报告可以同时出现 32 字节 scratch 和 0/0 spill；ABI 保存恢复使用 private 栈空间，不一定计入相同的寄存器分配 spill 统计。不能只看 spill 为 0 就断言没有 scratch 指令。
2. **callee 不用 scratch，整个 Mono 仍可能用。** `01` 的供应方没有 private 栈帧，调用者仍可因保持集合缩小而 spill；当前记录即有 16 字节/线程。
3. **缩小保持集合不保证降低最终资源或提升性能。** 当前 `01` 记录的资源高于另外两种。实际结果同时受寄存器分配、调用边界和后端约束影响；尚不能仅凭此表确定各因素的贡献，也不能据此做延迟排名。

本测试检查全网格 256 CTA 的驻留容量，以满足当前跨 CTA 等待的运行要求。`01` 的记录恰好为 256，增加压力后需要重新检查。`00/10` 的当前记录为 1024，也不代表换更大的 ASM 后仍有相同容量。

默认每个目录执行 zero/pattern/random 各三次，共 9 组 A/B、18 次融合 launch，ASM 变体累计 9×112＝1008 次 CTA 级执行。每条 native 或 ASM 路径各为一次 Mono launch；这不是 1008 次独立 GPU kernel launch。

检查包括中间结果及 QKV 的 CPU oracle、native/ASM 逐位一致性、112 个完整 tile 的 BF16 转换、guard、输入 padding、参数不变、mailbox tag，以及 QKV 确实读取供应方输出。三个 README 均记录这些 A/B 检查通过。

## 8. 如何运行与查看产物

在匹配的 gfx1250 环境中分别执行，不要求三个目录同时运行：

```bash
cd /home/feifei/repo/ATOM/mono_test00
./run.sh
```

```bash
cd /home/feifei/repo/ATOM/mono_test01
./run.sh
```

```bash
cd /home/feifei/repo/ATOM/mono_test10
./run.sh
```

共同支持 `--device 1`、`--cases pattern --repeat 1`、`--llvm-bin /path/to/llvm/bin` 等选项，具体环境依赖见各目录 README。`01` 对 LLVM 提交和工具内部寄存器表有额外要求。Clang 23 的未用 src2 编码及反汇编填充兼容处理由当前构建/审计脚本完成，不应关闭字节校验来绕过版本差异。

| 希望阅读的内容 | 00 | 01 | 10 |
| --- | --- | --- | --- |
| 修改后的 ASM 源码 | `asm/dq_convert.inline.s` | `asm/dq_convert.lowctx.s` | `asm/dq_convert.inline.s` |
| 实际调用边界 | `mono1250/kernels/dq_ffi.py` | `mono1250/kernels/dq_device.py` | `mono1250/kernels/dq_inline.py` |
| 核心构建逻辑 | `build_wrapper.py` | `device_codegen.py`、`callsite_regmask.py` | `asm/prepare.py`、`asm/audit.py` |
| 编译器生成的保护代码 | `build/ffi/wrapper.envelope.txt` 和函数反汇编 | `build/lowctx/caller.lowctx.s` | `build/inline/kernel.disasm.txt` |
| 最终执行目标 | `build/ffi/kernel.co` | `build/lowctx/kernel.co` | `build/inline/kernel.co` |
| 完整运行报告 | `build/result.json` | `build/result.json` | `build/result.json` |

以上 build 文件在对应构建或运行后生成。`00` 的 `build/wrapper/dq_wrapper.codegen.s` 用于独立 wrapper 离线检查，与最终 Mono 内 wrapper 的反汇编应分别阅读。

三种方法的 `.ll/.mir/.s/.co` 用途不能混淆：

- `00` 的 `.bc` 参与链接；导出的 `.ll` 主要用于检查函数属性和 clobber。
- `01` 的 `.mir` 是实际构建输入，改过掩码后由 `llc` 继续编译；`.s` 经汇编后参与机器码链接。
- `10` 的 `.inc` 是实际 inline 输入；提取用 `.co` 是可重定位代码容器，不是可单独启动的 GPU kernel。
- 最终的 `build/{ffi,lowctx,inline}/kernel.co` 才是各自包含 Mono 入口的可加载 code object。

## 9. 面向真实 ATOM 的选择建议

**默认考虑 `00`：** 需要独立函数边界、允许 call/return 和 scratch，希望尽量沿用 FlyDSL 现有接口。寄存器约定集中在 wrapper，Mono 只依赖稳定的函数签名。必须提供准确 clobber，并保证编译器能读取 wrapper bitcode。

**考虑 `10`：** 希望取消设备函数调用边界，能可靠适配片段、枚举 clobber，且片段大小和寄存器占用适合内嵌。当前例子的资源记录较好，但大型 ASM 是否同样适合，要看最终寄存器压力、代码体积和性能。

**考虑 `01`：** 必须保留独立 ASM 目标，同时希望明确缩小某个调用点的保持集合，并愿意维护编译器接入。它让被调函数避开保持区，但可能把保存压力转移到调用方。适合进一步研究定制 ABI，当前实现比另外两种更依赖工具链。

从当前样例迁移到真实 WQKV 或其他大算子时，应重新确认：算子的数学功能与数据布局、task 到逻辑 block 的映射、参与线程和 wave、LDS 复用、特殊寄存器/栈状态、寄存器污染集合，以及 mailbox 的等待和发布责任。ABI 适配不能自动消除布局转换和中间访存。

若供应方只有独立 kernel `.co/.hsaco`，三者也都不是“把任意二进制直接塞进来”。仍需有足够的信息可靠提取和适配指令；重定位、PC 相对引用、外部常量、描述符入口假设、原始 `s_endpgm` 等必须处理。本文现有流程针对的是已保留完整 `.s`、可逐条核对的 dq_convert。

## 10. 源码与相关阅读

- [00：README](../mono_test00/README.md)、[Mono 主体](../mono_test00/mono1250/kernels/projection_asm.py)、[包装器源代码](../mono_test00/asm/dq_wrapper.cpp)、[包装器审计](../mono_test00/wrapper_audit.py)。
- [01：README](../mono_test01/README.md)、[Mono 主体](../mono_test01/mono1250/kernels/projection_asm.py)、[调用点掩码](../mono_test01/callsite_regmask.py)、[编译 hook](../mono_test01/device_codegen.py)。
- [10：README](../mono_test10/README.md)、[Mono 主体](../mono_test10/mono1250/kernels/projection_asm.py)、[inline 边界](../mono_test10/mono1250/kernels/dq_inline.py)、[片段审计](../mono_test10/asm/audit.py)。
- [基线 Mono 单测说明](../mono_test_origin/README.md)。
- [早期方案头脑风暴](ASM_FLYDSL_MONO_INTEGRATION_OPTIONS.zh-CN.md)：含寄存器重命名和其他候选方案；历史阶段的验证状态及旧 `test20` 名称以本文和当前各目录为准。
