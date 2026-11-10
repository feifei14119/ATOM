# gfx1250 Mono：标准 ABI 包装器 bitcode + FlyDSL FFI

本目录用与 `mono_test10` 相同的供应方 ASM、相同的 Mono 计算和 A/B 单测，验证
**普通设备函数包装器 → `.bc` → FlyDSL `ffi + link_extern`** 的接入方式。

当前状态：**已在本机离线生成包装器 `.bc`、提取用 ASM `.co/.inc` 和包装函数代码生成
汇编，并通过相应 IR/源代码检查；没有编译整个 FlyDSL Mono，没有运行 GPU 单测。**
本机没有完整目标 FlyDSL/AITER 环境，最终接入与数值正确性留待 gfx1250 机器验证。

方案比较见 [ASM 接入方案文档](../mono_read/ASM_FLYDSL_MONO_INTEGRATION_OPTIONS.zh-CN.md)。

## 一键运行

在 gfx1250、ROCm PyTorch、支持 `rocdl.WMMAScale` 的 AITER/FlyDSL 环境中：

```bash
cd /home/feifei/repo/ATOM/mono_test00
./run.sh
```

```bash
./run.sh --device 1
./run.sh --cases pattern --repeat 1
./run.sh --llvm-bin /opt/rocm/llvm/bin
PYTHON=/path/to/python MONO_TEST_TIMEOUT_SECONDS=1800 ./run.sh
```

默认 zero/pattern/random 各三次，9 组 native/FFI A/B、18 次融合 launch、1008 次
CTA 级 ASM 执行。每个版本每次只启动一个 Mono kernel，包装函数没有单独的 GPU launch。

只重新构建包装器，不运行 GPU：

```bash
python3 build_wrapper.py --llvm-bin /opt/rocm/llvm/bin
```

需要 ROCm LLVM 的 `clang++`、`opt`、`llvm-dis`、`llvm-objdump`，以及 FlyDSL 提供
`flydsl.expr.extern.ffi`、`flydsl.compiler.extern_link.link_extern`。包装器的 bitcode
必须兼容 FlyDSL 内置 LLVM。没有沿用 test01 的 LLVM 提交白名单或 MIR 表布局依赖，
但也不保证任意 LLVM/FlyDSL 版本组合都能互读 bitcode。

脚本清空 `FLYDSL_COMPILE_LLVM_DIR`，使用 FlyDSL 自己的外部 bitcode 链接路径；不启用
其另一条 external codegen 模式。不下载或修改已安装依赖，运行产物集中在本目录 `build/`。

## 实际接入链

```text
asm/dq_convert.original.s                 原始独立 kernel，保留
        ↓ prepare.py 的已审计适配
asm/dq_convert.inline.s                   可嵌入片段，保留
        ↓ 离线汇编及完整符号提取
build/asm/dq_convert.inline.co
build/asm/dq_convert.inline.words.inc
        ↓ #include 到 C++ inline asm
asm/dq_convert_inline.h                   固定输入 + 完整 clobber
        ↓ forceinline 到下列包装器
asm/dq_wrapper.cpp                        标准 ABI，noinline + convergent
        ↓ Clang -emit-llvm；opt 仅清理无用 HIP 函数
build/wrapper/dq_wrapper.bc               真正的 LLVM bitcode 函数定义
        ↓ FlyDSL link_extern 注册 bitcode，ffi 生成 llvm.call
Mono IR + wrapper IR
        ↓ FlyDSL 原有链接、优化、寄存器分配、机器码生成
build/ffi/kernel.co                      Mono + 可调用包装函数
```

`.co` 在这里用于提取已经适配的指令；**传给 `link_extern` 的是 `.bc`，没有把 ELF 改扩展名
当成 bitcode**。`.long` 作为字符串保存在包装器 IR 内部，不会重新变回可优化的算子 IR。

本版本没有 `device_codegen.py`、`callsite_regmask.py`、自定义 MIR pass、手工 descriptor
补丁或安装文件修改。最终机器码由 FlyDSL 正常生成；不向已生成的 Mono 二进制中替换指令。

## 从 projection 到 ASM 的调用链

```text
projection(...)                           projection_asm.py
  └─ stage_wqkv_asm(matrix, task, ops, dq_args)
       └─ invoke_dq_convert(record, tid)    dq_ffi.py，构建 IR 的 helper
            └─ stage(args_address, tid)    link_extern(ffi(...), bitcode_path=...)
                 └─ llvm.call @mono_dq_convert_wrapper(i64, i32)
                      ↓ GPU 运行时是真实设备调用
                    mono_dq_convert_wrapper
                      ├─ 编译器生成的 ABI 保存代码
                      ├─ 准备 s0:s1 / v0 / s24
                      ├─ .long ASM 片段
                      └─ 编译器生成的恢复和返回代码
```

