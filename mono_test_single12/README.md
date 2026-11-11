# mono_test_single12：整个 stage_C 用 sp3 asm 实现（P2）

`attention.stage_C(c)` 的全部工作都在一段 inline sp3 片段里完成：wave guard、tile 坐标、wq_b MXFP8 GEMM、q_norm rstd、RoPE、bf16 存储。Python 侧只剩一个 wrapper：从字典 `c` 里取出片段需要的参数，交给 inline asm。

在 mono 的 dual 模式下（同一次 launch、同一份输入，每层先算原生 stage_C 再算 asm 版），4 层和 40 层、48 行和 6 行，所有层的 q 都与原生**逐位一致**。资源与原生相同：358 VGPR、105 SGPR，scratch 从 20 B 降到 16 B。

P1（只把 GEMM 主循环换成 asm）见 [`../mono_test_single11`](../mono_test_single11/README.md)，本目录的基础设施从那里复制而来。

## 文件

| 文件 | 内容 |
|---|---|
| `sp3/stage_c_full.sp3` | P2 片段源码（头注释写明寄存器契约和 hazard 处理） |
| `sp3/ref/` | 参考 sp3（poc_kl_sim 的 MXFP8 GEMM），GEMM 主循环由它改写 |
| `asm/build_fragment.py` | sp3 编译 → 去掉 `s_version` / 填充 → llvm-mc 反汇编 → 寄存器审计 → 生成 `build/asm/<name>.{inc,disasm.txt,contract.json}` |
| `kernels/stage_c_asm.py` | wrapper `stage_C_asm(c)` |
| `unit_stage_c.py` | 单元 kernel：只有 stage_C，原生 vs asm 逐位比较 |
| `run_test.py`、`run.sh` | mono 单卡测试（`--stagec native/asm/dual`，从 single11 复制，docstring 已更新） |
| `notes/native_stage_c.md` | 原生 epilogue 的 ISA 形式，以及 P2 与之的对应关系 |
| `build/isa/mono_asm.s` | asm 模式 mono 的最终 ISA |

## wrapper：从字典 `c` 到寄存器

```python
def stage_C_asm(c):
    args = [l]                                                       # v0
    args += [readfirstlane(c[k]) for k in ("qr8", "wqb", "qrs", "wqb_s", "ss", "q", "rpos", "rcos", "rsin")]   # s[0:17]
    args += [readfirstlane(c["b"]), readfirstlane(c["w"]), wave_mask(c["MT"])]                                    # s18 s19 s20
    llvm.inline_asm(None, args, FULL_TEXT, constraints, has_side_effects=True, ...)
```

- 传入的指针都是字典里的**原始基址**；tile、行、lane 的偏移全部在片段内用 VGPR 计算，作为 voffset 使用。这样片段不需要 SGPR 临时寄存器，clobber 只有 v1–v151、`vcc`、`scc`、`memory`。
- `MT` 是 trace 期常量，wrapper 把 guard `(w < 6) & (w % 3 < MT)` 折叠成掩码：MT=3 时是 `0b111111`，MT=1 时是 `0b001001`。片段入口用 `s_bitcmp1_b32 s20, s19` 判断，不该干活的 wave 直接跳到末尾。
- trace 期断言：`c["stx"] is stx_dev`（片段固定用 `global_store_b16 scope:SCOPE_DEV`）；`QL/NQ/HD/CTAS = 1280/8192/512/256`；`NORM_EPS` 的位模式是 `0x1e3ce508`。
- 约束串由 `build_fragment.py` 按 `FRAGMENTS["stage_c_full"]` 生成，存在 `build/asm/stage_c_full.contract.json` 中：`{v0},{s[0:1]},…,{s20},~{v1},…,~{v151},~{vcc},~{scc},~{memory}`。

调用栈与 P1 相同，只是最后一层变了：`step.body` → `for Ly` → `stage_C(c)`（运行时已被换成 `stage_C_asm`）→ `llvm.inline_asm` → 片段。

## 片段结构（`sp3/stage_c_full.sp3`，430 条指令，3660 字节）

