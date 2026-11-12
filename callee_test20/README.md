# 在 ASM 文件中嵌入 HIP 代码块：设计与最小 demo

状态：已补充 gfx1100 的受限混合预处理器、完整 ASM demo 和测试源码；通用 LLVM fragment 后端仍为设计提案。
设计记录日期：2026-11-11；demo 更新日期：2026-11-12。

**可运行 demo 见 [DEMO.md](DEMO.md)**，入口是 [kernel.s](kernel.s)，包含 `c = a + b*a` 与 `d = a - b/a` 两个 HIP 块，输出绑定到 v2/v7。已完成离线构建，没有执行单测或 GPU 测试。以下章节描述的类型、寄存器池和通用后端能力比当前 demo 更广，不能视为全部已实现。

## 1. 目标与工作方式

用户维护一个以手写 AMDGPU 汇编为主体的 `.s` 文件，仅在部分位置编写 HIP
device C++ 代码。构建工具将这些代码块编译成满足物理寄存器契约的指令，再插回
原位置，得到可以交给 AMDGPU 汇编器的完整 `.s` 文件。

用户的输入、输出及最终 kernel 都以 ASM 为主。用户不需要把 kernel 改写成 HIP，
不需要写 HIP 包装器，也不需要通过 HIP 的 inline asm 承载手写 kernel。
内部可以调用 Clang 编译提取出的 HIP 代码；内部辅助函数只是代码生成容器，
不会成为最终 kernel 中被调用的 device 函数。

```text
kernel.s：手写 ASM + 少量 .hip 代码块
        │
        ▼
混合 ASM 预处理器
        ├── 解析各块的类型、物理输入输出、临时寄存器和 FP 契约
        ├── Clang：HIP device C++ → LLVM IR
        ├── AMDGPU fragment 后端：IR → 受约束的汇编片段
        └── 在原位置插入片段，保留手写 ASM
        │
        ▼
kernel.generated.s + fragment 合约/资源报告
        │
        ▼
AMDGPU 汇编器 → .o → 链接 → 最终 code object
        │
        ▼
完整 kernel 的寄存器、descriptor 和边界检查
```

详细的前端、LLVM 扩展、构建产物和验收方案见
[IMPLEMENTATION.md](IMPLEMENTATION.md)。本文的通用接口仍为**拟议接口**；当前 demo
实际支持的 `.hip.*` 子集见 [DEMO.md](DEMO.md)。这些指令由混合预处理器识别，
Clang 和 LLVM assembler 不直接识别 `.hip.begin/end`。

## 2. 建议语法

下例省略正常 ASM kernel 的符号、descriptor、metadata 和参数准备；它展示的是
一个 kernel 主体中的局部代码块，不能直接作为完整 kernel 运行。

```asm
.amdgcn_target "amdgcn-amd-amdhsa--gfx942"

; 前面的手写代码已准备好 FP32 的 a、b。
; 若 a、b 来自异步 load，必须在这里满足相应等待条件。
...

.hip.begin arithmetic_0
    .hip.in  f32 a = v0
    .hip.in  f32 b = v1
    .hip.out f32 c = v2
    .hip.out f32 d = v7

    .hip.temp vgpr = v[32:47]
    .hip.temp sgpr = s[40:47]
    .hip.allow_clobber vcc, scc

    .hip.fp_contract off
    .hip.fast_math off
    .hip.code
        c = a + b * a;
        d = a - b / a;
.hip.end

; 此处 c 在 v2，d 在 v7，a、b 的原值仍在 v0、v1。
; 未授权改写的其他寄存器保持原值。
...
```

目标架构和 wave 大小属于整个构建的配置。预处理器必须检查命令行配置与原 ASM
的目标指令、descriptor 一致；同一输出文件不能混用不同架构的片段。

`.hip.code` 明确区分接口声明和 C++ 主体。块 ID 必须在当前编译单元中唯一，
用于诊断、产物命名、缓存和局部标签命名。

## 3. 物理寄存器契约

