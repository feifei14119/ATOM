# gfx1250 Mono：通过 inline `.long` 接入 dq_convert ASM

本目录复制自 `../mono_test_origin`，保留原始 Mono 作为 A/B 基线，同时增加一条真正嵌入 ASM 的 Mono 路径。外层 ATOM、`mono_test_origin`、`callee_test10` 和 `mono_read` 均不需要修改。

**当前状态：已编写并做静态检查，尚未编译、运行单测或进行 gfx1250 真机验证。** 已生成并保留原始/修改后的 `.s`；`.co`、`.inc` 和最终 Mono 二进制会在目标机器运行脚本时构建。原单测本身也尚未经过真机验证，A/B 的两条路径都会先接受资源检查和 CPU 数值校验。

## 一键运行

在 gfx1250 机器的 ROCm / PyTorch / AITER / FlyDSL 环境中：

```bash
cd /home/feifei/repo/ATOM/mono_test10
./run.sh
```

```bash
./run.sh --device 1
./run.sh --cases pattern --repeat 1
./run.sh --llvm-bin /opt/rocm/llvm/bin
PYTHON=/path/to/venv/bin/python MONO_TEST_TIMEOUT_SECONDS=1800 ./run.sh
```

默认测试 `zero/pattern/random` 三类输入，各重复三次：**9 组 A/B、18 次融合 kernel launch、1008 次 CTA 级 ASM 执行**。每组用相同输入分别运行 native 和 inline 两个 Mono，每条路径都是一次融合 launch。供应方 ASM 不作为另一个 GPU kernel 启动。

需使用支持 gfx1250 的 ROCm `clang++/llvm-objdump`，以及具备 `rocdl.WMMAScale` 的 FlyDSL 和对应 AITER。其他环境要求见复制保留的 [原单测说明](ORIGIN_README.md)。脚本不自动安装依赖、下载源码或切换 Git 分支；复制整个本目录即可搬到其他机器。

## 替换了什么

来源 ASM 为 `mono_read/mono_test1/atom` 中的 `fmha_bwd_hd64_dq_convert_bf16`。它执行 **FP32→BF16 转换和 tile 布局整理**，不执行 WQKV 矩阵乘。

本次替换的是原 `stage_wqkv_c1()` 的 `bf16_round(total)`：

```text
原始 Mono：
slice → RMSNorm/FP8 → WQKV WMMA → FP32 累加 → bf16_round → 发布 QKV

ASM Mono：
slice → RMSNorm/FP8 → 同样的 WQKV WMMA → 同样的 FP32 累加
    → 写 CTA 独立的 packed FP32 tile
    → wait + 全 CTA barrier
    → inline .long 执行 dq_convert
    → wait + 全 CTA barrier
    → 读取 ASM 的 BF16 输出、转回 FP32 表示
    → 使用原 task/上下文继续发布 QKV mailbox
```

ASM 后没有再调用 `bf16_round`。后续 QKV 数值来自供应方输出缓冲区，CPU 会检查这一点。`task`、`tid`、输出指针和 mailbox 上下文在 ASM 后仍然使用，因而能验证跨边界上下文的保留。

主体仍为单 token、256 CTA、每 CTA 256 线程、wave32。slice 和 norm 完全复用基线 stage。`feeds_index=True` 仍只用于输出 normed/NB 供校验，没有增加 indexer。

## 关键文件

| 文件 | 用途 |
| --- | --- |
| [run.sh](run.sh)、[run_test.py](run_test.py) | 一键入口、构建两条路径、资源检查和 A/B 数值测试 |
| [projection_asm.py](mono1250/kernels/projection_asm.py) | **接入后的 Mono 主体**，以及 `stage_wqkv_asm()` |
| [dq_inline.py](mono1250/kernels/dq_inline.py) | **真正的 inline asm 边界**：三个固定输入、`.long`、完整 clobber |
| [reference_projection.py](mono1250/kernels/reference_projection.py) | 未改写的原始 Mono / WQKV stage，作为 native 基线 |
| [asm_host.py](asm_host.py) | 每任务参数块、输入布局、完整 ASM tile 与后续 mailbox 校验 |
| [reference.py](reference.py) | 与原单测相同的独立 CPU 数值参考 |
| [dq_convert.original.s](asm/dq_convert.original.s) | **原始独立 ASM kernel，原样保留** |
| [dq_convert.inline.s](asm/dq_convert.inline.s) | **修改后的可嵌入 ASM，单独保留** |
| [prepare.py](asm/prepare.py) | 原始 `.s` 到适配 `.s` 的可复现生成器、目标机汇编和 `.inc` 导出 |
| [audit.py](asm/audit.py) | 寄存器/状态契约、ELF 符号、`.inc` 和最终嵌入字节校验 |
| [ASM 接口说明](asm/README.md) | 参数、clobber、原始汇编改写清单 |
| [ORIGIN_SNAPSHOT.json](ORIGIN_SNAPSHOT.json) | 复制时 `mono_test_origin` 的逐文件 SHA-256 |
| [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) | 固定 PR `7c925f72` 的 18 个来源模块清单 |

## 与 callee_test10 相同的接法

采用的是其 **“可重定位目标提取指令 → inline `.long` + 固定寄存器输入 + clobber”** 方法。寄存器集合按 dq_convert 实际写集合指定；没有把 gfx1100 测试中人为污染 v64 以上的行为搬过来。

