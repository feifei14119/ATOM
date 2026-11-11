# 实现与验证：AMDGPU 寄存器契约函数

需求和设计见 [ASM_REG_CONTRACT_REQUIREMENT.zh-CN.md](ASM_REG_CONTRACT_REQUIREMENT.zh-CN.md)。本文记录实际实现、与设计的差异，以及在 gfx1250 上的验证结果。

## 0. 结论

`mono_test00` 的同一份 ASM 已经以“契约函数”的形式接入 mono kernel，并在 gfx1250 上通过：

- **正确性：** 9 组 A/B 与 native 逐位一致（18 次融合 launch，1008 次 ASM 执行）。
- **零开销：** scratch = 0，VGPR/SGPR spill = 0，没有 `s_swap_pc`，也没有 wrapper 的 prologue/epilogue。
- **参数位置：** 参数正好落在 ASM 声明的 `s[0:1]`、`v0`、`s24`。
- **调用点报告：** 编译器输出每个调用点跨越的活跃寄存器，以及剩余的寄存器预算。
- **违约即报错：** 违反契约、改写集合超出 VGPR 上限、需要 spill，都会在编译期或打包期报错。

| 指标（K1 projection kernel） | native | mono_test00（标准 ABI wrapper） | mono_test_contract（契约函数） |
|---|---:|---:|---:|
| `.text` 字节 | 12928 | 15104 | 14720 |
| VGPR / SGPR | 126 / 68 | 126 / 70 | 126 / 68 |
| scratch（字节/线程） | 0 | **32** | **0** |
| scratch 指令 | 0 | 14 | 0 |
| `s_swap_pc` | 0 | 1 | 0 |
| 调用方需要手写的寄存器信息 | — | 78 个 clobber + readfirstlane 桥接 | 0（清单里写 3 个参数寄存器） |

契约版的 `.text` 比 native 多 1792 字节，基本就是 ASM fragment 本身（含 64 字节对齐填充）。mono_test00 比契约版多出的 384 字节，是 wrapper 的 prologue/epilogue、scratch 保存恢复和调用序列。

## 1. 交付物与位置

| 内容 | 位置 |
|---|---|
| LLVM 补丁（ROCm `amd-staging` `d177931e65e6`） | `/app/llvm-project`，分支 `asm-reg-contract`，构建目录 `build/` |
| LLVM 补丁（上游 `1df311a6`，测试实际使用） | `/app/llvm-upstream`（worktree），分支 `asm-reg-contract-upstream`，构建目录 `build/`。第一个提交是 FlyDSL 自带的 3 个 LLVM 补丁，契约补丁在其上 |
| FlyDSL 补丁 | `/app/FlyDSL`，分支 `asm-reg-contract`（基于 `8bcefbc0`）。测试时通过 overlay `/app/flydsl_overlay` 放到 `PYTHONPATH` 前面，没有改动已安装的 FlyDSL |
| 端到端用例 | `/app/ATOM/mono_test_contract/`（见其 `README.md`） |
| 补丁文件 | [asm_reg_contract_patches/](asm_reg_contract_patches/)：`llvm-rocm-d177931-asm-reg-contract.patch`、`llvm-upstream-1df311a6-asm-reg-contract.patch`、`llvm-upstream-1df311a6-flydsl-prereq.patch`、`flydsl-asm-reg-contract.patch` |

两棵 LLVM 树上的契约补丁内容一致，唯一差别是测试 RUN 行里 triple 的写法（ROCm 用 `amdgcn-amd-amdhsa -mcpu=gfx1250`，上游用 `amdgpu12.50-amd-amdhsa`）。补丁都没有提交，只保留在工作区和补丁文件中。

## 2. 使用方法

```yaml
# asm/dq_convert.contract.yaml —— ASM 提供方写
name: dq_convert
source: dq_convert.inline.s          # 原样使用，不需要改
symbol: mono_dq_convert_inline_fragment
target: gfx1250
align: 64
params:
  - {name: args, reg: "s[0:1]", type: uint64}
  - {name: lane, reg: v0,       type: uint32}
  - {name: wave, reg: s24,      type: uint32}
# clobbers 省略 = 取机器码实际写到的寄存器集合
preserves: [exec, mode]              # fragment 内部改了，但退出前已恢复
memory: true
```

