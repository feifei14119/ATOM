# mono_test30：完整 WQKV 的固定寄存器 ASM 接口

本例把 `mono_test00/01/10` 使用的 **gfx1250、C=1、slice → norm → WQKV** Mono 单测，接到已修改的 LLVM external-ASM contract 后端上。保留 FlyDSL 的 Mono 主体、任务分配和 mailbox 布局；用一个独立 ASM 设备函数承担完整的 WQKV，包括所有 WQKV 输入数据的加载。

已经完成离线编译和静态链接，产物是 `build/kernel.co`。**没有加载、启动 GPU kernel，也没有验证数值结果或性能。** 本目录用于查看真实可编译的接口和调用写法；没有提供 GPU 运行入口。

建议依次阅读：

| 文件 | 看什么 |
| --- | --- |
| [mono_kernel.py](mono_kernel.py) | Mono 主体及 `stage_wqkv_asm(c, task, 0, 1)` 调用点 |
| [stage_api.py](stage_api.py) | 把编译期上下文 `c` 展开成标量参数 |
| [asm/wqkv.contract.json](asm/wqkv.contract.json) | 参数寄存器、污染集合和资源声明 |
| [asm/wqkv.s](asm/wqkv.s) | 直接从约定寄存器读取参数的完整 WQKV 汇编 |
| [compiler.py](compiler.py) | FlyDSL FFI → LLVM 属性 → 修改后的 llc |
| [build_support.py](build_support.py) | 汇编对象检查、链接、资源报告和 LDS 范围检查 |

设计背景见 [ASM_WHOLE_STAGE_REGISTER_ABI_DESIGN.zh-CN.md](../mono_read/ASM_WHOLE_STAGE_REGISTER_ABI_DESIGN.zh-CN.md)；LLVM 原型见 [llvm_asm_contract/README.zh-CN.md](../llvm_asm_contract/README.zh-CN.md)。

## 1. 调用方怎么写

构建 kernel 时注册一次对象契约：

```python
stage_wqkv_asm = WqkvStage(manifest_path)
```

Mono 内保留原来的 `c` 和 plan，调用点是：

```python
enter_stage("k1.wqkv_a")
task = plan.stages["k1.wqkv_a"].first(bid)
if task < 112:
    stage_wqkv_asm(c, task, 0, 1)
```

这里的 `c` 是 Python 生成 IR 时使用的字典。不会把 Python 对象或一个新的 `WqkvStageArgs` 结构写到 global memory。适配器从 `c` 中取出地址、LDS 偏移和标量，将它们作为 LLVM 函数调用参数；寄存器分配时，后端根据契约放入指定物理寄存器。

调用前没有 `gemv_fp8_loads`、`reference_fp8_loads`、`load_x8` 或 `load_x8_words`。ASM 自己完成：

1. FP8 权重和权重 E8M0 scale 的 global load。
2. X8 mailbox 的 payload/tag 轮询与 LDS 拷贝。
3. X8S mailbox 的输入 scale 轮询与打包。
4. WMMA、八个 wave 的部分和归约、BF16 舍入。
5. QKV mailbox 的 payload/tag 写回。

FlyDSL 仍读取原框架的 layer/tag 等控制信息，并执行 slice/norm；这些不属于 WQKV 输入数据的预加载。

## 2. 参数的实际寄存器约定

入口是设备函数 `mono_wqkv_asm`，不是一个独立 dispatch 的 `__global__` kernel。它不从新 kernarg segment 取参。以下表格与 `stage_api.py` 的实参顺序、JSON 中的 `arguments` 顺序一致：

| 参数 | 类型 | 入口寄存器 | 来源与含义 |
| --- | --- | --- | --- |
| `qkv_base` | u64 | **s[2:3]** | 原 QKV mailbox 起始地址 |
| `tag` | u32 | s0 | 原 mailbox 当前 tag |
| `xl_offset` | u32 | s1 | 原 `c["xl"]` 的 LDS 字节偏移，内容由 ASM 准备 |
| `red_offset` | u32 | s4 | 原 `c["red"]` 的 LDS 字节偏移 |
| `task` | u32 | s5 | 原 plan 分配的 N16 任务，0…111 |
| `t0` | u32 | **v4** | token 起点，本例为每个 lane 中的 0 |
| `n` | u32 | s6 | token 数，本例为 1 |
| `weight_base` | u64 | s[8:9] | 原 packed FP8 权重地址 |
| `weight_scale_base` | u64 | s[10:11] | 原权重 E8M0 scale 地址 |
| `input_scale_base` | u64 | s[12:13] | 原 X8S mailbox 地址 |
| `input_base` | u64 | s[14:15] | 原 X8 mailbox 地址 |
| `tid` | u32 | v0 | 当前 CTA 中的 thread_idx.x，0…255 |
| `diag_base` | u64 | s[16:17] | 保留原诊断上下文，本例 ASM 未使用 |
| `failure_base` | u64 | s[18:19] | 原诊断区末尾的全局失败标志地址 |
| `bid` | u32 | s7 | block_idx.x，预留给诊断，本例 ASM 未使用 |
| `poll_limit` | u32 | s22 | 本例轮询次数上限 1,000,000 |

