# 需求：AMDGPU“寄存器契约函数”——以 mono_test00 的形态接入 ASM

**提给：** LLVM AMDGPU 后端（核心），以及 FlyDSL（调用侧和打包工具）。
**目标硬件：** gfx1250（MI455X），wave32，每个 wave 最多 1024 个 VGPR（v256 以上需要 `s_set_vgpr_msb` 寻址）。
**使用方：** ATOM DeepSeek V4.1 mono kernel，计划把 GEMM / attention / MoE 等关键算子替换为手写 ASM，后续还会不断接入新的 ASM。

> **实现状态（2026-11）：** P1–P5 已实现，并在 gfx1250 上用 `mono_test_contract` 端到端验证（scratch 0、无 spill、无 `s_swap_pc`，A/B 逐位一致）。详见 [ASM_REG_CONTRACT_IMPLEMENTATION.zh-CN.md](ASM_REG_CONTRACT_IMPLEMENTATION.zh-CN.md)。与本文设计的主要差异：
>
> - 契约用函数和参数属性表达，**没有新增 `amdgpu_contract` 调用约定**（5.1 节）；
> - 只实现了 `inline` 降级，`call` 降级和 HIP 属性留在 P6；
> - 打包工具是 `amdgpu-asm-footprint` 加 `python -m flydsl.compiler.asm_contract pack`，不是 `amdgpu-asm-pack`；
> - spill 策略和上限通过 llc 选项（`spill_hints()`）传入，不是第 6.2 节的 compile hint 键；
> - 返回值绑定、LDS 和 waitcnt 契约、寄存器分配前的估算尚未实现。

## 0. 一句话需求

保留 `mono_test00` 的接入形态：ASM 由提供方**单独打包成 bitcode 里的一个函数**，FlyDSL 通过 `ffi + link_extern` **像调用函数一样调用它**，mono 主体里不写任何 asm。在此基础上满足三点：

1. **零 spill、零 scratch**。做不到时编译报错，不允许静默退化。
2. **由 ASM 函数自己指定参数所在的物理寄存器**，例如 `s[0:1]` 传 workgroup id、`v[0:1]` 传 buffer 指针，并且可以使用 v256 以上的寄存器。
3. **ASM 函数向编译器声明自己占用的寄存器**。调用方据此限制调用点前后的寄存器使用；放不下时把每个调用点缺多少寄存器、是哪些值占用，报告给用户。

为此我们提出一个新的函数种类：**寄存器契约函数（register-contract function）**。它的“调用约定”不是固定的 ABI，而是函数自己声明的一份契约：参数在哪些寄存器、会改写哪些寄存器，以及进入和退出时的机器状态。编译器在调用点严格按契约处理，没有保存/恢复，没有栈帧。

**为什么坚持函数形态：** 接入一个新 ASM 只需要“一个 `.s` 加一份清单”，打包工具生成 `.bc`，调用方写一行 `ffi` 声明。mono 主体不需要知道 ASM 的寄存器细节，契约本身就存放在 bitcode 中，随函数一起分发。相比之下，`mono_test10` 那种直接 inline asm 的方式，每接一个 ASM 都要在调用方重复写出全部固定输入和 clobber，既容易出错，也不能复用。

---

## 1. 背景：mono_test00 好在哪里，差在哪里

`mono_test00` 的链路：

```text
dq_convert.inline.s ──汇编──> .words.inc ──#include──> dq_wrapper.cpp（标准 ABI 的 noinline 函数）
      ──clang -emit-llvm──> dq_wrapper.bc ──FlyDSL link_extern + ffi──> mono kernel 中的 llvm.call
```

**好的地方：**
- ASM 与 mono 主体完全解耦：提供方交付 `.bc`，调用方一行 `link_extern(ffi(...), bitcode_path=...)`。
- 契约（固定输入和 clobber）写在 bitcode 里，调用方不用重复。

**差的地方（第 2 节有实测）：**
- **这是一次真实的标准 ABI 调用。** 被改写的 callee-saved VGPR（v40–v45）会被保存到 scratch：32 字节/线程，静态 7 条 scratch store。调用方还要准备 `s32` 栈指针和 `s30:31` 返回地址，执行 `s_swap_pc`。
- **参数位置由标准调用约定决定**（`inreg i64` 落到 `s[0:1]`，`i64` 落到 `v[0:1]`），不能指定为 `s24` 或 `v300`。所以 wrapper 内部还要用一段 inline asm 把参数“桥接”到 ASM 需要的寄存器。
- **调用方看不到 ASM 的真实占用。** 标准调用约定假设被调用方可能改写所有 caller-saved 寄存器，调用方只好把跨调用点的值保存到 callee-saved 寄存器或 spill 掉。IPRA 也解决不了这个问题（见 E5）。
- **v256 以上的寄存器无法声明**（见 E2a），而编译器自己却会使用它们（见 E3a），这里有静默数据损坏的风险。