```bash
python -m flydsl.compiler.asm_contract pack asm/dq_convert.contract.yaml -o build/contract --llvm-dir /app/llvm-upstream/build
# 生成 dq_convert.contract.bc（契约函数）、dq_convert.contract.json（sidecar）、dq_convert.fragment.bin
```

```python
# mono kernel 调用方
from flydsl.compiler.asm_contract import ffi_contract, spill_hints
dq_convert = ffi_contract("build/contract/dq_convert.contract.json")   # 自动 link 对应 .bc
dq_convert(args=fx.Int64(addr), lane=tid & 31, wave=tid >> 5)          # 类型、寄存器都来自 sidecar

# 编译与 launch 都要在同一组 hints 下
with CompilationContext.compile_hints({"llvm_options": spill_hints("error", report="build/contract_report.jsonl")}):
    ...
```

环境变量：`FLYDSL_COMPILE_LLVM_DIR=/app/llvm-upstream/build`、`FLYDSL_COMPILE_LLVM_HANDOFF=llvm`（原因见第 5 节）。

## 3. LLVM 侧实现

### 3.1 IR 形态：用属性，不新增调用约定

与设计第 5.1 节不同，实现**没有新增 `amdgpu_contract` 调用约定**，契约完全由属性表达：

```llvm
define void @dq_convert(i64 "amdgpu-reg"="s[0:1]" %args, i32 "amdgpu-reg"="v0" %lane,
                        i32 "amdgpu-reg"="s24" %wave) #0 {
  %args.u = call i64 @llvm.amdgcn.readfirstlane.i64(i64 %args)
  %wave.u = call i32 @llvm.amdgcn.readfirstlane.i32(i32 %wave)
  call void asm sideeffect "s_branch 1f\0A.p2align 6\0A1:\0A.long 0xbfc00000 ...",
      "{s[0:1]},{v0},{s24},~{s[2:23]},~{s[25:29]},~{s[40:48]},~{v[4:45]},~{scc},~{memory}"(...)
  ret void
}
attributes #0 = { noinline convergent nounwind "amdgpu-contract"="dq_convert"
  "amdgpu-contract-clobber"="s[2:23],s[25:29],s[40:48],v[4:45],scc" "target-cpu"="gfx1250" }
```

- 调用点是普通的 `call void @dq_convert(...)`。调用前可以有一条标记 `call void asm sideeffect ";@amdgpu-contract-site <源码位置>", ""()`，用于诊断和报告。
- 理由：这样不用改 IR 语法、bitcode 格式、verifier 或 CallLowering，补丁集中在 AMDGPU 后端，FlyDSL 现有的 `ffi`/`link_extern` 也可以直接生成这种调用。由于目前只实现了 `inline` 降级，每个调用都会在 codegen 前展开，标准 ABI 的假设不会被用到。新增调用约定是为 `call` 降级（P6）准备的，留到那时再做。

### 3.2 改动清单

