# RFC：为 FlyDSL / LLVM AMDGPU 增加外部 ASM 调用契约

**目标：固定参数寄存器、按调用点约束活跃上下文，并强制零 GPR spill、零 scratch。**

日期：2026-11-10。状态：需求与设计草案，尚未实现、尚未向上游提交。

本文建议首先向 **FlyDSL 提出用户接口与集成需求**，同时拆出 **LLVM AMDGPU 后端需求**。希望使用者仍然通过类似 `mono_test00` 的 `ffi + link_extern` 调用 ASM；寄存器约束、链接、验证和报告由工具链完成。

文中的新 API、契约字段、IR 操作、选项和诊断名称都是**拟议接口**，不能直接用于当前 FlyDSL / LLVM。现有代码与实测记录单独标注。

## 1. 希望上游提供什么

希望支持一个由供应方提供的 **ASM 设备函数 + 调用契约**：

1. ASM 显式声明输入/输出使用哪些物理 SGPR、VGPR，例如两个 workgroup ID 分量分别放入 `s0`、`s1`，64 位 global 地址放入 `v[0:1]`。
2. ASM 显式声明读写的寄存器、保持的执行状态、最高寄存器编号、LDS 等资源，以及是否使用 private memory。
3. 编译器在寄存器分配前理解这个边界，自动为调用前后仍需使用的值选择安全寄存器、安排必要的普通寄存器复制或合法重算。
4. 开启严格模式后，**最终整个 Mono 及其可达被调函数不得生成 GPR spill 或使用 scratch/private memory**。不能满足时，编译失败并解释原因。
5. 编译器输出每个 ASM 调用点的参数位置、污染集合、可用保持集合、实际活跃上下文、寄存器搬运，以及最终 kernel 资源报告。

允许真正的设备函数 call/return、`s_swappc_b64` / `s_setpc_b64`、静态链接和普通寄存器搬运。不要求只有 `s_branch`，不要求零额外指令。

**核心不是“自动保存所有寄存器”，而是“让编译器按这个 ASM 的真实契约分配跨调用值，且不能偷偷退回 spill”。**

### 1.1 必须明确的可行性边界

如果 ASM 覆写了所有可用寄存器，而调用后还有不可重算的值，那么这些值必须被存到其他地方。禁止所有 spill，又没有保持寄存器时，编译器无法凭空保存它们。

因此需求应写成：

> **成功编译意味着已验证满足零 spill / 零 scratch；不能满足时必须报错。**

不能要求任意 ASM、任意 Mono 都成功。也不要求启发式寄存器分配器找到所有理论上存在的无 spill 分配；允许说明当前分配策略失败，不能把这种失败一律描述为数学上无解。

## 2. 当前实验为什么需要这项能力

详细实现对照见 [ASM_MONO_INTEGRATION.zh-CN.md](ASM_MONO_INTEGRATION.zh-CN.md)。

| 当前方法 | 已解决的问题 | 与本需求的差距 |
| --- | --- | --- |
| [mono_test00](../mono_test00/README.md)：标准 ABI wrapper `.bc` + FFI | 接口简洁；编译器自动处理普通设备调用 | wrapper 必须遵守默认 callee-saved 约定，可能为 ASM 改写的寄存器生成 scratch 保存；外层参数仍按标准 ABI 传入 |
| [mono_test01](../mono_test01/README.md)：设备函数 + MIR regmask 修改 | 调用方在寄存器分配前知道自定义保持集合 | 依赖编译 hook、MIR 和 LLVM 版本；只调整保持集合并不能保证无 spill，也没有完整固定参数接口 |
| [mono_test10](../mono_test10/README.md)：inline asm `.long` + 固定输入/clobber | 编译器直接看到寄存器边界；当前案例达到零 scratch | 手工内嵌机器码；缺少外部函数契约、强制策略、完整资源报告与稳定对象链接接口 |

三个 README 记录的 gfx1250 结果如下；本次编写 RFC 没有重新运行 GPU，不能将这些记录当作新的测量：

| 路径 | 最终 VGPR / SGPR | scratch 字节/线程 | VGPR / SGPR spill 计数 |
| --- | --- | --- | --- |
| 原始 Mono | 126 / 68 | 0 | 0 / 0 |
| test00 标准 ABI wrapper | 126 / 70 | 32 | 0 / 0 |
| test01 自定义保持集合 | 257 / 108 | 16 | 1 / 16 |
| test10 inline asm | 126 / 68 | 0 | 0 / 0 |

这里特别有价值的是：**test00 的 spill 统计为 0，仍然存在 32 字节/线程的 scratch**。默认 ABI 的保存/恢复不一定计入普通寄存器分配器的 spill 统计，不能仅检查 `.vgpr_spill_count` 和 `.sgpr_spill_count`。

这些实验只把 WQKV 中的 `bf16_round(total)` 换成经过适配的 dq_convert，保留矩阵乘与 FP32 累加。它们验证接入和上下文正确性，并未证明替换整个 WQKV 的性能。已有 tile 的 global memory 中间输入/输出属于算法数据，不应与上下文 spill 混为一谈。

### 2.1 不是 LLVM 完全没有相关机制

现有 LLVM 已有固定寄存器 inline asm 约束、clobber、机器指令 regmask、寄存器分配、资源分析，以及 AMDGPU 的多种 calling convention。AMDGPU 文档也介绍了 IPRA 对调用保持集合的优化。

目前核对的 FlyDSL 0.4.1 接口中，`ffi` 接收符号、标量参数类型、返回类型与 `is_pure`；`link_extern` 主要关联 bitcode 和初始化回调，没有本 RFC 要求的完整外部 ASM 契约。

实际缺口是：**把这些后端能力组织成受支持的外部 ASM 接口，并对固定参数、自定义保持集合、无 spill 保证、最终资源验证建立一致语义。** 这不是对所有最新上游分支能力的穷尽断言。

## 3. 需求优先级与第一版范围

