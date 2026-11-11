# ASM 中嵌入 FlyDSL 函数：最小可运行 demo

本目录实现 [callee_test20 设计](../callee_test20/README.md) 的一个受限原型：
**入口文件是手写的 [kernel.s](kernel.s)，其中一个局部块由 FlyDSL 函数生成。**
构建时把该块替换成普通 AMDGPU 指令，最终只启动这个 ASM kernel。

已于 2026-11-11 在 Radeon RX 7900 XTX / gfx1100 / wave32 / ROCm 7.2 上通过静态
检查和 GPU 完整输出检查。FlyDSL 使用仓库已有环境中的版本，见构建报告。
本目录没有修改 LLVM、FlyDSL 安装目录或其他实验目录。

## 1. 编写方式

ASM 中定义该位置的寄存器接口：

```asm
.flydsl.begin arithmetic_0
    .flydsl.function expressions.py:mul_add
    .flydsl.in f32 a = v0
    .flydsl.in f32 b = v1
    .flydsl.out f32 c = v2
    .flydsl.temp vgpr = v[32:35]
.flydsl.end
```

[expressions.py](expressions.py) 中编写纯 FlyDSL 函数：

```python
import flydsl.expr as fx

def mul_add(a: fx.Float32, b: fx.Float32) -> fx.Float32:
    return a + b * a
```

函数在构建时接收 FlyDSL 符号值，其重载运算生成真正的 MLIR `arith.mulf/addf`。
它没有 kernel 装饰器、GPU launcher 或 inline asm。Python 函数参数名和顺序须与
ASM 中的两个 input 声明一致；两个参数及返回值均为 FP32。

手写 ASM 负责从内存加载 a、b，等待输入 ready，设置外围哨兵和特殊状态，
以及把 c 和状态记录写回内存。a、b 的物理寄存器在片段执行后保持原值。

## 2. 构建和运行

```bash
cd /home/feifei/repo/ATOM/callee_test21
make check
```

`make check` 先编译、验证最终 ELF 和片段，再用 HIP host API 加载 ASM code object
执行 GPU 测试。自动选择 gfx1100 GPU，或指定设备：

```bash
make check DEVICE=0
```

离线构建和静态检查：

```bash
make inspect
```

只生成二进制与 host launcher：

```bash
make all
```

默认 Python 复用 `../mono_test20/build/venv/bin/python`（若存在），否则使用 python3。
该环境只用于离线 FlyDSL/MLIR 编译，GPU 测试由 C++ HIP host runner 执行，
不依赖 ROCm PyTorch。工具不会自动安装依赖。

```bash
make check PYTHON=/path/to/flydsl/python LLVM=/opt/rocm/lib/llvm/bin
```

本 demo 固定 gfx1100、wave32，每次 launch 只包含一个 1–32 线程的 workgroup。
需要支持 FlyDSL Python/MLIR 接口和 gfx1100 的 `llc`、`llvm-mc`、`ld.lld`、
`llvm-objdump`、`llvm-readelf`，以及 C++ 编译器、ROCm HIP headers/runtime。

## 3. 实际实现

```text
kernel.s + expressions.py
  → build.py 读取唯一 .flydsl 块及寄存器合约
  → 调用 FlyDSL 函数，生成 func.func + arith MLIR
  → MLIR lowering + LLVM IR translation
  → llc 编译一个纯计算 float(float,float) 辅助函数
  → 严格检查函数体、输入/返回 ABI 和指令白名单
  → 把辅助函数的 VGPR 操作数映射到授权临时池
  → 插回原 ASM，生成 kernel.generated.s
  → llvm-mc / ld.lld 生成 demo.co
```

内部 LLVM 辅助函数的普通接口为：输入在 v0/v1，返回值在 v0。
原型先确认它只有预期的入口等待、受支持的直线计算及结尾 `s_setpc_b64 s[30:31]`。
然后删除已确认的 ABI shell，保留计算和 `s_delay_alu`，并添加输入/输出 COPY。
最终 kernel 没有函数调用和返回指令，不链接该辅助函数，不嵌入 `.long` 字节。

当前生成的片段核心是：

```asm
v_mov_b32_e32 v32, v0
s_nop 7
v_mov_b32_e32 v33, v1
s_nop 7
v_mul_f32_e32 v33, v33, v32
s_nop 7
s_delay_alu instid0(VALU_DEP_1)
v_add_f32_e32 v32, v32, v33
s_nop 7
v_mov_b32_e32 v2, v32
s_nop 7
```