| 文件 | 改动 | 对应需求 |
|---|---|---|
| `AMDGPUContract.cpp`（新） | `AMDGPUExpandContractCalls`（IR 模块 pass，`-amdgpu-expand-contract-calls`）：检查契约函数形态（单个基本块，只含参数转换、一条 inline asm 和 ret；asm 的输入正好是各参数的 `amdgpu-reg`；asm 的 clobber 是 `amdgpu-contract-clobber` 的子集），然后在每个调用点原地展开；取地址、只有声明等情况报错。展开后的 asm 文本以 `;@amdgpu-contract <name> site=<site> clobber=<...>` 开头 | R1、R2、R3、R6、R9 |
| 同上 | `AMDGPUContractReport`（MIR pass，`-amdgpu-contract-check`，在寄存器分配之后、PEI 之前运行）：用 `LivePhysRegs` 统计每个契约调用点跨越的物理寄存器，算出剩余预算；执行 spill 策略；按 `-amdgpu-contract-report=<file>` 追加 JSON 行 | R4、R5 |
| 同上 | 选项 / 函数属性：`-amdgpu-spill-policy=allow\|error`（或属性 `"amdgpu-spill-policy"`）、`-amdgpu-sgpr-lane-spill-max=N`（或同名属性）、`-amdgpu-contract-report=<file>` | R4、R5 |
| `AMDGPUTargetMachine.cpp`、`AMDGPU.h`、`CMakeLists.txt` | 把展开 pass 放在 `AMDGPU Inline All Functions` 之前，把检查 pass 放在 `addPostRegAlloc` 开头（`SI Fix VGPR copies` 之前） | — |
| `SIISelLowering.cpp/.h` | `{vN}` 和 `{v[a:b]}` 在 1024-VGPR 目标上支持 N ≥ 256；重写 `ParseConstraints`：把区间 clobber（如 `~{v[4:511]}`）展开为单个寄存器；寄存器不存在、超出 kernel 的 VGPR 上限（由 `amdgpu-flat-work-group-size` / `amdgpu-waves-per-eu` 推导）时报错；同一个调用只报一次 | R1、R2、R7、R9（修复 E1、E2a、E2b） |
| `AMDGPUAsmPrinter.cpp` | v256 及以上的寄存器被打印进 asm 文本（`$N`）时报错（E6） | R9 |
| `AMDGPULowerVGPREncoding.cpp` | 契约 asm，以及任何带 VGPR 操作数（包括 def 和 clobber）的 inline asm，入口都把 MSB 归零（修复 E3c） | R8 |
| `llvm/tools/amdgpu-asm-footprint/`（新工具） | 反汇编目标文件的 `.text`（或某个符号），按 MSB 跟踪得到真实的读写寄存器集合（包括 v256 以上），输出 JSON；同时检查禁止的指令（`s_endpgm`、`s_setpc`/`s_swappc`/`s_call`、`s_rfe`）、重定位、退出时 MSB 是否为 0；`--bytes-out` 导出机器码 | R10 |
| 测试 | `amdgpu-contract-call.ll`（正例，含报告）；`amdgpu-contract-errors.ll`（9 个负例：超预算、不存在的 VGPR、写出 footprint、缺 `amdgpu-reg`、输入不匹配、取地址、保留寄存器、spill、只有声明）；`tools/amdgpu-asm-footprint/basic.s`；更新 `inline-asm-out-of-bounds-register.ll`（gfx1250 上 v256 改为合法）、`llc-pipeline.ll`、`sgpr-regalloc-flags.ll`（新 pass 出现在流水线里） | 第 8 节 T1、T6、T9–T12 |

### 3.3 调用点报告示例（真实输出）

```json
{"function":"_ZN4atom60gfx1250_contract_dq_k1_projection_front1_fold0_ix1_b256_t256E",
 "policy":"error","max_vgpr":512,"status":"ok","vgpr_spills":[],"sgpr_lane_spills":0,"sgpr_lane_spill_max":0,"stack_objects":0,
 "callsites":[{"contract":"dq_convert","site":"dq_ffi.py:27<projection_asm.py:51<projection_asm.py:123",
   "clobber":"s[2:23],s[25:29],s[40:48],v[4:45],scc",
   "live_vgpr":1,"live_vgpr_regs":"v1","free_vgpr":470,
   "live_sgpr":11,"live_sgpr_regs":"s[30:31],s33,s[36:39],s[52:54],s106","free_sgpr":70}]}
```

`site` 由 FlyDSL 自动生成，取最多 3 层用户调用栈，用 `<` 连接。违反策略时的报错示例：

```text
error: function '..._k1_projection_...' violates amdgpu-spill-policy=error:
  VGPR spill in bb.0
  contract call dq_convert@dq_ffi.py:29<projection_asm.py:51<projection_asm.py:123: live across VGPR 0 [], SGPR 11, free VGPR 1, free SGPR 70
```

## 4. FlyDSL 侧实现