| 声明 | 语义 |
|---|---|
| `.hip.in f32 a = v0` | 从入口的 v0 读取 FP32 位模式；a 在 C++ 中只读；出口保留 v0 原值 |
| `.hip.out f32 c = v2` | 块内生成 c；出口必须把 c 的位模式放入 v2；入口的 v2 不保证保留 |
| `.hip.inout f32 x = v4` | 从 v4 读取 x，允许修改 x，出口把新值写回 v4 |
| `.hip.temp vgpr = v[32:47]` | 授权片段使用的临时 VGPR 集合；出口不保留其中的旧值 |
| `.hip.temp sgpr = s[40:47]` | 授权片段使用的临时 SGPR 集合；按目标规则处理配对及对齐 |
| `.hip.allow_clobber vcc, scc` | 允许改写列出的特殊状态；不表示强制使用它们 |

绑定首先承诺块入口和出口。块内 C++ 临时值可以放在允许集合中，输出也可能经过
一次 COPY 才到指定寄存器；不承诺每条赋值立即写入对应物理寄存器。

第一版对 input-only 寄存器采取保守实现：允许读取，禁止实际指令写入。
以后可以扩展为“中间允许保存、覆盖、恢复，出口保持原值”，但这必须是明确的
接口升级，不能悄悄放宽当前契约。输出和 inout 槽可以参与块内寄存器分配。

如果希望 `a = a + b` 后仍在 v0，应该声明 `.hip.inout f32 a = v0`。
如果希望保留 v0 的原值并把新值送到 v2，则使用独立的 in/out。
第一版拒绝相互重叠的输入输出声明、input-only 与 temp 的重叠，以及不同变量
对同一物理槽的重复绑定；原地计算通过 inout 表达。

第一版默认保留 EXEC 和 MODE，禁止片段改写它们。VCC、SCC 等也默认保留；代码
需要使用这些状态时，必须授权，或在后续版本实现显式保存恢复。仅将某个特殊
寄存器标为 reserved，不代表指令不会隐式改写它，仍必须检查实际指令。

未声明为输出、inout、temp 或允许污染状态的资源，不得被片段改写。
输入及外围寄存器的保护覆盖整个 wave 的物理状态；第一版禁止 WWM/WQM、EXEC
变化和任何可能改写原本 inactive lane 的操作。

## 4. 类型和数值语义

寄存器绑定是位模式传递，不会隐式进行整数与浮点转换。
`f32 a = v0` 将 v0 中的 32 位解释为 FP32；`u32 a = v0` 将同样的位解释为无符号整数。
`c = a + b * a` 的生成代码取决于类型及 FP 选项。

第一版支持 VGPR 上的 `f32`、`u32`、`i32`。为避免有符号溢出语义带来的意外，
需要 32 位模运算时使用 `u32`。`f64`、64 位整数、packed f16/bf16、向量和 AGPR
绑定作为后续扩展，必须先定义 tuple 宽度、对齐和位布局。

`.hip.fp_contract off` 禁止对用户表达式进行乘加融合；`fast` 允许融合。
`.hip.fast_math off` 不启用 unsafe FP 优化；`on` 显式允许相关放宽。
这些选项不是“无条件 IEEE 严格”的承诺，实际语义还依赖 AMDGPU 的 FP MODE、
denormal 设置和目标指令能力。尤其是关闭用户表达式融合，并不禁止后端为了
实现除法而使用 FMA 指令。

MVP 要求原 ASM 设置与编译配置匹配的 FP MODE，并保持 MODE 不变；预处理器输出
该前置条件。若代码生成需要改变 MODE，应报错，不能未经授权自动修改它。

## 5. 已有能力和验证证据

2026-11-11 已用本机 ROCm 7.2 / AMD Clang 22 对 gfx942、gfx1250 做离线实验：
现有固定寄存器 inline asm 约束可以将值接入 HIP 表达式，再将结果送入指定寄存器。
相关汇编已由 `llvm-mc` 生成 ELF 对象；尚未做 GPU 数值或完整 kernel 集成验证。
这些是底层能力探针，不是本文产品的用户接口。

gfx942 上，在要求保留 a/v0、b/v1 并关闭 FP contraction 时，算术部分为：