Mono kernel 的约束让这些问题无法回避：

- 256 个 CTA × 256 线程必须同时驻留，生产检查（`dspark_runtime.check_residency`）要求 scratch 为 0、VGPR spill 为 0。
- 真正的 attention / MoE ASM 会用到 v256 以上的寄存器；按 256 线程/CTA 每 CU 驻留 1 个 CTA 计算，上限是 v511。
- 我们实测，调用点之前 mono 主体真正活跃的 VGPR 只有 1–8 个、SGPR 2–40 个，空间本来是足够的。缺的只是一种**能精确表达契约的函数调用**。

---

## 2. 现状证据（本机 AMD LLVM 23.0.0git，gfx1250，只编译）

复现：`asm_reg_contract_evidence/run.sh`（默认使用 `/app/ATOM/mono_test01/build/llvm-bin`，可用 `LLVM_BIN` 指定其他工具链）。

| 编号 | 输入 | 实际行为 | 违背的需求 |
|---|---|---|---|
| E5 | `noinline` 包装函数（`mono_test00` 的形态），加或不加 `-enable-ipra` | 被调用方都把 v40/v41 存入 scratch（`private_segment_fixed_size: 12`）；参数位置由调用约定决定；调用方设置 `s32` 并执行 `s_swap_pc_i64` | 需求 1、2 |
| E1 | 输出约束 `"={v300}"` | `error: could not allocate output register for constraint '{v300}'` | 需求 2：高位 VGPR 不能作为接口寄存器 |
| E2a | clobber `~{v300}` | **静默忽略**：`.vgpr_count: 1` | 需求 3：高位 VGPR 占用无法声明 |
| E2b | clobber `~{v[4:200]}` | **静默忽略**：`.vgpr_count: 1`。只有恰好对应一个寄存器元组的写法（如 `v[4:7]`）才生效 | 需求 3：没有区间语法，`mono_test00` 只能逐个列出 78 个 |
| E3a | clobber v0–v255，同时有值跨调用点活跃 | 编译器把活跃值**放进了 v256/v257**（`.vgpr_count: 258`）。真实 ASM 会写 v256 以上却无法声明（E2a），这会导致**静默的数据损坏** | 需求 1、3 |
| E3b | clobber s0–s105 | 静默用 `v_writelane` 做 SGPR spill（`.sgpr_spill_count: 3`）；clobber `s105` 只给 warning | 需求 1 |
| E3c | 同 E3a，看 asm 入口 | 进入 asm 时 VGPR MSB 仍是上一条指令留下的 `dst=1`。如果 ASM 第一条指令写 `v4`，实际写到的是 `v260`。根因：`AMDGPULowerVGPREncoding.cpp:591` 只在 asm **读** VGPR 时才把 MSB 归零 | 状态契约（R8） |
| E4 | 同 E3a，加 `"amdgpu-waves-per-eu"="4"`（上限 256 个 VGPR） | **静默 spill 到 scratch**：`private_segment_fixed_size: 12`，2 个 VGPR spill，编译成功 | 需求 1 |
| E6 | gfx1250 汇编器处理 `v_mov_b32 v300, 1` | `error: register index is out of range`。高位 VGPR 只能用 MSB 加低位编号书写，不能直接出现在 asm 文本中 | 打包工具必须处理（R10） |
| E7 | FlyDSL 0.4.1 的外部 LLVM 编译（`FLYDSL_COMPILE_LLVM_DIR`） | 遇到 `link_extern` 的 kernel 直接报错（`jit_function.py:829`、`:1531`） | 用修改后的 LLVM 验证本方案时，FlyDSL 也要改（F3） |

源码中的根因：

- **E1 / E2a：** `SITargetLowering::getRegForInlineAsmConstraint` 把 `{vN}` 物理寄存器约束固定解析到 `VGPR_32_Lo256RegClass`。
- **E2 静默忽略：** `SelectionDAGBuilder.cpp:10605` 在 clobber 解析失败时直接丢弃，不报错。

---

## 3. 需求清单

