# stage_C 换成 ASM：落地方案与详细步骤

本目录是"把 mono step kernel 中的一个步骤换成手写 ASM"的试验。基线单测在 `../mono_test_single_origin`（单卡、合成权重、TP 回环、`part=all, ndr=0`），本试验的全部代码都放在本目录，不改 `/app/ATOM` 下的原有源码，也不改已安装的 FlyDSL。

汇编伪代码与寄存器绑定见 [ASM_PSEUDO.zh-CN.md](ASM_PSEUDO.zh-CN.md)。

## 1. 替换对象

`kernels/attention.py:300–330` 的 `stage_C(c)`：`wq_b` GEMM，接 q_norm 后半（乘 rstd），再做 RoPE，最后 bf16 写 `q`。在 `step.py:316` 每层调用一次。

```text
每个 CTA（b = 0..255）、每个 wave w < 6 且 w%3 < MT：
  j = w // 3, mi = w % 3, n0 = (b + j*256) * 16          # 16 列 × 16 行的输出 tile
  acc[16x16] = Σ_{k=0..9}  WMMA_MX( qr8[mi*16 .. +16][k*128 .. +128],  qrs   (每行每 32K 一个 E8M0),
                                   wqb[n0 .. +16][k*128 .. +128],       wqb_s (32 行 × 32K 一个 E8M0) )
  cv[r] = acc[r] * rsq(ss[r] / 1280 + 1e-20)
  若 n0 % 512 >= 448（每个 head 末 64 维）：按 rpos[r] 查 rcos/rsin 做成对旋转
  q[r][n0 + col] = bf16(结果)                             # scope:SCOPE_DEV 存储
```

选它的原因（详见上一轮分析）：只在单个 CTA 内完成（中间没有 cluster 同步、handoff 或 atomic），不用 LDS，每个 wave 只有 10 条 WMMA；而且本身是确定性的，可以和原生版逐位对比。

参考 kernel：`/app/poc_kl_sim/src/mi400/mxfp8fp4gemm/shaders/MXFP8_GEMM_1TG_4W_128mx2_128nx2.sp3`（可读的 SP3 源码），编码对照用 `/app/poc_kl/mi400/mxfp8fp4gemm/shaders/MXFP8_GEMM_1TG_4W_64mx1_128nx4.s`。借用其中的 `v_wmma_scale_f32_16x16x128_f8f6f4` 用法、scale 寄存器组织和 `v_cvt_pk_bf16_f32` 尾部。不照搬它的 TDM→LDS 搬运、256×256 tile，也不照搬 1024 VGPR / 320 KB LDS 的资源配置。

## 2. 分两阶段

| 阶段 | ASM 负责 | FlyDSL 保留 | ASM 输出 |
|---|---|---|---|
| **P1** | GEMM 主循环（`attention.py:303–317`）：地址计算、10 步取数、10 条 WMMA | wave 选择、tile 坐标；rstd、RoPE、bf16 存储 | 累加器以 `={v[8:15]}` 寄存器输出直接交回 FlyDSL |
| **P2** | 整个 stage_C 的 tile 计算：P1 加上 rstd、RoPE、bf16 存储 | wave 选择、tile 坐标 | 直接写 `q`，没有寄存器输出 |

先做 P1：边界最小，尾部完全不变，出错只可能出在 GEMM 上。P1 逐位通过以后再做 P2。

## 3. 接入方式

沿用 mono_test10/11 已验证的模式：`llvm.inline_asm(has_side_effects=True)`，输入用固定寄存器约束，ASM 实际写到的寄存器全部写进 clobber。和 mono_test10 的区别如下：

- **不用 global 参数块，指针直接用 SGPR 传。** mono_test10 把 240 字节参数块的指针放在 `s[0:1]`，因为供应方 ASM 原来就从 kernarg 读参数。本试验的 ASM 是自己写的，tile 的基地址在 FlyDSL 里算好，`readfirstlane` 后通过 `{s[a:b]}` 约束传入。这样省掉了 host 端按层构造参数块，也省掉 ASM 里的一次 `s_load`。
- **P1 有寄存器输出**（`={v[8:15]}`，类型 `vector<8xf32>`）。已用 `/app/llvm-upstream/build/bin/llc` 在 gfx1250 上验证，LLVM 接受这种 VGPR 元组输出约束。
- **寄存器范围：** 不用 `s30–s39`（LLVM 的栈和返回地址相关寄存器，mono_test10 的结论），不用 TTMP，不改 M0。VGPR 全部在 v0–v255 以内，不依赖 v256 以上的 clobber 修复，也不需要 `s_set_vgpr_msb`。EXEC 进出都是全 1（wave 选择条件按 wave 统一）。
- **ASM 来源：** 先写助记符 `.s`，再用 `llvm-mc -mcpu=gfx1250` 汇编成 `.long` 序列嵌入（和 mono_test10 一样，保证嵌入的字节就是审核过的字节）。同时保留助记符文本，必要时可以直接嵌入做对照。
- **替换方式：** 不改 `step.py`。`run_test.py` 在构建前把 `step` 模块的全局名 `stage_C` 换成本目录的包装函数（`step.build` 在 trace 时按模块全局名查找 `stage_C`）。`sources` 参数加上模式后缀，避免 JIT 缓存命中原生版。

