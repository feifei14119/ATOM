# 通过调用点 regmask 将跨调用寄存器上下文限制在 v64 / s40 以下

本目录使用与 [callee_test00](../callee_test00/README.md) 相同的设备函数调用方式：
手写 `.s` 独立编译成 `.co`，与调用方链接，通过 `s_swappc_b64` / `s_setpc_b64`
调用和返回。计算主体机器码与 test00 **逐字节相同**，仍然覆盖：

```text
v64–v255 = 0xdeadbeef
s40–s105 = 0xbaadf00d
```

区别是两个目标调用点使用自定义 **call-preserved regmask**。v64 和 s40 本身
也被覆盖，所以这里的“以内”具体是 **v0–v63、s0–s39**。
在这个边界之外，可以继续使用高寄存器；不设置整个 kernel 的 VGPR/SGPR 上限。

已在 **RX 7900 XTX / gfx1100 / wave32 / ROCm 7.2 / Clang 22** 上验证。
实现是绑定本机 LLVM 版本的 MIR 原型，没有修改安装的编译器或实际 ATOM 算子。

## 1. 编译运行

```bash
make -C /home/feifei/repo/ATOM/callee_test01 check
```

默认自动选择 gfx1100，也可指定 `DEVICE=0`。`all` 构建；`inspect` 输出检查材料；
`check` 检查掩码、最终活跃寄存器、ELF、实际指令并运行 GPU/CPU 对照；`run` 同样
经过检查后运行。

供应方只有一个完整的 [stage_probe.s](stage_probe.s)，没有 `.inc`，也不生成或
嵌入 `.long`。数据参数、ID 获取、结果布局、两次调用和 CPU 校验沿用 test00。

## 2. 保留的寄存器是什么

从当前编译器的默认设备 ABI 掩码出发，删除所有包含高编号 GPR 的位：

```text
new_mask = default_device_mask
           删除任何 v >= 64 的保留位及其别名
           删除任何 s >= 40 的保留位及其别名
```

最终保留集合是：

| 类型 | 允许在寄存器中跨调用保持的集合 |
|---|---|
| VGPR | v40–v47、v56–v63，共 16 个 |
| SGPR | s30–s39，共 10 个 |
| 其他掩码位 | 保留默认 ABI 的非普通 GPR 位 |

这不是把所有低寄存器都升级成 callee-saved。这里只保留默认集合中满足边界的
部分，避免额外改变参数/返回值与临时寄存器约定。s30:s31 是返回地址，s32 是 SP，
s33/s34 有 FP/BP 等特殊用途；保留位并不意味着这 10 个 SGPR 都可自由分配给普通值。
EXEC、MODE 等状态仍需满足设备函数约定，不能只依靠一个 GPR 编号规则。

掩码还包含 16 位子寄存器和多个寄存器组成的 tuple。脚本从**正在使用的 llc**
读取实际寄存器名称表与默认掩码，处理所有别名，不硬编码另一版 LLVM 的寄存器 ID。
本机默认掩码有 956 个名称位，筛选后保留 177 个，移除 779 个。

## 3. 在编译器哪里施加约束

关键实现在 [callsite_regmask.py](callsite_regmask.py)：

1. HIP 正常编译 `caller.cpp` 到 `caller.bc`。
2. `opt` 删除本例未使用的 HIP assert/printf 辅助函数，保留 caller 与外部函数声明。
3. `llc -stop-after=finalize-isel` 输出 MIR；此时指令已选择，**所有寄存器分配器尚未运行**。
4. 只修改两条 `SI_CALL @stage_probe_lowctx` 的掩码：

   ```text
   ... SI_CALL ..., @stage_probe_lowctx, csr_amdgpu, ...
                        ↓
   ... SI_CALL ..., @stage_probe_lowctx, CustomRegMask(...低寄存器及别名...), ...
   ```

5. `llc -start-after=finalize-isel` 继续调度、寄存器分配、spill、等待指令插入等步骤。
6. 生成调用方汇编、编译为 `.o`，与独立 ASM 的 `.co` 链接。

检查器将修改后的两个 `CustomRegMask` 换回 `csr_amdgpu`，要求 MIR 与修改前完全
相同，保证没有顺手修改参数、其他指令或额外调用点。

