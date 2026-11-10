# gfx1250：手写 ASM Mono 主体，复现 mono_test10

本目录保留 `mono_test10` 的计算与校验，新增真正由汇编编写的 GPU 入口
[`mono_kernel.s`](mono_kernel.s)。它负责原 C1 plan 的任务分配和三次阶段调用，
分别调用 FlyDSL 导出的 slice、norm、WQKV 普通设备函数。WQKV 内仍然使用
原 test10 的 **inline `.long` + 固定输入 + 完整 clobber** 执行 dq_convert。

**当前状态：三个版本均已在本机离线编译成功，调度、来源、ABI 边界、资源和 ELF 检查通过；
尚未在 gfx1250 上执行 GPU 数值测试。** 本机设备为 gfx1100/gfx1036，没有把 gfx1250
二进制加载到它们上面。`build/OFFLINE_VALIDATION.json` 是离线检查记录，不能当成 GPU PASS。

原 `mono_test10` 与其他实验目录均未修改。原 test10 文档保存在
[TEST10_README.md](TEST10_README.md)，其中的实机通过记录属于父实验。

## 1. 运行方式

在 gfx1250 机器、ROCm PyTorch、支持 `rocdl.WMMAScale` 的 FlyDSL 环境中：

```bash
cd /home/feifei/repo/ATOM/mono_test20
./run.sh
```

```bash
./run.sh --device 1
./run.sh --cases pattern --repeat 1
./run.sh --llvm-bin /opt/rocm/llvm/bin
PYTHON=/path/to/python MONO_TEST_TIMEOUT_SECONDS=1800 ./run.sh
```

默认运行三条路径：

| 版本 | 入口主体 | dq_convert 接法 |
| --- | --- | --- |
| native | 原 FlyDSL Mono | 原生 BF16 舍入 |
| inline | 原 test10 FlyDSL Mono | 在 Mono 内 inline `.long` |
| asm_mono | **手写 ASM Mono** | 在导出的 WQKV 设备函数内 inline `.long` |

zero/pattern/random 各三次，共 9 组三路比较、27 次融合 GPU launch。
两个 ASM 版本各执行 1008 次 CTA 级转换，共 2016 次；每条路径每次只启动一个 Mono，
没有为三个阶段额外启动 GPU kernel。测试结束需要 `run.sh` 返回 0 且
`build/result.json` 的 `status` 为 `PASS`，才表示实机通过。

只编译并做 CPU/静态检查，不运行 GPU：

```bash
./run.sh --build-only --llvm-bin /opt/rocm/llvm/bin
```

只构建 ASM 版本：

```bash
python3 build_asm_mono.py --llvm-bin /opt/rocm/llvm/bin
```

脚本不自动安装依赖。需要 Python/PyTorch（离线构建可用 CPU 版）、NumPy、FlyDSL，
以及 gfx1250 工具链的 `clang++`、`llvm-mc`、`llvm-objdump`、`llvm-readelf`、`ld.lld`。
导出器使用 FlyDSL 0.4 风格的 `MlirCompiler.compile(module, *, arch, func_name, link_libs)`，
不兼容的接口会报错，不会退回整个 FlyDSL Mono。

AITER 的三个 FlyDSL helper 原样复制到 [vendor_aiter](vendor_aiter/SOURCE.json)，保留源路径和
SHA256，避免导入 AITER 的其他算子。因此这个副本不需要安装完整 AITER。
本机为离线验证建立的 `build/venv` 使用 CPU PyTorch；目标机应选择自己的 ROCm Python，
不要用这个 CPU 环境运行 GPU 测试。

## 2. 真正的 ASM 调度主体

[mono_kernel.s](mono_kernel.s) 定义唯一的新 GPU 入口 `mono_asm_projection`。
C=1、256 CTA、每 CTA 256 线程、wave32，沿用原计划：

```text
入口：保留 kernarg 地址、物理 bid、tid；初始化设备调用栈偏移

if bid < 160:
    call mono_stage_slice(record, task=bid, bid, tid)

if bid == 168:
    call mono_stage_norm(record, task=0, bid, tid)

task = (bid - 176) & 255
if task < 112:
    call mono_stage_wqkv(record, task, bid, tid)

s_endpgm
```

三段任务数量均小于 256，原 plan 的 stride-256 循环每 CTA 最多执行一次，因此可写成上述
条件分支。`verify_offline.py` 对 256 个 CTA、每个物理 wave 的首尾 lane 检查调度，
与 `C1ReferencePlan` 逐项比较，确认 slice=160、norm=1、WQKV=112。

这里没有把整个原始 Mono 藏进一个被调用函数。ASM 主体确实控制了三个不同阶段的分派。
阶段内部的计算、等待和 mailbox 发布继续复用原 FlyDSL helper。

## 3. 参数与上下文