| 编号 | 必须支持的能力 | 可验收结果 |
| --- | --- | --- |
| R1 | 按参数指定物理 SGPR/VGPR、宽度和顺序 | callee 入口的寄存器值符合声明 |
| R2 | 完整读写/保持契约，在寄存器分配前生效 | 跨调用活跃值不被 ASM 或调用序列覆盖 |
| R3 | 严格无 GPR spill / 无 private memory | 违反即编译错误，不能只警告 |
| R4 | 独立设备函数目标链接 | 不要求用户导出、修改 MIR 或嵌入 `.long` |
| R5 | 最终 kernel 资源合并 | descriptor 覆盖 caller、callee 与调用序列的资源 |
| R6 | 调用点及整个 kernel 的报告 | 同时有可读诊断与可解析 JSON |
| R7 | 明确 EXEC、收敛、同步、特殊寄存器规则 | 不因 ABI/GPU 执行状态不匹配而误编译 |
| R8 | 目标文件与契约绑定 | 不接受契约与实际链接对象不一致的组合 |

建议第一版收敛到以下范围：

- AMDHSA 的 gfx1250、wave32；后续再扩展其他架构与 wave64。
- 直接调用、静态链接、叶子 ASM 函数；禁止递归、未知间接调用和不透明嵌套调用。
- full EXEC 的 wave 一致调用；第一版 ASM 不改变 VGPR bank 分配状态。
- 32/64 位整数或地址标量参数，显式寄存器返回值；不支持隐式 byval/sret、栈传参和可变参数。
- ASM 不使用 private memory；LDS 第一版可要求为 0，支持 dq_convert 当前适配片段。随后增加显式 LDS 分区接口。
- 允许 SCC/VCC 等状态按契约污染；EXEC、MODE 等关键状态必须按目标规则保持或在可验证的边界恢复。

`co` 只是扩展名。本接口第一版接收包含可调用设备函数的 **ELF ET_REL `.o/.co`**。已有可启动 `.hsaco` 不会自动变成 device 函数，需要先适配入口、退出和执行环境。运行时动态链接与多个未知目标的函数指针不是首版要求。

## 4. 最小用户接口：仍然像 FFI 一样调用

以下代码是**拟议 API**。建议对 `ffi` 增加契约，对 `link_extern` 增加设备目标链接路径，而不是让 ATOM 使用者学习另一套后端流水线：

```python
# 拟议接口，当前 FlyDSL 不支持这些新增参数。
stage = link_extern(
    ffi(
        "mono_asm_stage",
        ["uint32", "uint32", "uint64", "uint32", "uint32", "uint32"],
        "uint32",
        is_pure=False,
        asm_contract="stage.contract.json",
    ),
    device_object_path="stage.co",
)

# 在 Mono 中，调用形式与普通 FFI 相同。
result = stage(block_x, block_y, buffer_address, thread_x, thread_y, 7)

# 拟议编译选项：作用于整个入口及其可达调用图。
compiled = compile_mono(
    projection,
    external_asm_policy={
        "scope": "entry_and_reachable_callees",
        "gpr_spill": "forbid",
        "private_memory": "forbid",
        "hidden_context_memory": "forbid",
        "on_violation": "error",
    },
    resource_report="build/projection.resources.json",
)
```

其中 `7` 在源程序中是立即数，契约仍可要求它在入口时位于 `s2`。编译器必要时生成 `s_mov_b32 s2, 7`。这不同于修改已经汇编好的指令，把 7 变成机器码 literal；后者属于算子特化，需要另行生成并绑定对应对象。

如果更倾向新增 `extern_asm(...)` 工厂，也可以封装同一套机制。接口名称可讨论，关键是**一份契约、一次注册、普通调用，无用户侧 MIR 修补**。

### 4.1 保留 `.bc` 集成体验，但不保留默认 ABI 包装层

可以继续提供 `bitcode_path=...`，让 `.bc` 携带类型声明、契约和适配逻辑；也可以由 FlyDSL 根据 manifest 自动生成这些 IR。

但不能简单沿用 test00 的默认 ABI `noinline` wrapper，然后只在内层增加 clobber。默认 ABI 仍要求 wrapper 保存被污染的默认 callee-saved 寄存器，scratch 问题没有消失。

建议有两种受支持的落地形式：

1. **首选：** FlyDSL 生成带契约的直接设备调用；callee 是独立 ASM ET_REL 目标。
2. **可选：** `.bc` 包装函数采用工具链认识的同一自定义调用契约；无必要的参数适配应在优化阶段消除。最终边界仍不能退回默认 ABI。

不能把任意 `.co` 改名为 `.bc`，也不能让独立 ASM 挂在普通 C ABI 声明后面却不履行该 ABI。

## 5. 调用契约需要包含哪些信息

### 5.1 参数位置和参数语义

以第 4 节的演示函数为例：

| 参数/结果 | LLVM 层逻辑类型 | 入口/出口位置 | 语义 |
| --- | --- | --- | --- |
| block_x | i32 | s0 | wave 内一致的 workgroup x |
| block_y | i32 | s1 | wave 内一致的 workgroup y |
| buffer_address | i64 | v[0:1] | 每个有效 lane 的 64 位 global 地址，低 32 位在 v0 |
| thread_x | i32 | v2 | 每 lane 的 thread x |
| thread_y | i32 | v3 | 每 lane 的 thread y |
| factor | i32 | s2 | wave 内一致的整数，本次传 7 |
| result | i32 | v4 | 每 lane 的返回值 |

这里 `s0:s1` 表示**两个 u32 坐标分量**；如果要传一个打包 u64，必须声明其打包规则。`v[0:1]` 是 64 位地址，不是通常需要 4 个 dword 的 buffer resource descriptor。

固定参数位置适用于 device 函数入口，不改变 HSA 入口 kernel 的硬件启动 ABI。Mono 入口获得自己的 kernarg、workitem/workgroup 信息后，由编译器将所需值安排到上述位置。

ATOM 的物理 CTA ID、Mono task ID、供应方算子的逻辑 tile ID 必须由调用者区分。ABI 负责传值，不负责判断某个 tile 应该使用哪组逻辑坐标。

SGPR 参数需要证明 wave 内一致。不能将任意 divergent VGPR 值静默 `readfirstlane` 后传入 SGPR；无法证明时，应报错，或使用单独定义且显式承担约束的 uniform assertion。首版以编译期可证明为准。

