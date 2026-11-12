# 混合 ASM 预处理器与 LLVM fragment 后端：实现细节

本文是 [README.md](README.md) 中通用方案的实现设计，不表示通用后端补丁已存在。
2026-11-12 已添加一个无需 LLVM 补丁的 gfx1100 受限 demo，实际实现和测试说明见 [DEMO.md](DEMO.md)。
用户入口始终是 ASM 文件；HIP 只出现在 `.hip.begin` / `.hip.end` 内。
内部不把手写 ASM 塞入 HIP wrapper，不在最终 kernel 中生成 device 函数调用。

## 1. 建议组件和构建产物

建议将 Python 预处理器与绑定版本的 LLVM fragment 编译器分开。

```text
callee_test20/
  README.md
  IMPLEMENTATION.md
  mixed_asm.py                 # 已有 gfx1100 受限 demo；通用版本仍为拟议
  contract.py                  # 拟议：类型/寄存器/FP 配置及验证
  fragment_codegen/            # 拟议：LLVM 补丁或绑定版本的工具
  examples/                   # 拟议：完整混合 ASM kernel
  tests/                      # 拟议：合约、代码生成、完整 GPU 输出验收
```

上面的目录结构描述通用扩展后的目标布局。当前已创建的 demo 使用 `kernel.s`、
`mixed_asm.py`、`test_mixed_asm.py`、`verify.py` 和 `test.cpp`，具体范围见 DEMO.md。

拟议命令：

```bash
python3 mixed_asm.py kernel.s \
  --target gfx942 --wave-size 64 \
  --llvm-dir /path/to/llvm/build/bin \
  --build-dir build/kernel \
  --output build/kernel/kernel.generated.s
```

每个块应保留：原始源码、规范化合约、generated HIP、LLVM IR、分配前后 MIR、
最终片段汇编、显式/隐式寄存器报告、诊断和编译环境。

完整构建另保存：拼接后的 `.s`、ELF 对象、链接后的 code object、反汇编、
descriptor/metadata 校验结果和源码映射。
保留手写 ASM 文本及其相对顺序；工具只替换 HIP 块并添加明确的映射/标签注释。

## 2. ASM 分段和接口解析

使用状态机分离普通 ASM、块声明和 HIP 主体。不要用一个跨行正则匹配所有块。

```text
ASM → .hip.begin <id> → DECLARATIONS
DECLARATIONS → .hip.code → HIP_BODY
HIP_BODY → .hip.end → ASM
```

在 HIP_BODY 中跟踪 C++ 注释、字符串、字符字面量和 raw string；其中出现的
`.hip.end` 文字不能终止块。拒绝嵌套块、重复 ID、不匹配结束符及缺少 `.hip.code`。
每条诊断使用原 ASM 文件名、行、列，而不是仅显示临时辅助文件的位置。

MVP 要求 HIP 块位于顶层，不允许在 `.macro`、`.rept`、`.irp` 或条件汇编区域中
定义 HIP 块，也不从 `.include` 自动发现 HIP 块。普通 ASM include 仍交给汇编器。
这样不会错误编译本来不应执行的条件分支，或错误理解宏参数中的寄存器编号。
后续支持这些组合时，需要先明确汇编展开与 HIP 编译的阶段顺序。

第一版只接受明确的寄存器编号，不接受依赖 ASM `.set`、宏参数等的符号绑定。
普通手写 ASM 可继续使用这些机制。

接口解析形成规范化合约，字段建议如下：

```json
{
  "schema_version": 1,
  "id": "arithmetic_0",
  "target": "gfx942",
  "wave_size": 64,
  "inputs": [
    {"name": "a", "type": "f32", "reg": "v0", "policy": "read_only"},
    {"name": "b", "type": "f32", "reg": "v1", "policy": "read_only"}
  ],
  "outputs": [
    {"name": "c", "type": "f32", "reg": "v2"},
    {"name": "d", "type": "f32", "reg": "v7"}
  ],
  "inouts": [],
  "temporary_vgprs": [{"first": 32, "last": 47}],
  "temporary_sgprs": [{"first": 40, "last": 47}],
  "allowed_special_clobbers": ["vcc", "scc"],
  "fp": {"contract": "off", "fast_math": false},
  "require_inputs_ready": true,
  "preserve_exec": true,
  "preserve_mode": true,
  "allow_calls": false,
  "allow_memory": false,
  "allow_spill": false
}
```

schema 中的寄存器集合要按目标合法性验证：编号范围、类型宽度、tuple 对齐、
子寄存器别名和架构资源限制。不能用另一版本 LLVM 的数字 register ID。
output/inout 与 temp 的同类重叠可以规范化去重；不同接口变量的重叠必须拒绝。
input-only 与可写集合不能重叠。

