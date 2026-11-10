# gfx1250 Mono：独立 ASM 设备函数 + 调用点 regmask

本目录在与 `mono_test10` 相同的单 token Mono 单测中，采用 `callee_test01` 的方法：
**ASM 独立汇编成 `.co`，调用方生成真实设备函数 call，在寄存器分配前缩小该调用点的
call-preserved regmask，然后链接为一个可启动的 Mono `.co`。**

当前状态：**已在 gfx1250 上用 `./run.sh` 完整通过。** 环境为 ROCm 7.16、
AMD clang 23.0.0git（`d177931e65e6`）、FlyDSL 0.4.1。9 组 native/lowctx A/B 逐位一致，
18 次融合 launch，1008 次 CTA 级 ASM 调用。结果见“gfx1250 运行结果”。

## 一键运行

在具备 gfx1250、ROCm PyTorch、支持 `rocdl.WMMAScale` 的 AITER/FlyDSL 的机器上：

```bash
cd /home/feifei/repo/ATOM/mono_test01
./run.sh
```

```bash
./run.sh --device 1
./run.sh --cases pattern --repeat 1
./run.sh --llvm-bin /opt/rocm/llvm/bin
PYTHON=/path/to/python MONO_TEST_TIMEOUT_SECONDS=1800 ./run.sh
```

工具链固定为 ROCm LLVM 提交 `d177931e65e6057dca59f1c5b95e643d29876db3`（`callee_test01`
原先固定的是 `7b800a19`）。需要 `clang++`、`llc`、`opt`、`llvm-dis`、`ld.lld`、
`llvm-objdump`。寄存器表从所选 `llc` 的 ELF 符号表读取，因此 stripped 或布局不同的
工具会被拒绝。换 LLVM 版本时必须同时更新 `callsite_regmask.py` 的 `LLVM_COMMIT`，
并让下文的 MIR 往返检查重新通过，不能跳过检查。

**`llc` 的来源。** ROCm 7.16 的 Python wheel 不带 `llc`。所选 LLVM 目录缺少 `llc` 时，
[build_llc.py](build_llc.py) 会用 [tools/llc](tools/llc) 中同一提交的 `llvm/tools/llc`
源码（未修改，SHA256 记录在 `SOURCE.json`），静态链接到 ROCm devel 包
（`_rocm_sdk_devel/lib/llvm`）的头文件和静态库，生成 `build/llvm-bin/llc`。约 10 秒，
按源码和工具链摘要缓存。其余工具以符号链接指向原安装。构建前要求头文件
`VCSRevision.h`、`clang++ --version` 和 `SOURCE.json` 的提交号三者一致。
脚本不下载、安装或改写系统编译器，也不需要外部 `mlir-opt/mlir-translate`。

另需 FlyDSL（已验证 0.4.1）提供以下接口：

- `flydsl.compiler.jit_function.MlirCompiler.compile(module, *, arch, func_name, link_libs)`，
  以及其内部使用的 `get_backend`、`CompilationContext.get_compile_hints`、
  `lower_compile_hints` 和 `_pipeline_fragments_for_mode`；
- `CompilationContext.get_current()` 和 `gpu_module_body`；
- 内置 ROCDL serializer 的 `gpu-module-to-binary{format=llvm}`；
- 配套 MLIR Python bindings、LLVM dialect 和 `llvm.call` 的 `convergent` 属性。

本地 codegen hook 按这些接口编写，并在运行时检查签名。不兼容会报告错误，不会退回普通
regmask。hook 按 `compile` 的原有步骤准备 module 和 pass 流水线，只替换最后的机器码生成。

## 替换的步骤

供应方仍是 `fmha_bwd_hd64_dq_convert_bf16`，仅执行 FP32→BF16 转换和 64×64 tile
布局整理。本目录替换 **WQKV 的 `bf16_round(total)`**，保留原 WQKV 矩阵乘和累加：

```text
projection：256 CTA × 256 threads，wave32
  slice
  RMSNorm / FP8
  WQKV：原 WMMA → 原八路 FP32 累加
       → 写入本任务的输入 tile
       → wait + CTA barrier
       → call mono_dq_convert_lowctx(args, tid)
       → wait + CTA barrier
       → 从 ASM 输出读取 BF16，转换成 FP32 表示
       → 用原 task / mailbox 上下文发布 QKV
```

ASM 后不再做第二次 BF16 舍入。ASM 不是整个 WQKV GEMM 的替代品。
`task`、`tid`、输出地址、mailbox 等状态跨越调用，结果还要被后续 Mono 代码使用。
所有八个物理 wave 都到达调用点；被调函数内部让 wave 4～7 直接返回。
`feeds_index=True` 只写出 normed/NB 供校验，不加入 indexer。