仅在 C++ 中写 `__device__` 不会产生这个自定义约定。本目录必须使用提供的构建
流程。为区分 ABI，函数符号改为 **`stage_probe_lowctx`**；函数签名和计算不变。
不能让一个普通默认 ABI 的调用方直接调用这个新二进制。

## 4. 为什么可以删除被调方的高寄存器保存/恢复

test00 的普通设备 ABI 允许调用方在高编号 callee-saved 寄存器中保留值，所以
被调方必须保存并恢复那些寄存器。本目录的调用点掩码已经通知 LLVM：

```text
跨这个调用，v64–v255 和 s40–s105 都不保证保留。
```

LLVM 会自行选择低寄存器、重新计算或 spill，不能依赖这些高寄存器里的旧值。
被调方只需满足新的保留约定。本例主体没有写 v40–v47、v56–v63、s30–s39，
因此 [stage_probe.s](stage_probe.s) 中可以直接执行污染与计算，再返回：

```text
相同的 2336 字节污染/计算主体
    ↓
s_setpc_b64 s[30:31]
```

整个函数 2340 字节。test00 中保存 96 VGPR + 34 SGPR 的包装已移除，供应方
private segment 为 0，没有 scratch load/store，也没有额外 wrapper 调用。
高寄存器的污染值会实际留在返回后的寄存器里；调用方不再把它们作为保留上下文。

## 5. 最终编译器如何安排上下文

保留 test00 中的测试锚点，在调用前后把两个实际数据值绑定到 v72 和 v255：

```cpp
asm volatile("" : "+{v72}"(live_lane), "+{v255}"(live_uniform));
auto r0 = stage_probe_lowctx(...);
auto r1 = stage_probe_lowctx(...);
asm volatile("" : "+{v72}"(live_lane), "+{v255}"(live_uniform));
```

它们只规定锚点处的位置。**调用点处的位置由新的 regmask 和寄存器分配器决定。**
实际代码中出现：

```asm
; 调用之前，编译器自动搬移两个快照
v_mov_b32_e32 v59, v255
v_mov_b32_e32 v58, v72
s_swappc_b64 s[30:31], s[36:37]
; ...准备第二次调用的参数...
s_swappc_b64 s[30:31], s[36:37]
; 两次调用之后，按测试锚点要求搬回
; v59 -> v255，v58 -> v72
```

调用地址使用 s36:s37，workgroup x/y 使用 s39/s38。最终 MIR 的独立 GPR 活跃性
审计得到（已排除调用新定义的返回值 v0 和返回地址）：

| 调用点 | 实际跨调用 VGPR | 实际跨调用 SGPR |
|---|---|---|
| 第一次 | v40–v42、v44–v47、v56–v59 | s33–s39 |
| 第二次 | v43、v46–v47、v58–v59 | 无 |

没有 v64 以上或 s40 以上的普通寄存器值直接跨调用保留。该检查针对本例单基本块
的实际 defs/uses；不会先用掩码删掉高寄存器再宣称它们不活跃。它不是任意 CFG、
任意 lane 语义的通用分析器，复杂 ATOM 控制流仍需要后端验证与相应测试。

## 6. 为什么还剩 16 字节 scratch

限制 callee-saved 集合并不保证零 scratch。当前 LLVM 为六个隐式 SGPR 参数值
使用 v60 的六个 lane，并将这个 VGPR 保存到 scratch、在第一次调用后重新读取，
再用 `v_readlane_b32` 准备第二次调用的隐式参数。

本次 caller 实际只有一条 `scratch_store_b32` 和一条 `scratch_load_b32`。
占用一个 4 字节 spill 槽，栈帧按要求对齐到 **16 bytes/thread**，s32 设置为 16。
这些指令全部由 LLVM 自动生成，供应方已经没有 scratch。跨调用的额外数据在内存
里，不违反“直接由寄存器保持的上下文必须低于边界”的约束。

如果要求连这点 scratch 也消失，需要进一步缩减跨调用状态、隐式参数需求或设计
其他 ABI。本例保持与 test00 相同的接口与计算，没有把零 scratch 作为通过条件。

## 7. 编译资源与 MIR 原型的限制

caller 中沿用以下资源声明：

```cpp
__launch_bounds__(256)
asm volatile("" ::: "v255", "s105");
```