R1–R10 是 LLVM 侧的需求，F1–F4 是 FlyDSL 和工具侧的需求。每条都给出验收标准。

### R1 契约声明随函数一起保存在 bitcode 中

一个契约函数声明以下内容，作为 IR 函数和参数的属性，属于函数类型的一部分，随 `.bc` 一起分发：

- **参数寄存器（R2）。**
- **改写集合（footprint）：** 用区间声明，覆盖 VGPR v0–v1023、SGPR s0–s105，以及 `vcc`、`m0`、`scc`、`exec`、`mode`；默认不包括特殊寄存器。
- **LDS 占用：** 偏移和大小，用于 kernel 的 LDS 分配和冲突检查。
- **机器状态约定（R8）。**

**验收：** 只链接 `.bc` 而不改调用方源码，调用方就能得到完整的契约。

### R2 参数固定到物理寄存器

- 每个参数可以绑定到任意物理寄存器或寄存器元组，例如 `s[0:1]`、`s24`、`v[0:1]`、`v[300:301]`，包括 v256 以上。
- 绑定到 SGPR 的参数必须是 wave-uniform 的。值可能是 divergent 时，调用方编译器在调用前插入 `readfirstlane`，或者报错，由契约声明选择哪一种。
- 返回值同样可以绑定到物理寄存器，例如累加结果放在 `v[300:303]`。
- 参数默认是“只读保持”：调用后寄存器中的值不变，调用方可以继续使用。也可以声明为“输入后被改写”。
- **验收：** 进入 ASM 时每个参数正好在声明的寄存器中；调用方生成的代码只有把参数搬到指定寄存器的 `mov`，没有其他内容。

### R3 零开销调用：没有保存、没有栈帧

- 契约函数没有 callee-saved 寄存器：契约之外的寄存器，ASM 本来就不碰。被调用方不生成 prologue/epilogue，也不保存任何寄存器。
- 调用方不需要栈指针 `s32`、scratch 描述符或 scratch 初始化。kernel 不能因为存在这个调用就打开 private segment。
- 支持两种降级方式，声明一致，由契约指定或编译器选择：
  - **`inline`（默认）：** 链接后把函数体展开到调用点，没有 `s_swap_pc`，也不用返回地址寄存器。
  - **`call`：** 保留一份函数体，用 `s_swap_pc` 调用，返回地址放在契约声明的寄存器对中（默认 `s[30:31]`，计入改写集合）。适合同一个 ASM 被多处调用、需要控制代码体积的情况。
- **验收：** 最终 ELF 中 `private_segment_fixed_size` 为 0，没有 scratch 指令；`inline` 方式下调用点没有 `s_swap_pc`。

### R4 严格无 spill 模式

- kernel 级策略，例如 `"amdgpu-spill-policy"="error"`：
  - 需要 VGPR spill、需要 scratch，或 `private_segment_fixed_size` 不为 0 时，**报错**而不是静默生成。
  - SGPR 写到 VGPR lane 的 spill 单独设上限：`"amdgpu-sgpr-lane-spill-max"="N"`。mono 48 行 K2 目前允许不超过 32 个，其余 kernel 为 0。
- **验收：** E4 在这个策略下编译失败，报错信息给出 spill 的值和最近的契约调用点。

### R5 调用点预算报告

- 对每个契约调用点，输出机器可读的报告（YAML 优化 remark，另外可以直接写成 JSON 文件），内容包括：
  - 跨调用点活跃的值：个数、32 位单位的宽度、分配到的物理寄存器、对应的调试位置（`DebugLoc`），以及是否可重算。
  - 预算：改写集合的补集，以及已使用数和剩余数。
  - 失败时：缺多少个寄存器，是哪些值占用的。
- 同时提供寄存器分配前的估算，让 FlyDSL 在完整 codegen 之前就能提示用户。
- **验收：** 能复现我们手写 `liveness.py` 的结果（例如 12 行 K2 的 att PV 调用点：VGPR 3 个、SGPR 35 个）。

### R6 调用方遵守契约

- 调用点的 regmask 恰好等于契约的改写集合（`call` 方式还要加上返回地址寄存器）。跨调用点活跃的值只能放在这个集合之外，包括 v256 以上（修复 E3a）。
- 空间不够时，允许编译器在调用后**重算**可以重算的值（常量、`workitem.id`、从 LDS 或 kernarg 重新加载的值），但不能 spill。
- **验收：** E3a 中的活跃值不会被分配到改写集合中的任何寄存器上。

### R7 资源统计与驻留检查

