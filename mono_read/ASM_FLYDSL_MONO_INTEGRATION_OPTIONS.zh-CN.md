# ASM 接入 ATOM / FlyDSL Mono 的方案比较

> 本文保留早期方案讨论与当时的离线检查记录。当前 `mono_test00/01/10` 的实现、编译调用流程及 README 中记录的 gfx1250 实机结果，统一整理于 [三种实现对照](ASM_MONO_INTEGRATION.zh-CN.md)。下文 `test20` 即已重命名的 `mono_test00`；“尚未运行”等描述属于早期状态。

本文整理 2026-11-10 的方案讨论。目标是复用供应方 ASM，并让它作为 ATOM Mono 的一个
内部步骤执行；算子前后仍有其他 stage，需要正确传递参数并保留调用者上下文。

现有实验：

- [mono_test10](../mono_test10/README.md)：适配 ASM → `.co` → `.long`，直接放进 Mono
  的 LLVM inline asm，声明固定输入与完整 clobber。
- [mono_test01](../mono_test01/README.md)：适配为独立设备函数，修改目标调用点的
  call-preserved regmask，限制直接保留的跨调用寄存器上下文，再链接为 Mono。
- [mono_test00](../mono_test00/README.md)：本次新增的标准 ABI 包装函数 bitcode 方案。
  原始和修改后的 ASM 均保留；包装器使用 `ffi + link_extern` 接入。

**mono_test00 已离线编译出包装器 `.bc`，并检查了 IR 和编译器生成的包装函数汇编；
尚未编译整个 FlyDSL Mono，也没有运行 CPU 数值单测或 GPU 单测。** 下文区分设计原理、已核对的源码事实和待验证的运行结果。

## 1. 两类问题应分别解决

第一类是执行接口：参数放在哪里，哪些寄存器会被改写，EXEC/MODE/栈状态怎样恢复，
函数如何返回，以及整个 kernel 要声明多少资源。

第二类是算子的数据接口：输入输出布局、tile 大小、参与线程数、同步与 mailbox 发布。
更换 ABI 不能自动解决第二类问题。

例如，原 `stage_wqkv_c1` 的 `bf16_round(total)` 只处理当前线程的寄存器值；我们选取的
`fmha_bwd_hd64_dq_convert_bf16` 却从 global memory 读取 packed FP32 64×64 tile，
将 BF16 tile 写回 global memory。因此三个实验都保留 WQKV 矩阵乘和八路累加，只替换
BF16 舍入，并增加输入写回、CTA 同步、ASM 转换、输出读取。

这部分是真实的运行开销。每 task 只有 16 个有效值，却转换 4096 个元素，只适合接入
流程/正确性演示。若以后替换整个 WQKV，应选用真正执行 WQKV 且匹配 Mono 布局的 ASM。

## 2. 方案总览

| 方案 | Mono 看见的边界 | 上下文管理 | 主要代价/限制 |
| --- | --- | --- | --- |
| 直接 inline `.long`（test10） | LLVM inline asm + clobber | 编译器保护跨片段活跃值 | 固定寄存器/特殊状态契约；片段在调用方展开 |
| 自定义 regmask（test01） | 真实 device call + 自定义保持集合 | 编译器按缩小后的集合分配/溢出 | 当前 MIR 原型绑定工具链，构建流程较复杂 |
| 标准 ABI + 寄存器重命名 | 普通 device call | 调用者按默认 ABI；ASM 避开保持区 | 需要足够合法的 caller-saved 寄存器，不能适用于所有大型 ASM |
| 标准 ABI 包装器 `.bc` + FFI（test20） | 普通 device call，callee 的 IR 含 opaque asm | 编译器管理 caller，并为 wrapper 保存被改写的 callee-saved | 允许 scratch；仍须提供准确 clobber 和特殊状态适配 |
| 汇编文本 + inline 操作数 | LLVM inline asm | 编译器按操作数与 clobber 分配 | test10 的简化变体；更适合有 `.s`、可参数化的小片段 |

这些方案仍使用单个 Mono GPU launch。独立 kernel launch / HIP Graph 能绕开设备 ABI
适配，但改变了单一 Mono 的执行边界，不作为本文首选。

## 3. 小型 ASM：默认 ABI + 寄存器重命名

思路是让供应方只使用默认 caller-saved GPR。它不改写 callee-saved，就不必保存它们；
调用者直接使用 LLVM 的默认设备函数约定，无需自定义 regmask。

针对当前 dq_convert，有以下候选映射：