FlyDSL 侧的核心声明在 [dq_ffi.py](mono1250/kernels/dq_ffi.py)：

```python
stage = link_extern(
    ffi('mono_dq_convert_wrapper', ['uint64', 'uint32'], 'void', is_pure=False),
    bitcode_path=str(BITCODE),
)
```

`invoke_dq_convert` 只负责调用这个对象，并给 FFI 刚生成的 `llvm.call` 补上 `convergent`
属性。当前 FFI 没有提供对应参数；这一步在普通 IR 构建阶段完成，不改寄存器分配或后端。
函数定义的 `noinline/convergent` 来自 `.bc`。

## 参数和保存恢复分别在哪里

外部接口：

```cpp
extern "C" __device__ __attribute__((noinline, convergent))
void mono_dq_convert_wrapper(std::uint64_t args_address, std::uint32_t linear_tid);
```

FlyDSL 传入 `uint64 + uint32`。包装器按标准设备 ABI 接收它们，再在内部桥接给供应方：

| 片段输入 | 内容 |
| --- | --- |
| s0:s1 | 统一的 240 字节参数记录地址 |
| v0 | `linear_tid & 31` |
| s24 | `readfirstlane(linear_tid) >> 5` |

地址的 low/high 32 位明确声明为无符号类型；本机 `readfirstlane` builtin 返回 `int`，
若用 `auto` 后直接转成 uint64，低 32 位可能被错误符号扩展。IR 检查包含对此问题的约束。

片段净污染：s2～s23、s25～s29、s40～s48；v4～v45；SCC 和内存。
这些声明在 [dq_convert_inline.h](asm/dq_convert_inline.h) 的 `asm volatile` 中，
会随 `.bc` 交给最终 LLVM 编译器。Mono 本身不用重复声明供应方的 clobber。

| 位置 | 负责的事情 |
| --- | --- |
| Mono 调用方 | 编译器按默认 ABI 管理跨调用活跃值 |
| 标准 ABI wrapper | 编译器为被改写的 callee-saved GPR 生成保存/恢复 |
| ASM 片段 | 内部恢复 EXEC/MODE；避开 s30～s39、VCC、M0、TTMP 和 VGPR bank 位 |

因此，这里既不限制整个 Mono 的 VGPR/SGPR 数量，也不缩小调用点的保持集合。允许 scratch，
最终是否有足够 CTA 驻留容量由最终可执行 ELF 的 HIP occupancy 检查决定。

## 本机离线编译观察

ROCm 7.2 / Clang 22、gfx1250 下已生成并检查：

- [dq_wrapper.bc](build/wrapper/dq_wrapper.bc)：只保留所需包装函数定义及 LLVM intrinsic 声明。
- [dq_wrapper.ll](build/wrapper/dq_wrapper.ll)：普通 `void(i64, i32)`、noinline/convergent、
  完整固定输入和 78 个 GPR clobber；opaque 字节与供应方片段一致。
- [dq_wrapper.codegen.s](build/wrapper/dq_wrapper.codegen.s)：编译器实际生成的 wrapper 汇编。

本次包装器单独代码生成结果：

| 项目 | 观察值 |
| --- | --- |
| VGPR 数量 | 46 |
| 编号 SGPR 数量 | 49 |
| private frame | 32 字节/线程 |
| 静态 scratch store / load 指令数 | 各 7 条 |
| 被片段改写的默认保持寄存器 | v40～v45、s48 |

汇编中，v40～v45 自动保存到 scratch 并恢复；s48 暂存在 v3 的 lane 0，返回前恢复。
额外的 v3 scratch 操作用于保留非活动 lane。该统计是静态指令数，不是实际执行访存次数；
本单测约定 full EXEC，因此不能据此推断每条 spill 指令的活跃 lane 数或性能。

这是 **同一个包装器的离线代码生成证据**，不是最终 Mono 的资源报告。FlyDSL 会用其内置
LLVM 再生成包含包装器的整个模块，最终数值与资源以 `build/ffi` 和 GPU 单测为准。

还发现本机 Clang 对 `noinline` 与 `noduplicate` 使用互斥的属性处理分支：同时写两者，
会丢掉 noinline。因此实现使用 `noinline + convergent`，不通过修改 IR 添加 noinline。
这由生成的 `.ll` 检查确认，避免包装器被意外展开到 Mono。

## 测试的计算范围

与 test10 相同，仍为单 token、256 CTA × 256 threads、wave32：

```text
slice → RMSNorm/FP8 → 原 WQKV WMMA → 原 FP32 累加
      → 写输入 tile → wait + CTA barrier
      → 调用标准 ABI wrapper，执行 dq_convert
      → wait + CTA barrier → 读 BF16 输出 → 发布 QKV mailbox
```

