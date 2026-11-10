# 需求：AMDGPU“寄存器契约”ASM 片段（Register-Contract ASM Fragment）

**提给：** LLVM AMDGPU 后端（核心需求），以及 FlyDSL（一层很薄的前端接口）。
**目标硬件：** gfx1250（MI455X），wave32，每个 wave 最多 1024 个 VGPR（v256 以上需要 `s_set_vgpr_msb` 寻址）。
**使用方：** ATOM DeepSeek V4.1 mono kernel，计划把 GEMM / attention / MoE 等关键算子替换为手写 ASM。

## 0. 一句话需求

我们希望像 `mono_test00` 那样，把一段手写 ASM 当作“函数”从 FlyDSL 调用，同时满足三点：

1. **零 spill、零 scratch**。做不到时编译报错，不允许静默退化。
2. **由片段指定参数所在的物理寄存器**，例如用 `s[0:1]` 传 workgroup id，用 `v[0:1]` 传 buffer 指针，并且可以使用 v256–v1023。
3. **片段向编译器声明自己占用的寄存器**。调用方据此限制调用点前后的寄存器使用；放不下时把每个调用点缺多少寄存器、是哪些值占用，报告给用户。

今天的 LLVM 和 FlyDSL 都做不到这三点（证据见第 2 节）。我们提出的设计以 **扩展现有 inline asm** 为主，不引入新的调用约定，整体改动集中在 LLVM AMDGPU 后端的几处位置（第 4 节），FlyDSL 只需加一个声明式接口（第 5 节）。

---

## 1. 背景：为什么现有方式不够

| 方式 | 做法 | 问题 |
|---|---|---|
| `mono_test00` | 把 ASM 包成标准 ABI 的 `noinline` 设备函数，编译成 `.bc`，FlyDSL 通过 `ffi + link_extern` 调用 | 形式最优雅，但这是一次真实的函数调用：被改写的 callee-saved VGPR（v40–v45）会被**保存到 scratch**（32 字节/线程，静态 7 条 scratch store）；参数寄存器由调用约定决定，不能指定；需要 `s30:31` 返回地址、`s32` 栈指针和 `s_swap_pc` |
| `mono_test01` | 独立 ASM，加自定义 MIR pass 改调用点的 regmask | 依赖特定 LLVM 提交和 MIR 布局，难以维护 |
| `mono_test10` | 直接在 FlyDSL 里写 inline asm（`.long` + 固定输入 + 完整 clobber 列表） | 没有调用开销，但 v256 以上无法声明、没有 spill 防护、没有报告，状态约定（MSB）也不受保护 |

Mono kernel 的约束让问题更严重：

- 256 个 CTA × 256 线程必须同时驻留，生产检查（`dspark_runtime.check_residency`）要求 scratch 为 0、VGPR spill 为 0。
- 真正的 attention / MoE ASM 会用到 v256–v1023。
- 我们实测，调用点之前 mono 主体真正活跃的 VGPR 只有 1–8 个、SGPR 2–40 个，空间本来是足够的。缺的只是一种**能精确表达这份契约**的机制。

---

## 2. 现状证据（本机 AMD LLVM 23.0.0git，gfx1250，只编译）

复现：`asm_reg_contract_evidence/run.sh`（默认使用 `/app/ATOM/mono_test01/build/llvm-bin`，可用 `LLVM_BIN` 指定其他工具链）。