- kernel 的 `.vgpr_count`、`.sgpr_count` 和 LDS 大小，取调用方使用量与所有契约函数声明中的较大值，包括 v256 以上，并按 gfx1250 的分配粒度取整。
- 契约改写集合超出 kernel 允许的 VGPR 上限（由 `amdgpu-flat-work-group-size`、`amdgpu-waves-per-eu` 推导）时，**编译期报错**。例如 256 线程/CTA、每 CU 1 个 CTA 时上限是 512，契约声明了 v600 就要报错。
- **验收：** 契约声明 v[4:511] 时 `.vgpr_count` = 512；声明 v[4:600] 并要求每 CU 1 个 CTA 时编译失败。

### R8 机器状态契约

- **VGPR MSB：** 调用方保证进入时 MSB 为声明值（默认 0，必要时插入 `s_set_vgpr_msb 0`）；退出后按声明值继续跟踪（默认“已恢复为 0”）。这一条修复 E3c。
- **EXEC：** 可以声明“要求整个 wave 都活跃（full EXEC）”。调用方无法证明时报错，或在调试模式下插入检查。
- **MODE / 等待计数器：** 默认 ASM 退出时 MODE 已恢复，`loadcnt`/`storecnt`/`dscnt`/`kmcnt` 已清空；也可以声明为“未清空”，由调用方在使用相关内存前插入等待。
- **其他：** 契约函数视为 `convergent`，内存效果按 `memory` 处理。函数体内不得出现 `s_endpgm`；`inline` 方式下也不得出现 `s_setpc`，由 R10 的工具检查。

### R9 非法契约一律报错

- 寄存器名未知或超出目标范围（今天 E2a、E2b 是静默忽略）→ 报错。
- 改写或绑定保留寄存器（`s32`、`s105` 等，今天只给 warning）→ 报错。
- 参数绑定之间、或参数绑定与返回地址寄存器重叠 → 报错。
- 函数体除了契约内容还有其他代码（`inline` 方式），或者在 `inline` 方式下被取地址、被间接调用 → 报错。
- **验收：** 每一种情况都有对应的 lit 测试，并输出可读的诊断。

### R10 打包工具（ASM → 契约函数 `.bc`）

- 输入 `.s`（或 `.co` 中的一个符号）加一份清单（格式见 5.1 节），输出契约函数的 `.bc`。
- 工具自动分析 ASM 的实际写集合，与清单中的改写集合对比，**不一致时报错**。也可以选择根据写集合自动生成改写集合。这部分逻辑与 `mono_test00/asm/audit.py`、`prepare.py` 相同。
- 处理 E6：ASM 以已编码的机器字（`.long`）嵌入函数体，所以 v256 以上的寄存器不需要出现在文本中。工具同时检查 MSB 在退出前已经恢复。
- 工具可以放在 LLVM 中（例如 `llvm-mc` 的一个模式，或单独的 `amdgpu-asm-pack`），也可以放在 FlyDSL 中，二者实现同一套清单格式即可。

### F1–F4 FlyDSL 侧

- **F1 声明：** `ffi` 和 `link_extern` 支持契约函数。调用方不重复写寄存器信息，而是从 `.bc` 读取契约。
- **F2 编译选项：** 提供 `spill_policy`、`sgpr_lane_spill_max`、驻留目标和报告路径等 compile hint，映射到 R4、R5、R7。
- **F3 外部 LLVM 支持 `link_extern`：** 修复 E7，否则无法用修改后的 LLVM 验证本方案。
- **F4 报告呈现：** 把 R5 的报告与 Python 源码行对应起来；编译失败时直接指出是哪一行的调用、缺几个寄存器。

---

## 4. 用户视角：接入一个新 ASM 需要做什么

### 4.1 ASM 提供方：一份 `.s` 加一份清单

```yaml
# att_pv.contract.yaml
name: mono_att_pv
target: gfx1250
wavefront: 32
lowering: inline                 # 或 call
params:
  - { name: wg_id, type: u64,        reg: "s[0:1]", uniform: true }
  - { name: buf,   type: ptr_global, reg: "v[0:1]" }
  - { name: wave,  type: u32,        reg: "s24",    uniform: true }
returns: []                      # 例如 [{ name: acc, type: v4f32, reg: "v[300:303]" }]
clobbers: ["s[2:23]", "s[25:29]", "v[4:511]", scc, vcc]
lds: { offset: 0, size: 32768 }
state:
  exec: full
  vgpr_msb: { entry: 0, exit: 0 }
  waitcnt_exit: drained
  mode_exit: restored
```