| 原始寄存器 | 候选映射 |
| --- | --- |
| v40～v45 | v48～v53 |
| s30～s37 | s40～s47 |
| s38 | s56 |

源码核对依据是现有工具链的 `CSR_AMDGPU` 表，以及 `callee_test01` 保存的掩码报告：
候选目标都属于 caller-saved，且未被该原始 ASM 占用；s38 没有出现在跨越它的 tuple 中。
这是静态可行性判断，还没有为该候选生成并验证新二进制。

仍需桥接参数、去掉 `s_endpgm`、处理普通 return、保持 EXEC/MODE 等状态，并正确统计
整个 kernel 的资源。调用者仍可能 spill；“callee 无需 GPR 保存”不等于“整个 Mono 零 scratch”。

大型算子如果几乎用满寄存器，可能没有足够的 caller-saved 空间。重命名必须保持
连续 tuple、对齐、指令编码范围和 VGPR bank 约定，不能只机械替换寄存器编号。
独立 `.co` 还需要代码生成/ELF 链接入口；`link_extern(bitcode_path=...)` 不能直接接收它。

## 4. 通用方向：标准 ABI 包装器 bitcode + FlyDSL FFI

### 4.1 结构

```text
供应方 .s / 可提取代码的 .co
    ↓ 一次性适配入口、出口和特殊状态
可嵌入片段 .s → 提取用 .co → .long .inc
    ↓ 包装器内声明输入、输出、clobber
extern "C" __device__ noinline stage_wrapper(...)
    ↓ Clang 生成真正的 LLVM bitcode
stage_wrapper.bc
    ↓ FlyDSL ffi + link_extern，在机器码生成前链接
Mono IR + wrapper IR
    ↓ 普通 LLVM 优化、寄存器分配、代码生成
单个 Mono .co：Mono 函数 + 可调用的 wrapper 函数
```

包装器包含一个真实 IR 函数定义，内部的 inline asm 对 LLVM 是不透明的计算区域，但其
寄存器污染是可见的。`.bc` 不代表从机器码恢复了算子 IR；提取用 `.co` 也没有改后缀冒充 `.bc`。

包装器保留 `noinline`，使 Mono 对它使用真实设备函数 call；`convergent` 描述需要协作
执行的语义。写内存的 ASM 不得标为 pure/readnone/readonly。

离线编译发现，本机 Clang 22 的前端对 `noduplicate` 和 `noinline` 使用互斥处理分支，
同时声明会使包装器 IR 丢掉 `noinline`。test20 因此采用 `noinline + convergent`，
不额外声明 `noduplicate`，并检查最终 `.bc` 中的实际属性；未通过 IR 补丁绕过此问题。

### 4.2 谁保存现场

| 位置 | 责任 |
| --- | --- |
| Mono 调用方 | LLVM 按默认 ABI 保留跨调用活跃值；可搬运、重算或 spill |
| 包装函数 | LLVM 根据 inline asm clobber 和包装函数自身用寄存器，保存/恢复所需 callee-saved |
| 原始片段的适配代码 | 处理不能简单交给通用 GPR 分配器的 EXEC/MODE、独立 kernel 出口等状态 |

这与“只声明一个外部 `__device__`，让编译器猜测黑盒 `.co` 会写什么”不同。**自动生成
包装函数的 GPR 保存恢复，以编译器看得到完整 clobber 为前提。** 外部已编译 `.co` 的内部
写集合不会自动变成 LLVM clobber。

按当前记录的默认 ABI，test20 沿用的 inline 片段会改写 v40～v45 和 s48 等保持寄存器，
因此它们需要由编译器在包装函数侧保护。实际保存方法和额外使用的保持寄存器取决于最终
编译结果，可包含 scratch、SGPR-to-VGPR lane spill 等，不承诺零 scratch。

本机离线生成的包装函数确实包含 v40～v45 的 scratch 保存/恢复，并用 v3 的 lane 0
暂存 s48；另外有用于保留 v3 非活动 lane 的保存恢复。该包装函数 private frame 为
32 字节/线程，静态 scratch store/load 各 7 条。这是包装器单独代码生成结果，
不是最终 Mono 的资源/性能结果，也不是 GPU 正确性验证。

不能把任意保留/特殊寄存器全部写入 clobber 后就认为问题已经解决。例如 SP、返回地址、
EXEC 和 VGPR bank 等仍须遵守接口。当前片段已经避开 s30～s39，并在内部恢复 EXEC/MODE。

### 4.3 FlyDSL 接口