固定寄存器绑定也不等于零 `v_mov` / `s_mov`：若源值已经处于目标寄存器，可通过 coalescing 消除复制；若源值位置不同或要保护原值，则复制仍可能必要。报告应让用户看到这些指令。

### 5.2 必须区分的四组寄存器信息

| 信息 | 用途 | 不能替代什么 |
| --- | --- | --- |
| `live_in`：入口要读的寄存器 | 固定参数、返回地址、隐式执行输入 | 不能仅用资源数量推导 |
| `may_write`：所有可能写到的寄存器 | 审计 ASM 与描述中间状态 | 不等于调用后一定破坏原值 |
| `net_clobber`：返回后不保证保持入口值的寄存器 | 推导 call-preserved regmask | 不等于最高使用编号 |
| `uses` / 资源上界：完整使用集合和最高编号 | 更新最终 kernel 资源 | 不能用于推导精确污染集合 |

例如 ASM 临时修改 MODE 后恢复，MODE 属于 `may_write`，但不属于 `net_clobber`。又如 ASM 只使用 `v80` 一个 VGPR，不能将资源需求写成“1 VGPR”；分配必须覆盖对应物理编号及硬件分配粒度。

契约至少支持 SGPR/VGPR；其他架构上的 AGPR 及其与 VGPR 的关系必须按 target 建模，不能假装所有架构共享同一套编号、alias 和资源计算。

### 5.3 一份示例 manifest

以下为**提案 schema 的示意 JSON**，使用第 5.1 节的演示接口，**不是当前 dq_convert 的真实契约**。范围字符串为闭区间；`REPLACE_WITH_SHA256` 是打包时必须替换的占位符。

```json
{
  "schema": "amdgpu.external_asm_contract.v1",
  "symbol": "mono_asm_stage",
  "object": {
    "path": "stage.co",
    "format": "ELF_ET_REL",
    "sha256": "REPLACE_WITH_SHA256"
  },
  "target": {
    "triple": "amdgcn-amd-amdhsa",
    "cpu": "gfx1250",
    "wavefront_size": 32,
    "call_contract_version": 1
  },
  "signature": {
    "inputs": [
      {"name": "block_x", "type": "u32", "register": "s0", "uniform": true},
      {"name": "block_y", "type": "u32", "register": "s1", "uniform": true},
      {"name": "buffer_address", "type": "u64", "register": "v[0:1]", "address_space": "global", "dword_order": "low_first"},
      {"name": "thread_x", "type": "u32", "register": "v2"},
      {"name": "thread_y", "type": "u32", "register": "v3"},
      {"name": "factor", "type": "u32", "register": "s2", "uniform": true}
    ],
    "outputs": [
      {"name": "result", "type": "u32", "register": "v4"}
    ]
  },
  "control": {
    "kind": "direct_device_call",
    "return_pc": "s[30:31]",
    "return_pc_must_survive": true,
    "leaf": true,
    "entry_exec": "full_wave",
    "exit_exec": "same_as_entry",
    "convergent": true,
    "workgroup_size": [256, 1, 1],
    "contains_workgroup_barrier": false
  },
  "registers": {
    "declaration": "complete",
    "uses": ["s[0:31]", "s[40:47]", "v[0:63]"],
    "may_write": ["s[0:29]", "s[40:47]", "v[0:63]", "scc", "vcc"],
    "net_clobber": ["s[0:29]", "s[40:47]", "v[0:63]", "scc", "vcc"],
    "unlisted_gprs": "untouched",
    "preserved_state": ["exec", "mode", "m0", "flat_scratch", "ttmp", "vgpr_bank_state"]
  },
  "resources": {
    "numbered_vgpr_extent": 64,
    "numbered_sgpr_extent": 48,
    "private_segment_bytes_per_thread": 0,
    "stack_arguments_bytes": 0,
    "lds_bytes": 0
  },
  "effects": {
    "memory": "read_write_global",
    "wait_state_entry": "drained",
    "wait_state_exit": "drained"
  }
}
```

补充规则：

- `uses` 此处列编号 GPR；特殊寄存器的读取、写入与保持由执行状态字段完整补充。可扩展 target 字段必须版本化。
- 输入寄存器也可以位于 `net_clobber` 中，表示读完可覆盖。上例保守声明 v0/v1 等输入可改写。
- 输出寄存器必须建模为定义；即使某次输出碰巧与旧值相等，也不能用来保存调用前的不相关值。
- `s[30:31]` 是本契约选择的返回 PC，callee 必须使其可用于返回；不能把这两个寄存器算成普通可用上下文容量。
- `numbered_*_extent` 是编号覆盖范围，不是最终 metadata SGPR/VGPR 数量；特殊寄存器与硬件粒度由后端计算。
- `unlisted_gprs=untouched` 是供应方对未列出 GPR 的完整承诺；不是工具看到缺失字段后自行假设保持。
- `wait_state=drained` 表示对应 target 的未完成内存/异步操作已按契约完成，不能只硬编码一条旧架构 `s_waitcnt` 就认为所有 counter 都清零。
- 目标特性、FP 模式、Xnack 等影响 ABI/代码的条件，应在实际 schema 中使用规范化 target feature 列表补全。

契约是编译正确性的输入。供应方错误声明保持关系会造成错误代码；工具需要尽可能检查，不能声称能自动理解任意黑盒机器码的完整语义。

## 6. 如何让调用者保住上下文，又不生成 scratch

### 6.1 为该边界建立真实的保持集合

粗略地，以物理 register unit 为单位定义：

```text
A       = 当前 target / 模式下允许分配的寄存器单元
C_asm   = callee 的净污染集合
C_setup = 参数准备、call 目标计算、返回地址设置等序列的覆盖集合
C_out   = 返回值及结果复制所需的定义集合
R       = ABI / 硬件 / 后端保留寄存器及临时用途

可用于原值跨整个边界保持的候选集合
P_safe ⊆ A - (C_asm ∪ C_setup ∪ C_out ∪ R)
```