## 3. HIP → LLVM IR

前端自动生成普通的纯计算 HIP helper。示意如下：

```cpp
struct FragmentResult {
    float c;
    float d;
};

extern "C" __attribute__((device, noinline, used))
FragmentResult fragment_arithmetic_0(float input_a, float input_b) {
    const float a = input_a;
    const float b = input_b;
    float c;
    float d;

    // 此处插入原块内容，并用 #line 指向原 ASM 的实际行号。
    c = a + b * a;
    d = a - b / a;

    return {c, d};
}
```

inout 生成可修改的局部值，并纳入返回结果。input-only 生成 const 局部值。
输出必须在返回前完全定义；不能只依靠普通 C++ 的未初始化变量警告。
MVP 的 AST/dataflow 检查应拒绝未赋值输出及所有不支持的语言节点。

IR 中的返回结构是编译容器；fragment 后端把各字段映射到约定的物理输出，
不会采用普通结构返回 ABI、sret 指针或内存写入。必要时前端对 aggregate 做
规范化，让后端明确获得各个输出标量。

建议首先仅支持纯内建标量表达式和显式转换，不允许用户 include 任意头文件、
定义其他函数或直接调用数学库。即使源级写的是简单 `/`，仍要检查最终降低
结果有没有调用、分支或 spill。

编译命令需要显式设置 GPU target、wave、FP contraction、fast math、denormal
配置和优化级别。不要继承主机环境中不透明的默认设置。
HIP RDC 的 `-S` 阶段可能输出 LLVM IR，不能只按文件扩展名判断它已经是汇编；
构建流程应显式区分 IR 生成和机器代码生成阶段。

Clang 完成 C++ 编译后，由预处理器或专用 IR 工具附加 fragment 属性及契约。
属性名称如 `amdgpu-fragment`、`amdgpu-fragment-contract` 是拟议名称。
需要定义哪些属性参与优化、克隆和代码生成，防止 inline 或 ABI lowering
丢失 fragment 语义。helper 必须保留到目标函数的代码生成阶段。

## 4. AMDGPU fragment 入口和出口

推荐在 AMDGPU 后端增加一种由函数属性触发的 fragment 模式。第一版可仅支持
SelectionDAG 路径，并对其他路径报明确错误；后续补齐 GlobalISel。

入口根据合约将物理寄存器添加为 MachineFunction/MachineBasicBlock live-in，
创建具有正确 register class 和类型的虚拟值，并将形式参数接到这些值。
出口将各结果接到固定物理 live-out，必要时生成 COPY。

应使用明确的出口 pseudo 或等价的后端机制，使物理输出在所有优化/分配阶段
都是可观察的用途。它既终止本片段，又不会在最终文本中生成普通 return 指令。
不能仅删除普通函数尾部的 `s_setpc`，因为普通 ABI 的 lowering、隐式参数、
callee-saved 保存和栈配置可能已经影响整个函数。

需要审查并旁路普通 device 函数相关的参数/返回、隐式 ID/指针、frame lowering
以及入口/出口处理。禁止参数 spill、栈访问和默认 ABI 的 callee-save 代码；
不能未经检查一律删除其 prologue/epilogue。

当前相邻 LLVM checkout 中可研究的切入点如下，具体符号/路径按版本复核：

| 模块 | 主要工作 |
|---|---|
| `llvm/lib/Target/AMDGPU/SIISelLowering.cpp` | fragment 形式参数、返回及寄存器值降低；参考 `LowerFormalArguments`、`LowerReturn` |
| `llvm/lib/Target/AMDGPU/AMDGPUCallLowering.cpp` | 后续补齐 GlobalISel 参数/返回路径 |
| `llvm/lib/Target/AMDGPU/SIMachineFunctionInfo.*` | 保存验证后的合约、可用集合及 fragment 状态 |
| `llvm/lib/Target/AMDGPU/SIRegisterInfo.cpp` | 扩展 `getReservedRegs`，限制普通分配集合及所有别名 |
| `llvm/lib/Target/AMDGPU/SIFrameLowering.cpp` | 防止 fragment 走普通调用栈/保存恢复路径 |
| `llvm/lib/Target/AMDGPU/AMDGPUAsmPrinter.cpp` | 输出片段代码及契约报告，不输出普通函数 ABI 包装 |
| AMDGPU target pass 配置 | 安排 fragment 验证及相关 hazard/resource 检查 |

不要一开始修改 `AMDGPUAsmParser` 来解析 C++。整个 C++ 编译发生在预处理阶段，
最终汇编器接收的只有标准 AMDGPU 汇编。

## 5. 临时寄存器池

对独立的 fragment MachineFunction，定义：

