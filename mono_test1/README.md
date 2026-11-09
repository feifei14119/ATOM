# Mono：直接使用固定寄存器输入约束 + .long

已在 [stages/sub.h](stages/sub.h) 中验证：ROCm 7.2 的 AMDGPU Clang 可以直接在 C++ inline asm 中使用 `"{v0}"(a)`，让编译器在进入 ASM 时将 32 位变量 a 放入 v0。无需在 ASM 内手写 `v_mov_b32 v0, ...`，也无需 C++ `register ... asm("v0")` 变量。

当前版本已采用这套写法。`.long` 机器指令体和三 CTA 算法不变；输入约束、实际破坏的寄存器以及 memory 均直接写在 `asm volatile` 中，没有全函数 VGPR/SGPR 数量上限，也没有 IR/MIR 修改脚本。

## 构建与运行

环境：ROCm 7.2，clang 提交 `7b800a19466229b8479a78de19143dc33c3ab9b5`，gfx1100 / Radeon RX 7900 XTX。

```bash
cd /home/feifei/repo/ATOM/mono_test1
make -j4
make run
make check
```

运行的仍是 `mono_kernel.cpp` 主 Mono，3 CTA × 128 threads：

```text
CTA 0：.long 减一 → first = input - 1 → 发布 first
CTA 1：stage_scale → second = first * 2 → 发布 second
CTA 2：stage_relu → output = max(second - 3, 0)
```

公式为 `y[i] = max(2*x[i] - 5, 0)`。host、六参数接口、mailbox、scale/relu 和原始供应方汇编保持不变。

## 实际修改

以前使用普通 `"v"` / `"s"` 输入，再在 ASM 内写 9 条 VGPR 和 3 条 SGPR 搬运。现在删除这 12 条手写搬运，直接指定输入位置，例如：

```cpp
asm volatile(
    // 等待、对齐与 .long 指令体……
    :
    : [in_lo] "{v0}"(static_cast<unsigned>(in)),
      [in_hi] "{v1}"(static_cast<unsigned>(in >> 32))
      // 其他固定输入……
    : "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15",
      "s0", "s1", "s2", "s3", "vcc", "scc", "memory");
```

完整约束在 [sub.h](stages/sub.h) 中，包含 12 个 i32 输入：

| 输入 | 固定输入约束 |
| --- | --- |
| input 指针低/高位 | `{v0}` / `{v1}` |
| first.data 指针低/高位 | `{v2}` / `{v3}` |
| first.tag 指针低/高位 | `{v4}` / `{v5}` |
| n / epoch | `{v6}` / `{v7}` |
| threadIdx.x | `{v31}` |
| 隐式 launch 参数指针低/高位 | `{s8}` / `{s9}` |
| blockIdx.x | `{s12}` |

当前将 64 位指针拆为两个 uint32，每个单寄存器约束的位宽都与操作数一致。不要把完整 uint64 直接传给单个 `{v0}` 并假定高位也会自动放进 v1。

这里使用的是 **asm 操作数约束字符串**。它和 `register ... asm("寄存器名")` 的变量寄存器名称语法不是同一个接口；不能根据后者对寄存器名称的限制，推断前者是否支持 `{v0}`。

## 编译器是否还会生成 v_mov

会按需生成。固定输入约束表示“进入 ASM 时，这个值必须在指定寄存器中”，不是“这个值从产生到销毁只能位于这里”，也不保证实现过程中完全没有搬运。

当前生成的 [build/mono_kernel.s](build/mono_kernel.s) 中，在 `;;#ASMSTART` 之前出现：

```asm
s_add_u32 s8, s2, 56
s_addc_u32 s9, s3, 0
s_waitcnt lgkmcnt(0)
v_dual_mov_b32 v0, s16 :: v_dual_mov_b32 v1, s17
v_dual_mov_b32 v2, s20 :: v_dual_mov_b32 v3, s21
v_dual_mov_b32 v4, s22 :: v_dual_mov_b32 v5, s23
v_dual_mov_b32 v6, s10 :: v_dual_mov_b32 v7, s11
s_mov_b32 s12, 0
;;#ASMSTART
```

这是 LLVM 自动完成的参数准备：指针原本由 scalar load 装入 SGPR，需要进入指定 VGPR。ASM 内已经没有手写的入口移动。其他场景下，编译器可以将生产该值的指令结果直接安排到目标寄存器，也可能仍然需要复制；以实际生成代码为准。

修改前的 sub.h、汇编和检查结果保存在 `build/fixed_binding_before/` 供本次对照，它们不参与当前构建，clean 后会删除。没有进行性能对比，不能仅按手写移动减少就宣称性能提升。

## 为什么 clobber 也要调整

删除 ASM 内的入口搬运后，v0–v7、v31、s8:s9 和 s12 都只是原体的只读输入，不再由这个 ASM 区域写入。它们不能同时作为只读固定输入和 clobber。

当前实际 clobber 只保留：

```text
v8–v15、s0–s3、VCC、SCC、memory
```

如果以后机器码会改写某个固定输入，应将对应操作数正确建模为读写或输出，不能继续把它声明成只读输入。EXEC 由原体恢复；MODE 和栈状态不被修改。

该约束是局部接口：LLVM 仍能自行分配其他寄存器，按需保留跨区域活跃值或使用 scratch。不需要增加 `amdgpu_num_vgpr`、`amdgpu_num_sgpr`、自定义 regmask 或 IR 数量限制。此主示例 CTA 0 在区域之后结束，不能把当前零 scratch 结果当作大型 ATOM 中间算子的普遍保证。

## .long 与编译链

```text
stages/sub_kernel.s → stage_sub.co（ELF REL）
    → embed_sub.py → build/sub_words.inc
    → sub.h 的 asm volatile
    → HIP 编译 → mono_kernel.bc → mono_kernel.o → mono_kernel.co
```

供应方函数为 292 B，移除最后 4 B 的设备 return 后，剩余 288 B 原样转换为 `.long` 字符串。内部相对分支和对齐 NOP 保持不变，最终写入主 kernel 的可执行 `.text`。

最终只链接主 kernel 对象，没有外部 stage 调用，也不修改编译器输出的指令。`make inspect` 和 `make check` 生成的 `.ll` / `.s` 仅用于阅读检查，不参与输入改写。

原体包含 CTA barrier，必须完整 CTA 一致到达；n 小于 CTA 大小时的线程掩码由原体处理。原 mailbox 的 release/acquire 协议保持不变。

## 本次验证结果

2026-11-09，直接修改本目录的 sub.h，并编译运行同一个主 Mono：

- C++ 直接接受 `{v0}` 等固定输入约束，生成的 LLVM IR 保留它们。
- ASM 内手写入口搬运为 0，所有指针高/低位均由编译器正确准备。
- `.long` payload 恰好出现一次、64 B 对齐、与原始去掉 return 的 288 B 逐字节一致。
- 主 kernel 无 getpc/swappc/setpc，无外部 stage 符号或剩余重定位。
- n=1、31、128、257、4096 的两个中间值、两个发布标记和最终输出全部通过。默认 host 测试 4096，其余尺寸用同一 `.co` 和临时 host 验证。
- 最终资源：32 VGPR、26 SGPR，LDS/private/spill 均为 0。这些是生成结果，不是数量上限。

结果见 [build/verification.json](build/verification.json) 与 [build/gpu_verification.json](build/gpu_verification.json)；后者记录了本次执行的 `.co` SHA-256。检查脚本 [verify.py](verify.py) 已同步更新，验证直接固定输入、只读输入不与 clobber 重叠以及 ASM 内无入口搬运。
