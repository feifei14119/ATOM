# LLVM 外部 ASM 调用契约：已实现的 v1 原型

本目录是 [外部 ASM 调用契约 RFC](../mono_read/AMDGPU_EXTERNAL_ASM_CALL_CONTRACT_RFC.zh-CN.md) 的第一版实现与验证入口。**LLVM 后端已修改并实际编译；手写 IR 和 FlyDSL 两条接入路径均已通过离线验证。** 当前机器没有 gfx1250，GPU 执行结果尚未验证。

## 1. 源码、补丁与构建产物

| 内容 | 位置 |
| --- | --- |
| 独立 LLVM 开发副本 | `/home/feifei/repo/llvm-project-asm-contract` |
| 开发分支 | `codex/amdgpu-external-asm-contract` |
| 上游 | `https://github.com/ROCm/llvm-project.git` 的 `amd-staging` |
| 拉取的基准提交 | `2006b625d467c5082c0ff68b8d3aba162082c9c3`，2026-11-10，LLVM 24 |
| 修改后的工具 | `/home/feifei/repo/llvm-project-asm-contract/build-contract/bin` |
| 可移植源码补丁 | [llvm.patch](llvm.patch) |
| 基准信息 | [SOURCE.json](SOURCE.json) |
| 拉取、打补丁、编译脚本 | [build_llvm.py](build_llvm.py) |
| 一键验证入口 | [run.sh](run.sh) |
| 最终验证报告 | [build/validation/result.json](build/validation/result.json) |
| 本次验证快照与补丁指纹 | [VALIDATION.json](VALIDATION.json)、[PATCH_MANIFEST.json](PATCH_MANIFEST.json) |

原 `/home/feifei/repo/llvm-project` 为 root 所有的只读副本，所以新建了可写开发目录。原 ROCm 安装、FlyDSL 安装及 `mono_test00/01/10` 源码未修改。LLVM 改动保留在开发分支的工作区，尚未提交或推送到上游。

## 2. 现在实现了哪些需求

| 需求 | 本次实际实现 |
| --- | --- |
| 指定参数物理寄存器 | 后端读取函数契约，在 SelectionDAG 中为参数和结果生成固定寄存器约束 |
| ASM 告知污染集合 | 为这个调用生成自定义 call-preserved regmask，处理重叠 tuple/alias 和 SCC/VCC 派生视图 |
| 编译器维护上下文 | LLVM 正常寄存器分配依据真实 regmask 保护跨调用值；允许寄存器复制和合法重算 |
| 禁止 GPR spill | 后端检查 spill 来源，包含 SGPR 到 VGPR lane 的 spill 和 ABI 保存 |
| 禁止 scratch/private | 检查完整已知调用图的帧、栈参数、动态保存、实际或潜在 private 访问，违反即错误 |
| 资源约束与报告 | 提前检查 callee 资源是否超过 caller 预算；后期合并 descriptor 资源，输出 JSON |
| 独立目标链接 | ASM 汇编为真正的 ET_REL `.co`；与 caller.o 静态链接 |
| FlyDSL 调用体验 | `AsmFFI(manifest)` 后直接调用；隔离的编译适配器使用新 LLVM，不修改 MIR |

这里没有用 `.long` 内嵌被调机器码，也没有修改最终二进制中的指令。保存/恢复策略由 LLVM 处理；严格模式不允许生成不符合要求的保存方式。

**保证是“成功编译则满足检查，无法满足则失败”。** 当前使用正常的 LLVM 分配器，再在后期严格拒绝 spill；尚未实现为零 spill 专门设计的寄存器分配搜索算法。

## 3. 一键验证

当前工作区的 LLVM 和 FlyDSL 环境已经准备好：

```bash
cd /home/feifei/repo/ATOM/llvm_asm_contract
./run.sh --build-only
```

默认不启动 GPU。此命令执行：