| 文件 | 改动 | 对应需求 |
|---|---|---|
| `compiler/asm_contract.py`（新） | 清单解析（YAML/JSON）；`pack()`：用 `llvm-mc` 汇编，再用 `amdgpu-asm-footprint` 得到写集合并检查（写集合 ⊆ clobbers、输入寄存器未被改写、exec/mode/m0 若被改写必须在 `preserves` 中、退出时 MSB=0、无禁止指令、无重定位），生成契约函数 IR（以 `.long` 机器字嵌入，因此 v256 以上不用出现在文本中），再用 `llvm-as` 得到 `.bc`，同时写出 sidecar JSON（含哈希和 footprint）；`ffi_contract()`：读 sidecar，注册 link，按参数名或位置调用，生成 site 标记和 `convergent` 的 `llvm.call`；`spill_hints()`；命令行 `python -m flydsl.compiler.asm_contract pack` | R10、F1、F2、F4 |
| `expr/extern.py` | `ExternFunction(..., convergent=True)`：在 `llvm.call` 上加 `convergent` | F1 |
| `compiler/jit_function.py` | 去掉外部 LLVM 模式下对 `link_libs` 的两处拒绝，把 link 选项也传给外部 LLVM 路径；外部模式下不再把 `llvm_options` 应用到内置 LLVM | F3（修复 E7） |
| `compiler/external_llvm.py` | 新的交接模式 `FLYDSL_COMPILE_LLVM_HANDOFF=llvm`（第 5 节）；交接前把 `#fly.` offloading handler 从克隆中移除，交接后再恢复 | F3 |
| `utils/env.py` | 新环境变量 `FLYDSL_COMPILE_LLVM_HANDOFF`（默认 `mlir`，与原行为一致） | F3 |

## 5. 为什么需要 `FLYDSL_COMPILE_LLVM_HANDOFF=llvm`

FlyDSL 原有的外部 LLVM 路径是把 MLIR 文本交给外部的 `mlir-opt`。但 FlyDSL 自带的 MLIR 是一个版本未知的 LLVM 24git 构建，它打印出来的 ROCDL 方言语法与两个 LLVM 基线都不一致：

- ROCm `d177931`（LLVM 23）无法解析 `rocdl.raw.ptr.buffer.load` 的 aux 参数；
- 上游 `1df311a6` 无法解析 `rocdl.make.buffer.rsrc ... : !llvm.ptr to <8>`。

新模式改为在进程内用 FlyDSL 自己的 MLIR 执行 `gpu-module-to-binary{format=llvm}`，得到已链接（含契约 `.bc`）、已优化的 LLVM bitcode，再交给外部的 `llc`（带上 `llvm_options`）和 `ld.lld -shared`。结果以 `CompilationTarget.Binary` 的形式放回 `gpu.binary`。LLVM bitcode 可以向后兼容读取，所以这条路径不受 MLIR 方言版本差异的影响。

另外，上游树先应用了 FlyDSL 构建内置 LLVM 时使用的 3 个补丁（`llvm-upstream-1df311a6-flydsl-prereq.patch`：lld argv0、waves-per-eu 区间、xnack any），让外部 LLVM 的行为与内置 LLVM 保持一致。

## 6. 验证结果

| 项目 | 命令 / 位置 | 结果 |
|---|---|---|
| LLVM 全量 AMDGPU lit（上游树） | `build/bin/llvm-lit llvm/test/CodeGen/AMDGPU llvm/test/MC/AMDGPU llvm/test/tools/amdgpu-asm-footprint` | 5761 passed，7 expectedly failed，**0 failed** |
| LLVM 全量 AMDGPU lit（ROCm 树） | 同上 | 5605 passed，11 expectedly failed，**0 failed** |
| FlyDSL 单测 | `tests/unit/test_asm_contract.py`（17 个，真实打包需 `FLYDSL_TEST_CONTRACT_LLVM_DIR`）、`tests/unit/test_external_llvm_codegen.py`（12 个） | 29 passed；原有的 extern / link / compile hints 测试也都通过 |
| GPU 端到端 | `mono_test_contract/run.sh` | 9/9 A/B 逐位一致，18 次融合 launch，1008 次 ASM 执行 |
| 资源审计 | `mono_test_contract/contract_audit.py` | fragment 在 `.text` 中恰好出现一次，64 字节对齐；没有 call/return；scratch、VGPR spill、SGPR spill 都是 0；报告只有一个调用点，`status=ok` |
| 负例 | `mono_test_contract/negative_tests.py` | 5/5：漏声明 `s5`、MODE 未恢复、改写输入 `v4`（打包期报错）；改写集合 `v[4:600]` 超过 512 的上限、`v[1:3],v[4:511]` 导致 spill（编译期报错） |
| footprint 工具 | 在 mono fragment 上运行 | 写集合为 `s[2:23]`、`s[25:29]`、`s[40:48]`、`v[4:45]`、exec、mode、scc，与 mono_test00 中手写的 78 个 clobber 完全一致 |

