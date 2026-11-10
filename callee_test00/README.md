# 高寄存器污染测试：普通 __device__ 调用

已按要求直接修改 `callee_test00` 和配套的 [callee_test10](../callee_test10/README.md)。
两边使用相同的计算指令、`caller.cpp` 和 CPU 测试，分别接入普通设备函数调用
和 inline asm `.long`。本目录的全部汇编直接写在 [stage_probe.s](stage_probe.s) 中。本例针对本机
**RX 7900 XTX / gfx1100 / wave32 / ROCm 7.2 / Clang 22**。

汇编主体现在实际执行：

```text
v64  ... v255 = 0xdeadbeef   // 192 个 VGPR，包含两个端点
s40  ... s105 = 0xbaadf00d   // 66 个 SGPR，包含两个端点
```

这是实际机器指令写入，不只是声明 clobber。gfx1100 的普通编号 GPR 到 v255、
s105 为止；本机汇编器拒绝 v256、s106。本例不把 TTMP、VCC、EXEC、MODE 等
特殊状态当作继续递增编号的普通 SGPR。VGPR 写入只影响有效 EXEC lane，未激活
lane 保持原状；本例调用的每个 wave 都至少有一个有效 lane。

**主体实际覆盖所有指定寄存器；符合 ABI 的设备函数在返回前恢复其中的
callee-saved 部分。** “内部写过”和“返回后允许值改变”是两个不同的接口属性。

## 1. 构建和运行

```bash
make -C /home/feifei/repo/ATOM/callee_test00 check
make -C /home/feifei/repo/ATOM/callee_test10 check
```

自动选择 gfx1100，也可加 `DEVICE=0`。`all` 只构建，`run` 运行，`inspect`
生成 IR、汇编和反汇编供阅读，`check` 同时做静态审计和 GPU/CPU 对照。
`build/caller.ll`、`build/caller.s` 不被修改，也不回灌到编译流程。

本目录不需要 `.inc`，也不生成 `.long`。以前的 `stage_body.inc` 只是手写汇编
源码的拆分文件，用汇编器 `.include` 包含，不是机器码提取产物；现在已合并回
`stage_probe.s`。`verify.py` 仅作设备函数静态检查，已去掉 `.inc` 生成与 inline
检查功能。inline 版本的 `build/stage_words.inc` 才是由机器码生成的 `.long` 文件。

## 2. 被调用函数与参数映射

```cpp
extern "C" __device__ uint32_t stage_probe(
    uint32_t bias, uint32_t* input, Record* record,
    uint32_t tx, uint32_t ty, uint32_t bx, uint32_t by);
```

下面是**该签名在本机编译器上的实际设备函数 ABI**。
普通参数包括 wave uniform 值，也按这里的 VGPR 参数规则传入。

| 参数/状态 | ASM 读取的位置 | 内容 |
|---|---|---|
| `bias` | `v0` | 两个调用点分别传入字面常量 `37u`、`0xa13579bdu` |
| `input` | `v1:v2`，低 32 位在前 | 当前线程的 global 数据地址 |
| `record` | `v3:v4`，低 32 位在前 | 当前线程、当前调用的 global 结果地址 |
| 显式 `tx` | `v5` | `threadIdx.x` |
| 显式 `ty` | `v6` | `threadIdx.y` |
| 显式 `bx` | `v7` | `blockIdx.x`，即 workgroup x |
| 显式 `by` | `v8` | `blockIdx.y`，即 workgroup y |
| 隐式 thread x | `v31[9:0]` | 按 gfx1100 设备函数 ABI 传入的 packed ID |
| 隐式 thread y | `v31[19:10]` | 同上 |
| 隐式 workgroup x/y | `s12` / `s13` | LLVM 在调用前按设备 ABI 准备 |
| 返回值 | `v0` | 32 位计算结果 |
| 返回地址 | `s30:s31` | `s_swappc_b64` 写入，`s_setpc_b64` 使用 |

这里的“传入立即数”指 C++ 调用点传常量。**跨设备函数边界仍然是寄存器
传参**：例如编译器生成 `v_mov_b32 v0, 37`，没有修改被调用 `.co` 的机器码。
64 位参数也不要求总从偶数编号 VGPR 开始；汇编将地址复制到 `v10:v11`
再执行 global load/store，以满足所用访存指令的操作数要求。

