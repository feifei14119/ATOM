# 用 HIP / ASM 编写 ATOM Mono 主体：设计、可行性与取舍

本文整理 2026-11-10 的设计讨论。目标是让一个 Mono GPU kernel 同时使用供应方 ASM 算子与 FlyDSL 编写的算子，讨论是否值得把 Mono 调用主体从 FlyDSL 改成 HIP 或 ASM。

**建议优先探索“薄 HIP 主体 + 可导出的 FlyDSL 设备函数 + 标准 ABI 的 ASM 包装器”。** HIP 可以简化混合调用的表达和构建组织，但最需要验证的是 FlyDSL stage 的设备函数导出。纯 ASM 主体提供最直接的寄存器控制，代价是手工维护调度、ABI、同步与资源。

本文属于设计方案，尚未实现 HIP/ASM Mono 主体，也没有编译或运行这些新架构。已有 `mono_test00/01/10` 的主体仍然都是 FlyDSL，它们的实现和已有运行记录见 [三种 ASM 接入方法对照](ASM_MONO_INTEGRATION.zh-CN.md)。

## 1. 要更换的是哪一层

这里的“主体”指 GPU 内负责安排 task、调用 stage、处理阶段间依赖并继续执行的 Mono 入口。外部仍由 host 启动一次 GPU kernel；内部 stage 使用设备函数调用或编译期内联，不额外启动 GPU kernel。

```text
host：启动一次 Mono
          ↓
Mono 主体：task 分配、依赖等待、stage 调用、结果发布
          ├── stage A：FlyDSL
          ├── stage B：供应方 ASM
          └── stage C：FlyDSL
```

在现有单测中，这个主体是 `build_projection_asm()` 内的 `projection()`。基线配置为 C=1、256 CTA、每 CTA 256 线程、wave32，计算是 slice → RMSNorm/FP8 → WQKV。

现有供应方 `dq_convert` 只替换 WQKV 累加之后的 BF16 舍入，并没有替换整个 WQKV 矩阵乘。换主体语言也不会改变该算子的数学能力或数据布局。

需要分别解决三层问题：

| 层次 | 内容 | 换主体语言的作用 |
| --- | --- | --- |
| 调用接口 | 参数、返回、GPR 保持、特殊状态、栈 | HIP 便于统一声明；ASM 便于直接控制 |
| 数据与执行契约 | tile 布局、逻辑坐标、参与线程、LDS、同步 | 三种语言都必须显式设计 |
| 构建与资源 | IR/目标链接、寄存器和 private/LDS 需求、驻留容量 | 可重新组织流程，不能省略资源核对 |

## 2. 方案 A：薄 HIP 主体 + 标准设备函数

### 2.1 结构与接口

HIP 主体保留 task 调度和公共状态，各算子通过稳定的设备函数签名接入：

```text
HIP __global__ mono_kernel
    ├── stage_norm_fly(...)      FlyDSL 导出的普通设备函数
    ├── stage_compute_asm(...)   标准 ABI 的 ASM 包装函数
    └── stage_post_fly(...)      FlyDSL 导出的普通设备函数
```

以下是接口示意，并非当前已有或可直接编译的代码。为便于表达，省略参数结构、工作区初始化和具体同步：

```cpp
extern "C" __device__
void stage_norm_fly(std::uint64_t args_address,
                    unsigned task, unsigned linear_tid, unsigned lds_offset);

extern "C" __device__
void stage_compute_asm(std::uint64_t args_address,
                       unsigned task, unsigned linear_tid, unsigned lds_offset);

extern "C" __device__
void stage_post_fly(std::uint64_t args_address,
                    unsigned task, unsigned linear_tid, unsigned lds_offset);

extern "C" __global__
void mono_kernel(std::uint64_t args_address) {
    unsigned tid = threadIdx.x;
    unsigned task = /* 当前 CTA 对应的逻辑任务 */;
    unsigned lds_offset = /* 已分配给这些 stage 的 LDS 工作区偏移 */;

    stage_norm_fly(args_address, task, tid, lds_offset);
    stage_compute_asm(args_address, task, tid, lds_offset);
    stage_post_fly(args_address, task, tid, lds_offset);
}
```

这个示意假定整个 CTA 对是否参与和调用顺序有一致决策。真实 ATOM 的 stage/task 分配不是简单让所有 CTA 顺序执行同样的三个函数，需要保持原 plan 和 mailbox 语义。