| 编号 | 输入 | 实际行为 | 违背的需求 |
|---|---|---|---|
| E1 | 输出约束 `"={v300}"` | `error: could not allocate output register for constraint '{v300}'` | 需求 2：高位 VGPR 不能作为接口寄存器 |
| E2a | clobber `~{v300}` | **静默忽略**：`.vgpr_count: 1` | 需求 3：高位 VGPR 占用无法声明 |
| E2b | clobber `~{v[4:200]}` | **静默忽略**：`.vgpr_count: 1`。只有恰好对应一个寄存器元组的写法（如 `v[4:7]`）才生效 | 需求 3：没有区间语法，只能逐个列出（`mono_test00` 列了 78 个） |
| E3a | clobber v0–v255，同时有值跨 asm 活跃 | 编译器把活跃值**放进了 v256/v257**（`.vgpr_count: 258`）。真实片段会写 v256+ 却无法声明（见 E2a），这会导致**静默的数据损坏** | 需求 1、3 |
| E3b | clobber s0–s105 | 静默用 `v_writelane` 做 SGPR spill（`.sgpr_spill_count: 3`）；clobber `s105` 只给 warning | 需求 1 |
| E3c | 同 E3a，看 asm 入口 | 进入 asm 时 VGPR MSB 仍是上一条指令留下的 `dst=1`。如果片段第一条指令写 `v4`，实际写到的是 `v260` | 状态契约（第 3 节 R8） |
| E4 | 同 E3a，加 `"amdgpu-waves-per-eu"="4"`（上限 256 个 VGPR） | **静默 spill 到 scratch**：`private_segment_fixed_size: 12`，2 个 VGPR spill，4 条 scratch 指令，编译成功 | 需求 1 |
| E5 | `noinline` 包装函数（`mono_test00` 的形式），加或不加 `-enable-ipra` | 被调用方都把 v40/v41 存入 scratch（`private_segment_fixed_size: 12`）；参数位置由调用约定决定（`inreg i64` 落到 `s[0:1]`，`i64` 落到 `v[0:1]`，不能指定为 `s24` 或 `v300`）；调用方需要设置 `s32` 并执行 `s_swap_pc_i64` | 需求 1、2 |

另外，FlyDSL 的 `waves_per_eu` hint 只能整体限制 VGPR 上限（例如 4 对应 256 个 VGPR），只会把问题变成 E4 里的 spill。

**结论：**

- **需求 1**：两条路线都可能静默产生 spill 或 scratch，没有“出现即报错”的模式。
- **需求 2**：只有 inline asm 路线能固定低位寄存器；函数调用路线做不到，高位寄存器在两条路线上都做不到。
- **需求 3**：没有可声明的占用区间，也没有逐调用点的报告。

---

## 3. 需求清单

编号 R1–R10，每条都给出验收标准。

### R1 片段寄存器占用声明（footprint）

- 片段能用**区间**声明自己会改写的寄存器：VGPR v0–v1023，SGPR s0–s105，以及特殊状态 `vcc`、`m0`、`scc`、`exec`、`mode`、`vgpr_msb`。
- 只读的输入寄存器不算改写。可以声明为“只读保持”，也可以声明为“输入后被改写”。
- **验收：** `~{v[4:1023]}` 与逐个列出 v4…v1023 的效果完全相同；`.vgpr_count` ≥ 1024。

### R2 接口寄存器固定（pinned operands）

- 输入/输出可以绑定到任意物理寄存器或元组：`{s[0:1]}`、`{s24}`、`{v[0:1]}`、`{v[300:301]}`，包括 v256 以上。
- 绑定到 SGPR 的输入必须是 wave-uniform 的。值可能是 divergent 时，编译器要么自动插入 `readfirstlane`，要么报错。是哪一种由约定决定，但不能静默产生错误代码。
- **验收：** E1 能编译通过，`$0` 就是 v300；进入片段时值正确放在指定寄存器。

### R3 零开销降级（不是函数调用）

- 调用点降级为一条带约束的 `INLINEASM`。不使用 `s_swap_pc`，不用 `s30:31` 和 `s32`，没有栈帧，也不保存 callee-saved 寄存器。
- 片段可以放在单独的 bitcode 里，通过 FlyDSL 的 `link_extern` 链接（保留 `mono_test00` 的工程形态）。链接后必须展开到调用点；无法展开时报错。
- **验收：** 最终 ELF 中没有对片段的 `s_swap_pc`，片段指令字节恰好出现在调用点。

### R4 严格无 spill 模式

- 函数级（可选：调用点级）策略，例如 `"amdgpu-spill-policy"="error"`：
  - 寄存器分配需要 VGPR spill、需要 scratch、或产生非零的 `private_segment_fixed_size` 时，**报错**而不是静默生成。
  - SGPR 写到 VGPR lane 的 spill 单独控制：`"amdgpu-sgpr-lane-spill-max"="N"`。Mono 48 行 K2 目前允许不超过 32 个，其余 kernel 为 0。
- **验收：** E4 在这个策略下编译失败，报错信息给出 spill 的值以及它跨越的 asm 调用点。

### R5 调用点预算报告