```bash
amdgpu-asm-pack att_pv.s --contract att_pv.contract.yaml -o att_pv.bc   # R10
```

工具会检查 ASM 的实际写集合确实落在 `clobbers` 内、没有碰保留寄存器、退出前恢复了 MSB 和 MODE。不满足时直接报错，而不是等到 GPU 上出现错误结果。

### 4.2 Mono 调用方：一行声明，一行调用

```python
att_pv = link_extern(ffi_contract("mono_att_pv"), bitcode_path="build/asm/att_pv.bc")

# 在 mono kernel 主体中：
att_pv(wg_id=wg, buf=ptr, wave=wave_id)
```

- 参数名、类型和寄存器都从 `.bc` 中读取，调用方不重复写。
- 编译时，FlyDSL 对每个调用点给出类似下面的提示：

```text
dspark_dynamic_index_down.py:206  mono_att_pv
  可保留: VGPR v0-v3（4 个，其中 v0:1 为只读参数 buf）  SGPR s0:1, s24, s30-s104（非保留）
  实际活跃: VGPR 3 / SGPR 35   -> OK
```

- 放不下时编译报错，例如“需要再多 2 个 VGPR；`%row_base`（v2）和 `%tok`（v3）跨越了调用点”。用户据此在调用后重算这些值，或者从 LDS 重新加载（mono 已有的 `late_meta` / `fresh()` 机制）。

---

## 5. LLVM 侧设计

### 5.1 IR 表示

新增调用约定 `amdgpu_contract`，加上函数属性和参数属性：

```llvm
define amdgpu_contract void @mono_att_pv(
    i64 inreg "amdgpu-reg"="s[0:1]" %wg_id,
    ptr addrspace(1) "amdgpu-reg"="v[0:1]" %buf,
    i32 inreg "amdgpu-reg"="s24" %wave) #0 {
  call void asm sideeffect convergent "<.long 机器字>",
      "{s[0:1]},{v[0:1]},{s24},~{s[2:23]},~{s[25:29]},~{v[4:511]},~{scc},~{vcc},~{memory}"
      (i64 %wg_id, ptr addrspace(1) %buf, i32 %wave)
  ret void
}

attributes #0 = { convergent
  "amdgpu-contract-clobber"="s[2:23],s[25:29],v[4:511],scc,vcc"
  "amdgpu-contract-lds"="0,32768"
  "amdgpu-contract-state"="exec=full,vgpr_msb.entry=0,vgpr_msb.exit=0,waitcnt.exit=drained,mode.exit=restored"
  "amdgpu-contract-lowering"="inline" }
```

- **函数属性**是契约的唯一来源。函数体中 inline asm 的约束由打包工具根据属性生成，IR verifier 检查两者一致：asm 的 clobber 必须是 `amdgpu-contract-clobber` 的子集，asm 的输入必须正好对应各参数的 `amdgpu-reg`。
- **调用点**就是普通的 `call amdgpu_contract void @mono_att_pv(...)`。FlyDSL 的 `ffi` 只需要生成这种调用约定。参数属性来自声明，调用方不重复。
- 选新调用约定而不是只加属性，是为了让“这不是标准 ABI”在类型上显式可见。这样标准调用约定的假设（callee-saved 集合、栈、`s30:31`）不会被误用，跨模块调用也会被 verifier 检查。

### 5.2 降级

**`inline` 方式（默认）：**

1. 链接后，在 IR 层把调用点展开（与 `alwaysinline` 相同的机制，但仅限 `amdgpu_contract`，并且是强制的）。展开后调用点就是一条带固定输入和完整 clobber 的 inline asm，后端复用 inline asm 的寄存器分配。
2. 展开前检查 R9：不允许取地址、间接调用或递归；函数体必须符合 5.1 节的形式。
3. 展开时保留调用点的 `DebugLoc`，并在 inline asm 上附加 `!amdgpu.contract` 元数据（契约名、状态约定），供 R5 的报告 pass 和 R8 的 MSB pass 使用。

**`call` 方式：**

1. 新增 `CCAssignFn`：按 `amdgpu-reg` 把参数放到指定物理寄存器；返回地址放在契约声明的寄存器对中。
2. 被调用方：没有 callee-saved 寄存器（`getCalleeSavedRegs` 返回空），不生成栈帧；需要栈时报错。
3. 调用方：调用点 regmask = 改写集合 ∪ 返回地址寄存器；不设置 `s32`，不初始化 scratch；kernel 不能因此被标记为“有调用”而打开 private segment。
4. `AMDGPUResourceUsageAnalysis` 对契约函数直接使用声明的占用，不需要分析函数体。

