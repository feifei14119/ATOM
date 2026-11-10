# 高寄存器污染测试：inline asm + .long

本目录与 [callee_test00](../callee_test00/README.md) 使用相同的计算指令、
`caller.cpp` 和 CPU 测试；本目录的 `stage_body.inc` 对应 device 版本
`stage_probe.s` 内 `.Lpayload_begin` 到 `.Lpayload_end` 之间的代码。两者在 gfx1100 上比较 inline 边界和普通
设备函数 ABI。计算主体实际覆盖 **v64–v255、s40–s105**，分别写入
`0xdeadbeef`、`0xbaadf00d`，然后执行原来的参数记录与计算。

两边不是只修改了 clobber 声明；[stage_body.inc](stage_body.inc) 的 `.irp`
会被汇编器展开为每个寄存器的一条实际写入指令。

## 1. 构建运行

```bash
make -C /home/feifei/repo/ATOM/callee_test10 check
```

默认选择 gfx1100，也可加 `DEVICE=0`。`all` 只构建，`run` 运行 GPU 测试，
`inspect` 生成供阅读的 IR、汇编和反汇编。`caller.ll`、`caller.s` 不被修改。

```text
stage_probe.s + stage_body.inc → build/stage_probe.co
stage_probe.co → verify.py emit → build/stage_words.inc + stage_words.bin
caller.cpp + stage_api.h + stage_words.inc → caller.bc → caller.o → caller.co
```

`stage_probe.co` 在这里是 **ET_REL 字节提取产物**，不能作为普通设备函数连接：
它没有保存完整的 callee-saved 集合。最终链接只使用 caller.o，机器指令已经在
inline asm 中。只有 `caller.co` 内的 `caller_kernel` 被 host 启动。

## 2. 输入、输出和污染声明

[stage_api.h](stage_api.h) 保留原来的参数协议：

| 内容 | 位置 |
|---|---|
| 常量参数 bias / 返回值 | `+{v0}` |
| input global 指针 | v1:v2 |
| record global 指针 | v3:v4 |
| 显式 thread x/y、workgroup x/y | v5、v6、v7、v8 |
| packed thread ID | v31，x/y/z 各 10 bit |
| workgroup x/y | s12、s13，由 inline 调用方显式准备 |

clobber 包含主体原有的 `v9–v17`、`s0`、SCC、memory，以及新增的
**全部 v64–v255 和 s40–s104**。v0 是读写操作数，其余输入保持不变。
LLVM 在寄存器分配前就看见这些约束，跨片段活跃值可以移到其他寄存器，必要时
也可以 spill。本例没有直接设置 VGPR/SGPR 数量上限。

### 为什么 s105 单独保护

原始主体确实会覆盖 s105。安装版本 LLVM 在降低 kernel 时会暂时把最高的
SGPR 保留给 whole-wave spill/copy 的 EXEC 保存。直接把它加入 clobber 会触发
reserved-register 诊断。为保持边界契约完整，本例在 `.long` 前后显式保护它：

```cpp
unsigned saved_s105;
asm volatile(
    "s_waitcnt_depctr 0\n"
    "s_mov_b32 %[saved], s105\n"
    "s_waitcnt_depctr 0\n"
#include "stage_words.inc"  // 内部仍然写 s105 = 0xbaadf00d
    "s_mov_b32 s105, %[saved]\n"
    "s_waitcnt_depctr 0\n"
    : "+{v0}"(result), [saved] "=&s"(saved_s105)
    : /* 固定寄存器输入 */
    : /* v64-v255、s40-s104 等净污染 */);
```

`=&s` 请求编译器分配一个不与输入或 clobber 重叠的临时 SGPR。当前两个展开点
分别用 s2、s1。它们小于 s40，且不与主体的 s0、输入 s12/s13 冲突。
保存槽不需要 scratch。s105 在整个 inline 边界结束后保持原值，因而不再声明
为净 clobber；指定范围内的每个寄存器在主体内部都仍然被覆盖。

## 3. 资源配置与活跃值

两个版本的 [caller.cpp](caller.cpp) 都有：

```cpp
__global__ __launch_bounds__(256) void caller_kernel(...) {
    asm volatile("" ::: "v255", "s105");
    // ...
}
```

256 是测试实际使用的最大 block 线程数；这使 gfx1100 的驻留预算允许使用
全部 256 个 VGPR。空 asm 让最高寄存器也计入最终 descriptor，不生成机器指令。
特别是 s105，虽然被边界恢复，机器码仍需要它，资源声明不能忽略它。
这不是把调用方限制为使用 v0–v63 或 s0–s39。

为验证高寄存器上的真实活跃值，测试在调用前后把两个快照绑定到 v72 和 v255：

```cpp
asm volatile("" : "+{v72}"(live_lane), "+{v255}"(live_uniform));
// 两次 stage_probe(...)
asm volatile("" : "+{v72}"(live_lane), "+{v255}"(live_uniform));
```

实际反汇编显示，LLVM 在第一段 `.long` 前将它们搬到 v23、v24，跨两段汇编
保持，结束后再搬回 v72、v255。普通 device 版本则保持在高寄存器，由被调用方
的 ABI 包装保存/恢复。两者都正确，但维护上下文的责任不同。

## 4. 校验与产物

2026-11-10 在 **RX 7900 XTX / gfx1100 / ROCm 7.2 / Clang 22** 上运行：
15 组配置、24,414 次 ASM 执行全部通过，结果摘要为 `e78925df34c1787c`，
与 device 版本完全一致。最终构建没有 reserved-register 警告。

- 每段原始主体 2336 bytes，精确嵌入最终 caller 两次。
- 两边的原始主体 SHA256 相同：`811cad1494f520906e7f414f2a8112bd8a1263f692685aa3b3c9413de02a3380`。
- metadata：VGPR 256、SGPR 108、private segment 0、LDS 0、spill count 0。
- 被测 caller 中没有 scratch，也没有 `s_swappc_b64` / `s_setpc_b64`。
- 相同测试覆盖两种 bias、global 地址/读写、显式和隐式 ID、返回值、跨调用快照、
  首次返回值、保护区，以及不完整尾 wave。

[verify.py](verify.py) 检查实际高寄存器写入覆盖、全部净 clobber、s105 的低
SGPR 备份/恢复、精确嵌入字节、最高寄存器资源和无 PC 调用/返回。

| 产物 | 作用 |
|---|---|
| [stage_probe.s](stage_probe.s) | 原始主体的汇编容器，末尾带可移除的返回 |
| [stage_body.inc](stage_body.inc) | 手写 ASM，含全部高寄存器污染与原计算 |
| [stage_api.h](stage_api.h) | inline 约束、完整净 clobber 和 s105 边界保护 |
| [build/stage_probe.co](build/stage_probe.co) | 字节提取产物，不连接到 caller |
| [build/stage_words.inc](build/stage_words.inc) | 生成的 C++ `.long` 字符串，附逐条反汇编注释 |
| [build/stage_words.bin](build/stage_words.bin) | 2336 字节原始主体 |
| [build/caller.co](build/caller.co) | 可启动的最终 kernel |
| [build/caller.disasm.txt](build/caller.disasm.txt) | 最终执行代码，包括 LLVM 插入的搬运 |
| [build/verification.json](build/verification.json) | 静态检查结果 |
| [build/test.log](build/test.log) | 真机测试结果 |

完整参数映射、输出结构和参考计算见 [device 版 README](../callee_test00/README.md)。
移植到 gfx1250 时需重新核对 ISA、隐式 ID 和资源配置；本例不声称验证了 gfx1250。