每任务 16 个有效结果用一个完整 64×64 tile 转换。112 个任务分别有独立输入、输出、
240 字节参数记录，以及 tile 两侧各 256 字节 guard。这是接入正确性演示，有明显额外
访存和转换开销，没有性能提升结论。完整输入布局与参数见 [asm/README.md](asm/README.md)。

## 从 projection 到实际设备调用

```text
projection(...)                            projection_asm.py
  └─ stage_wqkv_asm(matrix, task, ops, dq_args)
       └─ invoke_dq_convert(record, tid)     dq_device.py：生成 IR 的 Python helper
            └─ llvm.call @mono_dq_convert_lowctx(ptr, i32)
                 ↓ LLVM instruction selection
               SI_CALL ..., @mono_dq_convert_lowctx, csr_amdgpu, ...
                 ↓ callsite_regmask.py（寄存器分配之前）
               SI_CALL ..., @mono_dq_convert_lowctx, CustomRegMask(...), ...
                 ↓ LLVM 分配寄存器、处理 spill、生成指令
               s_swappc_b64 s[30:31], ...       （gfx1250 反汇编为 s_swap_pc_i64）
                 ↓ 独立汇编函数
               mono_dq_convert_lowctx:
                 ... 参数桥接、ASM 转换 ...
                 s_setpc_b64 s[30:31]           （gfx1250 反汇编为 s_set_pc_i64）
```

`dq_device.py` 在 GPU module 中建立外部 `llvm.func` 声明，并发出真实 `llvm.call`。
声明/调用标记 convergent，声明还含 noinline、noduplicate、nounwind；不会给它标记
readonly/readnone。C++ 对照声明在 [dq_convert_api.h](asm/dq_convert_api.h)，FlyDSL
不 include 这个头文件。

该文件仍有用于等待的短 inline asm，以及空字符串的资源声明 `~{v69},~{s48}`。
空声明让编译器把供应方的资源下限计入最终 kernel；它既不是资源上限，也不是调用点
的保持掩码。**算子指令全部来自独立 `.s/.co`，不生成 `.inc`，不嵌入 `.long`。**

## 保留集合与 ASM 重命名

与 `callee_test01` 一样，从默认 `CSR_AMDGPU` 删除所有包含 v≥64 或 s≥40 的保持位，
包括半寄存器和 tuple 别名，保留默认非 GPR 位。不是将所有低寄存器升级为 callee-saved。

| 类型 | 调用点承诺保持的普通编号寄存器 |
| --- | --- |
| VGPR | v40～v47、v56～v63，共 16 个 |
| SGPR | s30～s39，共 10 个 |

s30:s31 是返回地址，s32/s33/s34 涉及 SP/FP/BP，不能把这 10 个 SGPR 都视为可自由
保存业务值的空间。限制的是直接由寄存器保持的跨调用上下文，其他阶段仍可使用高寄存器。
LLVM 可以产生搬运、重算和 scratch spill/reload，不承诺零 scratch。

供应方原始 ASM 会写 s30～s38 和 v40～v45，直接链接即使缩小 regmask 也不正确。
本目录选择重命名到未使用、且新 ABI 不保证保持的寄存器：

| 原始寄存器 | 适配后 | 原因 |
| --- | --- | --- |
| s30～s38 | s40～s48 | 避开返回地址、栈指针和低 SGPR 保持区 |
| v40～v45 | v64～v69 | 避开低 VGPR 保持区 |

保留集合完全不被写入，因此被调函数不需要为它们添加保存/恢复代码，也不需要 private
栈帧。MODE 低 8 位仍在函数内部保存到 caller-clobbered s5，返回前恢复；EXEC 要求
整 wave 进入并恢复 full wave32。VCC、M0、TTMP、s30～s39 不被改写。

没有复制 `callee_test01` 为测试而写满 v64～v255/s40～s105 的人工污染指令。
这里测试实际供应方：资源下限是 70 VGPR、49 个编号 SGPR，且供应方 LDS/private 为 0。
最终 Mono 的资源可能更高，须检查包含调用方 spill 的最终 ELF 与 HIP occupancy。

## 完整构建顺序

1. 检查 gfx1250、工具链版本和可读取的 `llc` 寄存器表。
2. `asm/prepare.py` 检查生成器与 `.s` 一致；独立汇编原始 `.s` 做机器码往返检查，
   汇编 `dq_convert.lowctx.s → build/asm/dq_convert.lowctx.co`。