```asm
v_mul_f32_e32 v2, v1, v0
v_add_f32_e32 v2, v0, v2
```

允许 FP contraction 后，可以生成为：

```asm
v_fma_f32 v2, v1, v0, v0
```

若只约束 c/v2，不约束保留 a、b，已有编译器会合法地把 v1 当临时寄存器覆盖。
因此仅有入口/出口位置约束，还不足以保护外围 ASM 的状态。

在 gfx942 的普通 FP 除法实验中，`d = a - b / a` 使用了 v2–v6、s0–s1 和 VCC，
最后输出到 v7。开启 fast math 的另一构建可缩成 reciprocal 与 FMA，但数值语义
随之改变。所以上面的建议语法不仅列出 d，还列出临时池及允许污染状态。
**将该除法改为只使用 v32–v47、s40–s47，尚未验证，需要本文拟议的受约束后端。**

现有能力探针还带有普通 device 函数的等待与返回代码，不能直接完整嵌入 ASM。
产品实现必须提供真实片段入口/出口，而不是按两个文本标记随意剪切函数。

## 6. 为什么需要 LLVM fragment 扩展

Clang 已负责 HIP/C++ 语法、类型和优化；LLVM AMDGPU 后端已负责指令选择、
寄存器分配、调度和等待。缺少的是一套专门面向 ASM 插入点的接口：

1. 按契约读取物理 live-in，并在出口写入指定物理 live-out。
2. 让所有分配及后期临时资源服从允许的寄存器集合。
3. 生成没有普通 device 调用 ABI、返回、栈和 spill 的片段。
4. 验证未授权的显式/隐式改写，并输出资源与边界要求。

inline asm 的 clobber 描述“该 asm 会改写什么”，不能直接限制中间 C++ 计算的
寄存器分配。普通 VGPR 数量上限也不能表达任意的离散临时池。

建议通过预处理器复用 Clang，再扩展 AMDGPU 代码生成；不在 LLVM MC 汇编器中
直接嵌入完整 C++ parser。这样 C++ 仍由前端处理，汇编器只接收纯汇编。

## 7. MVP 与后续范围

MVP 支持直线代码块：上述三类 32 位类型、局部标量、算术、位运算、显式转换、
输入输出绑定及临时池。结果必须赋值完整；禁止指针、访存、数组、循环、源级
分支、调用、barrier、LDS、scratch、内建 ID 获取和块外跳转。

限制针对实际降低结果也生效：即使源代码没有调用或分支，后端若生成相关操作，
MVP 仍拒绝该片段。输入-ready 和外围硬件 hazard 不能仅凭 C++ 源码判断。

第一阶段先完成语法解析、合约、产物布局和代码生成能力探针；第二阶段实现
受约束 fragment 后端；第三阶段验证完整 ASM kernel 的状态保留和数值结果。
有了这些基础，再加入 SGPR 接口、tuple、条件、循环和访存。

第一版不跨 HIP 块和手写 ASM 调度，不改变手写指令的相对顺序。手写代码里的
标签、跳转和控制流由原 ASM 管理；禁止从块外跳入生成片段内部，或从片段内部
跳到块外。每个块都是当前位置 EXEC 下执行并正常顺序落出的局部计算。

## 8. 完整 kernel 的责任

ASM 仍负责参数/ID 准备、输入 load 等待、执行掩码、FP MODE、barrier 和 descriptor。
工具负责检查片段及报告前置条件，最终验证必须覆盖拼接后的完整 kernel。

独立片段调度无法看见前面的 MFMA、load 或后面的消费者。块内编译成功不等于
边界 hazard 正确；需要完整指令检查或目标相关的保守边界处理。

descriptor 不能沿用原来的寄存器数量而不检查。例如使用到 v47，通常至少需要
覆盖 48 个编号 VGPR，再按目标的分配粒度和相关资源规则核算。实际占用、SGPR
特殊状态、AGPR 联动以及驻留情况必须使用对应架构的规则。
MVP 保留用户的 descriptor，并验证它足够；发现不足时输出所需资源并报错。
自动更新 descriptor 可以作为后续显式构建选项。