这是解释用的保守公式。真正实现应将参数 COPY、call 定义、regmask、返回 COPY 和生存区间一起建模，不能只减寄存器数量；根据值的身份和生存期，有些固定输入能够复用原值。

`C_setup` 由编译器生成，不应要求供应方猜测。例如需要一对 SGPR 计算调用目标时，后端必须把它们纳入临时资源和活跃性分析，避免覆盖 `s0:s1` 参数或保存的上下文。

标准 ABI 中某个寄存器是不是 callee-saved，不能代替本契约。自定义契约可以明确使用不同的保持集合，但后端必须真正支持对应 calling convention 和寄存器类。不能单纯向默认 mask 随意添加位而忽略其他调用降低假设。

### 6.2 只约束跨这个调用点仍活跃的值

```text
阶段 A 中的临时值 ──最后一次使用──┐
                               │  可与 ASM 复用同一物理寄存器
                               ▼
Mono 上下文 ─────────────── [ASM call] ─────────────── 后续阶段
                    必须在安全寄存器中保持，或合法重算
```

不是要求整个 `projection()` 只能使用某个低编号范围。调用前已经死亡的值以及调用后新产生的值仍可使用 ASM 污染的寄存器。

对于跨调用值，编译器可以：

1. 直接分配到该调用点安全的保持寄存器。
2. 拆分生存区间，在边界前后进行普通寄存器复制。
3. 合法重算常量、地址偏移等值，或调整纯计算调度以减少 live-through 压力。
4. 找不到符合策略的分配时，产生编译错误。

不能通过未经语义证明的 global reload 代替保存旧值。例如 callee 可能写入原地址，重载就不再等价。也不能隐式添加 LDS/global 上下文表，声称因为没有 `scratch_*` 指令所以成功。

### 6.3 低编号保持区可作为额外约束，但不是默认必要条件

如果供应方污染 `v64` 及以上、`s40` 及以上，且未污染的低编号 GPR 足够，编译器就应将跨调用上下文放入可用低编号区域。实际还要扣除参数、返回 PC、调用临时值、保留寄存器和 alias。

可提供拟议选项 `live_through_allowed_regs`，进一步要求某个调用点的上下文只用给定范围。它与 kernel-wide 的 `amdgpu-num-vgpr` / `amdgpu-num-sgpr` 不是同一概念，也不一定更快：人为缩小集合可能使本来能无 spill 的调用失败。

报告需要说明“低编号范围中有多少实际可用空间”，不能把 s0～s39 一律当作 40 个可用 SGPR。已有 test01 中 s30:s31 和 SP/FP/BP 等位置就不能按普通业务寄存器计数。

### 6.4 调用者和被调用者必须遵守同一契约

新契约下，callee 允许直接覆盖 `net_clobber` 中的寄存器，即使它们在默认 C ABI 中属于 callee-saved。编译器应提前将 caller 的活跃值移开，而不是再为 callee 生成默认 ABI 的整套保存/恢复。

若 callee 承诺保持某寄存器，却实际写坏它，属于契约违反。若需要在寄存器内暂存并恢复某状态，暂存寄存器也必须进入 `uses`、污染和资源分析，不能无成本地消失。

若 Mono 之外又有默认 ABI 调用者，则外层 ABI 的保持义务仍然存在。严格策略必须检查完整可达调用图，不能只证明内层 ASM 边界无 scratch。

## 7. “零 spill / 零 scratch”的精确定义

建议严格策略拆成三个开关，默认一起开启：

| 策略 | 禁止的行为 |
| --- | --- |
| `gpr_spill=forbid` | VGPR/SGPR/适用时 AGPR 的 spill/reload；也禁止后端为 SGPR spill 生成 VGPR lane 存取 |
| `private_memory=forbid` | caller/callee 的 scratch、ABI 保存帧、局部栈对象、栈传参、动态栈、emergency spill slot 等 |
| `hidden_context_memory=forbid` | 工具链为了维护跨调用上下文而隐式引入 LDS/global 等替代保存区 |

允许普通 `s_mov`/`v_mov`、parallel-copy 解析、寄存器 coalescing 和合法 rematerialization。普通复制不是内存 spill；SGPR-to-VGPR-lane 的 **spill lowering** 则在本提案严格模式中被禁止。

验证时要同时看生成过程和最终代码。不能因为算法本来使用 `v_writelane` 就判定发生 spill，也不能仅凭没有 `scratch_load/store` 文本就放行：不同目标还可能通过 buffer/flat 等指令访问 private memory。

**严格模式默认覆盖整个入口及所有可达被调函数。** 若将来提供仅检查调用边界的局部模式，报告必须清楚写“boundary-only”，不得输出“整个 Mono 零 scratch”。

允许算法正常的 global/LDS 输入输出，例如 test10 为 dq_convert 准备的 tile。这不意味着允许编译器将上下文保存伪装为算法数据访存。对供应方手写 ASM 的用途不能完全自动证明，必须由已审核契约声明并由测试补充验证。

### 7.1 实现上可以先尝试编译，再严格拒绝产物

第一阶段可以让分配器正常尝试，通过中间审计和最终校验发现 spill 后拒绝发布可执行产物。这已经提供“成功即满足”的语义。

后续再让 spill policy 在分配、调度和 rematerialization 策略选择中生效，增加成功率、减少无效工作。不能仅在最早看到 spill 候选时就判定最终一定需要 scratch；有些中间伪指令之后可能被消除。

无论采用哪条实现路线，最终仍须在 prologue/epilogue、scavenging、call lowering 等可能引入额外保存的阶段之后检查。失败时可保留用于调试的中间文件，但不能缓存或交付为符合契约的 kernel。

## 8. LLVM 后端需要增加什么

### 8.1 不可被优化忽略的 IR 语义

需要正式表示以下内容：目标、契约版本/身份、函数类型、固定输入输出、净污染/保持状态、资源、执行约束和严格策略。

可讨论的实现形式是目标专用 call intrinsic，或**后端正式支持的自定义 calling convention + 参数/函数属性**。MLIR 层可以提供专用操作，再降低为对应 LLVM 表示。