- 对每个片段调用点，输出机器可读的报告（YAML 优化 remark 或 JSON），内容包括：
  - 跨调用点活跃的值：个数、位宽、分配到的物理寄存器、对应的 IR 值名或调试位置（`DebugLoc`），以及是否可重算（rematerializable）。
  - 预算：可用寄存器集合（片段占用的补集），以及已使用数和剩余数。
  - 失败时：缺多少个寄存器，是哪些值占用的。
- 同时提供**寄存器分配前的估算**，让 FlyDSL 在完整 codegen 之前就能给出提示。
- **验收：** 能复现我们手写 `liveness.py` 得到的结果（例如 12 行 K2 的 att PV 调用点：VGPR 3 个、SGPR 35 个），并且能直接从报告看出“v4 以上可用”。

### R6 调用方遵守占用

- 跨调用点活跃的值只能放在片段占用之外的寄存器中，包括 v256 以上（修复 E3a）。
- 空间不够时，允许编译器在调用点之后**重算**可以重算的值（常量、`workitem.id`、从 LDS 或 kernarg 重新加载的值），但不能 spill。
- **验收：** E3a 中的活跃值不会被分配到片段声明占用的任何寄存器上。

### R7 资源统计与驻留检查

- kernel 的 `.vgpr_count` 和 `.sgpr_count` 取调用方使用量与片段最高寄存器两者中的较大值，包括 v256 以上，并按 gfx1250 的分配粒度取整。
- 可选：声明驻留目标（例如“每个 CU 至少 1 个 256 线程的 CTA”），无法满足时报错。
- **验收：** 片段声明占用 v1023 时 `.vgpr_count` = 1024；与驻留目标冲突时编译报错，而不是到运行时才发现 kernel 无法启动。

### R8 机器状态契约

- **VGPR MSB：** 进入片段前，编译器保证 MSB 为声明值（默认 0，必要时插入 `s_set_vgpr_msb 0`）；退出后按声明值继续跟踪（默认“已恢复为 0”，也可以声明为“未知”，此时由编译器重新设置）。这一条修复 E3c。
- **EXEC：** 可以声明“要求整个 wave 都活跃（full EXEC）”。编译器无法证明时报错，或在调试模式下插入检查。
- **MODE / 等待计数器：** 可以声明片段退出时 MODE 已恢复，`loadcnt`/`storecnt`/`dscnt`/`kmcnt` 已清空（默认）；也可以声明为“未清空”，由编译器在使用相关结果前插入等待。
- **其他：** 片段视为 `convergent`；不得包含 `s_endpgm` 或 `s_setpc`（可以在审计工具中检查）。

### R9 非法声明一律报错

- 寄存器名未知或超出目标范围（今天 E2a、E2b 是静默忽略）→ 报错。
- clobber 保留寄存器（`s32`、`s105` 等，今天只是 warning）→ 在契约模式下报错。
- 不能满足的接口约束（今天的 E1）→ 报错，并说明原因（例如“v300 已被片段占用”）。

### R10 工具支持（非阻塞）

- 提供从 `.s` 或 `.co` 自动推导片段占用、生成清单的工具（类似 `mono_test00/asm/audit.py` 和 `prepare.py` 的写集合分析）。清单与源码中的声明不一致时报错。

---

## 4. LLVM 侧设计

### 4.1 IR 形式：扩展 inline asm，而不是新增调用约定

片段在 IR 中仍然是一次 `call ... asm sideeffect`。约束串与今天兼容，只扩展语义：

```llvm
call void asm sideeffect convergent "...片段指令或 .long ...",
    "{s[0:1]},{v[0:1]},{s24},~{s[2:23]},~{s[25:29]},~{v[4:1023]},~{scc},~{memory}"
    (i64 %wg_id, i64 %buf, i32 %wave), !amdgpu.asm.contract !0

!0 = !{!"vgpr_msb.entry", i32 0, !"vgpr_msb.exit", i32 0,
       !"exec", !"full", !"waitcnt.exit", !"drained", !"mode.exit", !"restored"}
```