`s[30:31]` 是调用指令写入的返回 PC。ASM 最后用 `s_setpc_b64 s[30:31]` 返回。JSON 的 SGPR 参数均声明 `uniform: true`，要求同一 wave 的值相同；调用方应保证这个语义，属性不是对任意 DSL 数据流的统一性证明。

例如，ASM 用下面的访问形式读取权重和写回 QKV：

```asm
// v12 是 ASM 根据 task、wave 和 lane 计算的字节偏移。
global_load_b128 v[16:19], v12, s[8:9] scope:SCOPE_DEV

// v2 是 ASM 计算的输出字节偏移；v66/v67 是 payload/tag。
global_store_b64 v2, v[66:67], s[2:3] scope:SCOPE_DEV
```

调用方为参数安排寄存器时，仍可能生成 `s_mov` / `v_mov`。固定寄存器绑定保证入口位置，不保证准备参数完全没有复制指令。

## 3. 上下文如何跨调用保持

ASM 在 JSON 中声明：

```json
"clobbers": [
  "v[1:3]", "v[6:67]", "v95",
  "s[20:21]", "s[23:27]", "s40", "s48", "s63", "scc", "vcc"
],
"resources": {
  "vgpr_count": 96,
  "sgpr_count": 64,
  "private_bytes": 0,
  "lds_bytes": 0
}
```

这里两个概念不同：`clobbers` 表示返回时可能改变的寄存器；`vgpr_count` / `sgpr_count` 表示设备函数使用的寄存器编号范围所要求的资源。使用 v95 要求至少覆盖 v0…v95，但不意味着其中每个寄存器都被污染。`lds_bytes: 0` 表示 **callee 没有独立 LDS 分配**；借用的 caller LDS 另在 `borrowed_lds` 中声明。

修改后的 LLVM 在调用 lowering 时建立该调用的 call-preserved regmask。普通寄存器分配器据此安置跨调用值，必要时生成寄存器复制或合法重算。它没有先把所有寄存器保存到内存，也不需要手工规定整个 Mono 只能使用前若干寄存器。

本例给 caller 加上：

```llvm
"amdgpu-no-gpr-spill"
"amdgpu-no-private-memory"
"amdgpu-asm-full-wave-calls"="true"
```

其中最后一项由接入层明确断言：本例的 task 分支只依赖 CTA id，进入 WQKV 的 CTA 全部 256 个线程一起调用。ASM 内有 CTA barrier，仅 wave-uniform 而 CTA 内不一致的调用路径不满足要求。

`no-gpr-spill` / `no-private-memory` 是编译失败条件，不是编译器能无条件满足的保证。如果新 ASM 污染了所有可用于保护跨调用值的寄存器，且这些值无法消除或合法重算，编译必须失败。它不会凭空创造上下文存储空间，也不会自动退回 scratch。

ASM 还必须恢复入口 EXEC，并保持 MODE、m0、ttmp、VGPR bank 状态和 s[30:39] 等约定状态。本例使用两个局部 EXEC save/restore 对、一个最终返回，没有其他调用。源码中最后故意写 v95、s40、s48、s63，使自定义污染约定在反汇编中可见。

### 用真实调用观察活跃值

为避免调用后没有有用值而掩盖上下文问题，本例在原 14 个 launch 参数后增加了第 15 个 `live_state` 地址：

```python
at = live_state + (bid * 256 + tid) * 16
before = snapshot(at)       # volatile load，不能用调用后重新读取替代
old_tag = c["mailbox_tag"]

stage_wqkv_asm(c, task, 0, 1)

record(before ^ 0x2468ace0, at + 4)
record(old_tag, at + 8)
record(tid, at + 12)
```

这是 caller 上下文的观察输入/输出，不是 spill 区，不给 WQKV 搬运参数。每个 thread 预留 16 字节，整个 grid 为 `256 × 256 × 16 = 1,048,576` 字节；仅 WQKV CTAs 访问对应位置。若后续加入运行器，应在每个 slot 的 +0 写入测试输入，并检查 +4/+8/+12 的结果。