```text
// 语义示意，不是当前合法 MLIR/LLVM IR 语法。
amdgpu.extern_asm.call @mono_asm_stage(%bx, %by, %ptr, %tx, %ty, %factor)
  contract = @stage_contract_v1
  convergence = full_wave
  effects = read_write_global
  no_spill = true
```

不能只附加一个普通未知 metadata，再假设优化器和后端都会遵守。对于不认识该语义的工具链，必须诊断“不支持契约版本”，不能静默降级为普通 `ccc` call。

类型检查、bitcode 链接、LTO、函数克隆和内联都要保留语义。具有不同契约的同名符号应报错；调用声明和定义的契约不一致应报错。第一版可禁止该 ASM 边界内联，保证外部设备函数身份稳定。

### 8.2 在所有相关寄存器分配之前降低

后端需要：

1. 验证固定参数寄存器的类型、宽度、配对、合法编号、uniformity 与冲突。
2. 为输入/输出生成真实的 fixed physical operands 或等效的约束 COPY。
3. 生成 target-aware 的 call-preserved regmask，并正确处理 subregister、superregister、tuple 和 register-unit alias。
4. 将 callee 资源下限与调用序列使用的临时寄存器通知资源分析和调度。
5. 将约束交给 SGPR、VGPR、适用时 AGPR 分配和 WWM/执行掩码相关处理。
6. 保证参数设置、返回地址、目标地址、复制循环解决所需临时值同样符合无 spill 策略。

不能在寄存器分配之后才修改 regmask。也不能只处理一套 SGPR/VGPR 数量而漏掉被覆盖的 tuple alias。

### 8.3 区分 call-preserved mask 与 callee 自身保存义务

mask 告诉 caller 哪些值能跨调用存活；callee 按什么 ABI 生成 prologue/epilogue 是另一件事。

对于独立 ASM，供方负责满足契约。对于 `.bc` wrapper，编译器必须按同一契约生成代码，不能继续套默认 `CSR_AMDGPU` 保存规则。IPRA 可以辅助分析已知机器函数，但不能单独取代固定参数接口、外部二进制契约和无 scratch 保证。

### 8.4 资源分析与最终验证

最终 kernel 的资源必须覆盖：

- caller 使用的物理寄存器；callee 声明并经审计使用的物理寄存器。
- call/return 序列、寄存器复制、特殊状态处理所需资源。
- target 的寄存器粒度、特殊寄存器计数和适用时动态 VGPR 分配约束。
- LDS 大小、对齐及并存生命周期；不能把各阶段 LDS 简单取 max，除非已证明其分区可以安全复用。
- 完整调用图的 private/stack 需求。严格模式下必须为 0。

编号 GPR 通常按 caller/callee 的最高覆盖需求取并集后再按目标规则计算，不是把两个函数的寄存器数相加。LDS/private 又有各自的合并规则，不能混用一个公式。

需要一个最终 MachineFunction/链接验证环节，检查 spill 来源、frame objects、特殊保存、真实 private 访问和资源一致性。外部目标必须参与验证，不能只扫描 caller 的 `.ll`。

### 8.5 可以借鉴的现有机制

- inline asm 的固定寄存器输入输出、clobber 与 MachineInstr regmask。
- AMDGPU 现有 CSR、`SI_CALL` lowering、资源分析、优化 remarks。
- IPRA：利用已知被调代码的实际寄存器使用信息。
- `amdgpu_cs_chain` / `amdgpu_cs_chain_preserve` 等约定：说明后端已有专门执行契约的先例。

但 `amdgpu_cs_chain` 使用专用 chain intrinsic、指定参数规则和不同执行/保持语义，不是这里所需的任意固定寄存器、普通返回的 AMDHSA device call 接口，也不自动保证无 scratch。不建议仅替换 calling convention 名称就把当前问题视为解决。

## 9. FlyDSL 应负责什么

| 层次 | FlyDSL 的职责 | LLVM/目标工具链的职责 |
| --- | --- | --- |
| 用户声明 | 简洁 API、manifest schema、参数类型与 target 初检 | 对契约提供真实代码生成语义 |
| IR 构建 | 保留 source location、convergence、memory effects；输出对应调用 | 固定寄存器 lowering、保持集合、资源约束 |
| 机器码生成 | 使用受支持的 LLVM 通道；拒绝版本不匹配 | RA、调度、调用序列、无 spill 策略 |
| 外部链接 | 收集设备对象和契约，按内容 hash 缓存 | 处理符号/重定位，合并并验证资源 |
| 用户反馈 | 将 diagnostics 和 JSON 关联到 Mono stage/task 位置 | 提供真实活跃值、寄存器与失败原因 |

FlyDSL 本身可以先做 manifest、对象注册和最终“编译后检查、不合格则拒绝”的界面。若以 inline asm 作实验性 lowering，必须清楚标注限制，不能宣称已实现稳定的自定义外部设备 ABI。

完整的独立函数调用方案应由 LLVM 提供正式支持；不应把 test01 的版本相关 MIR Python 修改器变成长期公共接口。

### 9.1 推荐构建流程

```text
供应方 stage.s + stage.contract.json
            ↓ 汇编、检查目标/符号/重定位，绑定对象 hash
         stage.co + 已验证契约
                        │
FlyDSL Mono + ffi 注册  │
            ↓           │
MLIR / LLVM：带调用契约的外部符号与 call
            ↓           │
契约检查 → 固定参数 lowering → 调用点活跃性/寄存器分配
            ↓           │
caller.o ──────── 设备静态链接 ────────┘
            ↓
最终资源合并 + 无 spill / 无 scratch 验证
            ↓
Mono kernel.co + resources.json + diagnostics
            ↓
FlyDSL 原有加载/launch 路径
```

参数寄存器和保持契约必须在编译 caller 前已知，不能等链接得到 `.co` 后才读取 callee 资源再修改 caller 已分配的寄存器。

## 10. 执行状态、同步与黑盒 ASM 的限制

仅有 GPR clobber 不足以定义合法调用。契约还应覆盖以下内容：