```text
A_v = 输出 VGPR 槽 ∪ inout VGPR 槽 ∪ 临时 VGPR 池
A_s = 输出 SGPR 槽 ∪ inout SGPR 槽 ∪ 临时 SGPR 池
```

第一版 input-only 的物理槽不属于通用分配池，仅允许固定 live-in 读取。
其他普通 GPR 从通用分配集合排除，但合法 input-only 寄存器仍可作为固定物理
源操作数。原有架构保留状态不能被契约反向解锁。

reserved 集合的实现必须考虑所有 aliases、子寄存器和 tuple：tuple 中任意组成
不允许分配，就不能分配该 tuple。宽度和配对要求可能使“剩余总数够用”的池
仍然不可用。AGPR/共享资源扩展必须按具体架构单独处理。

该集合只限制这个独立编译的片段，不限制手写 ASM kernel 其他位置的寄存器使用。
不能把此方式直接套成整个混合 kernel 的全局保留集合。

寄存器不足时应产生具体诊断，例如：

```text
kernel.s:87: fragment arithmetic_0 cannot satisfy its register contract
allowed temporary VGPRs: v32-v35
output slots: v2, v7
reason: register allocation would require a spill
```

不能在未成功分配时声称已经知道最小所需寄存器数。若要建议更大的池，应通过
放宽集合的独立诊断编译或有依据的压力分析给出，并注明是候选预算。

还要限制后期 register scavenger、长分支、SGPR spill-to-VGPR-lane、WWM 分配、
复制展开等路径。只改普通 VGPR allocator 的 reserved 集合并不够。
MVP 没有长分支或 WWM 功能；一旦出现 spill/scavenging 的未授权资源，直接拒绝。

## 6. 实际指令验证

在寄存器分配和所有会新增/改写指令的后期 pass 结束后，运行 fragment verifier。
需要遍历真实指令，使用目标指令描述中的显式及隐式 uses/defs，并检查别名。

至少验证：

1. 入口物理值与合约一致，出口固定寄存器得到正确的结果。
2. 所有普通 GPR 的实际写入都在允许集合内；input-only 无实际写入。
3. VCC/SCC/EXEC/MODE 等隐式写入满足合约。input-ready 前置条件被报告。
4. 没有 scratch、SGPR lane spill、栈、callee-save、调用和未支持的控制流。
5. 没有内存访问、LDS、barrier、ID 获取或其他 MVP 未授权的操作。
6. 没有改变 EXEC、WWM/WQM 或覆盖 inactive lane 的行为。
7. 内部调度/等待满足目标规则，代码没有普通函数 return 或 fallthrough 以外的出口。

报告至少区分“读取过”“写入过”和“出口允许污染”。三者不能混为一谈。
例如 VCC 被读写后恢复，与直接允许出口污染 VCC，是不同接口。
当前 MVP 没有自动特殊状态保存恢复；需要但未授权时应报错。

对代码对象的最终反汇编做第二层复核，防止 AsmPrinter、汇编或链接阶段引入
未审查变化。MIR verifier 无法看见原 ASM 的未声明副作用，完整 kernel 仍需检查。

## 7. 边界等待和 FP MODE

片段独立编译，无法知道前面是否仍有异步 load、MFMA 等操作，也无法知道后面
是否紧接特殊消费者。MVP 要求 ASM 在进入块前保证所有输入及被复用物理槽可用，
并明确报告这一前置条件。后续可以增加显式的 entry/exit fence 模式。

`s_waitcnt` 不解决所有指令依赖；MFMA、depctr、目标相关的 delay/hazard 必须分别
按架构处理。gfx942 的处理不能直接套用到 gfx1250。
不得把普通 device ABI 编译器插入的入口全等待当作任意 ASM 边界正确性的证明。

独立片段的首尾没有邻接指令信息；最终验证应把拼接后的完整指令序列交给
目标相关检查。若暂时没有可靠的自动处理能力，应限定接受的边界并报告限制，
不能宣称生成的任意混合 kernel 都安全。

FP 模式由构建配置与原 ASM 协同指定。MVP 禁止片段写 MODE；若除法等降低需要
临时模式调整，应拒绝或使用已验证的不改 MODE 路径。
gfx1250 等目标还可能有寄存器寻址 bank 状态；应把它作为独立的目标契约检查，
不能只校验可见的浮点模式字段。

## 8. 片段输出、拼接与资源

按块 ID 给内部标签加唯一前缀，保留目标相关调度/等待指令。MVP 禁止用户标签
和 goto，不产生跨块跳转。将片段作为指令文本插回当前位置，不使用 `.long`
机器码注入，不链接为普通被调用 device 函数。

若后续出现常量池、符号引用或重定位，要保留相应 section/符号和链接关系；
MVP 仅接受可在当前位置独立插入的直线指令，不以丢弃重定位的方式绕过这些问题。