当前实际后端报告的 `call_instruction_live_through`：

```text
v5, v69, v70, v72, v73
```

对应旧输入值、旧 tag、tid 和观察缓冲区地址，全部位于 callee 不污染的寄存器中。普通的 SGPR 值广播到 VGPR，例如 tag 的 `v_mov`，与通过 `v_writelane` 保存 SGPR spill 不同。后端报告的 SGPR lane-save 和 spill 计数都为 0。

因此本例是“LLVM 根据调用契约维护上下文”的实例，但当前具体分配 **不需要内存保存/恢复代码**。以上具体编号是本次构建的结果；修改代码后应重新查看报告。

## 4. 与原 C1 测试的对应关系

| 项目 | 本例 |
| --- | --- |
| C | 1 |
| grid / block | 256 CTAs / 256 threads，wave32 |
| slice | 原 `stage_slice_c1`，160 个任务 |
| norm | 原 `stage_norm_c1`，CTA 168 的一个任务 |
| WQKV | 112 个 N16 任务，`task=(bid-176) mod 256` |
| WQKV 输入 / 输出 | HIDDEN=5120，QKV_ROWS=1792 |
| K 分配 | 8 个 wave，各处理 `w, w+8, …, w+32` 共 5 个 K128 步 |
| LDS | 保留原 `Smem` 和 `StageLds` union，共 14,848 字节 |
| global mailbox | 保留原 pair 布局，每个元素为 payload/tag 共 8 字节 |

本例新写的 `asm/wqkv.s` 以现有 reference WQKV 的布局和计算为依据，承担完整 WQKV。旧 `mono_test00/01/10` 的 `dq_convert` 接入对象没有实现这一完整 stage；本例没有把那个转换函数称为完整 WQKV。

实际编译的 LDS 参数为：

```text
s1 = 0       → xl  使用 [0, 5120)
s4 = 12800   → red 使用 [12800, 13312)
caller descriptor 覆盖 [0, 14848)
```

适配器传的是 AS3 指针转出的 LDS 字节偏移，LLVM 仍拥有两块分配。`xl` 所在的 union 和 `red` 分配相互独立。构建脚本检查 IR 分配大小、调用处实际常量偏移、对齐和范围；若该已知布局变化，检查会拒绝生成成功结果。它不是任意 ASM 的 LDS 别名或内存访问证明。

原框架名为 `scratch` 的 launch 参数是 **global mailbox 工作区地址**，与这里要求禁止的 AMDGPU private/scratch 寄存器 spill 内存不同。保留它符合零 private/scratch 的要求。

## 5. 编译流程与产物

在仓库根目录运行：

```bash
./mono_test30/run.sh --build-only
```

省略 `--build-only` 也始终只编译。默认使用已有的 `mono_test20/build/venv/bin/python`（FlyDSL 0.4.1）和 `/home/feifei/repo/llvm-project-asm-contract/build-contract/bin`。可以指定兼容环境：

```bash
PYTHON=/path/to/python ./mono_test30/run.sh --build-only \
  --llvm-bin /path/to/patched-llvm/bin \
  --output /path/to/output
```

流程：

1. `llvm-mc` 把 `asm/wqkv.s` 编译成独立的 `build/stage/wqkv.co`，这是可重定位 ET_REL 设备函数对象。
2. 反汇编检查符号大小、分支落点、寄存器声明、资源符号和对象 hash；运行 CPU 整数地址布局检查。
3. `WqkvStage` 通过本地 `AsmFFI` 生成带契约的真实 `llvm.call`，并记录原 plan 的 x8/x8s poll、qkv put 效果。
4. FlyDSL 生成 MLIR/LLVM bitcode；在寄存器分配前，把固定寄存器、污染集合、资源数量及严格策略写入 LLVM 属性。
5. 修改后的 `llc` 编译 `caller.bc → caller.o`，同时生成资源与跨调用活跃值报告；另外输出可读的 `caller.s`。
6. `ld.lld -shared --no-undefined` 链接 `caller.o + wqkv.co → kernel.co`，检查 callee 的字节在链接前后相同。
7. 检查最终 metadata、实际 LDS 参数及零 spill/private 条件；编译 hook 在 GPU launch 前主动结束。

本例没有修改 MIR，没有在最终 Mono 二进制里替换指令，也没有使用 `.long` 的 inline asm 接入。callee 是实际的独立符号调用，反汇编中有一次 `s_swap_pc_i64`（`s_swappc_b64` 的 gfx1250 命名形式），返回后继续执行 caller 的观察输出代码。