`args_address` 的整数形式便于初期对齐现有 FFI 标量接口；生产接口也可以使用正确地址空间的指针。`lds_offset` 只是设计选项，不能把普通整数偏移当成已经分配的 LDS：主体必须提供有效工作区，callee 必须按约定构造 LDS 地址、遵守大小和对齐。

### 2.2 优先考虑 bitcode 级组合

```text
HIP mono.cpp ─────────────→ mono.bc
FlyDSL stage 导出 ────────→ fly_stage.bc
ASM + C++ ABI wrapper ────→ asm_wrapper.bc
                               ↓
                  链接兼容的 LLVM IR 和所需设备库
                               ↓
                  LLVM 优化、寄存器分配、代码生成
                               ↓
                 含一个 Mono 入口的最终 code object
```

这种组织让编译器在生成机器码之前看到调用关系与各函数定义。ASM wrapper 可复用 `mono_test00` 的基本结构：包装器内部用 inline asm 描述供应方片段和 clobber，包装器对外使用标准设备 ABI。

需要核对的不只是函数名字，还包括 LLVM/bitcode 兼容性、target triple、gfx 架构、wave 大小、函数调用约定、参数属性、地址空间、设备库和浮点模式。IR 能链接成功不等于运行接口已经正确。

如果供应方必须以独立机器码目标交付，也可以用调用方目标与 ASM 目标进行链接，但 callee 的 ABI 与资源信息必须可靠提供。`.co` 后缀不能说明它是可重定位函数对象还是已链接的独立 kernel；黑盒机器码也不会自动向 LLVM 提供 clobber 和栈需求。

### 2.3 HIP 主体带来的收益

- 普通 C/C++ 函数声明便于统一签名、类型与符号，调用代码直观。
- 标准 ABI 的调用者上下文由 LLVM 维护，不需要为每个调用点手工选择物理寄存器。
- 容易组织 HIP 调用方、FlyDSL 导出产物和供应方目标的构建步骤。
- 可以把供应方固定寄存器约定集中在包装器内，主体不依赖这些物理寄存器。
- 主体可保持较薄，task 参数、工作区和函数边界更容易独立检查。

### 2.4 HIP 主体的成本与限制

- 首先要实现 FlyDSL stage 的可调用函数导出；现有 Python helper 不会自动成为外部符号。
- 真正迁移 ATOM 主体需要移植或生成 task 循环、mailbox 协议和 LDS 规划，不能只翻译函数名。
- 独立函数边界可能增加 call/return、保存恢复或参数搬运，改变原来跨 stage 的优化机会。
- HIP 同样使用 LLVM 后端，不会因为前端换成 C++ 就自动减少 scratch 或改善寄存器分配。
- 已编译、不守标准 ABI 的 ASM 不能通过一个 `__device__` 声明自动变得安全；仍需包装器或适配。

因此，HIP 的主要收益是工程组织和接口表达。是否提升性能，需要看实际代码生成及测量。

## 3. 核心待验证项：把 FlyDSL stage 导出为设备函数

### 3.1 当前 stage 为什么不能直接从 HIP 调用

现有 [stage_wqkv_c1](../mono_test00/mono1250/kernels/reference_projection.py) 的接口是：

```python
def stage_wqkv_c1(c, task, ops):
    ...
```

这里 `c` 是构建期 Python 字典，包含 IR 值、LDS 指针以及 `put/poll` 等函数；`ops` 是构建期组织的向量操作数集合。这些 helper 在构建 Mono 时生成内部代码，并非天然存在于最终 ELF 中的独立函数。

| 现有表示 | 能否直接作为 HIP 普通设备函数调用 |
| --- | --- |
| Python helper | 不能，必须生成真正的函数定义 |
| FlyDSL GPU kernel 入口 | 不能直接按普通 device ABI 调用 |
| 使用兼容 ABI 的 LLVM 设备函数 | 可以作为链接目标，仍需核对属性和资源 |

`amdgpu_kernel` 入口与普通设备函数的参数传递、隐式状态和出口语义不同。简单改调用约定名称或把 `__global__` 换成 `__device__` 不是通用转换方法。

### 3.2 导出时需要处理什么