- `{v[a:b]}` 作为**操作数**时，仍然表示宽度为 b-a+1 的元组，但需要支持 a、b ≥ 256（修复 E1）。
- `~{v[a:b]}` 作为 **clobber** 时，表示寄存器集合 {va…vb}，不要求是合法的元组宽度。clobber 一个元组本来就等于 clobber 其中每个寄存器，所以这对已有代码完全向后兼容，只是让今天被静默忽略的写法生效（修复 E2b）。SGPR 同理。
- `!amdgpu.asm.contract` 元数据承载 R8 的状态约定。没有这个元数据时，行为与今天相同。

**为什么不选新的调用约定：** 函数调用需要返回地址、栈指针和 callee-saved 寄存器，这正是 E5 中 scratch 的来源。即使用 IPRA 收窄调用方的 regmask，被调用方仍然会保存 callee-saved 寄存器（E5 实测）。`amdgpu_cs_chain` 不返回，不适合 stage 调用。inline asm 已经具备“精确 clobber、无栈帧、可固定寄存器”的语义，缺的只是表达范围、错误处理和状态约定。

### 4.2 打包为 bitcode（保留 `mono_test00` 的形态）

片段作为一个函数放在 `.bc` 中，函数体只有一条上述 inline asm：

```llvm
define internal void @mono_att_pv_frag(i64 %wg_id, i64 %buf, i32 %wave)
    #0 {
  call void asm sideeffect convergent "...", "{s[0:1]},{v[0:1]},{s24},~{v[4:1023]},..."(...)
  ret void
}
attributes #0 = { alwaysinline convergent "amdgpu-asm-fragment" }
```

- 新增函数属性 `"amdgpu-asm-fragment"`。IR verifier 检查函数体只有一条 inline asm 加 `ret`，以及参数的简单转换。如果到 codegen 时该函数仍未被展开（例如被取地址或间接调用），后端**报错**。
- 这样 FlyDSL 的 `link_extern` 路径完全不用改：链接、`alwaysinline` 展开、优化，最终调用点就是一条 `INLINEASM`。

### 4.3 后端改动点

| 改动 | 位置（AMDGPU 后端） | 对应需求 |
|---|---|---|
| 解析 `{vN}` 和 `{v[a:b]}` 时支持 N ≥ 256，并在 clobber 中支持任意区间；未知寄存器名报错 | `SITargetLowering::getRegForInlineAsmConstraint`，以及通用的 clobber 解析和诊断 | R1、R2、R9 |
| 寄存器分配遵守包括高位在内的 clobber regmask | 修复 E2a 之后自然满足；需要确认 `INLINEASM` 的 regmask 覆盖了 v256–v1023 | R6 |
| 严格无 spill 策略：在 spill 槽创建或 SGPR lane spill 时检查函数属性，违反时发出 `DiagnosticInfoResourceLimit` 类错误，附上虚拟寄存器、IR 值和最近的片段调用点 | `SIRegisterInfo` / `SIFrameLowering` 的 spill 路径，以及寄存器分配后对 `SIMachineFunctionInfo` 的检查 | R4 |
| 调用点报告 pass：寄存器分配前基于 `LiveIntervals` 在 asm 的 `SlotIndex` 处统计活跃值（忽略 `undef` 操作数和未定义的子 lane），寄存器分配后输出物理分配结果；以 `OptimizationRemarkAnalysis` 形式输出（`-pass-remarks-analysis=amdgpu-asm-fragment`，可配合 `-pass-remarks-output` 生成 YAML） | 新增 `AMDGPUAsmFragmentReport` | R5 |
| MSB 处理：片段入口按契约设置 MSB；出口按契约更新跟踪状态，没有契约时保守地视为“未知” | `AMDGPULowerVGPREncoding`（`s_set_vgpr_msb` 插入 pass） | R8 |
| 资源统计包含 asm 显式和隐式定义的高位寄存器，可选驻留目标检查 | `AMDGPUResourceUsageAnalysis` 及 metadata 输出 | R7 |
| 契约模式下 clobber 保留寄存器报错 | 现有 “reserved registers” warning 的位置 | R9 |
| waitcnt 和 EXEC：按契约对 asm 后的等待计数器作出假设；可选插入 EXEC 检查 | `SIInsertWaitcnts`，以及调试模式下的 EXEC 检查 | R8 |

### 4.4 报告格式示例（R5）