前者匹配最大 256 线程的测试 block，后者使 LLVM 计入 ASM 实际使用的最高
寄存器；不产生指令，也不是全函数寄存器数量上限。最终仍分配 VGPR 256、
SGPR metadata count 108，只有跨调用的保留集合变小。
`-amdgpu-assume-external-call-stack-size=0` 说明这个已知叶子供应方不需要栈帧；
它不禁止 LLVM 给 caller 分配自己的 spill 槽。

本机 LLVM 的 MIR 暂停/恢复有需要明确处理的限制：

- 脚本绑定编译器提交 `7b800a19466229b8479a78de19143dc33c3ab9b5`，读取本机
  llc 的寄存器表；版本变化或表布局不符时拒绝构建。
- 未改掩码的 MIR 往返必须复现默认流水线的 caller 指令，作为兼容性检查。
- 这个版本的 MIR 序列化会丢失入口 user-SGPR preload count。脚本从默认流水线
  恢复 `.amdhsa_user_sgpr_count`，本例为 13；不复用默认流水线的 VGPR/SGPR/private
  资源计数。另补齐未定义的零 named-barrier 资源符号。
- 没有对最终 `.co` 指令打补丁，也没有将供应方机器码嵌入 caller。上述修正发生在
  调用方汇编组装前，并在 README 中公开记录。

**实际 ATOM 接入应在 LLVM 编译进程中实现同样的 pre-RA MachineInstr regmask
修改，或增加明确的自定义 calling convention。** 那样不需要这个 MIR 文件往返
和 descriptor 兼容修正。FlyDSL 生成 LLVM 调用时还需关联同一份 ABI 与资源契约。

## 8. 验证结果与文件

2026-11-10，本机 15 组配置、24,414 次 ASM 执行全部通过。输出摘要
`e78925df34c1787c` 与 test00 相同，覆盖参数、global 读写、返回值、跨调用快照、
高寄存器锚点、保护区，以及只有 1 lane 和不完整尾 wave 的配置。

| 项目 | callee_test00 | callee_test01 |
|---|---:|---:|
| 计算主体字节数 | 2336 | 2336，相同 SHA256 |
| 供应方函数总字节数 | 5396 | 2340 |
| 供应方 scratch 指令数 | 260 | 0 |
| 调用方 scratch 指令数 | 0 | 2 |
| 最终 private segment bytes/thread | 528 | 16 |
| 最终 VGPR / SGPR metadata count | 256 / 108 | 256 / 108 |
| caller VGPR / SGPR spill count | 0 / 0 | 1 / 6 |

这里的指令数是静态数量，不是性能计时；没有声称获得特定加速比。test00 的手写
保存指令不会被 caller 的 spill 计数统计，因此 private bytes 和实际反汇编更直接。

| 文件 | 用途 |
|---|---|
| [caller.cpp](caller.cpp) | 同一测试逻辑，调用新 ABI 符号 |
| [stage_api.h](stage_api.h) | 声明和自定义 ABI 使用要求 |
| [stage_probe.s](stage_probe.s) | 完整供应方汇编，无 `.inc` |
| [callsite_regmask.py](callsite_regmask.py) | 读取默认掩码、筛选全部别名、pre-RA 修改两处调用 |
| [verify.py](verify.py) | 掩码、实际活跃寄存器、ELF 和机器码审计 |
| [build/stage_probe.co](build/stage_probe.co) | 独立可链接的自定义 ABI 设备函数 |
| [build/caller.co](build/caller.co) | 最终可启动的模块 |
| [build/callsite_regmask.json](build/callsite_regmask.json) | 完整原始/保留/删除寄存器名称和工具链记录 |
| [build/caller.before_regmask.mir](build/caller.before_regmask.mir) | 修改前，尚未寄存器分配 |
| [build/caller.lowctx.mir](build/caller.lowctx.mir) | 两个调用点带自定义掩码 |
| [build/caller.allocated.mir](build/caller.allocated.mir) | 最终机器指令与活跃性审计输入 |
| [build/caller.function.s](build/caller.function.s) | 便于阅读的 caller 指令 |
| [build/verification.json](build/verification.json) | 检查结果、两处调用的实际跨调用寄存器 |
| [build/test.log](build/test.log) | GPU 单测日志 |

`caller.default_abi.s` 和 `caller.roundtrip.s` 仅用于编译器往返对照，不能与这个
取消了高寄存器保持的新供应方组合启动。最终模块使用的是 `caller.s`。