### 5.3 后端改动点

| 改动 | 位置 | 对应需求 |
|---|---|---|
| `{vN}` 和 `{v[a:b]}` 支持 N ≥ 256（仅对 `has1024AddressableVGPRs` 的目标）；clobber `~{v[a:b]}` 解析为寄存器集合；未知或越界的寄存器报错 | `SITargetLowering::getRegForInlineAsmConstraint`；重写 `SITargetLowering::ParseConstraints` 来展开区间并做诊断 | R1、R2、R9 |
| 高位 VGPR 作为 `$N` 被打印进 asm 文本时报错（E6，汇编器无法接受） | `AMDGPUAsmPrinter::PrintAsmOperand` | R9 |
| 新调用约定 `amdgpu_contract`、参数属性 `"amdgpu-reg"`、契约函数属性的解析与 verifier 检查 | `CallingConv.h`、IR verifier、`AMDGPUCallLowering` / `SIISelLowering::LowerCall` / `LowerFormalArguments` | R1、R2、R3、R9 |
| 强制展开 `amdgpu_contract` 调用（`inline` 方式） | 新的 IR pass（或在 AMDGPU 的 always-inliner 前加一个 pass），在 codegen 前运行 | R3 |
| 契约调用不需要栈和 scratch | `SIFrameLowering`、`SIMachineFunctionInfo`（是否有调用、是否需要 private segment 的判断） | R3 |
| 严格无 spill 策略和 SGPR lane spill 上限 | 寄存器分配后、PEI 前检查 spill pseudo（`SI_SPILL_*`）；再在 `AMDGPUAsmPrinter` 对最终 `ScratchSize`、spill 计数做一次兜底检查 | R4 |
| 调用点报告 pass：寄存器分配前用 `LiveIntervals` 在调用点的 `SlotIndex` 统计活跃值（忽略 `undef` 操作数和未定义子 lane）；寄存器分配后用 `LivePhysRegs` 给出物理寄存器；输出 `OptimizationRemarkAnalysis`，并支持 `-amdgpu-contract-report=<file>` 直接写 JSON | 新增 `AMDGPUContractReport` | R5 |
| MSB：inline asm 只要有任何 VGPR 操作数（包括 clobber 和 def）就按契约设置入口 MSB；退出后按契约更新跟踪状态 | `AMDGPULowerVGPREncoding.cpp:589–593` | R8 |
| waitcnt 和 EXEC 按契约处理 | `SIInsertWaitcnts`；调试模式下的 EXEC 检查 | R8 |
| 资源统计计入契约声明的寄存器和 LDS；改写集合超出 kernel 的 VGPR 上限时报错 | `AMDGPUResourceUsageAnalysis`；kernel LDS 大小计算；`ParseConstraints` 或 verifier 中按 `getMaxNumVGPRs(F)` 检查 | R7 |

### 5.4 HIP/Clang 前端（可选，方便用 C++ 写契约函数）

```cpp
extern "C" __device__
__attribute__((amdgpu_contract(clobber("s[2:23]", "s[25:29]", "v[4:511]", "scc"),
                               state("exec=full"))))
void mono_dq_convert(__attribute__((amdgpu_reg("s[0:1]"))) uint64_t args,
                     __attribute__((amdgpu_reg("v0")))     uint32_t lane,
                     __attribute__((amdgpu_reg("s24")))    uint32_t wave) {
  __builtin_amdgcn_contract_body(
#include "dq_convert.inline.words.inc"
  );
}
```

这样 `mono_test00` 的 `dq_wrapper.cpp` + `dq_convert_inline.h`（固定输入、78 个 clobber、readfirstlane 桥接）可以缩成上面几行，Clang 生成与 5.1 节相同的 IR。

---

## 6. FlyDSL 侧设计

### 6.1 接口

```python
from flydsl.expr.extern import ffi_contract
from flydsl.compiler.extern_link import link_extern

att_pv = link_extern(ffi_contract("mono_att_pv"), bitcode_path="build/asm/att_pv.bc")
att_pv(wg_id=wg, buf=ptr, wave=wave_id)
```