```yaml
--- !Analysis
Pass:     amdgpu-asm-fragment
Name:     FragmentBudget
DebugLoc: { File: dspark_dynamic_index_down.py, Line: 206 }
Function: dspark_dynamic_index_down_k2
Args:
  - Fragment: mono_att_pv_frag
  - Footprint: 'v[4:1023], s[2:23], s[25:29], scc'
  - Pinned:    's[0:1]=%wg_id, v[0:1]=%buf, s24=%wave'
  - BudgetVGPR: 'v[0:3]'     # 片段占用的补集；v0:1 是只读输入，内容在调用后保持
  - LiveAcrossVGPR: 3
  - BudgetSGPR: 's[0:1], s24, s[30:105] 中的非保留寄存器'
  - LiveAcrossSGPR: 35
  - Values:
      - { name: '%buf',      bits: 64, reg: 'v[0:1]', remat: false }
      - { name: '%row_base', bits: 32, reg: v2,       remat: false }
      - ...
  - Status: OK               # 或 'ERROR: need 2 more VGPR (no spill allowed)'
```

---

## 5. FlyDSL 侧设计

### 5.1 声明式接口

```python
from flydsl.expr.asm import AsmFragment, regs

att_pv = AsmFragment(
    name="mono_att_pv",
    code=AsmFragment.words("build/asm/att_pv.inline.words.inc"),  # 也支持 .s 文本或 .co
    inputs={"wg_id": "s[0:1]", "buf": "v[0:1]", "wave": "s24"},
    outputs={},                                   # 例如 {"acc": "v[300:303]"}
    clobbers=regs("s2-s23", "s25-s29", "v4-v1023", "scc", "memory"),
    state=dict(exec="full", vgpr_msb=(0, 0), waitcnt="drained", mode="restored"),
    manifest="build/asm/att_pv.footprint.json",   # 可选：由 R10 工具生成，校验一致
)

# 在 mono kernel 主体中调用：
att_pv(wg_id=wg, buf=ptr, wave=wave_id)
```

- 生成的 IR 就是第 4.1 节的 inline asm；`att_pv.to_bitcode(path)` 生成第 4.2 节的 `.bc`，可以直接交给已有的 `link_extern`，与 `mono_test00` 一样。
- `inputs` 和 `outputs` 的键就是 Python 侧的参数名，不再需要 `mono_test00` 中“ABI 参数到片段寄存器”的 C++ 桥接层。

### 5.2 编译选项与报告

```python
compile_hints = {
    "spill_policy": "error",          # R4
    "sgpr_lane_spill_max": 0,         # 48 行 K2 可设为 32
    "residency": {"ctas_per_cu": 1, "threads": 256},   # R7
    "asm_fragment_report": "build/k2/asm_callsites.json",  # R5
}
```

- FlyDSL 把这些映射为函数属性和 `-pass-remarks-*` 选项，并把 YAML remark 整理成 `asm_callsites.json`。
- **codegen 前提示：** FlyDSL 自己就知道每个调用点的片段占用，可以先打印“这个调用点之前最多可以保留 N 个 VGPR、M 个 SGPR”。LLVM 的分配前估算到位后，再给出实际活跃值的对照。
- 编译失败时，FlyDSL 显示 LLVM 的诊断，并指向 Python 源码行（依赖 `DebugLoc`）。

### 5.3 用户在 mono 中的写法和效果

以 12 行 K2 的 att PV 为例：我们测得调用点有 3 个 VGPR、35 个 SGPR 跨调用点活跃。

- **片段占用 `v[4:1023]`：** 调用方有 v0–v3。其中 v0:1 是只读输入可以保持，3 个活跃值里放不下的部分由编译器在调用后重算，或者由 mono 主体通过已有的 `late_meta` / `fresh()` 机制从 LDS 重新加载。都做不到时，**编译报错**，并在报告中列出是哪几个值。
- **SGPR 侧：** 35 个活跃值放在片段未占用的 s30–s105（除保留寄存器外）。片段占用更多 SGPR 时，同样会在报告中给出“缺多少”。

---

## 6. 验收测试（建议加入 LLVM lit 测试）