1. **构建期对象与运行时参数分开。** 把字典/闭包中的运行时数据整理为标量、指针或参数记录；tile 形状、数据类型等编译期配置仍在生成函数时固定。
2. **生成普通函数符号。** 在合适的设备 IR module 中生成外部可见、签名稳定的函数定义，保留需要的 convergent 等属性。
3. **显式管理坐标。** 优先传入 task 和所需线程信息，减少初期对 kernel 入口隐式参数的依赖；若继续使用 builtin，必须核对设备调用路径如何传递其隐式状态。
4. **把 LDS 纳入接口。** 由统一规划的工作区提供共享存储，避免多个独立导出阶段的静态 LDS 分配意外相加或互相覆盖。
5. **确定 mailbox 责任。** 等待和发布可以放在主体，也可以封装在 stage，必须保持原有内存顺序及进度条件。
6. **保留合法 lowering。** 导出函数仍需完成 FlyDSL/MLIR 的正常 lowering、intrinsic 和设备库处理，再生成可链接 IR。

现有 [ffi + link_extern](../mono_test00/mono1250/kernels/dq_ffi.py) 证明的是“FlyDSL 调用外部函数”这条方向，不能据此断言反方向的导出已经具备现成接口。本文没有确认一个可直接使用的 FlyDSL stage 导出 API；需要先检查目标 FlyDSL 版本，并以最小函数验证。

### 3.3 函数边界可逐步调整

第一阶段建议对导出函数保留 `noinline`，便于确认调用、参数和保存恢复确实正确。打通以后，若 HIP 与 FlyDSL IR 一起链接，可以再研究：

- 小型 FlyDSL stage 允许内联到 HIP 主体；
- 大型供应方 ASM 保留独立 wrapper；
- 对确有收益的小 ASM 选择直接 inline。

这属于同一套导出架构下的优化选择，实际是否内联以及收益以生成代码为准。不能同时假定“有独立 ABI 边界”和“编译器会跨边界任意优化”。

## 4. 方案 B：ASM 主体 + 标准 ABI 的子函数

### 4.1 结构

```text
手写 ASM Mono 入口
    → 按标准设备 ABI 准备参数与隐式状态
    → 调用 FlyDSL 导出的设备函数
    → 调用标准 ABI 的供应方函数/包装器
    → 继续调度与结果发布
```

这里主体的物理寄存器由人直接分配，不需要让 LLVM 把“主体自身的状态”限制到某个范围。参数可以直接装入目标 ABI 要求的寄存器，调用和返回也可以直接编写。

不过，手写主体必须提供 callee 需要的调用环境：返回地址、栈及相关状态、有效 EXEC、目标 wave 模式、隐式参数，以及正确的 kernel descriptor。嵌套调用还需要妥善保留上层返回地址。具体寄存器约定必须按目标工具链核对，不能把某一次示例的分配当成所有 GPU 的规则。

### 4.2 优点

- 精确知道主体哪些值放在哪些物理寄存器，保存恢复范围可直接控制。
- 能精确安排参数装载、等待和跳转，不受 HIP/FlyDSL 前端表达方式限制。
- 对极小的调度状态，有机会减少冗余搬运或不必要的长活跃区间。

### 4.3 缺点

- FlyDSL 函数导出仍然需要实现，手写主体不能跳过它。
- 寄存器分配、分支、spill、EXEC 和同步都由人维护，复杂控制流更难验证。
- 需要手工组织入口资源和调用环境，独立对象的资源需求不会因链接完成而自动全部正确。
- ISA、ABI 和工具链变化可能要求重新适配；跨架构维护成本高。
- 如果 callee 仍使用标准 ABI，callee 自身的保存恢复成本并不会因 caller 是 ASM 而消失。

“主体只用低寄存器”只有在所有被调用函数承诺保护这些寄存器，或调用前显式保护它们时才安全。供应方也写这些低寄存器，就仍然会破坏主体状态。

## 5. 方案 C：ASM 主体 + 自定义 stage 执行协议

如果供应方几乎用满通用寄存器，可以进一步放弃长期把调度状态留在寄存器中，改为在边界保存少量状态：

```text
主体保存必要的 task、进度等状态到专用 LDS/global 区域
    ↓
准备供应方入口
    ↓
执行 stage
    ↓
通过约定的返回/继续位置恢复调度
    ↓
重载或重建主体状态，进入下一个 stage
```

另一种选择是约定一小组保留寄存器专门放主体状态，但要求每个 stage 都遵守。无论采用哪一种，都必须设计“最小存活状态”：返回路径如何保留、恢复状态的内存地址从哪里取得，以及栈/特殊状态如何继续有效。

**不能既允许 stage 任意破坏全部状态，又期望主体无条件自动恢复。** 必须存在可靠的返回协议、保留锚点或可重新获得的上下文位置。

| 收益 | 代价 |
| --- | --- |
| 调度器不必长期占用较大的寄存器集合 | 每个边界增加状态存取或重算 |
| 可以围绕特定供应方定义更小的接口 | 所有参与者必须适配自定义协议 |
| 长算子中，少量边界开销可能较小 | 短 stage 较多时可能得不偿失 |
| 手写 caller 可精确保护自己的状态 | 全流程的同步和正确性验证复杂 |