| 状态 | 需要明确的规则 |
| --- | --- |
| EXEC / inactive lanes | 入口是否 full wave；出口恢复什么；是否读写 inactive lane 的值 |
| SCC/VCC | 是否被写坏，是否有调用后的隐式使用 |
| MODE | 浮点舍入/denorm 等模式是否与 caller 一致；临时修改是否恢复 |
| M0 / TTMP / FLAT_SCRATCH | 目标相关读写与保留要求，不能只凭寄存器名称做跨架构假设 |
| VGPR bank / 动态分配状态 | 是否改变映射；首版要求不改变 |
| 内存与 wait counters | 入口/出口等待责任；是否有未完成的 load/store/异步操作 |
| barrier | wave/CTA 参与条件、barrier 对象/编号与预期参与者 |
| 收敛性 | 禁止不合法的复制、外提或移动；`convergent` 不是自动 full-CTA 证明 |

对于包含 CTA barrier 的算子，仅证明每个 wave 内调用一致还不够，需要证明/声明 CTA 全体按规定参与。同样，full EXEC 也不自动意味着所有 CTA wave 都执行同一路径。

`memory` clobber 或 read/write memory effects 只约束编译器优化，不能替代硬件等待或 barrier。工具可在边界生成保守的 drain 操作，再在更精确契约下减少等待；生成的所有指令和状态影响都应计入报告。

对于无法证明的 full-wave/CTA 前提，严格模式不能静默假设。可要求使用已有可证明的 DSL collective 区域；如将来允许显式 assertion，应说明其为供方/调用方的正确性责任，并提供 debug 验证途径。

## 11. 对象检查：哪些可以自动验证

推荐先支持受限、可审计的叶子 ASM：

- 已知目标指令集，函数边界明确；完整反汇编指定 symbol 的真实大小。
- 无未知间接分支、无隐藏函数调用、无未经声明的代码/数据重定位。
- 控制流出口是符合契约的返回；禁止独立 kernel 的 `s_endpgm` 作为普通返回。
- 指令使用的显式/隐式寄存器不超出声明；识别目标指令的 tuple、alias、bank 和 special-state 效果。
- 不存在 private 访问、未申报 LDS 使用或调用链资源。
- 有效返回路径与可检查的 EXEC/MODE 恢复模式符合要求。

可以对“写过”的寄存器做保守静态推断；要证明“写过但所有出口都恢复到原值”，通常需要数据流分析或受限的已知模板。不能只看一条寄存器恢复指令就下结论。

验证分级建议：

1. **结构验证：** ELF、target、符号、hash、范围、重定位、参数/资源一致性。
2. **机器码审计：** 指令读写与声明匹配、无 private 访问、受限控制流和返回。
3. **供方承诺：** 无法静态证明的语义，例如某地址用途、精确模式恢复或 CTA 参与前提；报告必须列出这些假设。

首版严格模式可直接拒绝无法识别的指令或控制流。对允许供方承诺的扩展模式，必须明确“保证以供方契约成立为前提”，不能输出“已证明任意黑盒 ASM 正确”。

对象 hash、规范化契约 hash、LLVM/FlyDSL 版本、目标特性、严格策略都进入缓存键。链接时再次核对对象身份；更换同名 `.co` 必须触发重新编译或拒绝加载旧 caller。

## 12. 应向用户报告什么

### 12.1 成功时的报告

至少同时输出人类可读文本和 JSON。每个调用点需要：

- 源位置、stage 名、callee symbol、contract hash。
- 实际固定输入/输出位置和 uniformity 检查结果。
- callee 净污染、call lowering 的额外污染、target 保留集合。
- 可用于跨调用的保持寄存器集合，按 register class/tuple 说明限制。
- 分配前的活跃需求估计，以及分配后的实际 live-through 位置。
- 参数 COPY、上下文 COPY、合法重算的数量与对应值；允许优化造成名称不可追溯，应提供 IR value ID。
- spill 分类、ABI 保存、SGPR lane spill、private frame、最终 private 指令验证结果。
- caller、callee、最终 kernel 的编号覆盖范围、metadata 资源数、LDS 与占用率约束。
- 静态无法证明而依赖供方/调用方承诺的条件。

示意文本，**以下值名和位置不是当前 Mono 的测量结果**：

```text
ASM call: projection / stage_wqkv_asm / mono_asm_stage
contract: v1, target gfx1250 wave32
arguments: block_x=s0, block_y=s1, buffer=v[0:1], tx=v2, ty=v3, factor=s2
result: v4
callee clobber: v[0:63], s[0:29], s[40:47], SCC, VCC
reserved: target + return-PC + call-temporary registers (expanded in JSON)

live-through assignment examples:
  task              -> s48
  mailbox_address   -> s[50:51]
  per_lane_context  -> v64

verification scope: entry_and_reachable_callees
GPR spill / ABI memory saves / SGPR lane spills: 0 / 0 / 0
private frame: 0 bytes per thread
status: VERIFIED_NO_SPILL_NO_PRIVATE_MEMORY
```

上例选择 v64 意味着最终资源至少覆盖该编号，不能继续照抄 callee 的 `numbered_vgpr_extent=64`。成功的零 scratch 分配也可能使用更多 GPR，从而降低 occupancy；报告必须如实显示。

静态编译器可以报告 target 上限和预计每 CU 驻留限制；总 CU 数、最终运行设备的 occupancy 等需要 runtime/device 查询。不能将静态估计冒充实机验证。ATOM 若依赖全部 CTA 同时驻留，应另有显式运行时检查。

### 12.2 失败时的诊断

以下为拟议诊断示例，其中容量只用于展示，不是 gfx1250 的统一硬件限制：

```text
error: external ASM call cannot satisfy the no-spill policy
  at: stage_wqkv_asm -> mono_asm_stage
  required live-through VGPR demand: 18 dwords
  usable preserved VGPR capacity at this call: 16 dwords
  attempted fallback: 2 VGPR spill slots (forbidden)

  values contributing to pressure:
    %task_result, %mailbox_address_parts, %post_stage_state, ...

  options:
    shorten these live ranges or legally rematerialize them;
    provide an ASM variant that preserves more registers;
    raise an explicitly configured resource budget, if hardware permits.
```

寄存器对齐、tuple、不同 lane 活跃性或复制循环也可能导致数量看似足够仍分配失败。诊断应说明真实冲突，不能一律简化成 `required > available`。