```python
from flydsl.expr.extern import ffi
from flydsl.compiler.extern_link import link_extern

stage = link_extern(
    ffi("mono_dq_convert_wrapper", ["uint64", "uint32"], "void", is_pure=False),
    bitcode_path="/absolute/path/dq_wrapper.bc",
)

# 在 Mono 的完整 CTA 路径中：
stage(args_address, linear_tid)
```

`uint64` 表示参数记录地址，包装器内部转回指针。这与当前 FFI 支持的标量类型一致。
标准设备 ABI 的具体参数落点仍由目标编译器决定；wrapper 内的固定输入约束再桥接到供应方
所需的 s0:s1、v0、s24，Mono 不直接依赖这些供应方寄存器。

查阅的 FlyDSL FFI 会生成 `llvm.call`，`link_extern` 会把 `.bc` 注册到编译上下文。
当前 FFI 没有 convergence 参数，因此 test20 只给刚生成的 call 补上 MLIR `convergent`
属性，函数定义的其他属性来自包装器 bitcode。这是源 IR 上的语义标记，不是自定义编译流程。

当前 FlyDSL 外部 bitcode 路径使用内置 codegen，可能使用 `#fly.explicit_module` 管理
模块加载。应遵循其现有流程；不要同时启用 `FLYDSL_COMPILE_LLVM_DIR` 的外部 codegen。
test20 不改写已安装 FlyDSL，也不挂接 `MlirCompiler.compile`，不经过 MIR 文件。

### 4.4 优势与边界

- 参数与寄存器保存恢复遵循标准 ABI，无自定义调用点掩码。
- wrapper 和 Mono 在同一个 LLVM 编译过程中可见，资源分析能看到 wrapper 的寄存器与栈需求。
- Mono 源码通过正常 FFI 调用，不读取 `.inc`，不构造 `.long` inline asm。
- `.inc`、供应方寄存器约定和 clobber 集中在一个独立的包装层，便于复用。
- 可能比缩小保持集合的方案多保存寄存器；性能要测量，不能只按源码行数判断。
- Clang 产出的 bitcode 必须能被 FlyDSL 内置 LLVM 读取，gfx1250、wave32 和属性需兼容。
- 固定输入/完整 clobber、最终资源计数和完整 tile 数值仍需检查。

## 5. 有汇编源码时：直接使用文本与操作数

如果 `.s` 可修改，可把片段主体直接作为 inline asm 文本，用操作数约束替换部分硬编码
寄存器。这能减少预汇编和 `.long` 提取步骤，错误也更容易定位。

不过，这本质上仍是 test10 类的 inline 边界。LLVM 不会把一整段汇编自动展开成可独立
优化的普通 IR 指令；准确 clobber、内部依赖等待、特殊状态和同步依然必需。只有 `.co`
时也仍需可靠解码/适配，不能跳过机器码边界检查。

## 6. 面向真实 ATOM 的接口整理

长期应统一 stage 参数记录和执行契约：输入输出指针/stride、task 和虚拟 block 坐标，
tile 布局、CTA/wave 参与条件、同步责任、mailbox 发布责任，以及 LDS/private 等资源。

公共适配层可以隐藏这些重复工作，让主体只写 `wqkv_stage(args, task)`。这是接口设计
建议，不是现有 FlyDSL 内置 API。真正减少运行开销还需要供应方直接消费 Mono 已有布局，
并输出下一 stage 所需布局；把搬运封装进 helper 只能减少源码行数。

小型算子优先评估默认 ABI 的寄存器重命名；通用供应方优先验证标准 ABI wrapper `.bc`
接入。在数值和上下文正确后，再决定是否值得引入自定义 regmask 等优化。

## 7. 来源与当前实现

- [FlyDSL FFI](https://github.com/ROCm/FlyDSL/blob/main/python/flydsl/expr/extern.py)
- [FlyDSL link_extern](https://github.com/ROCm/FlyDSL/blob/main/python/flydsl/compiler/extern_link.py)
- 本地 AITER 使用示例：`aiter/ops/flydsl/kernels/mega_moe_tp/mega_moe_tp_kernel.py` 的 SDMA 外部函数。
- 默认设备 ABI 来源：LLVM `AMDGPUCallingConv.td` 中的 `CSR_AMDGPU`，以及 callee_test01 的实际表快照。
- [mono_test00 运行与构建说明](../mono_test00/README.md)

上面的在线 main 分支是接口核对来源，不是承诺所有 FlyDSL wheel 都具有相同版本。
test20 会检查必要接口和实际编译产物，目标环境验证前不宣称运行通过。