专用 LDS/global 状态区必须与算子工作区隔离，并明确是每 CTA、每 wave 还是每 lane 的状态。LDS 状态占用可能降低驻留，global 状态访问也有延迟。更换保存位置并不等于消除保存成本。

接入标准 ABI 的 FlyDSL 函数时，还需要适配层来建立它所需的调用环境。如果希望 FlyDSL 函数也遵循自定义寄存器保持集合，就又涉及调用约定或 regmask 的编译器支持。纯 ASM 主体仅消除了“caller 由编译器分配寄存器”的问题，并未自动改变 callee 的约定。

## 6. 对三种主体都有效：缩小跨 stage 活跃上下文

相比立刻重写主体，更容易先验证的改进是整理函数边界，让跨调用状态尽量小。

| 尽量跨调用保留 | 尽量放进 stage 或在返回后重建 |
| --- | --- |
| 参数记录地址、task、必要调度进度 | 输入输出地址计算、buffer descriptor、tile 偏移、临时向量 |

这有助于减少 caller 的寄存器压力，并让接口更稳定。但标准 ABI wrapper 仍须保存它修改的 callee-saved 寄存器；caller 活跃值减少，不代表独立 callee 的保持责任同步减少。

需要保护 ATOM 已有的延迟隐藏。在当前 [reference_projection.py](../mono_test00/mono1250/kernels/reference_projection.py) 中，顺序是：

```text
reference_fp8_loads：提前加载权重，得到 ops
    ↓
reference_load_x8_c1：等待并取得输入
    ↓
stage_wqkv_c1：使用提前加载的 ops 计算
```

权重跨等待留在寄存器是有意安排。若拆成独立函数并把权重写回内存，或把预取移到等待后，可能破坏原先的重叠。一个候选边界是把“权重预取 → 等待输入 → 计算”整体封装为同一个 FlyDSL 设备函数，由它内部维护这段生命周期；是否合适需要结合真实 task 调度验证。

## 7. 统一 Stage 契约比主体语言更重要

建议把以下信息整理为每个 stage 的固定接口和构建期契约，而非散落在调用方假设中。它可以由 Python plan 生成并同时供 HIP/ASM 使用，不要求为所有信息新增运行时字段。

| 契约项 | 必须明确的内容 |
| --- | --- |
| 数学与数据 | 功能、dtype、tile 形状、输入输出布局及对齐 |
| 参数 | 地址空间、指针/stride/立即数、记录布局、生命周期 |
| 坐标 | 物理 CTA/thread ID 与 task 对应的逻辑 block 坐标 |
| 参与条件 | 全 CTA、指定 wave 或指定 lane，入口 EXEC 条件 |
| ABI | 参数与返回、GPR 保持集合、隐式状态、嵌套调用 |
| 特殊状态 | EXEC、MODE、栈、返回地址及架构相关状态的责任 |
| LDS | 大小、对齐、工作区偏移、复用时机、状态区隔离 |
| 同步 | 输入就绪、硬件等待、CTA barrier、mailbox 发布顺序 |
| 资源 | VGPR/SGPR、LDS、private frame、目标 wave 模式 |

统一接口不能替代检查。例如当前 dq_convert 的 packed tile 与 WQKV 寄存器结果之间仍需搬运和同步；把这些操作藏进 helper 只减少源码行数，不会消除运行开销。

同样，device call 不会为下一个 stage 重新分配独立的硬件资源。最终 Mono 的入口描述和运行时分配必须覆盖实际执行路径所需的资源：寄存器有分配粒度及调用约束，LDS 能否复用取决于生命周期，private 栈还受调用深度影响，不能简单相加或只取供应方的最大值。

对当前含跨 CTA 等待的单测，要重新检查最终二进制是否满足其 256 CTA 驻留要求。增加资源压力可能影响进度保证；将主体改成 HIP/ASM 不会改变这一事实。CTA barrier 也不能代替跨 CTA 同步。

## 8. 方案选择对照