## 4. 验证设计

stage_C 的输入（`qr8/qrs/ss`）由 stage_A 产生，`ss` 是 atomic 累加的，所以两次 launch 之间 `q` 本来就不逐位一致（约 1e-5）。因此逐位对比必须在**同一次 launch** 内完成：

- **`dual` 模式：**
  - 原生 stage_C 照常写 `q`，供后续 stage_D 使用，kernel 后续行为与基线完全一致；
  - 原生 stage_C 再执行一次，写到历史区 `H[2*Ly]`；
  - ASM 版写到 `H[2*Ly+1]`。

  历史区放在 `q` 缓冲之后：测试把 `scratch["q"]` 分配成 `(1 + 2*NL) * T*NQ*2` 字节，`H[k] = q + (1+k)*T*NQ*2`，其中 `Ly` 是运行时循环变量，偏移在 kernel 内计算。launch 之后逐层比较 `H[2Ly]` 和 `H[2Ly+1]`，要求逐位相同（bf16 位模式，48×8192×NL 个元素）。
- **`asm` 模式：** 只运行 ASM 版并写 `q`，作为真正的替换，复用基线单测的全部检查：无超时、数值有限且不退化、run-to-run 相对 L2 在容差内，可选 golden 对比（相对 L2）。
- **`native` 模式：** 原样运行，是对照组。

此外，在接入整个 mono 之前，先用一个**独立的单元 kernel** 快速迭代：256 CTA × 256 线程，只跑合成输入上的 stage_C，原生和 ASM 写到两块输出再逐位比较。mono 整体编译耗时很长，这个小 kernel 编译只需要几秒。

## 5. 详细步骤

### 步骤 0：准备（本次已完成）
1. `mono_test_single` 改名为 `mono_test_single_origin`，并更新 README 里的路径。
2. 新建本目录，写出本方案和 [ASM 伪代码](ASM_PSEUDO.zh-CN.md)。

### 步骤 1：提取原生 stage_C 的指令作为基准
1. 构建原生 mono（`native` 模式，6 行 × 1 层即可），导出 ISA（FlyDSL dump 目录放在 `build/` 下，不放 `/tmp`）。
2. 在反汇编中定位 stage_C：特征是 10 条连续的 `v_wmma_scale_f32_16x16x128_f8f6f4`，前面是 `wqb` 的 `global_load_b128`，后面是 `v_rsq_f32`。
3. 记录以下几点，作为 P2 逐位一致的依据：
   - `ss/1280` 的实现方式：是完整的 `v_div_scale/v_div_fmas/v_div_fixup` 序列还是倒数乘法；
   - RoPE 是 `v_mul + v_sub/v_add` 还是收缩成了 `v_fma`；
   - bf16 转换用的指令（预计是 `v_cvt_pk_bf16_f32`，RNE）；
   - `xor 1` 的 shuffle 用的是 DPP 还是 `ds_swizzle/v_permlane`；
   - 存储的 scope（预计是 `global_store_b16 ... scope:SCOPE_DEV`）；
   - WMMA 前后编译器插入的 hazard 处理（`s_nop`/`v_nop` 或指令间距），包括"WMMA 读源寄存器后，load 再写同一寄存器"和"WMMA 结果被 VALU 读取"两种情况。
4. 输出 `notes/native_stage_c.md`，附相关反汇编片段。

### 步骤 2：编写 P1 ASM 与构建脚本
1. `asm/stage_c_gemm.s`：按 ASM_PSEUDO 第 3 节编写，10 步全部展开，4 级加载流水，与原生 `mx_loop(D=4)` 的取数和 WMMA 顺序一致。
2. `asm/build_fragment.py`：
   - 用 `llvm-mc` 汇编，用 `llvm-objdump` 反汇编回读；
   - 生成 `.long` 序列和 `contract.json`（固定输入、输出、写到的寄存器、clobber 字符串、字节数和 SHA-256）；
   - 审核规则：
     - 实际写到的寄存器必须是 clobber 的子集，输入寄存器只读；
     - 不出现 `s30–s39`/TTMP/M0/EXEC 写入，也不出现 `s_endpgm`、`s_setpc`；
     - 所有 VGPR < 256。