3. 正常编译 native Mono，保存为 `build/native/kernel.co`，作为 A/B 基线。
4. 只在编译 lowctx Mono 期间，`device_codegen.py` 临时接管 FlyDSL 的编译入口；
   原有 FlyDSL lowering 照常执行，末尾改用 `format=llvm` 导出 bitcode。
   它保留 ROCDL 正常的设备库链接、target 属性和 LLVM 优化步骤，没有先生成 kernel 再伪造 call。
5. `callsite_regmask.py` 对 bitcode 删除未用函数，并核对只有目标 kernel 和一个外部 call。
   核对普通 pointer+i32 参数、convergent 等属性和实际 `v0:v1/v2` 隐式使用。
6. 运行默认 llc 流水线和 `-stop-after=finalize-isel`；未改掩码的 MIR 往返必须保持
   调用方指令文本、机器码、重定位记录和 kernel descriptor 一致。
7. 只将目标 `SI_CALL` 的 `csr_amdgpu` 改为筛选后的 `CustomRegMask`。
   把掩码换回后，MIR 必须逐字相同。用 `-start-after=finalize-isel` 继续所有寄存器分配。
8. 汇编调用方，与独立供应方通过 `ld.lld -shared --no-undefined` 链接。
9. 将新链接的 ELF 放进普通 `gpu.binary` 容器，交回 FlyDSL launcher。检查容器内的
   二进制与链接产物逐字节相同；退出该编译作用域即恢复原 FlyDSL Python 方法。
10. 对最终可启动二进制做资源/驻留检查，之后才进行 A/B GPU 测试。

这是与 `callee_test01` 同类的 **MIR 原型**。沿用的已知兼容处理是恢复 MIR 丢失的
`.amdhsa_user_sgpr_count` 和补齐零 named-barrier 资源符号；修正发生在汇编调用方之前。
不复制默认流水线的 VGPR/SGPR/private 计数。任一步往返不一致都会报错。
生产集成更适合在 LLVM 编译进程内实现 pre-RA regmask pass，避免 MIR 序列化。

### 当前工具链的兼容处理

- **MIR 中的 `$vcc_lo`。** wave32 MIR 打印器给 `S_CBRANCH_VCC(N)Z` 和
  `V_DIV_FMAS_F32/F64_e64` 写出 `implicit $vcc_lo`，解析器却要求指令描述中的
  `implicit $vcc`。读回前在 `$vcc_lo` 后补 `implicit undef $vcc`（本次 Mono 中共 32 处：
  8 条分支、24 条 `V_DIV_FMAS_F32`）。undef 使用不产生活跃性；未改掩码的往返仍须与
  默认流水线逐字节一致，这一检查已通过。
- **未使用的 src2 编码。** 原始 ASM 重汇编时，25 条双源 VOP3 指令未使用的 src2 字段
  （第二个 dword bit 26:18）由供应方的 `0` 变为 Clang 23 的 `0x80`。`prepare.py` 逐条比较，
  只放行这一种差异，记录在 `build/asm/resources.json` 的 `reassembly_unused_src2`。
- **反汇编名称与范围。** gfx1250 反汇编使用 `s_swap_pc_i64` / `s_set_pc_i64`，审计接受新旧
  两种拼写。新版 `llvm-objdump --disassemble-symbols` 会继续输出符号后的
  `s_code_end` / `s_nop 0` 填充，审计按 ELF 符号大小截断，并断言截掉的只有填充。
- **`hip_runtime` 模块名冲突。** AITER 导入时会把 `aiter/jit/utils/` 插到 `sys.path` 最前，
  其中的同名文件会遮蔽本目录的 HIP 辅助模块，因此改名为 [mono_hip_runtime.py](mono_hip_runtime.py)。

## 运行时验证

默认 zero/pattern/random 各三次，共 **9 组 A/B、18 次融合 launch、1008 次 CTA 级 ASM 调用**。
两版都用相同输入和独立 CPU oracle，检查 LIN、PMIX、normed/NB、FP8 数据/scale 和 QKV；
所有对应输出必须逐位一致。此外检查完整 112 个 ASM tile 的 BF16 转换、输入 padding、
参数记录不变、所有 guard、mailbox tag、诊断区，以及 QKV 确实来自 ASM 输出。

启动前还验证：供应方无 relocation/descriptor；其符号字节链接前后一致；调用方包含一次
真实 `s_swappc_b64`；供应方通过 `s_setpc_b64` 返回；最终 wave32、资源下限和实际驻留量
都满足测试要求。运行时 launcher 使用的 ELF 摘要必须等于此前检查过的二进制。