1. 新增 LLVM 正向/负向测试与 13 个已有调用/资源回归测试。
2. ASM 对象和 manifest 的 6 个拒绝测试。
3. 手写 LLVM IR caller → 新 llc → 链接 `.co`。
4. 真实 FlyDSL caller → LLVM bitcode → 新 llc → 链接相同 ASM。
5. 编译 HIP host 校验程序，保存汇总 JSON。

在 gfx1250 机器上：

```bash
./run.sh --run-gpu --python /path/to/flydsl-env/bin/python
```

将分别运行两个最终 kernel，各 9 个二维 grid/seed 案例。host 检查完整输出、参数记录、跨调用旧值和 guard。找不到 gfx1250 时明确失败，不会在其他架构上执行这些代码。

也可以指定源码和工具目录：

```bash
./run.sh --build-only \
  --source /path/to/llvm-project-asm-contract \
  --llvm-bin /path/to/llvm-project-asm-contract/build-contract/bin \
  --python /path/to/flydsl-env/bin/python
```

FlyDSL 适配器目前针对 0.4.1。默认复用 `mono_test20/build/venv/bin/python`；换机器时需要提供安装了 FlyDSL 及其依赖的 Python 环境。LLVM bitcode 必须与这套 LLVM 24 工具兼容。

## 4. 最小单测与实际参数位置

两个 caller 使用同一个 [demo/stage.s](demo/stage.s)：

| 参数 | 位置 |
| --- | --- |
| workgroup x / y，各一个 u32 | s0 / s1 |
| 立即数 factor | s2 |
| 每 lane 的 64 位 global 地址 | v0:v1，低 dword 在 v0 |
| thread x / y | v2 / v3 |
| 返回结果 | v4 |
| 返回 PC | s30:s31 |

ASM 会写坏 `s4:s6,s40,s48,s63,v4:v9,v64,v72,v95,SCC`。其中包含标准 ABI 的 callee-saved 寄存器，但这里使用显式契约，callee 无需为默认 ABI 生成保存帧。

caller 先读取 volatile 快照，连续调用 ASM 两次，再使用旧快照与两次返回值。ASM 每次修改输入内存，避免错误的调用后重载看起来像正确保存。详细计算与 host 检查见 [demo/README.md](demo/README.md)。

实际反汇编中可见：

```asm
; 参数已在契约指定的位置。
s_swap_pc_i64 s[30:31], s[8:9]
s_mov_b32 s2, 0xa13579bd
v_mov_b32_e32 v10, v4
s_swap_pc_i64 s[30:31], s[8:9]
```

`s_swap_pc_i64` 是这版 LLVM 的打印名称，对应此前讨论的 `s_swappc_b64`。第一次的返回值在 v10 中跨第二次调用保持；旧快照位于 v12/v13。参数地址仍可保存在 callee 承诺不覆写的 v0:v1 中。

## 5. LLVM 的实际接口

本分支使用正式被 AMDGPU 后端消费的实验性 target string attributes。它们是本次新增能力，旧 LLVM 可能忽略未知属性，因此集成脚本必须先探测后端是否识别契约版本。

```llvm
declare i32 @contract_stage(i32, i32, i64, i32, i32, i32) #1

attributes #1 = {
  convergent noinline nounwind norecurse
  "amdgpu-asm-contract"="1"
  "amdgpu-asm-arg-regs"="s0,s1,v[0:1],v2,v3,s2"
  "amdgpu-asm-result-reg"="v4"
  "amdgpu-asm-clobbers"="s[4:6],s40,s48,s63,v[4:9],v64,v72,v95,scc"
  "amdgpu-asm-vgpr-count"="96"
  "amdgpu-asm-sgpr-count"="64"
  "amdgpu-asm-private-bytes"="0"
}
```

在 caller 上添加：

```llvm
"amdgpu-asm-full-wave-calls"="true"
"amdgpu-no-gpr-spill"
"amdgpu-no-private-memory"
```