3. `kernels/stage_c_asm.py`：`stage_C_asm(c, phase, out=None)`：
   - 保留原 guard `(w < 6) & (w % 3 < MT)`；
   - 计算 `mi/n0` 和各 tile 基地址，`readfirstlane` 成 SGPR；
   - 调用 inline asm；P1 用原生的尾部代码处理返回的 `acc`。

### 步骤 3：单元 kernel 验证 P1
1. `unit_stage_c.py`：合成以下输入：
   - `qr8/qrs`：随机 e4m3 和 E8M0 码，码值在 118–124 之间；
   - `wqb/wqb_s`：形状和层权重相同；
   - `ss`：正数；
   - `rpos`：行位置；
   - `rcos/rsin`：用基线的 `rope_tables`。
2. 同一个 kernel 内分别运行原生和 ASM 版，写到两块输出，要求逐位相同。覆盖 `TR = 6, 16, 48`（MT = 1, 2, 3）。另加一组 NaN/Inf 码的边界输入，确认两边的 NaN 位置一致（对比按位模式，NaN 也要相同）。
3. 检查编译结果：kernel 的 `.vgpr_count` 不超过 512、无 scratch spill；`contract.json` 的审核全部通过。

### 步骤 4：接入 mono，跑 P1 的 dual 和 asm 两种模式
1. 复制基线 `run_test.py` 和 `run.sh` 到本目录，增加以下参数：
   - `--stagec {native,asm,dual}`
   - `--phase {1,2}`
   - `--dump-isa`
   - 历史区分配和逐层比较。
2. `dual`：先跑 48 行 × 4 层，再跑 48 行 × 40 层，要求每层 `H[2Ly] == H[2Ly+1]` 逐位相同。
3. `asm`：跑 48 行 × 4 层，按基线标准检查：无超时、数值健康、run-to-run 相对 L2 在容差内。
4. 对比整个 kernel 的资源（VGPR/SGPR/spill/占用率），以及每层耗时（设备时间戳 slot 0/18）。

### 步骤 5：P2（把尾部也换成 ASM）
1. 按步骤 1 记下的原生指令形式编写 `asm/stage_c_full.s`（ASM_PSEUDO 第 4 节），只有这样才能保证逐位一致。
2. 先在单元 kernel 上逐位验证，再在 mono 上跑 dual 和 asm 模式，标准与步骤 3、4 相同。

### 步骤 6：整理结果
在 `README.md` 中记录：替换范围、寄存器约定、所有运行命令、结果表（逐位一致的层数和元素数、资源、耗时），以及没有完成的部分。

## 6. 计划的目录结构

```text
mono_test_single11/
  PLAN.zh-CN.md            本文档
  ASM_PSEUDO.zh-CN.md      汇编伪代码与寄存器绑定
  asm/
    stage_c_gemm.s         P1：GEMM 主循环
    stage_c_full.s         P2：完整 tile 计算
    build_fragment.py      汇编 → .long + contract.json + 审核
  kernels/
    stage_c_asm.py         FlyDSL 包装（guard、tile 地址、inline asm、P1 尾部）
  unit_stage_c.py          单元 kernel：原生和 ASM 逐位对比
  run_test.py, run.sh      mono 单卡测试（来自 origin，增加 --stagec/--phase）
  notes/native_stage_c.md  原生 ISA 摘录
  build/                   生成物、日志、dump
```

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 内联 asm 中的 WMMA 和相邻 VMEM/VALU 之间的 hazard，LLVM 不会替 asm 内部插入处理 | 按步骤 1 摘录的原生间距处理；在 asm 末尾 WMMA 和交回 FlyDSL 之间加保守的等待，然后再按单元 kernel 结果收紧 |
| P2 尾部浮点运算和原生不一致（除法实现、FMA 收缩、舍入） | 严格照抄原生指令形式；单元 kernel 逐位验证 |
| clobber 范围较大（约 150 个 VGPR），迫使编译器在 stage_C 前后搬运活跃值，VGPR 总数上升 | stage_C 位置的活跃值很少（指针大多按需从表里重新读取）；步骤 3 检查 `.vgpr_count ≤ 512` 和 spill；必要时把加载流水从 4 级降到 2 级（约 80 个 VGPR） |
| guard 在 LLVM 看来是分支（`w` 来自 `opaque_v`） | 条件对整个 wave 统一，EXEC 进入时为全 1；ASM 内部的 DPP 和存储都假设 EXEC 全 1，在审核清单里注明 |
| `rpos * 64` 用 32 位偏移 | 合成输入的位置都远小于 2^25；包装函数在 host 端检查 `rpos < 2^25` |
| 本机 SCOPE_DEV 访问很慢（load 约 32.6 µs/次） | ASM 和原生都只有 store 是 SCOPE_DEV，load 都是普通 load，耗时对比是公平的 |
