# 原生 stage_C 的 ISA 摘录（PLAN 步骤 1）

来源：`build/isa/unit_native.s`，即 `unit_stage_c.py --mode native` 的最终 ISA（单元 kernel 中只有 stage_C）。mono 中的 stage_C 见 `build/isa/mono_native.s`，指令形式相同。

## 主循环（P1 已复现）

- 操作数顺序：`v_wmma_scale_f32_16x16x128_f8f6f4 D, A, B, C, SA, SB`，其中 A 来自 `qr8`，B 来自 `wqb`，SA 来自 `qrs`，SB 来自 `wqb_s`，opsel 全为 0；第一步的 C 是内联常数 0。
- 4 级加载流水，每步先发 B 再发 A。A 和 B 用 64 位地址的 `global_load_b128 … off offset:kb+32c`；scale 用 `global_load_b64` 一次取两步的 4 码。我们的片段用 saddr 形式、每步 `b32`，数值相同。
- hazard：
  - WMMA 刚读完的寄存器，紧接着被 VMEM load 覆盖：编译器**不插**等待；
  - VALU 写 WMMA 刚读过的 A/B 寄存器：插 **4 个 `v_nop`**。和 LLVM `GCNHazardRecognizer::checkWMMACoexecutionHazards` 一致：这条 WMMA 延迟 8，属类别 0，VALU 需要 4 个 wait state；
  - VALU 读 WMMA 的结果（D）也需要 4 个 wait state，所以片段末尾放了 4 个 `v_nop`。

## 尾部（P2 必须照抄）

| 原生代码 | 指令形式 |
|---|---|
| `ss / F32(1280)` | 完整 IEEE 除法：`v_div_scale_f32`（分母、分子各一次）→ `v_rcp_f32` → `v_fma_f32/v_fmac_f32`（两轮牛顿迭代）→ `v_div_fmas_f32`（**读 VCC**，用 `s_mov_b32 vcc_lo, sN` 切换各行的标志）→ `v_div_fixup_f32`。会用到 VCC 和若干 SGPR 临时寄存器 |
| `+ F32(1e-20)` | `v_pk_add_f32 v[a:a+1], 0x1e3ce508, v[b:b+1] op_sel_hi:[0,1]`，两行一组 |
| `rsq(...)` | `v_rsq_f32` |
| `cv = acc * rstd` | `v_mul_f32`（`v_dual_mul_f32`） |
| `x = cv.to(BF16).to(F32)` | **`v_fma_mixlo_bf16 vX, acc, rstd, neg(0)`**：直接把 acc·rstd 舍入成 bf16，只舍入一次，不经过 f32 的 cv |
| `y = cv.shuffle_xor(1).to(BF16)` | `v_cvt_pk_bf16_f32_e64_dpp vY, cv, s0 quad_perm:[1,0,3,2] … bound_ctrl:1`：先取邻居 lane 的 f32 cv，再舍入 |
| `x * cs`、`y * sn` | `v_fma_mix_f32_bf16 v, v(bf16), cs/sn(bf16), neg(0) op_sel_hi:[1,1,0]`。两个 bf16 的乘积在 f32 中是精确的 |
| 偶数 lane 取负 | `v_cmp_eq_u32 vcc, 0, l&1` + `v_cndmask_b32 v, v, -v, vcc` |
| 相加 | `v_add_f32`（x·cs + (±y·sn)），没有收缩成 FMA |
| RoPE 选择 | `v_cmp_lt_i32 vcc, 0x1bf, n0%512` + `v_cndmask_b32` |
| bf16 存储 | `v_cvt_pk_bf16_f32 v, res, s0`（只用低半）→ `global_store_b16 … scope:SCOPE_DEV`，每两条 store 之间有 `s_wait_xcnt 0x0` |

和 [ASM_PSEUDO](../ASM_PSEUDO.zh-CN.md) 第 4 节伪代码的差异（写 P2 时以本表为准）：

- x 要用 `v_fma_mixlo_bf16(acc, rstd)`，不能用 `cvt_pk_bf16(cv)`。两者在双重舍入的边界情况下结果不同。
- 乘法用 `v_fma_mix_f32_bf16`，偶数 lane 取负用 `v_cndmask`。伪代码里"翻符号位再相加"的位模式与之相同，可以保留，但为了和原生指令一致，优先照抄原生写法。
- 除法序列需要 VCC 和 SGPR 临时寄存器，P2 的 clobber 要加上 `vcc` 和这些 SGPR（避开 s30–s39）。