1. 入口 `s_wait_xcnt 0`，然后做 guard。
2. 计算 tile 坐标：`j = (11w) >> 5`，`mi = w - 3j`，`n0 = (b + 256j) * 16`；再算出 A/B/SA/SB 四个 voffset。
3. GEMM：与 P1 相同，4 级 load 流水，10 步 `v_wmma_scale_f32_16x16x128_f8f6f4`，最后接 4 个 `v_nop`。
4. rstd：逐行做原生的完整 IEEE 除法序列（`div_scale` → `rcp` → 牛顿迭代 → `div_fmas` → `div_fixup`），然后 `+eps` → `rsq`，得到 `cv = acc * rstd`。
5. RoPE：仅当 `n0 % 512 >= 448` 时执行（wave 一致，用 `s_cbranch_vccz` 跳过）。
   - 先算 `fi*2` 和 64 位的 rcos/rsin 地址，用 `global_load_u16` 取表；
   - `x = cvt_pk_bf16(cv)`，`y = cvt_pk_bf16_e64_dpp(cv, quad_perm:[1,0,3,2])`；
   - 两个乘积用 `v_fma_mix_f32_bf16`，偶数 lane 用 `v_cndmask` 取负，最后 `v_add_f32`。
6. 存储：`v_cvt_pk_bf16_f32` → `global_store_b16 … scope:SCOPE_DEV`，相邻两条 store 之间有 `s_wait_xcnt 0`。出口有 `s_wait_xcnt 0` 和 `s_wait_storecnt 0`，因为 LLVM 的 waitcnt pass 看不到片段内的 store。

LLVM 不检查 inline asm 内部的 hazard，片段里手工处理了以下几类（gfx1250 只剩这些需要处理的 hazard）：

- WMMA → VALU：4 个 wait state；
- TRANS（`v_rcp`、`v_rsq`）之后，如果紧跟的 VALU 读它的结果或改写它的源寄存器，中间插 `v_nop`（`FeatureTransCoexecutionHazard`）；
- 入口和 store 之间的 xcnt 等待。

gfx1250 属于 `hasNoDataDepHazard` 的架构，DPP、`div_fmas` 读 VCC 这两类旧架构的 nop 规则不适用。

SP3 语法要点：

- 带 bf16 源操作数的 `fma_mix` 写成 `v[x].l`，会把 op_sel_hi 置 1；
- 原生的 `neg(0)` 写成 `-0.0`，编码为 f32 字面量 `0x80000000`，数值语义相同；
- DPP 直接在指令后加 `quad_perm:[…] row_mask bank_mask bound_ctrl`；
- 分支标签要以 `label_` 开头。

## 结果

| 测试 | 结果 |
|---|---|
| `unit_stage_c.py`（rows 48/32/16/6 × seed × 有无特殊值：NaN 行/列、inf、E8M0 下溢、ss=0、ss=3e38） | 全部 0 mismatch；MT×16 行之外没有任何写入 |
| 负测试：去掉偶数 lane 取负 | 被检出（FAIL） |
| mono dual，48 行 × 4 层 × 3 次 launch | 每次 launch 的 4 层全部逐位一致 |
| mono dual，48 行 × 40 层 × 3 次 launch | 每次 launch 的 40 层全部逐位一致 |
| mono dual，6 行 × 4 层 | PASS |
| mono asm（kernel 中只有 asm 版 stage_C），4 层 / 8 层 | PASS，输出有限、有界，kv_rows 的 run-to-run 差异 0.09–0.17，与原生的 0.06–0.27 同量级 |
| 每层耗时，4 层 × 5 次 launch | 原生 53.8–58.2 ms，asm 54.5–60.6 ms，差别在噪声范围内 |

### 一个需要注意的发现：x 的舍入

源码是 `x = cv.to(BF16)`，即先得到 f32 的 cv，再舍入成 bf16，共两次舍入。mono 里的原生代码就是这样编译的。但在只含 stage_C 的单元 kernel 里，LLVM 把它折叠成了 `v_fma_mixlo_bf16(acc, rstd)`，只舍入一次。

我最初照抄的是单元 kernel 的形式，单元测试全部通过，mono dual 却在每次 launch 的 157 万个 q 元素里出现 1 个 1-ulp 差异（都在 RoPE 列）。改成两次舍入后 mono 逐位一致，单元测试仍然通过：单元测试的随机输入碰不到 bf16 舍入中点，把 x 换成两种写法中的任何一种都能通过。所以**以 mono 的 dual 模式为准**。

## 运行

```bash
cd /app/ATOM/mono_test_single12
python3 asm/build_fragment.py stage_c_full          # 改了 sp3 之后重建（FRAGMENT_TAG 随之变化，JIT 缓存自动失效）
PYTHONPATH=/app/ATOM python3 unit_stage_c.py         # 单元测试，逐位比较
./run.sh --stagec dual --layers 40 --out build/result_dual_L40.json
./run.sh --stagec asm  --layers 4  --out build/result_asm_L4.json
```