这里临时池隔离了编译器对输入槽的复用，实际只写 v32、v33 和输出 v2。
重映射针对已解析且通过白名单的三操作数指令进行，不对任意汇编做全局字符串替换。
额外 `s_nop 7` 为该 gfx1100 算术 demo 提供保守间隔，包括新加的 COPY 边界；
没有做性能优化，也不把这种间隔当作任意架构、MFMA 或访存的通用等待规则。

ASM 明确声明 36 个编号 VGPR、16 个编号 SGPR，以及 VCC 资源；metadata 中为
36 VGPR / 18 SGPR / 0 private / 0 LDS。gfx1100 wave32 的 descriptor 实际按
8 个 VGPR 的粒度分配，因此编码覆盖 40 个 VGPR。辅助函数的返回地址等资源
不进入最终 kernel 的预算。

## 4. 验证结果和产物

本机 `make check` 输出：

```text
Static PASS: 44 fragment bytes, writes [2, 32, 33], 3 rejection checks
GPU 0: Radeon RX 7900 XTX (gfx1100)
GPU PASS: 27 launches, 414 records, all 12 fields and memory guards checked
```

GPU 覆盖 1、13、32 线程的 launch，每种运行 zero/pattern/random 三类输入，
各重复三次；包括部分 EXEC 和 full EXEC。每条记录检查：a、b 原始位模式、
独立 CPU FP32 参考的 c、VGPR/SGPR 哨兵、SCC、VCC、EXEC、MODE 前后相等、lane ID
以及记录尾哨兵。输入内存及输出两端 guard 也完整检查。CPU 参考分别舍入乘法和
加法，构建关闭 FP contraction；当前数值测试范围为有界有限输入及正负零，
未覆盖 NaN/Inf、极端溢出或 denormal。

静态验证将插入片段与独立汇编的字节对照，检查完整 ELF、唯一 ASM 函数、
实际指令无调用/返回/scratch、metadata 及 descriptor 的 VGPR 编码。
还检查重叠临时池、池容量不足和未知指令三种拒绝路径。

| 产物 | 用途 |
|---|---|
| `build/fragment.mlir`、`fragment.lowered.mlir`、`fragment.ll` | FlyDSL → MLIR → LLVM IR 证据 |
| `build/fragment.native.s` | 保留的原始 LLVM 辅助函数汇编 |
| `build/fragment.inc` | 插入 ASM 的受限片段 |
| `build/kernel.generated.s` | 完整纯 ASM 输出 |
| `build/demo.co` | 最终可加载 code object |
| `build/kernel.disasm.txt`、`kernel.elf.txt` | 完整 kernel 指令及资源检查材料 |
| `build/build_report.json` | 合约、寄存器映射、工具版本与源码/二进制 hash |
| `build/static_report.json` | 静态检查结果 |
| `build/gpu_result.json`、`test.log` | GPU 完整输出校验结果 |

构建成功本身的状态是 `BUILT_NOT_GPU_TESTED`；GPU PASS 只由实际执行测试产生。
重建时清除旧成功报告，避免失败构建仍保留上次成功的 code object 或结果。
`build/` 是可重新生成的产物，受仓库 ignore 规则覆盖。

## 5. 原型限制和下一步

这是可以运行的最小片段预处理器，尚未实现设计中的通用 LLVM fragment 后端。
它只支持一个顶层块、两个 FP32 输入和一个 FP32 输出，以及 add/sub/mul 的
直线符号表达式。输入输出槽必须互不重叠且与临时池分离。

拒绝其他 MLIR 操作、常量/SGPR/tuple 操作数、VOPD、未知调度指令、访存、
函数调用、scratch、额外基本块、ASM 宏/条件展开和不足的寄存器池。
`.flydsl.*` 是本目录预处理器的实验语法，不是 FlyDSL 或 LLVM 汇编器原生语法。
更换 LLVM 后若普通 helper 的 ABI shell 或代码形态改变，会报错而不是猜测。

默认 kernel 的 load/store 与 output 记录仍使用 v2。如果修改 `.flydsl.out`，
必须同步修改手写 ASM 消费者；若增加临时池，要同步满足 descriptor 和 metadata。
构建检查授权池的预算，静态检查实际指令和最终资源；不会自动修改 descriptor。

下一步应将固定物理 live-in/live-out 和临时池接入 LLVM 分配前的 fragment 模式，
配合完整的显式/隐式资源 verifier，从而支持更多表达式并减少额外 COPY。
复杂除法、tuple、控制流、访存和跨边界 hazard 需要独立的后端支持，不能仅放宽
当前白名单就宣称支持。