`s12/s13` 是这个**设备函数调用边界**的约定，不应据此硬编码最外层
`__global__` kernel 的入口寄存器布局；后者还受 kernel descriptor 影响。

## 3. ASM 做什么

计算主体直接位于 [stage_probe.s](stage_probe.s) 的 `.Lpayload_begin` 和
`.Lpayload_end` 标签之间。
每个线程独立工作，不使用 LDS 或 barrier。主体先覆盖下面说明的全部高编号寄存器，
然后执行原来的计算：

1. 从 `input` 地址读取一个 `uint32_t`。
2. 将 `loaded ^ 0x9e3779b9` 写回 `input`，制造实际内存副作用。
3. 读取显式 x/y 参数和隐式 x/y ID，分别写入 `record`。
4. 计算并写回结果，同时通过 `v0` 返回。

所有算术按无符号 32 位溢出：

```text
result = ((loaded ^ 0x13579bdf) + bias
          + tx + (ty << 8) + (bx << 16) + (by << 24))
         ^ (implicit_bx ^ implicit_by)
```

每个 `Record` 为 64 字节：

| word 下标 | 含义 | 写入方 |
|---|---|---|
| 0–5 | bias、loaded、tx、ty、bx、by | ASM |
| 6–9 | implicit_tx、implicit_ty、implicit_bx、implicit_by | ASM |
| 10 | 计算结果 | ASM |
| 11 | 通过 `v0` 得到的返回值 | C++ 调用方 |
| 12–13 | 调用前读取的每线程值、uniform 值 | C++ 调用方 |
| 14 | 第一次调用的返回值，跨第二次调用使用 | C++ 调用方 |
| 15 | `0xcdcdcdcd`，应保持不变 | 初始化后不再写入 |

汇编中保留了较保守的等待指令，便于观察边界和避免手动调度依赖。
这是接入正确性测试，不是性能优化示例。

## 4. Device 版本的保存/恢复

[stage_probe.s](stage_probe.s) 的顺序是：

```text
保存被覆盖的 callee-saved 寄存器
    ↓
stage_probe.s 内的计算主体    // 覆盖所有高编号寄存器，再执行计算
    ↓
恢复被覆盖的 callee-saved 寄存器
    ↓
s_setpc_b64 s[30:31]
```

需要恢复的集合由本机标准设备 ABI 决定：

```text
VGPR：v72-v79、v88-v95、...、v248-v255
      从 v72 开始每 16 个中的前 8 个，共 96 个。
SGPR：s48-s55、s64-s71、s80-s87、s96-s105，共 34 个。
```