| 测试 | 输入 | 期望 |
|---|---|---|
| T1 | E1 | 编译通过，`$0` = v300，前后有正确的 `s_set_vgpr_msb` |
| T2 | E2a / E2b | `.vgpr_count` 分别为 301 和 201；对 `~{v1024}` 报错 |
| T3 | E3a，clobber 改为 `~{v[0:1023]}` | 活跃值不在 v0–v1023 中 → 编译报错（无处可放），而不是静默分配到 v256 |
| T4 | E3a，clobber 改为 `~{v[4:1023]}` | 活跃值被分配到 v0–v3 中 |
| T5 | E4 加 `"amdgpu-spill-policy"="error"` | 编译报错，诊断给出 spill 的值和 asm 调用点 |
| T6 | E3b 加 `"amdgpu-sgpr-lane-spill-max"="0"` | 编译报错；设为 `"3"` 时通过 |
| T7 | E3c 加 `!amdgpu.asm.contract`（`vgpr_msb.entry` = 0） | asm 前插入 `s_set_vgpr_msb 0`（或可以证明当前状态已经是 0） |
| T8 | 4.2 节的 bitcode 片段，被 `link_extern` 链接 | 最终 ELF 中没有 `s_swap_pc`，片段字节出现在调用点；被取地址时报错 |
| T9 | `-pass-remarks-analysis=amdgpu-asm-fragment` | 输出 4.4 节格式的 remark，活跃值数量与 `liveness.py` 的结果一致 |

---

## 7. 分阶段交付建议

| 阶段 | 内容 | 价值 |
|---|---|---|
| P1 | 高位 VGPR 约束和 clobber、区间 clobber、未知寄存器名报错（R1、R2、R9）；MSB 入口归零（R8 的 MSB 部分） | 修复今天就存在的静默损坏风险（E2a、E3a、E3c），改动小，最容易进上游 |
| P2 | 严格无 spill 策略和 SGPR lane spill 上限（R4），资源统计（R7） | 满足 mono 的驻留规则，不再到运行时才发现问题 |
| P3 | 调用点报告 pass（R5） | 满足“调用方据此限制并报告给用户” |
| P4 | FlyDSL `AsmFragment` 接口、bitcode 打包、`"amdgpu-asm-fragment"` 属性（R3、第 5 节） | 达到 `mono_test00` 的使用体验 |
| P5（可选） | 自动推导片段占用的工具（R10）；以及只提供已汇编对象、没有 IR 时的链接期方案 | 降低维护成本 |

P1–P3 是 LLVM 后端的通用能力，对所有在 AMDGPU 上写 inline asm 的项目都有用，不只服务 mono。

---

## 8. 曾考虑但不推荐的替代方案

- **标准 ABI 包装函数 + IPRA：** IPRA 可以让调用方只保存被调用方实际改写的寄存器，但被调用方仍要保存 callee-saved 寄存器（E5 实测有 scratch），参数位置也仍然由调用约定决定。
- **新增“无 callee-saved”的调用约定：** 可以去掉保存，但仍然需要返回地址、`s_swap_pc` 和栈指针，而且要新增参数到物理寄存器的属性，改动面比扩展 inline asm 大。
- **用 `waves_per_eu` / `amdgpu-num-vgpr` 限制整体 VGPR：** 只能限制总量，表达不了“调用点两侧不同的占用”，结果就是 E4 中的 spill。
- **自定义 MIR pass 改 regmask（`mono_test01`）：** 能工作，但依赖内部数据结构，不可移植，也无法上游。
- **事后扫描最终 ELF 检查 spill：** 只能事后发现，不能指导调用方，也给不出原因。

---

## 9. 相关文件

- 证据与复现脚本：[asm_reg_contract_evidence/](asm_reg_contract_evidence/)（`run.sh`，`e1`–`e5` 的 `.ll` 文件）
- 现有接入方案对比：[ASM_MONO_INTEGRATION.zh-CN.md](ASM_MONO_INTEGRATION.zh-CN.md)、[ASM_FLYDSL_MONO_INTEGRATION_OPTIONS.zh-CN.md](ASM_FLYDSL_MONO_INTEGRATION_OPTIONS.zh-CN.md)
- `mono_test00` 的包装器与 clobber 声明：`../mono_test00/asm/dq_convert_inline.h`、`../mono_test00/asm/dq_wrapper.cpp`
- FlyDSL 现有接口：`flydsl/compiler/extern_link.py`（`link_extern`）、`flydsl/expr/extern`（`ffi`）