SGPR 参数必须通过 divergence 检查。后端不会将不同 lane 的值静默 `readfirstlane` 成一个 SGPR 值。返回支持 i32/i64 或 64 位地址，已覆盖 64 位 SGPR 输入和 64 位 VGPR 返回测试。

“64 个编号 SGPR”是 callee 的资源范围；最终 caller+callee 使用 66 个 SGPR，包含 caller 的额外用法。本例 VCC 未被使用，不能把 66 解释成固定的“64+VCC”。

`amdgpu-asm-full-wave-calls=true` 是显式前提，不是任意控制流的证明。后端会拒绝部分可判定的 divergent 分支调用，但调用方仍需保证 full EXEC 和所需的 CTA 参与条件。本单测使用固定 32×8 block、无分支调用路径。

## 6. FlyDSL 如何接入

[flydsl_adapter.py](flydsl_adapter.py) 提供隔离的实验性接口：

```python
stage = AsmFFI("build/stage/stage.contract.json")

# 在 FlyDSL kernel 内：
result = stage(block_x, block_y, address, thread_x, thread_y, factor)

# 编译上下文需要明确承诺 full wave，并指定新 LLVM：
with asm_codegen(manifest_path, llvm_bin, output_dir,
                 assert_full_wave_calls=True):
    ...
```

可直接阅读完整 [test_flydsl.py](test_flydsl.py)。流程是：

```text
stage.s → llvm-mc → stage.co → 对象审计和 hash 绑定
                                   │
FlyDSL → 带契约的 LLVMFuncOp/call    │
       → FlyDSL 原有 lowering       │
       → serializer 输出 bitcode   │
       → 新 llc 分配寄存器/检查策略 │
       → caller.o ── ld.lld ───────┘
       → 最终 kernel.co / gpu.binary
```

契约通过 MLIR API 添加到函数声明；没有用文本替换 LLVM IR 或修改 MIR。适配器暂时接管一个编译上下文，退出后恢复原编译器入口。这是本地 FlyDSL 适配层，尚未向上游 FlyDSL 增加公共 API，也不修改 installed package。

构建器先用契约版本 999 做负向探测，确保新 llc 返回预期错误，避免旧 LLVM 默默按默认 ABI 编译。

## 7. 资源报告与验证结果

后端选项：

```bash
llc -mtriple=amdgcn-amd-amdhsa -mcpu=gfx1250 \
  -mattr=+wavefrontsize32 -global-isel=0 \
  -amdgpu-asm-contract-report=resources.json \
  caller.ll -filetype=obj -o caller.o
```

每个函数报告：实际 SGPR/VGPR spill、ABI lane/memory saves、WWM spill、private frame、栈参数、private 访问及资源范围。每个 call 报告固定参数、污染集合、保持集合和实际物理 live-through 寄存器。

`call_instruction_live_through` 对应**参数准备之后的 call 指令**，不等于整个参数准备和返回 COPY 序列，也不声称恢复了源程序变量名。

本次最终结果：

| 检查 | 结果 |
| --- | --- |
| LLVM 回归测试文件 | 16/16 PASS，包括多个内嵌正向/拒绝场景 |
| 外部对象拒绝测试 | 6/6 PASS |
| 手写 IR 接入 | OFFLINE_PASS |
| FlyDSL 接入 | OFFLINE_PASS |
| 两个最终 kernel 的 VGPR / SGPR | 均为 96 / 66 |
| private / scratch / LDS | 均为 0 |
| 普通 spill / SGPR ABI lane save / ABI memory save | 均为 0 |
| 每个 caller 的真实设备调用 | 2 |
| HIP host | 已编译 |
| gfx1250 GPU 执行 | NOT_RUN；当前 GPU 为 gfx1100 |