| 方案 | 接入供应方 ASM | 复用 FlyDSL | 上下文控制 | 主要成本 |
| --- | --- | --- | --- | --- |
| 保留 FlyDSL 主体 | 已有 00/01/10 路径 | 当前 stage 直接复用 | 编译器边界或定制 regmask | ASM 适配与契约维护 |
| HIP 主体 + 标准 ABI | C++ 包装和链接组织直接 | 需要设备函数导出 | LLVM 管理 caller；wrapper 管理 ABI 保持 | 导出能力、调度迁移、边界开销 |
| ASM 主体 + 标准 ABI | 参数和跳转控制直接 | 仍需函数导出 | 主体手写，callee 仍守标准 ABI | 手工调用环境、资源、同步 |
| ASM 主体 + 自定义协议 | 可围绕供应方定制 | 需适配层或编译器支持 | 手工规定最小保留/内存状态 | 全部参与者的协议一致性及维护 |

对于当前目标，优先顺序建议如下：

1. 继续以已有 FlyDSL 主体作为正确性与性能基线，统一参数和 stage 契约。
2. 先验证 HIP 主体能调用一个 FlyDSL 导出函数，再与 ASM wrapper 组合。
3. 验证导出路径后，再评估迁移真实 ATOM 调度是否值得；逐步调节内联边界。
4. 只有确有自定义寄存器协议需求，或测出主体代码生成存在显著问题，再考虑 ASM 主体。

这不是性能排名。HIP 的优势主要在工程组织，ASM 的优势主要在精确控制；整体性能取决于数据流、调度、寄存器压力、调用开销和驻留。

## 9. 最小验证路线

以下是后续实验建议，本次只记录，不新建实现目录或运行测试。

### 第一步：先验证 HIP → FlyDSL

导出一个简单 FlyDSL 加法或地址写入函数，参数包括常量、global 地址、显式线程坐标和 task。用 HIP Mono 调用它，并在返回后继续使用调用前生成的值。

离线检查普通函数定义/调用约定、参数类型、外部符号、目标属性和最终机器码。第一次实验保持 `noinline`，以确认是真正的设备函数调用，而非被优化成内联后绕过 ABI。

### 第二步：加入 ASM，形成前后都有 stage 的链

```text
HIP Mono
  → FlyDSL stage A：产生数据
  → ASM wrapper：读取并修改数据
  → FlyDSL stage B：消费修改后的结果
  → HIP 主体写出跨调用状态用于检查
```

初期选择数据布局一致、无复杂 LDS 的算子，使用已知写集合的 ASM，减少无关适配。要检查后续输出确实消费 ASM 结果，且调用前的 lane 独立值、uniform 值和指针在返回后仍正确。

### 第三步：验证执行契约

再加入二维线程/逻辑 task 坐标、LDS 工作区、全 CTA barrier 和必要内存顺序。核对逻辑坐标不依赖物理 CTA 的偶然映射；随后扩展到最小 mailbox 依赖。

### 第四步：复用真实 Mono stage

以现有 C1 slice → norm → WQKV 单测为基线，迁移一个完整 stage，保持 CPU oracle、中间结果和 mailbox 校验。避免一开始同时改调用语言、数据布局和算子算法。

### 第五步：比较开销，再决定是否写 ASM 主体

比较最终函数边界、调用/返回及保存恢复指令、private/LDS 需求、驻留容量，并在相同输入和计算范围下测量延迟。不能从 `s_swappc_b64` 的数量，或从源码行数直接推断性能。

验收应包括：只有预期的 Mono launch、没有未解析符号、正确的设备调用、跨调用上下文正确、各阶段结果符合参考，以及所需同步和驻留条件成立。

## 10. 相关实现与文档

- [现有 00/01/10 三种接入实现](ASM_MONO_INTEGRATION.zh-CN.md)。
- [mono_test00 标准 ABI wrapper](../mono_test00/asm/dq_wrapper.cpp) 与 [内部 clobber](../mono_test00/asm/dq_convert_inline.h)：HIP 主体可以复用的 ASM 包装思路。
- [mono_test00 的 FFI 入口](../mono_test00/mono1250/kernels/dq_ffi.py)：现有方向为 FlyDSL 调外部函数。
- [mono_test01 调用点 regmask](../mono_test01/callsite_regmask.py)：定制保持集合的现有原型。
- [mono_test10 inline 边界](../mono_test10/mono1250/kernels/dq_inline.py)：直接嵌入 ASM 的现有实现。
- [基线 projection](../mono_test00/mono1250/kernels/reference_projection.py)：构建期上下文、预取、等待和 WQKV stage 的实际组织。
- [原始 Mono 单测说明](../mono_test_origin/README.md)：C1 配置与验证范围。

本文的 `StageArgs` 类接口概念、FlyDSL 导出层、HIP/ASM 主体和自定义内存状态协议均为设计建议，不是现有实验已经实现的能力。