- `ffi_contract` 在构建 IR 时从 `.bc` 读取契约函数的签名和属性，按参数名检查类型，生成 `llvm.call` 并标注 `amdgpu_contract` 调用约定和 `convergent`。今天 `mono_test00` 需要手动给 `llvm.call` 补 `convergent`，这一步也不再需要。
- 也可以显式写出签名作为额外校验：`ffi_contract("mono_att_pv", params={"wg_id": "u64", ...})`。与 `.bc` 不一致时报错。

### 6.2 编译选项

```python
compile_hints = {
    "spill_policy": "error",                       # R4
    "sgpr_lane_spill_max": 0,                      # 48 行 K2 设为 32
    "residency": {"ctas_per_cu": 1, "threads": 256},   # R7
    "contract_report": "build/k2/contract_callsites.json",  # R5
}
```

FlyDSL 把这些映射为 kernel 函数属性和 LLVM 选项，并在内置 LLVM 和外部 LLVM（`FLYDSL_COMPILE_LLVM_DIR`）两条路径上都支持 `link_extern`（F3）。

### 6.3 报告

- **codegen 前：** FlyDSL 已经知道每个调用点的契约，可以先打印“这个调用点最多可以保留 N 个 VGPR、M 个 SGPR”。
- **codegen 后：** 把 LLVM 的 JSON 报告与 Python 源码行对应起来；编译失败时，错误信息直接指向调用所在的 Python 行。

---

## 7. 报告格式示例（R5）

```json
{
  "kernel": "dspark_dynamic_index_down_k2",
  "callsites": [{
    "loc": "dspark_dynamic_index_down.py:206",
    "contract": "mono_att_pv",
    "lowering": "inline",
    "clobber": "s[2:23],s[25:29],v[4:511],scc,vcc",
    "budget": { "vgpr": "v[0:3]", "sgpr": "s[0:1],s24,s[30:104] - reserved" },
    "live_across": {
      "vgpr": 3, "sgpr": 35,
      "values": [
        { "reg": "v[0:1]", "bits": 64, "def": "dspark_dynamic_index_down.py:198", "remat": false, "note": "param buf, preserved" },
        { "reg": "v2",     "bits": 32, "def": "dspark_dynamic_index_down.py:190", "remat": true }
      ]
    },
    "status": "ok"
  }],
  "spills": { "vgpr": 0, "sgpr_lane": 0, "scratch_bytes": 0 },
  "resources": { "vgpr_count": 512, "sgpr_count": 106, "lds_bytes": 32768, "ctas_per_cu": 1 }
}
```

---

## 8. 验收测试（建议加入 LLVM lit 测试）

| 测试 | 内容 | 期望 |
|---|---|---|
| T1 | 用 `amdgpu_contract` 改写 E5 | 调用点没有 `s_swap_pc`（`inline` 方式），没有 scratch，参数在 `s[0:1]` / `v[0:1]` / `s24` |
| T2 | 同 T1，改为 `call` 方式 | 有 `s_swap_pc`，但没有 `s32` 设置、没有 scratch，被调用方没有 prologue |
| T3 | 参数绑定 `v[300:301]` | 编译通过，进入 ASM 时值在 v300:301；前后有正确的 `s_set_vgpr_msb` |
| T4 | 改写集合 `v[4:1023]`，调用方有 3 个 VGPR 跨调用点活跃 | 活跃值被分配到 v0–v3 中 |
| T5 | 同 T4，调用方有 5 个 VGPR 跨调用点活跃，策略为 `error` | 编译报错，列出跨越调用点的值 |
| T6 | E4 加 `"amdgpu-spill-policy"="error"` | 编译报错 |
| T7 | E3b 加 `"amdgpu-sgpr-lane-spill-max"="0"` / `"3"` | 前者报错，后者通过 |
| T8 | 进入契约调用时 MSB 非 0（E3c 的情形） | 调用前插入 `s_set_vgpr_msb 0` |
| T9 | 改写集合 `v[4:600]`，`flat-work-group-size=256,256`，要求每 CU 1 个 CTA | 编译报错：超出 512 个 VGPR 的上限 |
| T10 | 未知寄存器、保留寄存器、参数重叠、`inline` 方式被取地址、asm 约束与契约属性不一致 | 各自报出对应的诊断 |
| T11 | `-amdgpu-contract-report=out.json` | 输出第 7 节格式的报告，活跃值数量与 `liveness.py` 的结果一致 |
| T12 | `amdgpu-asm-pack`：ASM 写了清单之外的寄存器 / 退出时没有恢复 MSB | 工具报错 |

端到端：把 `mono_test00` 改写为契约函数版本，在 gfx1250 上与 native 版本逐位对比，并要求 scratch = 0。