关键负测包括：参数重叠、宽度不匹配、返回地址冲突、资源越界、SGPR divergent 输入、已知 divergent 调用路径、未知/递归调用、真实 VGPR spill、以及 **private=0 但 SGPR lane spill=1**。

后端报告 `checked` 表示编译模块与声明契约通过检查。LLVM 无法读取尚未交给链接器的 `.co`，所以完整流程还要验证对象身份、寄存器使用、受限指令、最终 descriptor 和链接后函数字节。示例集成已执行这些检查。

## 8. 实现位置与当前限制

LLVM 核心文件，均在独立源码目录的 `llvm/` 下：

| 文件 | 作用 |
| --- | --- |
| `lib/Target/AMDGPU/AMDGPUAsmCallContract.{h,cpp}` | 契约解析、固定位置、完整保持 mask |
| `lib/Target/AMDGPU/SIISelLowering.cpp` | SDAG 调用/返回 lowering、uniformity/full-wave 前提、资源预算 |
| `lib/Target/AMDGPU/AMDGPUCallLowering.cpp` | GlobalISel 明确拒绝当前接口 |
| `lib/Target/AMDGPU/AMDGPUResourceUsageAnalysis.cpp` | 独立 callee 资源计数合并 |
| `lib/Target/AMDGPU/AMDGPUAsmPrinter.{h,cpp}` | 最终严格策略验证与 JSON 报告 |
| `test/CodeGen/AMDGPU/asm-call-contract*.ll` | 固定参数、返回、mask 与非法契约测试 |
| `test/CodeGen/AMDGPU/asm-contract-no-spill.ll` | spill/private/调用图负测 |
| `docs/AMDGPUExternalAsmContract.rst` | 实际 ABI 接口说明 |
| `docs/AMDGPUAsmStrictPolicies.rst` | 严格策略语义与报告说明 |

当前范围是 **gfx1250 / wave32 / SelectionDAG / 直接静态叶子 ASM 调用**。不支持间接调用、动态 VGPR 分配、LLVM IR wrapper 定义、隐式栈参数。callee 需保持约定的执行状态，无 private/LDS；示例对象审计只接受限定的线性指令集合。

callee 资源范围会在调用降低时检查预算，并参与最终资源合并；尚未接入全部 occupancy 调度启发式。严格模式可以拒绝启发式分配失败的程序，不承诺所有理论上可无 spill 的程序都能编译。

本次没有替换真实 ATOM projection 中的 dq_convert，也没有声称已经验证任意黑盒 `.co`。下一步可以复用已有 dq_convert 适配，扩充对象审计覆盖，然后通过该正式后端边界接入真实 Mono 单测。

## 9. 在其他机器重建

需要 Git、CMake、C/C++ 编译器、Ninja 和 Python。可把 Ninja/lit 安装到独立环境：

```bash
python3 -m venv /home/feifei/repo/llvm-project-asm-contract-tools
/home/feifei/repo/llvm-project-asm-contract-tools/bin/python -m pip install ninja lit

cd /home/feifei/repo/ATOM/llvm_asm_contract
python3 build_llvm.py --jobs 5
./run.sh --build-only --python /path/to/flydsl-env/bin/python
```

若默认源码目录不存在，脚本拉取 [SOURCE.json](SOURCE.json) 指定的提交，应用 [llvm.patch](llvm.patch)，仅构建 AMDGPU 和所需 LLVM/LLD 工具。若已经存在，脚本检查基准和补丁状态，不会 reset 用户源码。

可以用 `--source`、`--build`、`--cc`、`--cxx`、`--ninja` 指定其他路径。修改源码后用同一脚本增量构建；开发中的补丁尚未重新导出时，可显式使用 `--skip-patch`。

已安装 ROCm 的编译器用于构建 LLVM 自身，最终 kernel 则由新构建的 llc/llvm-mc/lld 生成。ROCm runtime、HIP headers 和 gfx1250 驱动只在 host 构建/硬件执行阶段需要。