新入口保持 test10 的 15 个 64 位参数及顺序，kernarg 为 120 字节。
入口的 s0:s1 指向这份参数记录，主体把它保存在 s36:s37，并将该地址传给每个阶段。
各阶段按原字段偏移加载其所需的输入地址；GPU kernarg 在本次 kernel 执行期间有效。

导出的普通设备函数使用统一签名：

```text
void mono_stage_*(uint64 record, uint32 task, uint32 bid, uint32 tid)
```

| 寄存器 | 内容 / 责任 |
| --- | --- |
| v0:v1 | 调用参数 record 地址 |
| v2 | 调用参数 task |
| v3 | 调用参数物理 bid |
| v4 | 调用参数 tid |
| s30:s31 | 标准设备函数返回地址 |
| s32 / s33 / s34 | SP / FP / BP，根入口初始化为 0，根本身无栈帧 |
| s36:s37 | 跨调用的 record 地址，默认 callee-saved |
| s38 | 跨调用的 bid，默认 callee-saved |
| s39 | task，默认 callee-saved |
| v40 | 跨调用的 tid，默认 callee-saved |

这些是当前 AMDGPU 设备 ABI 与本例签名的约定，不是独立 GPU kernel 的参数布局。
主体用 `s_getpc + rel64 + s_swappc` 调用，阶段用 `s_setpc` 返回；gfx1250 工具可能打印为
`s_get_pc_i64 / s_swap_pc_i64 / s_set_pc_i64`。

每个 FlyDSL 阶段都是普通 ABI 函数，LLVM 自动履行它对 callee-saved 的保持责任。
当前 WQKV 会因为内部 `.long` clobber 保存/恢复 v40～v45 和 s48；v40 因而能继续保存主体 tid。
主体不手写这些保存恢复，也不修改调用点 regmask，不限制阶段的 VGPR/SGPR 使用数量。

s36～s39 并不代表所有低 SGPR 都是自由寄存器，s30～s34 仍承担返回和栈状态责任。
阶段的 EXEC/MODE 与 VGPR bank 状态仍须符合普通调用及原 inline 片段契约。

## 4. FlyDSL 阶段怎样导出

[stage_kernels.py](stage_kernels.py) 只组织计算体，不包含主体调度：

- slice 调用原 `stage_slice_c1`。
- norm 调用原 `stage_norm_c1`。
- WQKV 保持 `reference_fp8_loads → reference_load_x8_c1 → stage_wqkv_asm`，
  保留权重预取在输入等待之前的顺序。

构建时先用 `@flyc.kernel` 作为 IR tracing 容器；它不在 GPU 上运行。
[export_stages.py](export_stages.py) 在正常 FlyDSL lowering 之后、LLVM 优化和寄存器分配之前：

1. 删除仅用于 tracing 的 host launcher。
2. 将所有 `rocdl.workitem.id.x / workgroup.id.x`，包括诊断 helper 内的读取，替换为显式参数。
3. 去除 kernel 专属属性，保留外部可见的普通 C calling convention。
4. 设置 `noinline + convergent + nounwind` 和实际 256 线程工作组范围。
5. 拒绝剩余 dispatch/kernarg 隐式依赖，以及阶段自己声明的 LDS/global 对象。
6. 由 FlyDSL 自带 LLVM 生成设备函数 bitcode、汇编和机器码。

因此没有直接跳入一个仍使用 kernel ABI 的入口，也没有在机器码中改写 `s_endpgm` 来冒充
普通设备函数。线程参数在 LLVM 优化之前就是显式参数，避免先按 kernel 参数的 uniform
假设优化、之后再改成 divergent 设备函数参数。

hook 仅存在于当前 Python 进程的阶段导出作用域，结束即恢复；不修改安装的 FlyDSL 文件。

## 5. LDS 与资源

由 ASM 入口一次性分配 14848 字节 LDS，采用和 test10 相同的布局：

```text
[0, 2048)      red[512]
[2048, 14848)  union(slice, wqkv)
  slice: rl @2048，fl @2560
  wqkv:  xl @2048，xsl @7184
```

三个阶段用显式 LDS 地址访问这份空间，不产生三套独立静态 LDS 分配。阶段内 barrier
与 mailbox 语义保持原样；一个 CTA 返回后再复用工作区。

`build_asm_mono.py` 读取实际生成的 `.s` 资源符号，生成 `mono_resources.inc` 和
`mono_metadata.inc`。由于三个阶段均为叶函数、根入口无 private 栈帧，private 大小取阶段
需求的最大值；遇到嵌套调用、动态栈、递归、AGPR 或 named barrier 会明确拒绝，需要扩展契约。
寄存器数覆盖根和全部阶段的实际需求，属于资源声明，不是寄存器分配上限。

本次离线结果（FlyDSL 0.4.1，内置 LLVM 24；ROCm 7.2 LLVM 22 工具参与包装/链接）：

| 项目 | native | 原 inline | ASM 主体 |
| --- | --- | --- | --- |
| VGPR | 126 | 126 | 320 |
| metadata SGPR | 68 | 68 | 66 |
| private，字节/线程 | 0 | 0 | 32 |
| LDS，字节/CTA | 14848 | 14848 | 14848 |