```text
asm/dq_convert.original.s
    └── 已生成 asm/dq_convert.inline.s，保留原件

目标机器执行 run.sh：
    original.s → build/asm/dq_convert.original.co（原始往返检查）
    inline.s   → build/asm/dq_convert.inline.co（ET_REL）
                         ↓ 提取完整、有 size 的符号，检查无 relocation
                  dq_convert.inline.words.inc + .bin + contract
                         ↓ 作为 LLVM inline asm 输入
                  FlyDSL/MLIR → 正常 LLVM 寄存器分配 → inline/kernel.co
```

`dq_inline.py` 发出等价于 C++ `asm volatile` 的 `llvm.inline_asm(..., has_side_effects=True)`：

```text
输入：{s[0:1]}, {v0}, {s24}
污染：~{s2} … ~{s23}, ~{s25} … ~{s29}, ~{s40} … ~{s48},
      ~{v4} … ~{v45}, ~{scc}, ~{memory}
```

`.long` 在编译过程中直接进入最终 Mono 的 `.text`。没有覆盖已生成二进制的指令，没有把提取用 `.co` 链接为 device 函数，也没有设置 VGPR/SGPR 数量上限、修改 MIR regmask 或补丁修改 descriptor。

编译器看到这些 clobber 后，可以为跨边界活跃值选择其他寄存器、搬运或 spill。这里允许 scratch，并对**最终包含 ASM 的完整二进制**重新做 HIP occupancy 检查。不存在“片段本身不使用 scratch，所以最终 Mono 必然不使用 scratch”的保证。

## 每个 WQKV 任务的 tile

原 WQKV 有 112 个任务，每任务输出 16 个数。供应方 ASM 固定转换完整的 64×64 tile，因此每个任务分别分配：

- 16 KiB packed FP32 输入；
- 8 KiB 行主序 BF16 输出；
- 240 字节 `DqConvertArgs`；
- 每个输入/输出 tile 前后各 256 字节 guard。

112 个参数块组成 GPU 全局表，作为 ASM Mono 的**第 15 个指针参数**传入。设备侧按 `dq_args + task*240` 取本任务记录，原有 14 个参数的顺序保持不变。

16 个有效值放在逻辑 tile 的第 0 行、第 0～15 列；这些位置恰好也是供应方 packed 布局的前 16 个位置。其余位置由 host 填入随 task/seed 变化的有限数值，用于检查完整 tile 的转换和布局。进入 kernel 前，有效槽填 NaN，必须由 WQKV 的 FP32 结果覆盖。

输入、输出 tile 和参数表均采用 uncached GPU 分配。生产者写输入时采用 device-scope store，各 wave 等待自己的 store 完成后再进行 CTA barrier。ASM 内等待其读写完成，返回后再次全 CTA 汇合，然后读取输出并沿原 tagged mailbox 协议发布。

所有 8 个 wave 都执行 inline 边界；`.s` 内部让 wave 4～7 跳过转换体，wave 0～3 完成完整 tile。**不能把 ASM 调用放在 `tid < 16` 的条件中。** `tid < 16` 仅用于前面的有效输入写入和后面的 mailbox 发布。

为了验证接入而为每 16 个有效结果转换 4096 个元素，会增加明显的访存和转换开销。此版本是流程/正确性测试，不是性能优化方案。

## 构建后和真机执行时检查什么

在启动 GPU 前：

1. 原始 `.s` 的摘要和改写清单、真实写寄存器集合、固定输入只读、EXEC/MODE 恢复。
2. 原始 `.s` 重汇编与注释机器码一致；适配 `.co` 无重定位；`.inc` 与完整符号的机器码逐字节一致。
3. native/inline 两个 Mono 都是 wave32，实际驻留容量均至少覆盖 256 CTA。
4. inline Mono 的目标函数中恰好存在一份完整片段，保持 64 字节对齐，资源描述覆盖片段使用的最高 VGPR/SGPR。

每组 A/B 执行后：

- 两条路径都接受原 CPU oracle 对 LIN、PMIX、normed/NB、FP8 量化和 QKV 的校验。
- 所有对应中间结果及 QKV 的 native/inline 字节必须一致。
- 112 个完整 tile 共 458752 个 BF16 结果，逐位等于各自实际 FP32 输入的 CPU 转换。
- 每个 QKV payload 必须等于 ASM tile 中的对应 BF16 值，证明结果被后续 Mono 代码使用。
- 参数表和输入 padding 不变，全部 tile guard / 普通 buffer guard 不变，mailbox tag 正确，诊断区全零。

两条路径之间会重新初始化公共缓冲区和 tag，每组重复也使用不同 seed。供应方转换不会作为额外的独立 GPU launch 执行。

## 产物

所有运行产物位于本目录 `build/`：

```text
build/
  run.log / result.json
  asm/
    dq_convert.original.co
    dq_convert.inline.co
    dq_convert.inline.words.inc
    dq_convert.inline.bin
    dq_convert.inline.disasm.txt
    inline_contract.json
  native/
    kernel.co / kernel.mlir / kernel.disasm.txt / resources.json
  inline/
    kernel.co / kernel.mlir / kernel.disasm.txt / resources.json / boundary.json
  failure.pt / mailbox_failure.json    # 对应失败时生成
  cache/
```

`result.json` 记录两条路径的源码/二进制指纹、软件环境、资源、A/B 结果及 ASM tile 校验。只有本次脚本退出码为 0、最后打印 `[PASS]` 且报告状态为 `PASS` 才表示通过；本文没有宣称这些运行检查已经通过。

`asm/prepare.py --source-only` 只重新生成修改后的 `.s`，不会编译。正常 `run.sh` 会检查 `.s` 与生成器一致再构建；修改供应方或改写规则时必须同步复核寄存器和状态契约。复制保留的 C++ `.h` 仅作接口对照，实际 FlyDSL kernel 使用 `dq_inline.py`，不会 `#include` C++ header。