寄存器侧使用所选 LLVM 的 machine verifier、pre/post-RA regmask 检查和供应方写集合
检查。**没有把 `callee_test01` 只适用于单基本块的 liveness 检查器套到 Mono 的复杂 CFG，
也没有宣称已获得所有真实活跃物理寄存器的独立报告。** 跨调用上下文的正确性由下面的
GPU A/B 测试验证。

## gfx1250 运行结果

`./run.sh` 在 gfx1250 设备 0 上通过：

| 项目 | native | lowctx |
| --- | --- | --- |
| VGPR / SGPR | 126 / 68 | 257 / 108 |
| spill（VGPR / SGPR） | 0 / 0 | 1 / 16 |
| scratch | 0 | 16 字节/线程 |
| LDS | 14848 字节 | 14848 字节 |
| 驻留容量 | 4 CTA/CU，共 1024 ≥ 256 | 1 CTA/CU，共 256 = 256 |

缩小 regmask 后，跨调用上下文只能放在 v40～v47、v56～v63、s30～s39 中，其余活跃值由
LLVM 搬运或 spill，因此 lowctx 的资源高于 native。这符合上文“不承诺零 scratch”的预期。
驻留容量刚好等于 256 个 CTA，没有余量；调用方再增加寄存器压力就可能无法全部驻留。

zero/pattern/random 各三次：native 与 lowctx 的所有中间结果及 QKV 逐位一致，112 个 ASM tile
全部校验通过。目标 `SI_CALL` 改用的 `CustomRegMask` 经寄存器分配后仍然保留
（保留 177 个、删除 779 个掩码项）。

## 文件与产物

| 文件 | 用途 |
| --- | --- |
| [run.sh](run.sh)、[run_test.py](run_test.py) | 一键构建与 A/B 单测 |
| [projection_asm.py](mono1250/kernels/projection_asm.py) | 修改后的 Mono 主体与 WQKV stage |
| [dq_device.py](mono1250/kernels/dq_device.py) | 外部函数声明与真实 LLVM call |
| [device_codegen.py](device_codegen.py) | 本进程内的 FlyDSL 编译接入 |
| [callsite_regmask.py](callsite_regmask.py)、[regmask_tables.py](regmask_tables.py) | pre-RA 修改、别名筛选、往返检查和链接 |
| [build_llc.py](build_llc.py)、[tools/llc](tools/llc) | 所选 LLVM 缺少 `llc` 时，用同一提交的源码构建 |
| [dq_convert.original.s](asm/dq_convert.original.s) | 原始 ASM，原样保留 |
| [dq_convert.lowctx.s](asm/dq_convert.lowctx.s) | 重命名寄存器并适配设备 ABI 的 ASM |
| [prepare.py](asm/prepare.py)、[audit.py](asm/audit.py) | 可复现改写、汇编与接口核对 |
| [asm_host.py](asm_host.py) | 每任务 tile/参数/guard 初始化和结果检查 |
| [PARENT_SNAPSHOT.json](PARENT_SNAPSHOT.json) | 来源目录的源码摘要，确认未改动 |
| [ORIGIN_README.md](ORIGIN_README.md) | 保留的原始 Mono 单测说明 |

```text
build/
  run.log / result.json
  llvm-bin/                                # 仅在所选 LLVM 缺少 llc 时生成
    llc / stamp.json / 指向原安装工具的符号链接
  asm/
    dq_convert.original.co
    dq_convert.lowctx.co / dq_convert.lowctx.disasm.txt / resources.json
  native/
    kernel.co / kernel.mlir / kernel.disasm.txt / resources.json
  lowctx/
    origin.mlir / before_binary.mlir / offload.mlir / caller.bc
    caller.codegen.ll / caller.before_regmask.mir / caller.roundtrip.mir
    caller.lowctx.mir / caller.allocated.mir
    caller.default_abi.s / caller.roundtrip.raw.s / caller.lowctx.raw.s
    caller.default.s / caller.default.o
    caller.roundtrip.s / caller.roundtrip.o
    caller.lowctx.s / caller.lowctx.o
    kernel.co / kernel.mlir / kernel.disasm.txt / resources.json
    callsite_regmask.json / boundary.json
  cache/
```

默认 ABI 和 MIR 往返对象仅供检查，不能与这个自定义 ABI 供应方组成可执行测试。
运行脚本只加载最终 `lowctx/kernel.co`。所有新增/运行文件留在本目录，原始 ATOM、
`mono_test_origin`、`mono_test10`、`callee_test01` 均不需要修改。

只重新生成 `.s`、不编译时：

```bash
python3 asm/prepare.py --source-only
```