## 7. 与需求的对照

| 需求 | 状态 | 说明 |
|---|---|---|
| R1 契约随 bitcode 分发 | 已完成 | 用函数属性和参数属性表达，见 3.1；LDS 占用、状态声明还没有做成属性 |
| R2 参数固定到物理寄存器 | 部分完成 | 输入参数（含 v256 以上）已支持；SGPR 参数自动 readfirstlane。**返回值、“输入后被改写”的参数**尚未支持 |
| R3 零开销调用 | `inline` 方式已完成 | `call` 方式（`s_swap_pc` + 无栈）未实现（P6） |
| R4 严格无 spill | 已完成 | 寄存器分配后检查；spill 的归属只能精确到基本块（例如 “in bb.0”） |
| R5 调用点报告 | 部分完成 | 寄存器分配后的物理寄存器报告已完成；**分配前估算、每个值的 DebugLoc、是否可重算**尚未实现 |
| R6 调用方遵守契约 | 已完成 | 复用 inline asm 的 clobber 机制；没有实现自动重算 |
| R7 资源统计与上限检查 | 已完成 | 区间 clobber 计入 `.vgpr_count`；超过 kernel 上限报错 |
| R8 机器状态 | 部分完成 | 入口 MSB 归零已完成；exec/mode/m0 由打包工具检查是否恢复；**waitcnt 约定、full-EXEC 检查**尚未实现，fragment 需要自行清空等待计数器 |
| R9 非法契约报错 | 已完成 | 见 `amdgpu-contract-errors.ll` 的 9 个用例 |
| R10 打包工具 | 已完成 | `amdgpu-asm-footprint`（LLVM）+ `asm_contract.pack`（FlyDSL） |
| F1–F4 | 已完成 | `ffi_contract`、`spill_hints`、外部 LLVM 支持 `link_extern`、报告和报错中带 Python 源码位置 |
| 5.4 节 HIP/Clang 属性 | 未实现 | P6 |

## 8. 已知限制

- **报告反映的是寄存器分配后的结果，** 不是“最多能保留多少”的上界。放不下时，表现为 spill 报错加上调用点信息，而不是“缺几个寄存器、是哪些值”。
- **固定输入可能多占寄存器。** 参数值如果在调用后还要使用，编译器会先复制一份再放到固定寄存器，这份拷贝也要放在改写集合之外。
- **流水线位置。** 检查 pass 位于 `addPostRegAlloc` 开头，寄存器分配产生的 spill 和栈对象都能在这里发现。PEI 之后才出现的 scratch 使用（frame lowering 出于其他原因分配的栈）目前由 `contract_audit.py` 检查最终的 `private_segment_fixed_size`，LLVM 中还没有对应的兜底报错。
- **两个基线 LLVM 都要求 FlyDSL 使用 `FLYDSL_COMPILE_LLVM_HANDOFF=llvm`，** 原因见第 5 节。FlyDSL 升级到与外部 LLVM 一致的版本后，默认的 `mlir` 模式也可以使用。
- **改动未提交。** 上游 worktree 只提交了 FlyDSL 前置补丁，契约补丁仍在工作区；FlyDSL 和 ROCm 树的改动都在工作区。

## 9. 复现

```bash
# LLVM（以上游树为例；ROCm 树相同）
cd /app/llvm-upstream && ninja -C build llc opt llvm-mc llvm-as ld.lld amdgpu-asm-footprint
build/bin/llvm-lit -s llvm/test/CodeGen/AMDGPU/amdgpu-contract-call.ll llvm/test/CodeGen/AMDGPU/amdgpu-contract-errors.ll llvm/test/tools/amdgpu-asm-footprint

# FlyDSL 单测
cd /app/FlyDSL && FLYDSL_TEST_CONTRACT_LLVM_DIR=/app/llvm-upstream/build PYTHONPATH=/app/flydsl_overlay \
  python3 -m pytest -q tests/unit/test_asm_contract.py tests/unit/test_external_llvm_codegen.py

# GPU 端到端与负例
cd /app/ATOM/mono_test_contract && ./run.sh && PYTHONPATH=/app/flydsl_overlay python3 negative_tests.py
```