最值得查看的构建产物：

| 文件 | 内容 |
| --- | --- |
| `build/caller.ll` | `declare void @mono_wqkv_asm`、真实 call 和全部 LLVM 属性 |
| `build/caller.s` | 参数准备、一次 swap-PC 调用及调用后代码 |
| `build/stage/wqkv.co` | 独立 ASM 可重定位对象 |
| `build/stage/wqkv.dis.s` | ASM 对象的完整反汇编 |
| `build/kernel.co` | 最终链接的 Mono code object |
| `build/kernel.dis.s` | 包括 caller 和 callee 的反汇编 |
| `build/backend.resources.json` | 编译器的 regmask、live-through 和 spill/private 报告 |
| `build/stage/wqkv.audit.json` | 对象检查和 CPU 地址公式检查 |
| `build/result.json` | 汇总结果、实际 LDS 范围、是否执行 GPU |

## 6. 本次离线验证的结果与边界

2026-11-11，执行 `./mono_test30/run.sh --build-only`：

| 检查 | 结果 |
| --- | --- |
| 状态 | `OFFLINE_COMPILED` |
| 最终 VGPR / SGPR metadata | 96 / 68 |
| 最终 private segment | 0 字节 |
| 最终 LDS | 14,848 字节 |
| 设备调用数 | 1 |
| SGPR / VGPR spill dwords | 0 / 0 |
| SGPR ABI lane saves / ABI memory saves / WWM spill registers | 0 / 0 / 0 |
| private frame / private access instructions / stack arguments | 0 / 0 / 0 |
| 完整函数对象字节在链接前后保持一致 | 通过 |
| 权重布局检查 | 1,146,880 个 16B load 端点与逻辑 packed W 布局一致 |
| X 拷贝、K 分配、reduction、plan task 覆盖 | 通过 CPU 整数公式检查 |
| GPU 数值 / 性能验证 | **未执行** |

最终 SGPR 的 68 是 LLVM 按 caller、callee 和特殊寄存器规则汇总的 metadata，不能简单等同于 ASM 声明的 64 个编号 SGPR。资源计数不是硬件驻留率或运行时间测量。

**目前修改后的 LLVM 可以完成本例的固定寄存器参数、真实 call-preserved regmask、零 spill/private 策略和资源报告。** 本次没有继续修改 LLVM 核心源码。但为了接入整个 stage，本目录在已有桥接层上增加了 void 返回的 FFI 处理、借用 caller LDS 的约定，以及针对本函数分支/DS/WMMA 的对象检查。原 `llvm_asm_contract` v1 demo 的对象检查仅覆盖无 LDS 的有限线性代码；本例是对已知 C1 stage 的局部扩展，不代表上游 FlyDSL/LLVM 已提供通用、稳定的外部 ASM stage ABI。

其余实际限制：

- 固定 gfx1250/wave32、256 threads、HIDDEN=5120、1792 输出行、`t0=0,n=1`，不支持任意形状、tail 或其他架构。
- 必须 CTA 一致进入含 barrier 的 ASM；完整 EXEC 的断言来自已知调用路径，未提供通用控制流证明。
- 汇编用了保守的 `s_wait_alu 0` 和等待指令，供接口阅读，不作性能承诺。
- ASM 轮询采用最多 1,000,000 次重试与 `s_sleep 64`，超时置原 failure 标志，并以零 payload 继续执行同一组 CTA barrier。它未复刻原 mailbox 的按时间超时和详细诊断记录；保留的 `diag_base` / `bid` 参数暂未使用。
- 地址公式检查不执行指令，不能证明 WMMA 数值、缓存可见性或整条 GPU 同步路径正确；需要另行真机验证。
- 增加了第 15 个 `live_state` 参数，不能直接用旧单测的 14 参数 launcher 加载本二进制。

依赖源码复制在本目录 `mono1250/`、`vendor_aiter/`，来源与 hash 记录在 [SOURCE_SNAPSHOT.json](SOURCE_SNAPSHOT.json)。其中本地 `mono1250/device/ops.py::fresh` 将非空 `v_mov` inline asm 改为无指令的 tied identity 约束 `"", "=v,0"`，使严格后端不再遇到不透明指令文本；这保留数值 identity，但可能改变调度提示。原仓库对应文件未修改。`reference.py` 保留原 CPU 数值参考供后续使用，本次没有运行其 GPU 输出比对。
