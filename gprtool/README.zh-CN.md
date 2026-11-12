# gprtool：stage 插入点的真实 VGPR/SGPR 预算

回答两个问题：在 mono step kernel 的某个 stage 插入点，编译器真正要跨过去保留哪些寄存器？换成 asm 后，asm 可以用哪些寄存器、输入绑在哪里？

数字全部来自编译出的代码：FlyDSL 把 bitcode 交给修复版 LLVM（`/app/llvm-upstream/build`，gfx1250 inline asm 的 v256–v1023 clobber 生效），工具用同一条 llc 命令加 `-stop-before=prolog-epilog` 取寄存器分配后的 MIR，读每个基本块带 lane mask 的 `liveins`，往回推到每条标记 asm。分析结果再用 GPU 运行验证。

## 文件

| 文件 | 作用 |
|---|---|
| `gprtool.py` | 入口，子命令 `analyze` / `contract` / `verify` / `limit` |
| `probe.py` | FlyDSL 构建钩子：按 plan（`GPRTOOL_PLAN`）在每个 stage 调用处插标记、替换成 asm、加 clobber 或毒化代码 |
| `mir.py` | 分配后 MIR 的解析：基本块、指令的 def/use、标记处的活跃集合、溢出统计、立即数常量判定 |
| `regs.py` | MIR 寄存器名到 32 位单元（`v12`、`s5`、`vcc_hi`）的换算，区间格式化 |
| `report.py` | 把 json 结果生成 markdown 表 |
| `run_test.py` | mono kernel 的单 GPU 测试驱动（构建 `step.build` 的层循环、合成输入、检查结果、golden 对比），`probe.py` 在它之上挂钩子；来自 `mono_test_single12/run_test.py`，gprtool 只用 `--stagec native` |
| `stage_inputs.py` | 扫描 ATOM kernel 源码，找出每个 stage 读取的 `c[...]` 键（replace 模式的 asm 输入） |
| `llvm_patch/` | `/app/llvm-upstream` 的修复：gfx1250 上 inline asm 的 `{vN}`/`~{vN}`（N ≥ 256）不再被限定在 v0–v255。基于 `/app/llvm-upstream` 的提交 `2e27f6b7`（上游 `1df311a6` 加 FlyDSL 补丁），在 LLVM 源码根目录执行 `git apply` |
| `patches/` | `--patch` 用的 kernel 运行时补丁（实验用，不改 ATOM 源码） |

结果写在 `gprtool/build/gpr/`（被 `.gitignore` 忽略）：`analyze.json`、`contract.json`、`verify.json`、`limit.json`，每次构建一个子目录（`plan.json`、`log.txt`、`post.mir`、`bind.json`、`info.json`）。

## 子命令

```bash
cd /app/ATOM
python3 gprtool/gprtool.py analyze
python3 gprtool/gprtool.py contract [--replace stage_A stage_C ...] [--limit 512] [--vslack 0] [--patch patches/zero_sgpr_spill.py]
HIP_VISIBLE_DEVICES=1 python3 gprtool/gprtool.py verify [--only 'stage_C#0:in'] [--vrange 0 256] [--no-sgpr]
HIP_VISIBLE_DEVICES=1 python3 gprtool/gprtool.py limit [--at stage_E#0:in] [--n 512 768 1024]
python3 gprtool/report.py
```

- **analyze**（只编译，约 20 s）：每个 stage 调用前后插 `; gpr: <stage>#<k>:in` / `:out` 两条不带操作数的 asm，分配结果与原生 kernel 相同。输出每个点的入口/出口活跃集合，以及贯穿 stage 的集合（入口活跃 ∩ 出口活跃 − stage 内重新定义的）。
- **contract**（只编译，约 15 min）：`--replace` 里的 stage 每次调用都换成一条 asm，输入是该 stage 运行时读取的 `c[...]` 值和运行时参数（`stage_inputs.py` 扫描源码得到）。绑定：`v0` = 硬件线程号 tid（`thread_idx.x` 本身，只读，每个 asm 都绑定；asm 自己从 v0 得到 t）；SGPR 从 s0 开始，64 位优先、偶数对齐，跳过预留寄存器，作为 tied output 声明（asm 可以改写）。然后：
  1. 不声明 clobber 编译一次（R0）。**禁止任何 SGPR spill**（spill 到 VGPR lane 或 scratch 都不行）：R0 只要有一条就报错退出（rc 2），并打印每条 spill 所在区域和被 spill 的值的定义指令。原生 ATOM 源码会出现这种情况，需要加 `--patch patches/zero_sgpr_spill.py`。
  2. 取每个 asm 之后仍活跃（跨 asm）的物理寄存器个数 K。保留窗口：VGPR 为堆顶部 K 个（加 `--vslack`），SGPR 为可用 SGPR 顶部 K 个；其余寄存器全部逐个声明为 clobber。
  3. SGPR 窗口取不产生任何 SGPR spill 的最小全局余量，再逐点收回。VGPR 窗口不加余量，放不下的由 LLVM 生成 scratch，工具给出警告，并按区域列出 scratch 指令数。最终构建再检查一遍：SGPR spill 为 0，跨 asm 活跃的普通寄存器都在窗口内。

  每个调用点输出：调用前和调用后的活跃寄存器（最终构建）、跨调用必须保留的个数（R0 → 最终）、入参绑定的 VGPR/SGPR 个数和具体寄存器、保留窗口、asm 可用的 VGPR/SGPR 区间（包括可改写的 SGPR 入参）、可 clobber 的 `vcc_lo`/`vcc_hi`/`scc`、该点之后的 VGPR scratch 指令数。