只替换 `bf16_round(total)`，不是用转换算子替代 WQKV 矩阵乘。每个 WQKV task 有 16 个有效
结果，但供应方转换完整 64×64 tile，因此额外步骤和性能开销仍存在。数据与验证复用
`asm_host.py`；112 个任务有独立输入、输出、240 字节参数记录和双侧 guard。

进入 ASM 前，有效槽填 NaN，必须由 GPU WQKV 结果覆盖；其余槽用 task/seed 相关数据填充。
所有 8 个物理 wave 都进入包装器；片段内部让 wave≥4 跳过转换。调用后仍使用原 task、tid、
输出指针和 mailbox 上下文，验证实际跨调用状态的使用。

每组 A/B 两版都接受原 CPU oracle 验证，并逐位比较所有对应中间结果和 QKV。额外检查：

- 112 个完整 tile 的 FP32→BF16 转换和布局；
- QKV payload 来自 ASM 的 BF16 输出；
- tile guard、普通 buffer guard、参数记录和输入 padding；
- mailbox tag、诊断区、重复运行时的初始化；
- 实际 launcher 使用的二进制 SHA256 与驻留检查时一致。

## 启动前的构建检查

1. 原始 ASM 重汇编必须与原注释机器码一致，适配片段无 relocation，指令覆盖完整符号。
2. C++ clobber 与片段实际写集合一致，`.bc` 里的固定输入/clobber/指令字均保留。
3. `.bc` 是标准设备函数定义，noinline/convergent 保留，不带 VGPR/SGPR 上限。
4. 最终 ELF 中有独立 wrapper，ASM 字节恰好在 wrapper 内出现一次，并保持 64 字节对齐；
   Mono 函数本体中不应有这份片段。
5. Mono 有一个真实调用点；wrapper 没有其他设备调用，通过 return-PC 指令返回。
   检查器同时接受 gfx1250 的 `s_swap_pc_i64/s_set_pc_i64` 和旧拼写别名。
6. 最终 ELF 没有未解析符号，wave32、资源下限和 256 CTA 的实际驻留容量满足要求。

最终会导出 wrapper 的编译器生成前后段供阅读。检查器没有声称能符号执行任意 prologue
或推导完整 CFG 中的所有活跃寄存器；实际上下文恢复还要由目标 GPU 的 A/B 单测验证。

## 文件与产物

| 文件 | 用途 |
| --- | --- |
| [run.sh](run.sh)、[run_test.py](run_test.py) | 一键构建和 Mono A/B 单测 |
| [build_wrapper.py](build_wrapper.py) | 离线生成 `.co/.inc/.bc/.ll` 和包装器代码生成汇编 |
| [dq_wrapper.cpp](asm/dq_wrapper.cpp)、[dq_wrapper.h](asm/dq_wrapper.h) | 标准 ABI 包装函数 |
| [dq_convert_inline.h](asm/dq_convert_inline.h) | 包装器内部的固定输入与污染声明 |
| [dq_ffi.py](mono1250/kernels/dq_ffi.py) | FlyDSL 原生 FFI/bitcode 接口 |
| [projection_asm.py](mono1250/kernels/projection_asm.py) | 接入后的 Mono 主体 |
| [dq_convert.original.s](asm/dq_convert.original.s) | 原始独立 ASM kernel |
| [dq_convert.inline.s](asm/dq_convert.inline.s) | 适配后的片段 |
| [wrapper_audit.py](wrapper_audit.py) | C++/IR/最终 ELF 包装边界检查 |
| [PARENT_SNAPSHOT.json](PARENT_SNAPSHOT.json) | 来源目录摘要，用于确认原文件未改 |
| [ORIGIN_README.md](ORIGIN_README.md) | 原始 Mono 单测说明 |

```text
build/
  asm/
    dq_convert.original.co
    dq_convert.inline.co / .bin / .disasm.txt / .words.inc
    inline_contract.json
  wrapper/
    dq_wrapper.raw.bc / dq_wrapper.bc / dq_wrapper.ll
    dq_wrapper.codegen.s / build.json
  native/                                  # 到目标机器编译 Mono 后才生成
    kernel.co / kernel.mlir / kernel.disasm.txt / resources.json
  ffi/                                     # 到目标机器编译 Mono 后才生成
    kernel.co / kernel.mlir / kernel.disasm.txt / resources.json
    mono.function.disasm.txt / wrapper.function.disasm.txt
    wrapper.envelope.txt / boundary.json
  run.log / result.json                     # 运行 run.sh 后才生成
  cache/
```

`build/wrapper/build.json` 的 `BUILT` 仅表示包装器离线构建通过。只有 `run.sh` 返回 0，
并且 `build/result.json` 状态为 `PASS`，才表示 Mono 单测通过。当前还没有该运行结果。