其他应有的错误包括：

```text
E_ASM_DIVERGENT_SGPR_ARGUMENT: thread_x cannot be bound to s0 without a uniformity proof
E_ASM_FIXED_REGISTER_CONFLICT: parameter overlaps the selected return-PC pair
E_ASM_CONTRACT_MISMATCH: linked object hash differs from the compilation contract
E_ASM_UNDECLARED_WRITE: instruction may write v80, absent from may_write
E_ASM_PRIVATE_MEMORY: callee contains private-memory accesses
E_ASM_ABI_SAVE_REQUIRED: wrapper generated a forbidden callee-saved memory save
E_ASM_UNSUPPORTED_STATE: dynamic VGPR-bank changes are not supported by contract v1
E_ASM_LATE_SPILL: register scavenging introduced a forbidden spill after allocation
E_ASM_CALL_CONVERGENCE: full-wave entry requirement could not be established
```

建议提供 `--emit-asm-call-report` 一类报告选项，但具体名字由上游决定。报告应保存到文件，不能只有难以捕获的临时 stderr 日志。

## 13. 验收测试

实现应同时覆盖 LLVM 回归测试、FlyDSL 集成测试和 gfx1250 硬件测试。纯反汇编只能证明部分代码生成属性，不能替代执行正确性。

| 场景 | 验收要求 |
| --- | --- |
| 固定 s0/s1 坐标、v0:v1 地址、v2/v3 线程坐标、s2 常量 | ASM 根据全部参数计算结果，与参考一致；反汇编/报告证实入口绑定 |
| 中间阶段调用，后续仍使用 task/tid/pointer/mailbox | 上下文未损坏；覆盖多 seed、不同物理 CTA 和逻辑 task |
| ASM 污染 v64 及以上、s40 及以上的合法目标寄存器 | 能分配时上下文位于安全集合；不能分配时编译失败，不生成 scratch |
| ASM 污染所有可用保持资源且存在不可重算 live-through 值 | 明确拒绝，不偷偷写 LDS/global/private |
| 正常参数与返回 COPY | 允许寄存器搬运；只在必要时生成，报告列出 |
| tuple/alias 冲突 | 不允许 v0:v1 与被污染的 v1 产生错误保持关系 |
| divergent 值绑定 SGPR | 拒绝隐式丢 lane；一致值路径成功 |
| callee 使用默认 ABI 的保存序言 | 检出 private frame；不会被 spill_count=0 蒙混通过 |
| caller 高压力、SGPR lane spill、late scavenger spill | 全部受严格策略约束，诊断来源不同 |
| alloca、栈参数、嵌套未知调用 | 首版明确拒绝 |
| EXEC/MODE 未恢复、错误 wave 大小、未知 bank 状态 | 契约检查或受限审计拒绝 |
| CTA barrier 与不完整 CTA 参与 | 拒绝非法调用位置或标明需要满足的显式前提 |
| callee 使用高编号但只使用少量寄存器 | 最终 descriptor 覆盖高编号，资源不能只按寄存器个数填 |
| `.co` 被替换、契约修改、同名符号 ABI 冲突 | 缓存失效或编译/链接报错 |
| 严格策略关闭 | 允许正常 spill，但报告仍提供，不假称无 scratch |
| 整个 Mono 中另一处产生 scratch | entry-wide 严格模式仍失败，不能只检查目标 ASM call |

可复用当前 `callee_test00/01/10` 的参数与寄存器污染测试思路，但应移除测试脚本中的人工 ABI/MIR 修补，直接使用正式接口。

ATOM 集成验收继续使用 `mono_test00/01/10` 的单卡 C=1 projection 单测：相同的 slice → norm → WQKV 流程，相同 dq_convert 适配，相同中间结果/guard/mailbox 校验。

不应把“新的外部 call 一定复现 test10 的 126/68 寄存器数”列为硬性要求：真实调用的临时寄存器、返回 PC 和优化边界不同。硬性要求是结果正确、参数正确、满足无 spill 策略或给出明确错误；额外性能和 occupancy 数据作为优化指标。

## 14. 分阶段实现建议

### 阶段 A：规范与验证工具

- 明确 schema、target 范围、固定参数、执行状态和严格策略。
- 提供 `.s/.co + manifest` 的审计与打包工具。
- 先覆盖无 private、无 LDS、无嵌套调用的叶子函数，输出资源/寄存器报告。
- 为无法验证的行为确定拒绝规则，避免先承诺支持所有独立 `.hsaco`。

### 阶段 B：LLVM 最小调用语义

- 提供正式的 target call 表示，固定输入输出与自定义 regmask。
- 确保 calling convention 同时控制 caller 和 callee 生成规则。
- 接入资源分析；先以完整编译后验证落实“无 spill，否则失败”。
- 建立参数、上下文、late spill 和 ABI frame 的回归测试。

### 阶段 C：FlyDSL FFI 集成

- 增加契约注册、设备对象链接、版本协商与缓存键。
- 暴露 entry-wide 严格策略和资源报告。
- 将错误映射回 `stage_wqkv_asm` 等 DSL 源位置。
- 移植 ATOM 单测，不再需要 `callsite_regmask.py` 或内嵌 `.long`。

### 阶段 D：优化与扩展

- 让寄存器分配/调度更主动地考虑无 spill 策略，提高成功率。
- 比较不同保持集合、参数布局和资源预算的代价，提供建议或供方变体选择。
- 增加显式 LDS 分区、更多架构、wave64、受限嵌套调用。
- 后续如需动态链接，必须在编译时固定契约，并在加载时验证所有实际目标；不能任意热替换不同寄存器行为的符号。

## 15. 从当前 ATOM 实验迁移

对于 `mono_test00`，优先迁移如下：