ASM 主体的编号 SGPR 需求为 64，metadata 另计 VCC。独立 ABI 函数会改变寄存器分配，
当前结果不代表比原 inline 快。尚未实测驻留容量或延迟；GPU 运行前会对每个实际二进制
做 HIP occupancy 检查，必须满足当前测试 256 CTA 的驻留要求，否则停止而不启动它。

## 6. 机器码构建与链接

```text
原 dq_convert.original.s → 原适配 dq_convert.inline.s → .co → .long .inc
                                                          ↓
FlyDSL slice / norm / WQKV（WQKV 内含原 .long + clobber）
    ↓ 正常 lowering，然后在 MLIR 中导出普通设备函数
每阶段 stage.bc / stage.s / stage.codegen.co
    ↓ 确认单函数、无重定位、无外部数据、无调用/PC 相对数据引用
提取完整函数 stage.bin → stage.package.s 的 .incbin → stage.o（ET_REL）
                                                           │
手写 mono_kernel.s + 根据阶段需求生成的资源/metadata → mono.o │
                                                           ↓
                                              ld.lld 构建时链接
                                                           ↓
                                         build/asm_mono/kernel.co
```

之所以从 FlyDSL 原生编译产物提取完整函数，是为了使用同一套 LLVM 完成阶段代码生成与汇编：
当前 FlyDSL 的 LLVM 24 bitcode/高 VGPR bank 指令语法不能直接交给本机 LLVM 22。
`stage.codegen.co` 是只有设备函数的临时已链接 ELF，不作为 GPU kernel 启动。

重包装前严格检查没有重定位、外部常量/数据或其他 helper 函数，原始 `stage.s` 全部保留。
包装器只把完整函数字节放入对齐的可重定位 `.text`，不改指令、不插入保存恢复代码。
当前 `.relro_padding` 是链接器附加的非程序数据填充，提取时排除。
如果以后出现外部数据或函数引用，必须改成真正的可重定位导出，不能继续套用本方法。

三个阶段的字节在重包装和最终链接后必须保持一致；唯一需要链接重定位的是手写主体的
三个函数调用目标。检查器直接解析其实际 rel64 指令编码，确认分别指向 slice/norm/WQKV。
最终只有一个 kernel descriptor，dq_convert 片段只存在于 WQKV 函数内。

## 7. 测试与产物

离线检查包括：原目录未改、复制的计算模块除 helper 导入路径外未改、供应方原始/适配
汇编未改、调度与 C1 plan 相同、普通函数边界、函数机器码完整性、调用地址、片段对齐、
资源以及三条路径的实际 kernel descriptor 浮点模式一致。
调度检查会把抽象 callee 的 volatile 寄存器设为垃圾值，检查主体不依赖这些跨调用状态。
这不是 GPU 指令模拟，也不替代实机上下文和数值验证。

实机沿用 test10 的输入、CPU oracle、完整 tile 和 guard 校验，并增加第三条 ASM 主体路径。
各条路径重新初始化相同数据；比较所有中间结果和 QKV 的字节，检查参数不变、padding、
mailbox tag、诊断区，以及 QKV 确实消费 ASM 输出。launcher 使用的二进制摘要必须与
此前检查和驻留评估的二进制一致。ASM 主体通过 HIP `hipModuleLaunchKernel` 直接启动；
native/inline 继续使用原 FlyDSL launcher。

```text
mono_kernel.s                          手写主体
stage_kernels.py / export_stages.py     计算阶段和普通函数导出
build_asm_mono.py / build_all.py        构建与检查
asm_launcher.py / run_test.py          实际加载、三路数值测试
asm/dq_convert.original.s              原始供应方 ASM
asm/dq_convert.inline.s                原 test10 适配 ASM
build/
  asm/                                 原供应方 .co/.bin/.inc
  stages/{slice,norm,wqkv}/
    origin.mlir / lowered.mlir          tracing 和正常 lowering 结果
    device.mlir / stage.bc              普通设备函数定义
    stage.s / stage.codegen.co         FlyDSL 自带 LLVM 生成
    stage.bin / stage.package.s         完整函数提取与包装
    stage.o / stage.disasm.txt          用于链接的目标
  asm_mono/
    mono_resources.inc / mono_metadata.inc
    mono.o / kernel.co / build.json
    mono.function.disasm.txt / kernel.disasm.txt / kernel.elf.txt
  native/ / inline/                     两条原始基线的最终产物
  OFFLINE_VALIDATION.json               离线检查结果
  run.log / result.json                 实机运行后生成
```

`build/asm_mono/build.json: BUILT` 只代表构建与二进制检查成功。
`build/OFFLINE_VALIDATION.json: OFFLINE_CHECKS_PASS` 只代表离线检查成功。
本目录目前没有宣称 `build/result.json: PASS`；这需要在 gfx1250 机器执行 `./run.sh` 后得到。
