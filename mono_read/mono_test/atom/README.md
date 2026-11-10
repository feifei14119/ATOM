# AITER gfx1250 dq_convert：原版反汇编与 Mono 适配目标

本目录已从 AITER 的 `fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co` 恢复可编译汇编，生成 Mono 算子侧的适配版本，并用 ROCm 7.2 LLVM 完成汇编、链接与静态验证。

**用于后续接入的文件是 [dq_convert.mono.co](dq_convert.mono.co)，其中应提取 `mono_dq_convert_stage` 符号的完整 1576 字节。** 该片段有明确的非零 symbol size，没有 `s_endpgm` 或 PC call/return，末尾通过普通分支进入紧接着它的调用方代码。

这次完成的是算子侧准备。真实 ATOM 主体中的编译器可见 clobber、寄存器保存/恢复、LDS 布局和 mailbox 对接仍按[接入方案](../GFX1250_AITER_INTEGRATION_PLAN.md)实施。本机没有 gfx1250 GPU，本目录产物尚未做 gfx1250 运行验证。

## 文件入口

| 文件 | 用途 |
| --- | --- |
| [dq_convert.original.co](dq_convert.original.co) | AITER 原始文件的逐字节副本 |
| [dq_convert.original.disasm.txt](dq_convert.original.disasm.txt) | `llvm-objdump` 原始反汇编输出，包含地址、机器码与填充 |
| [dq_convert.original.s](dq_convert.original.s) | **完整可汇编原版**：可读指令、`.amdhsa_kernel` descriptor、metadata 和原始 code-end 填充 |
| [dq_convert.original.o](dq_convert.original.o) / [dq_convert.roundtrip.co](dq_convert.roundtrip.co) | 原版 `.s` 重新汇编、链接的结果 |
| [dq_convert.mono.s](dq_convert.mono.s) | **完整可汇编适配版**：入口映射、wave gate、stage 出口与独立验证入口 |
| [dq_convert.mono.o](dq_convert.mono.o) / [dq_convert.mono.co](dq_convert.mono.co) | 新的目标文件与 code object |
| [dq_convert.mono.disasm.txt](dq_convert.mono.disasm.txt) | 新 `.co` 的反汇编 |
| [dq_convert.mono.stage.bin](dq_convert.mono.stage.bin) | 从新 `.co` 导出的 1576 B stage 原始机器码 |
| [dq_convert.mono.stage.inc](dq_convert.mono.stage.inc) | 相同 stage 的 `.long` 指令字，可作为后续 inline-asm 模板的片段 |
| [contract.json](contract.json) | 架构、入口、参数、clobber、资源、布局和调用方义务 |
| [verification.json](verification.json) | 字节、descriptor、分支与布局检查结果 |
| [embedding_check.s](embedding_check.s) / [embedding_check.o](embedding_check.o) | 两次嵌入同一片段的静态装配检查；不是可运行的完整 Mono |
| [prepare.py](prepare.py) / [Makefile](Makefile) | 可复现的生成、构建和检查流程 |

`.disasm.txt` 是阅读用的工具输出，`.s` 才是完整的 assembler 输入。

## 编译与复查

```bash
cd /home/feifei/repo/ATOM/mono_test/atom
make
```

核心命令为：

```bash
/opt/rocm/llvm/bin/clang++ --target=amdgcn-amd-amdhsa -mcpu=gfx1250 \
  -x assembler -c dq_convert.mono.s -o dq_convert.mono.o
/opt/rocm/llvm/bin/ld.lld -shared --no-undefined \
  dq_convert.mono.o -o dq_convert.mono.co
python3 prepare.py verify
```

`make` 在源 `.co` 或生成器变化时重新生成汇编；平时直接编辑 `.s` 后运行 `make` 会重新汇编该文件。检查器固定了这次允许的修改范围，进一步改算法/入口时，需要同时更新接口与验证预期。

## 适配版改了什么

1. **供应方 grid x/y/z 置零。** 原始指令体 `+0x64/+0x68/+0x70` 三处，分别改成 `s2=0,s3=0,s4=0`，用 NOP 保持每处长度不变。Mono 传入的 tile 指针已经按真实 CTA 偏移，不能再叠加供应方硬件 block id。
2. **增加 256→128 线程分派。** 通过 TTMP8 读取物理 wave id，wave 0–3 执行转换；wave 4–7 用标量条件分支跳过。没有通过 `EXEC=0` 让后四个 wave 顺序进入会主动打开 EXEC 的供应方代码。
3. **建立 lane 输入。** 执行波从 full EXEC 下用 `v_mbcnt_lo_u32_b32` 得到 `v0=lane_id`，不依赖主体原本放在 `v0` 的值。
4. **转换 kernel 退出。** 原 `s_endpgm` 改成普通分支到完成段，补 `s_wait_loadcnt/storecnt/kmcnt 0`，保证本阶段自己的访存完成；恢复 full EXEC，再分支到片段后继位置。
5. **保留独立验证入口。** `mono_dq_convert_kernel` 包含完整 descriptor/metadata，并在 stage 范围之外保留一个 `s_endpgm`。