依据是安装编译器对应版本的
[AMDGPUCallingConv.td](https://github.com/ROCm/llvm-project/blob/7b800a19466229b8479a78de19143dc33c3ab9b5/llvm/lib/Target/AMDGPU/AMDGPUCallingConv.td)。
低编号部分如 v40-v47、v56-v63、s30-s39 没被主体覆盖，因而不用另存。
其余被覆盖的 caller-clobbered 高寄存器在返回后可以保留污染值。

本例直接在 `.s` 中写出保存和恢复指令，编译时不再自动生成这段包装：

| 每线程 scratch 偏移 | 内容 |
|---|---|
| 0–383 bytes | 96 个需要保持的 VGPR |
| 384–519 bytes | 34 个需要保持的 SGPR，每个复制到有效 lane 的 v18 再存储 |
| 520–527 bytes | 16 字节对齐的预留空间 |

帧大小为 **528 bytes/thread**。`s32` 是传入的帧基址，这个叶函数不调整它。
SGPR 恢复使用 `scratch_load_b32 v18` 加 `v_readfirstlane_b32`，支持本例的
不完整尾 wave；不扩展 EXEC，也不覆盖未激活 lane。

普通 ABI 的调用方活跃值仍由 LLVM 管理。新增测试用空 inline asm 在调用前后
将两个实际数据值绑定到 v72、v255，用来明确测试被覆盖的高 VGPR。实际生成的
caller 让它们跨两次设备调用保持在 v72、v255，依靠上述 ABI 保存/恢复正确运行。
workgroup ID 和调用地址也使用被覆盖范围内的 callee-saved SGPR。
这些空 asm 是测试与资源声明，执行路径仍然是独立 `.co` 的设备函数调用。

## 5. 外部 ASM 的资源必须告知调用方

外部 `.co` 只提供机器码，当前编译流程不会自动把其资源需求合并进已经编译的
caller descriptor。只修改 `stage_probe.num_vgpr` 不能解决这个问题。本例使用：

```cpp
// caller.cpp，两个版本相同；不产生机器指令。
asm volatile("" ::: "v255", "s105");
```

它让 LLVM 计入最高编号寄存器，是最低资源需求的声明，不是 VGPR/SGPR 分配
数量上限，也不会把整个 caller 的可用寄存器限制在某个低编号集合。
inline 版本同样保留这一声明，因为其边界会恢复 s105，但仍需要覆盖 s105 的资源。

Device 版本另外在原生对象生成阶段使用：

```text
-mllvm -amdgpu-assume-external-call-stack-size=528
```

这是外部调用 scratch 帧大小的编译器选项。最终 descriptor 和 metadata 中的
`private_segment_fixed_size` 为 528；没有手动打补丁。

两个 caller 都声明 `__launch_bounds__(256)`，匹配测试的最大 block 大小。
默认的 1024 线程上限会使 gfx1100 编译器为整组驻留预算只开放较少 VGPR；
使用全部 256 个 VGPR 时必须提供与实际 launch 一致的 workgroup 上限。
这里限制的是 block 的线程数，没有使用 `amdgpu_num_vgpr/sgpr`。

## 6. 产物与验证结果

```text
stage_probe.s → stage_probe.co (ET_REL，可链接设备函数)
caller.cpp → caller.bc → caller.o
caller.o + stage_probe.co → caller.co (ET_DYN，可启动的 caller_kernel)
```

2026-11-10 在本机运行：两个版本各 **15 组测试、24,414 次 ASM 执行全部通过**。
结果摘要均为 `e78925df34c1787c`。测试覆盖显式/隐式参数、两次 global 读写、
返回值、跨调用活跃值、输入/输出保护区，以及 1 lane 和不完整尾 wave。

| 项目 | callee_test00：device | callee_test10：inline |
|---|---:|---:|
| 相同污染+计算主体 | 2336 bytes | 2336 bytes |
| 独立 stage 对象内函数字节数 | 5396 | 2340，末尾返回仅供提取时移除 |
| VGPR metadata count | 256 | 256 |
| SGPR metadata count | 108 | 108 |
| private segment bytes/thread | 528 | 0 |
| LDS bytes | 0 | 0 |
| 被测 caller/stage 中静态 scratch 指令数 | 260 | 0 |
| 主体执行后的额外保持 | 96 VGPR + 34 SGPR | s105 边界保护 |

SGPR metadata count 108 包括 106 个编号 SGPR 和保留的 VCC 对。
Device 的 260 条 scratch 指令来自汇编中的显式保存/恢复。caller 的
`vgpr_spill_count/sgpr_spill_count` 仍为 0，因为编译器没有统计外部手写函数的
保存指令；不能用这两个计数断言没有 scratch。

查看：

- [stage_probe.s](stage_probe.s)：完整的设备 ABI 保存/恢复、污染和计算汇编。
- [build/stage_probe.co](build/stage_probe.co)：可链接设备函数。
- [build/stage_probe.disasm.txt](build/stage_probe.disasm.txt)：实际写寄存器与保存/恢复指令。
- [build/caller.disasm.txt](build/caller.disasm.txt)：被测 caller/stage 的反汇编。
- [build/verification.json](build/verification.json)：污染覆盖范围、保存数量、资源和主体 hash。
- [build/test.log](build/test.log)：真机测试结果。

`verify.py` 检查每个指定寄存器确实被写入、ABI 保存集合和槽位覆盖、链接前后
函数机器码一致、两次设备调用和资源覆盖。它针对本例 ABI，不是任意二进制的
自动适配器。移植 gfx1250 时需重新核对指令、隐式 ID 和资源配置。