---

## 9. 分阶段交付建议

| 阶段 | 内容 | 价值 |
|---|---|---|
| P1 | 寄存器层面的基础能力：高位 VGPR 约束、区间 clobber、未知或越界寄存器报错、高位 VGPR 被打印进文本时报错、MSB 入口归零（R1 的寄存器部分、R2 的寄存器解析、R8 的 MSB 部分、R9 的一部分） | 修复今天就存在的静默损坏风险（E2a、E3a、E3c），也是契约函数的地基；改动小，最容易进上游 |
| P2 | 严格无 spill 策略和 SGPR lane spill 上限（R4）；资源统计和 VGPR 上限检查（R7） | 满足 mono 的驻留规则，不再到运行时才发现问题 |
| P3 | 调用点报告 pass（R5） | 满足“调用方据此限制并报告给用户” |
| P4 | `amdgpu_contract` 调用约定、`"amdgpu-reg"` 参数属性、verifier、`inline` 降级（R1、R2、R3、R6、R9） | 达到 `mono_test00` 的使用形态，并且零开销 |
| P5 | 打包工具（R10）；FlyDSL `ffi_contract`、compile hint、外部 LLVM 支持 `link_extern`（F1–F4） | 接入新 ASM 变成“一份 `.s` 加一份清单” |
| P6 | `call` 降级、HIP/Clang 属性（5.4 节） | 控制代码体积；方便用 C++ 写契约函数 |

P1–P3 是在 inline asm 层面就有用的通用能力，P4 在其上实现契约函数。`inline` 降级展开后就是一条 inline asm，所以前三个阶段的成果会被 P4 直接复用。

---

## 10. 曾考虑但不推荐的替代方案

- **直接在 mono 主体中写 inline asm（`mono_test10`）：** 没有调用开销，但每个调用点都要重复写全部固定输入和 clobber，契约不能随 ASM 一起分发，接入新 ASM 时容易出错。这正是这次需求变更要避免的。
- **标准 ABI 包装函数 + IPRA（`mono_test00` 现状）：** IPRA 可以收窄调用方需要保存的寄存器，但被调用方仍要保存 callee-saved 寄存器（E5 实测有 scratch），参数位置也仍由调用约定决定。
- **只加“无 callee-saved”的属性，不新增调用约定：** 仍要使用标准调用约定的参数分配、返回地址和栈指针，也无法在类型层面防止误用。
- **用 `waves_per_eu` / `amdgpu-num-vgpr` 限制整体 VGPR：** 只能限制总量，表达不了“调用点两侧不同的占用”，结果就是 E4 中的 spill。
- **自定义 MIR pass 改 regmask（`mono_test01`）：** 能工作，但依赖内部数据结构，不可移植，也无法上游。
- **事后扫描最终 ELF：** 只能事后发现问题，既不能指导调用方，也给不出原因。

---

## 11. 相关文件

- 证据与复现脚本：[asm_reg_contract_evidence/](asm_reg_contract_evidence/)（`run.sh`，`e1`–`e5` 的 `.ll` 文件）
- 现有接入方案对比：[ASM_MONO_INTEGRATION.zh-CN.md](ASM_MONO_INTEGRATION.zh-CN.md)、[ASM_FLYDSL_MONO_INTEGRATION_OPTIONS.zh-CN.md](ASM_FLYDSL_MONO_INTEGRATION_OPTIONS.zh-CN.md)
- `mono_test00` 的包装器与 clobber 声明：`../mono_test00/asm/dq_wrapper.cpp`、`../mono_test00/asm/dq_convert_inline.h`、`../mono_test00/mono1250/kernels/dq_ffi.py`
- 实现所用的 LLVM 源码：`/app/llvm-project`（ROCm `amd-staging` 的 `d177931e65e6`，分支 `asm-reg-contract`，基线已编译在 `build/`）
- FlyDSL 相关接口：`flydsl/compiler/extern_link.py`（`link_extern`）、`flydsl/compiler/external_llvm.py`、`flydsl/compiler/jit_function.py`（E7 所指的两处拒绝已在 `/app/FlyDSL` 分支 `asm-reg-contract` 中移除）
- 实现与验证：[ASM_REG_CONTRACT_IMPLEMENTATION.zh-CN.md](ASM_REG_CONTRACT_IMPLEMENTATION.zh-CN.md)、补丁 [asm_reg_contract_patches/](asm_reg_contract_patches/)、端到端用例 `../mono_test_contract/`