原转换主体去掉退出后为 1524 B。只允许 3 处共 20 B 入口区间发生修改，其余 **1504 B 保持逐字节相同**。wave gate 和完成段是额外的适配代码。

## 两个符号的用途

```text
mono_dq_convert_kernel:         独立验证入口，有对应 .kd/metadata
    s_branch mono_dq_convert_stage

mono_dq_convert_stage:          真正应嵌入 Mono 的 1576 B
    wave gate
    适配后的 AITER 指令体
    wait / full EXEC
    s_branch mono_dq_convert_stage_end
mono_dq_convert_stage_end:      不包含在 stage symbol size 内
    s_endpgm                   只供独立入口使用
```

独立验证入口的预定 launch 是 **grid=(1,1,1)、block=(256,1,1)**，参数布局仍为 240 B，处理一个 64×64 tile。其 host launch 尚未在 gfx1250 上执行。

嵌入时，从 `.co` 按 `mono_dq_convert_stage` 的地址和 size 提取，或直接使用已经导出的 `.stage.bin/.stage.inc`。调用方恢复代码要紧接片段最后一个字节：

```asm
; caller: 先保存已由编译器约束的 R_keep，建立 s[0:1] 参数块指针
.include "dq_convert.mono.stage.inc"
; 此处正是片段最后一条 s_branch 的目标
; caller: full-CTA 同步、恢复 R_keep、使用转换结果、继续后继阶段
```

片段内部所有跳转都是相对分支，目标位于片段内部或恰好为其末尾，不需要重定位。已经将同一 `.inc` 在不同地址装配两次，确认两份字节一致、分别到达各自后继。

**`mono_dq_convert_stage` 不是遵循设备函数 call/return ABI 的函数。** 不要用普通 C++ 外部函数调用去链接它；也不要把带独立 `s_endpgm` 的整个 `.text` 直接嵌入 Mono。

## 与编译器边界的连接

stage 的保守破坏集合是 `v0–v45,s0–s47,EXEC_LO,SCC,memory`；TTMP、MODE、M0、VCC 不被本片段改写。这个列表描述算子侧，**不是主体可省略保存的证明**。

后续的 `llvm.inline_asm` 应包住“保存 → 本片段 → 恢复”整个边界，并声明它的**净 clobber**。若要将主体跨边界活跃状态限制到小集合，还需要把允许分配范围中该集合之外的寄存器声明为 clobber，并检查后端生成结果。仅生成新 `.co` 无法约束另一次编译中的寄存器分配。

入口要求完整 256 线程 CTA 收敛到边界、full EXEC、已有操作完成。每个实际 CTA 使用自己的 input/output/参数块。后四个 wave 会先到达 stage 后继，所以调用方必须在消费其他 wave 的结果或复用保存区前完成合适的 CTA 同步。

## 参数与布局

接口沿用 [接入文档第 4 节](../GFX1250_AITER_INTEGRATION_PLAN.md#4-第一步冻结输入并做独立算子基线) 的 240 B 参数块。输入并非普通行主序，目标输出 `Y[r,c]=bf16(X[r,c])` 对应：

```python
sr = 16 * (r // 16) + 8 * ((c // 16) % 2) + r % 8
sc = 32 * (c // 32) + 16 * ((r // 8) % 2) + c % 16
input_fp32[sr * 64 + sc] = X[r * 64 + c]
```

固定 `r,c ∈ [0,64)`、input stride 256 B、output stride 128 B。布局公式已用供应方全部 wave/lane 的实际 load/store 地址进行 4096 元素一一映射验证。

## 已检查的资源与限制

| 项目 | 结果 |
| --- | --- |
| 原版 `.text` 往返 | 2048 B 全部一致，包括 code-end 填充 |
| 原版/适配版 descriptor | 除 entry offset 外，其余 56 B 与供应方逐字节一致 |
| stage 大小 | 1576 B |
| stage 分支 | 3 条直接分支，无 `s_endpgm/getpc/swappc/setpc` |
| 独立验证入口 metadata | 256 线程、wave32、240 B kernarg |
| 供应方与适配器资源 | VGPR=46、SGPR=48、LDS=0、private=0 |
| ELF 重定位 | 最终两个 `.co` 均无未解决重定位 |
| 两次嵌入 | 相同字节，分别到达各自后继 |
| GPU 运行 | 未执行，需要 gfx1250 |

特别注意，原 descriptor 的 **FP32 denorm mode=0**，16/64 位 denorm mode=3；已原样保留。最终嵌入时运行在 Mono 的 FP MODE 下，不能因 standalone descriptor 相同就忽略与 Mono 的模式兼容性。

重新链接改变了 ELF 布局、符号表和 LLVM 的 feature flag 表示，`dq_convert.roundtrip.co` 不是整个文件的逐字节副本；真正的原文件副本是 `dq_convert.original.co`。往返一致性断言针对代码字节和 descriptor 资源字段。最终 ATOM 的总寄存器数、LDS 保存区、private/spill 与驻留仍需单独验证。