1. 保留 `dq_convert.original.s` 和已有适配审计；输入记录、tile staging 和正确性参考先不改变。
2. 将片段改成符合新契约的叶子 device 函数，明确返回 PC 和函数出口，汇编成独立 ET_REL 目标。
3. 将 [dq_convert_inline.h](../mono_test00/asm/dq_convert_inline.h) 中的固定输入和完整 clobber 转成 manifest。**实际 dq_convert 输入仍是 s0:s1 的参数记录地址、v0 的 lane、s24 的 wave**；不要误套第 5 节演示接口。
4. 补全 `.co` 身份、真实资源、EXEC/MODE/wait 状态及无 private 声明。
5. 用新的 `ffi + link_extern` 注册契约与 `.co`，删除承担默认 ABI 的 wrapper 层。
6. 对整个 projection 开启严格策略，查看跨调用活跃值与失败报告。
7. 如果失败，根据报告减少边界 live-through 值，或生成保留更多寄存器的 ASM 变体；不要用修改最终 metadata 的方式掩盖 scratch。
8. 在 gfx1250 上重复完整单测并测量资源和延迟，保留新的报告作为回归基线。

这条路线追求的是 **test00 的使用便利性 + test10 的编译器可见性 + test01 的独立函数能力**，并新增三者都没有的严格无 spill 保证和稳定报告接口。

## 16. 可直接提交给上游的 Issue 摘要

建议先开 FlyDSL 需求，并关联 LLVM AMDGPU 后端讨论。以下为英文摘要，便于直接粘贴；本文尚未代为提交。

**Title**

> [RFC][AMDGPU] Contract-based external ASM calls with fixed argument registers, call-site preservation, and enforced no-spill/no-private-memory codegen

**Problem**

We integrate precompiled AMDGPU assembly operators into a FlyDSL-generated ATOM Mono kernel. We want an FFI-like interface, without user-side MIR patching or embedding instruction words in the caller. A standard device-ABI bitcode wrapper is convenient, but may introduce scratch saves for default callee-saved registers overwritten by the assembly. A custom call-preserved mask alone does not prevent caller spills.

**Requested behavior**

Allow an external device function to provide a versioned, target-specific call contract describing:

- Fixed physical argument/result registers, e.g. two uniform u32 workgroup coordinates in s0/s1 and a 64-bit global address in v0:v1.
- Complete register inputs, writes, net clobbers/preservation, resource extents, and execution-state requirements.
- Object identity and linking requirements for a callable ELF relocatable device function.

Lower the contract before register allocation. Honor it in argument lowering, call-preserved masks, caller live-range allocation, callee ABI obligations, resource accounting, and final verification. Require proof of uniformity for SGPR arguments; do not silently discard divergent lane values.

Provide an opt-in strict policy covering the entry kernel and reachable callees: no GPR spilling, no SGPR-to-VGPR-lane spill lowering, no private/scratch memory including ABI saves, stack arguments, local stack objects or emergency spills, and no implicit LDS/global fallback for caller context. Ordinary register copies and legal rematerialization remain allowed.

Successful compilation must satisfy this policy; otherwise compilation must fail with actionable diagnostics. We do not require arbitrary register-destructive assembly to compile without storage, nor an allocator that finds every theoretically possible spill-free assignment.

**API and diagnostics**

Please expose the feature through a supported FlyDSL FFI/object-linking API backed by LLVM AMDGPU semantics. Report fixed bindings, effective clobbers, available preserved registers, live-through assignments, copies/rematerialization, spill/save provenance, final private usage and kernel resource/occupancy constraints. Bind manifests to object hashes and reject unsupported or mismatched contracts.

**Initial scope**

gfx1250 wave32, AMDHSA, direct static calls to leaf assembly functions, full-wave invocation, explicit scalar/register-tuple parameters, no private memory, and no dynamic VGPR-bank changes. A separately launched `.hsaco` is not assumed to be device-callable without adaptation.

**Acceptance**

Validate fixed register parameters and live context after a middle-stage call. A callee that clobbers high registers must either obtain a valid spill-free caller allocation or produce a compile error. Inspect final caller and callee code, not only spill counters. Include negative tests for divergent SGPR inputs, register aliases, late spills, default-ABI save frames, contract/object mismatch, and unsupported execution-state changes.

## 17. 参考资料与证据范围

本 RFC 基于工作区已有实验和本机工具链接口检查；没有声称新接口已经实现，也没有进行新的 GPU 性能测量。

- [当前三种 ASM 接入实现对照](ASM_MONO_INTEGRATION.zh-CN.md)。
- [mono_test00 标准 ABI wrapper 源码](../mono_test00/asm/dq_wrapper.cpp)、[实际 FFI 注册](../mono_test00/mono1250/kernels/dq_ffi.py)。
- [mono_test01 调用点 regmask 修改器](../mono_test01/callsite_regmask.py)。
- [mono_test10 inline asm 调用实现](../mono_test10/mono1250/kernels/dq_inline.py)。
- [HIP/ASM 作为 Mono 调用主体的设计讨论](HIP_ASM_MONO_CALLER_DESIGN.zh-CN.md)。
- [LLVM AMDGPU Usage](https://llvm.org/docs/AMDGPUUsage.html)：calling conventions、非 kernel 函数 ABI、资源和函数属性。与目标工具链版本配套阅读。
- [LLVM Inline Assembler Expressions](https://llvm.org/docs/LangRef.html#inline-assembler-expressions)：固定寄存器、输入输出与 clobber 的现有基础。
- [LLVM MIR Language Reference](https://llvm.org/docs/MIRLangRef.html)：现有 MIR 表示，不代表本 RFC 应以用户修改 MIR 实现。
- [FlyDSL extern.py](https://github.com/ROCm/FlyDSL/blob/main/python/flydsl/expr/extern.py)、[extern_link.py](https://github.com/ROCm/FlyDSL/blob/main/python/flydsl/compiler/extern_link.py)：建议扩展的接口位置；本文实际核对的是本地安装的 FlyDSL 0.4.1 副本，上游路径/内容可能随版本变化。
- 本机 LLVM 源码：`/home/feifei/repo/llvm-project/llvm/lib/Target/AMDGPU/AMDGPUCallingConv.td`、`AMDGPUResourceUsageAnalysis.cpp`，以及 `llvm/docs/AMDGPUUsage.rst`。默认 CSR 与保留寄存器规则必须按实际 target/版本核对，不能将某次实验的编号范围作为通用 ABI。