- **verify**（GPU，约 2 min）：用 analyze 构建，在每个标记处把判为"死"的寄存器写成 `0xDEAD0000 + n`（SGPR 是 `0xDEAD8000 + n`），并逐个声明为 clobber，然后和 golden 对比；负对照（`--negative`，默认 `stage_E#0:in`）把活跃的 VGPR 也毒化，应当出错。`--only`、`--vrange`、`--no-sgpr` 用来二分定位问题点。
- **limit**（GPU）：在 `--at` 处声明 clobber v(n−1)，看 kernel 的 VGPR 数变成 n 后能否启动。
- **`--patch FILE`**（所有子命令）：构建时在 trace 之前执行一个 python 文件，对 kernel 模块做运行时替换，不改 ATOM 源码，用来评估源码改动对寄存器的影响。`patches/zero_sgpr_spill.py` 用 `patches/step.py`（`kernels/step.py` 的修改副本）替换 step 模块，并给 front 子阶段加区间边界。改法：kernarg 和指针表按区间、按基本块重新读取（不透明基址）；层循环和内层循环里用到的 `b` / `lc` / `Ly` 都用不透明副本，避免被 LICM 提到循环外；上下文改为用到时才读。效果：原生和 R0 的 SGPR spill 都为 0，原生 VGPR scratch 从 33 条降到 10 条，GPU 结果与原生一致（两者都有同样的间歇性失败，不是补丁引入的）。旧的 `patches/sload_epoch.py`（只做到 17 条）：让 step.py 读指针表时以 handoff / front 子阶段为界重新读取（不跨区间合并，也不被提到层循环外），层循环里的 front 改成用到时才读指针。效果：原生 SGPR 溢出从 58 条写入降到 17 条（R0 从 75 条降到 18 条），`front_B#1` 的 asm SGPR 从 7 个增加到 44 个，`front_D#0` 从 24 个增加到 52 个（结果在 `build/gpr_patch/`）。

## asm 必须遵守的规则（都是用本工具实测得到的）

1. **用到的寄存器全部逐个声明为 clobber。** post-RA 调度器会把与 asm 没有寄存器依赖的指令跨过 asm 移动，`sideeffect` 不起作用。不声明就写，在 16 个插入点会破坏活跃值（GPU 访存出错）。`~{v[a:b]}` 这种区间写法 LLVM 不认，必须逐个列出。
2. **自己保存和恢复 VGPR MSB。** 没有 VGPR 操作数的 asm 入口处 MSB 是任意的，结束后编译器又假定它没变：

   ```
   s_getreg_b32  sT, hwreg(HW_REG_WAVE_MODE, 12, 8)
   s_set_vgpr_msb 0x0          // 写 v256–v511 前改成 0x40（dst）等
   ...
   s_setreg_b32  hwreg(HW_REG_WAVE_MODE, 12, 8), sT
   s_nop 0                     // 紧跟 MODE setreg 的 s_set_vgpr_msb 会被丢弃
   ```

   只写 v0–v255 也要这样做，否则同样会出错。`s_set_vgpr_msb` 的 imm[7:0] 是新模式，每 2 位对应一个操作数位置：src0 [1:0]、src1 [3:2]、src2 [5:4]、dst [7:6]；imm[15:8] 是旧模式。
3. **预留寄存器：** s32（栈）、s102:s103（长跳转）、s105（EXEC 拷贝）、m0都不能碰（SGPR 不再 spill，所以没有 WWM 寄存器）；`exec` 和 v0 退出时必须保持原值。wave32 下 `vcc_hi` 是一个普通 SGPR，能否 clobber 按 contract 的结果。
4. **VGPR 上限 v511：** 256 线程的 CTA，kernel 的 VGPR 数到 768 时启动报 `hipErrorLaunchOutOfResources`。

## 已知限制

- 窗口放在寄存器堆顶部；改成 R0 中实际用到的那组寄存器反而更差，因为贪心分配器不会照搬 R0 的解。
- 线程号的处理决定了 VGPR scratch 的多少。`opaque_v` 的 `"=v,0"` 操作数只能放在 v0–v255，而低区在 asm 处几乎全被 clobber，所以凡是跨 asm 存活、又要喂给 `opaque_v` 的值都会被 spill。因此有两条做法：asm 绑定硬件线程号本身（整个 kernel 里只有这一个值，常驻 v0）；补丁版 step.py 里，线程号副本一律用到时才现做（`fresh_t()`），不长期持有。不能直接到处用 `thread_idx.x`，否则相同的比较会被合并成长期存活的 SGPR mask，产生 SGPR spill。这样做之后 contract 的 scratch 是 14 条：分配器在未替换的原生 stage 内部临时把 tid 挪出 v0。
- 契约表里的 scratch 对应 asm 用满“可用”寄存器的情形；asm 实际 clobber 得少时更少（每个 asm 只 clobber 6 个 VGPR 时为 0 条）。
- 数字适用于 `--replace` 列出的那组 stage 同时替换的情形，换一组要重新跑 contract。
- 2026-11-11 跑 `limit --n 1024` 时 GPU 驱动卡死，测试进程停在 D 状态，需要复位驱动。复位后再跑 GPU 子命令。