片段资源报告只统计实际机器指令涉及的资源，不把已删除的普通 helper ABI
寄存器计算进来。原 ASM 自身使用的资源也必须计入完整 kernel。

MVP 不自动改写用户 descriptor。最终检查至少比较：

- 完整代码的 VGPR/SGPR/AGPR 使用与 descriptor、metadata、架构粒度是否一致；
- 原 kernel 与片段要求的 wave、FP 模式和目标是否一致；
- scratch/private、LDS、barrier 等是否仍符合声明；
- 输入 ready、边界等待及实际指令覆盖是否可以验证。

验证应理解普通 ASM 的宏展开、符号范围和原有编码；仅对源文件做寄存器正则
扫描不够。可复用 MC 指令/资源信息与最终反汇编；无法解析的 `.long`、未知 opcode
或未覆盖区域必须报告。必要时先限制可接受的手写代码范围。

若 descriptor 不足，输出所需预算并失败。未来的自动修正应使用对应目标的
资源计算规则，并作为显式选项；不能只用最高编号加一替代所有资源核算。
资源声明正确后，真实 launch 配置下的 occupancy 仍需单独检查。

## 9. 原型策略与 LLVM 改动边界

可以先用 stock LLVM 做底层能力探针：固定寄存器约束配合纯表达式，验证类型、
代码生成和入口/出口 COPY。这类内部探针不改变产品的 ASM 用户入口。
它不能作为指定临时池、完整状态保护或无 ABI fragment 的实现证明。

若暂时不改 LLVM，可以尝试版本绑定的 pre-RA MIR 实验：在所有分配前建立物理
live-in/live-out，修正普通 ABI 相关机器信息，再继续后端流程。必须逐项验证
参数/返回、frame、隐式资源、分配池和后期 pass；不能只替换 MIR 中几个数字。
将其定位为实验后端，不承诺跨 LLVM 版本稳定。

正式路线优先实现专用 fragment 模式及 verifier。先完成正确的入口/出口和
有限资源分配，再考虑减少 COPY、合并输出槽与临时池、调度优化等性能工作。

## 10. 验收与实施阶段

### P0：解析器、契约和产物

- 接受建议语法，生成规范化 JSON、纯 HIP helper 和原源码诊断。
- 对非法类型、寄存器重叠、未定义输出、嵌套及不支持的 AST 节点报错。
- 保留 ASM 文本，不运行 GPU，不把底层探针输出宣称为最终片段。

### P1：受约束片段后端

- 验证 `c = a + b*a` 的融合/不融合形式，固定输出 v2，保护输入 v0/v1。
- 验证 `d = a-b/a` 输出 v7，并只使用授权的临时池与特殊状态。
- 在更小池、缺少 VCC/SCC 授权、输出 tuple 冲突等情况下明确失败。
- 检查最终代码无调用、栈、spill、EXEC/MODE 改写及未授权寄存器写入。

### P2：完整 ASM kernel

- 生成一个有真实参数、load/store 和 descriptor 的 ASM 测试 kernel，仅中间计算
  使用 HIP 块；外围 load/store 完全保持手写。
- 在外围寄存器放置 sentinel，完整输出输入、结果及受保护状态，对照独立参考。
- 覆盖普通输入、随机输入、零、正负零、极值、NaN/Inf、denormal；根据明确的 FP
  模式和 math 选项定义参考及容差，不能对所有模式统一要求逐位一致。
- 先验证 full EXEC，再覆盖合法的部分 EXEC 及 inactive lane 保留；对应 FP MODE
  和边界条件要分别测试。
- 复核完整反汇编、descriptor 和实际 launch 的资源/驻留限制。

### P3：扩展能力

依次考虑 SGPR 输入输出及 uniform 性检查、f64/整数 tuple、packed 类型、内部
控制流、访存和数学库。每种能力都要补齐合约、后端资源、等待和完整输出验收。
barrier、跨块控制流和全局调度不是简单放开 AST 就能支持的功能。

## 11. 缓存和可复现性

缓存键至少包含：HIP 原文、规范化合约、目标/wave、FP/优化选项、Clang/LLVM
版本和补丁版本、编译前端的依赖内容，以及生成器/schema 版本。
原 ASM/include 内容另作为完整拼接、汇编和链接阶段的依赖。

不要复用另一个寄存器池或另一 target 编译的片段。环境记录保留完整命令、
工具路径、版本和输入/输出 hash；目标特定的寄存器名称表也要绑定正在使用的
LLVM。外部编译器进程使用结构化 argv，避免把用户 C++ 内容拼接成 shell 命令。

诊断构建和真正采用的构建要分别记录；不能先放宽池得到代码，再把宽池指令
作为满足原契约的结果输出。
