# stage_C 的 ASM 伪代码与寄存器绑定

对应 [PLAN.zh-CN.md](PLAN.zh-CN.md) 的 P1（只做 GEMM 主循环）和 P2（完整 tile 计算）。目标是 gfx1250、wave32。下文出现的每种指令格式都已用 `/opt/rocm/llvm/bin/llvm-mc -mcpu=gfx1250` 汇编通过：`global_load_b128/b32` 的 saddr 形式、`v_wmma_scale_f32_16x16x128_f8f6f4`、DPP `quad_perm`、`v_cvt_pk_bf16_f32`、`global_store_b16 … scope:SCOPE_DEV`、`v_mad_u32_u24`、`v_lshl_add_u32`、`s_cmp_lt_u32`。

记号：`l` 为 lane（0..31），`r = l & 15`，`h = l >> 4`。i 行 = tile 内第 `h*8 + i` 行，i = 0..7。

## 1. 原生代码在 lane 层面做了什么（ASM 要逐位复现）

| 内容 | 原生代码 | lane l 的值 |
|---|---|---|
| A 操作数（每个 K128 步） | `ld_op(arow, kb, l)` | 16 个 dword，来自 `qr8 + (mi*16 + r)*1280 + kb + 16h + 32c` 处的 4 次 16 B 读取，c = 0..3 |
| A 的 scale | `gload(qrs + (mi*16 + r)*40 + kb/32, I32)` | 第 `mi*16 + r` 行在这个 K128 内的 4 个 E8M0 码 |
| B 操作数 | `ld_op(brow, kb, l)` | 同上，行为 `n0 + r`，基址 `wqb`，行跨度 1280 |
| B 的 scale | `gload(wqb_s + ((n0 + r)//32)*40 + kb/32, I32)` | 因为 n0 是 16 的倍数，`(n0 + r)//32 = n0//32`，**所有 lane 读同一个地址** |
| WMMA | `wmma_mx(A, SA, B, SB, c)` | `v_wmma_scale_f32_16x16x128_f8f6f4 D, A, B, C, SA, SB`，opsel 为 0；第一步 C 用内联常数 0 |
| 累加器 | `acc[i]`，i = 0..7 | 第 `mi*16 + h*8 + i` 行、第 `n0 + r` 列 |
| rstd | `acc[i] * rsq(ss[row]/1280 + 1e-20)` | `ss` 每行 1 个 f32 |
| RoPE（仅当 `n0 % 512 >= 448`） | `fi = (n0%512 + r - 448) >> 1`；x = bf16(cv)，y = bf16(cv 取 lane^1 的值)；奇数 lane：`y*sn + x*cs`，偶数 lane：`x*cs - y*sn` | `cs/sn = bf16 表[rpos[row]*32 + fi]` |
| 存储 | `stx_dev(q + (row*8192 + n0 + r)*2, bf16)` | `global_store_b16 … scope:SCOPE_DEV` |

## 2. 包装函数（FlyDSL 侧，`kernels/stage_c_asm.py`）

```python
@ASTRewriter.transform
def stage_C_asm(c, phase):
    w, l, b, MT = c["w"], c["l"], c["b"], c["MT"]
    if (w < 6) & (w % 3 < MT):                       # guard 不变，对整个 wave 统一（EXEC 全 1）
        wu  = readfirstlane(w)                        # 后面的 tile 坐标都基于 wave 统一的值
        mi  = wu % 3
        n0  = (b + (wu // 3) * 256) * 16
        S0  = rfl64(c["qr8"]   + mi*16*1280)          # -> s[0:1]
        S2  = rfl64(c["wqb"]   + n0*1280)             # -> s[2:3]
        S4  = rfl64(c["qrs"]   + mi*16*40)            # -> s[4:5]
        S6  = rfl64(c["wqb_s"] + (n0//32)*40)         # -> s[6:7]
        if phase == 1:
            acc = inline_asm(vec8f32, [l, S0, S2, S4, S6], P1_TEXT, P1_CONSTRAINTS)
            ...  # 后面是原 attention.py:318–330 的尾部，原样照抄，acc 用的是 asm 的输出
        else:
            S8  = rfl64(c["ss"]   + mi*16*4)          # -> s[8:9]
            S10 = rfl64(c["q"]    + (mi*16*8192 + n0)*2)   # -> s[10:11]（dual 模式下改成历史区地址）
            S12 = rfl64(c["rpos"] + mi*16*8)          # -> s[12:13]
            S14 = rfl64(c["rcos"]); S16 = rfl64(c["rsin"])  # -> s[14:15], s[16:17]
            S18 = rfl32(n0 % 512)                     # -> s18
            inline_asm(None, [l, S0, S2, S4, S6, S8, S10, S12, S14, S16, S18], P2_TEXT, P2_CONSTRAINTS)
```

`rfl64/rfl32` 是 `rocdl.readfirstlane`。`l` 是 `t % 32`，以 VGPR 形式传入。

## 3. P1：GEMM 主循环

### 3.1 寄存器绑定

**输入（只读，固定寄存器）**

| 寄存器 | 约束 | 内容 | 由谁计算 |
|---|---|---|---|
| `v0` | `{v0}` | lane `l`（0..31） | FlyDSL：`t % 32` |
| `s[0:1]` | `{s[0:1]}` | A tile 基址 = `qr8 + mi*16*1280`（字节地址） | FlyDSL，readfirstlane |
| `s[2:3]` | `{s[2:3]}` | B tile 基址 = `wqb + n0*1280` | 同上 |
| `s[4:5]` | `{s[4:5]}` | A scale 基址 = `qrs + mi*16*40` | 同上 |
| `s[6:7]` | `{s[6:7]}` | B scale 基址 = `wqb_s + (n0/32)*40` | 同上 |

**输出**

| 寄存器 | 约束 | 内容 |
|---|---|---|
| `v[8:15]` | `={v[8:15]}`（`vector<8xf32>`） | `acc[i]` = 第 `h*8+i` 行、第 `r` 列的 fp32 累加值（tile 内坐标） |

**ASM 内部使用的寄存器（声明为 clobber）**

| 寄存器 | 用途 |
|---|---|
| `v1` | `voff_AB = r*1280 + h*16`（A、B 共用，因为两者行跨度都是 1280） |
| `v2` | `voff_SA = r*40` |
| `v3` | 0（B scale 的地址对所有 lane 相同） |
| `v4` | 临时值 |
| `v[16:31] v[32:47] v[48:63] v[64:79]` | A 的 4 个流水槽 S0..S3 |
| `v[80:95] v[96:111] v[112:127] v[128:143]` | B 的 4 个流水槽 |
| `v144..v147` | A scale 的 4 个流水槽 |
| `v148..v151` | B scale 的 4 个流水槽 |

约束字符串：

```text
={v[8:15]},{v0},{s[0:1]},{s[2:3]},{s[4:5]},{s[6:7]},~{v1},~{v2},~{v3},~{v4},~{v16},~{v17},...,~{v151},~{memory}
```

clobber 必须逐个列出（`~{v[16:151]}` 这种区间写法会被 LLVM 静默忽略，mono_test11 已证实）。P1 不写 SGPR，不写 VCC/SCC，不改 EXEC/M0/MODE。

### 3.2 伪代码

正式实现见 `sp3/stage_c_gemm.sp3`。实现时有两处改动：入口加了 `s_wait_xcnt 0`（LLVM 不会为 inline asm 的 clobber/输出插入这个等待，紧挨在片段前的 store 可能还在读将被改写的 VGPR）；`WMMA_WAR_GUARD` 为空（原生 ISA 证实 VMEM 覆盖 WMMA 源寄存器无需等待），`WMMA_RAW_GUARD` = 4 个 `v_nop`。

```asm
// ---------- 地址准备 ----------
    s_wait_xcnt      0
    v_and_b32        v4, 15, v0                 // r
    v_lshrrev_b32    v1, 4, v0                  // h
    v_lshlrev_b32    v1, 4, v1                  // 16*h
    v_mad_u32_u24    v1, v4, 1280, v1           // voff_AB = r*1280 + 16h
    v_mul_u32_u24    v2, 40, v4                 // voff_SA = r*40
    v_mov_b32        v3, 0                      // voff_SB

// ---------- 取一个 K128 步的数据：ISSUE(k)，槽 s = k % 4，kb = 128*k ----------
// 顺序与原生 mx_loop 一致：先 B 再 A（fb 在 fa 之前），每步共 10 条 load
.macro ISSUE k
    s  = \k % 4 ;  kb = 128 * \k
    A  = 16 + 16*s ;  B = 80 + 16*s ;  SA = 144 + s ;  SB = 148 + s
    global_load_b128 v[B+0 :B+3 ],  v1, s[2:3] offset:kb+0
    global_load_b128 v[B+4 :B+7 ],  v1, s[2:3] offset:kb+32
    global_load_b128 v[B+8 :B+11],  v1, s[2:3] offset:kb+64
    global_load_b128 v[B+12:B+15],  v1, s[2:3] offset:kb+96
    global_load_b32  v[SB],         v3, s[6:7] offset:kb/32
    global_load_b128 v[A+0 :A+3 ],  v1, s[0:1] offset:kb+0
    global_load_b128 v[A+4 :A+7 ],  v1, s[0:1] offset:kb+32
    global_load_b128 v[A+8 :A+11],  v1, s[0:1] offset:kb+64
    global_load_b128 v[A+12:A+15],  v1, s[0:1] offset:kb+96
    global_load_b32  v[SA],         v2, s[4:5] offset:kb/32
.endm
// 立即数偏移最大为 1152+96 = 1248，在 gfx1250 的 24 位有符号范围内；10 步全部展开，不需要 SALU 改地址

// ---------- 流水 ----------
    ISSUE 0
    ISSUE 1
    ISSUE 2
    ISSUE 3
.for k = 0 .. 9
    s_wait_loadcnt  WAIT[k]                     // WAIT = 30,30,30,30,30,30,30,20,10,0（见 3.3）
    v_wmma_scale_f32_16x16x128_f8f6f4  v[8:15], v[A(k):A(k)+15], v[B(k):B(k)+15], C(k), v[SA(k)], v[SB(k)]
                                                // C(0) = 0（内联常数），其后 C(k) = v[8:15]
    .if k + 4 <= 9
        WMMA_WAR_GUARD                          // 槽 k%4 刚被 WMMA 读过，下面要用 load 覆盖它：间距照抄原生（步骤 1）
        ISSUE k+4
    .endif
.endfor
    WMMA_RAW_GUARD                              // 交回 FlyDSL 前，保证 v[8:15] 可以被 VALU 读取（照抄原生 WMMA→VALU 间距）
// 结束：v[8:15] = acc。没有 s_endpgm，直接接 FlyDSL 的后续代码
```

### 3.3 `s_wait_loadcnt` 的取值

gfx1250 上同类 load 按发出顺序返回，每步 10 条 load。执行第 k 条 WMMA 前，必须等槽 k 到齐，允许后面已发出的槽仍在路上：

| k | 已发出的步 | 槽 k 之后还在路上的 load 数 | WAIT[k] |
|---|---|---|---|
| 0 | 0–3 | 30 | 30 |
| 1–6 | 0..k+3（每条 WMMA 后补发一步） | 30 | 30 |
| 7 | 0–9 | 20 | 20 |
| 8 | 0–9 | 10 | 10 |
| 9 | 0–9 | 0 | 0 |

### 3.4 和原生版逐位一致的依据

K 的累加顺序（0→9）、每步的 A/B/scale 数值、WMMA 指令及其 opsel、初始 C = 0 都和原生 `mx_loop` 完全相同。WMMA 的结果只取决于这些输入，和加载时序无关。

## 4. P2：完整 tile 计算

### 4.1 寄存器绑定

**输入（只读）**：P1 的五个输入加上下表（P2 没有寄存器输出）。

| 寄存器 | 约束 | 内容 |
|---|---|---|
| `v0` | `{v0}` | lane `l` |
| `s[0:1]` `s[2:3]` `s[4:5]` `s[6:7]` | 同 P1 | A、B、A scale、B scale 的 tile 基址 |
| `s[8:9]` | `{s[8:9]}` | `ss + mi*16*4`（本层 ss 区，已按层偏移） |
| `s[10:11]` | `{s[10:11]}` | `q + (mi*16*8192 + n0)*2`；dual 模式下改成历史区 `H[k]` 的同一位置 |
| `s[12:13]` | `{s[12:13]}` | `rpos + mi*16*8`（int64 位置） |
| `s[14:15]` | `{s[14:15]}` | `rcos`（bf16 `[pos][32]`） |
| `s[16:17]` | `{s[16:17]}` | `rsin`（bf16 `[pos][32]`） |
| `s18` | `{s18}` | `nmod = n0 % 512`（决定是否做 RoPE，wave 统一） |

**ASM 内部使用的寄存器（clobber）**

| 寄存器 | 用途 |
|---|---|
| `v1–v4`、`v16–v151` | P1 部分同上；GEMM 结束后槽寄存器复用为下列尾部临时寄存器 |
| `v[8:15]` | acc → cv（就地计算）；P2 中是 clobber，不是输出 |
| `v5` | 偶数 lane 的符号掩码 = `((l & 1) ^ 1) << 31` |
| `v6` | `voff_q = h*131072 + r*2`（131072 = 8 行 × 8192 × 2 B） |
| `v7` | `voff_ss = h*32` |
| `v40` | `voff_rpos = h*64` |
| `v41` | `fi2 = (nmod + r - 448) & ~1`，即 fi*2 的字节偏移 |
| `v[16:23]` | ss[i] → rstd[i] |
| `v[24:39]` | rpos[i]（8 个 i64，只用低 32 位） |
| `v[48:55]` / `v[56:63]` | cs[i] / sn[i] |
| `v[64:71]` | rope 表的偏移 |
| `v[72:79]` / `v[80:87]` | x[i] / y[i] |
| `v[88:95]` | 结果 |
| `v[96:99]` | bf16 打包结果 |
| `scc` | `s_cmp` 和分支 |
| `vcc`（视情况） | 如果原生的 `/1280` 是完整除法序列（`v_div_scale` 写 VCC，`v_div_fmas` 读 VCC），就要声明 `~{vcc}` |

约束字符串：

```text
{v0},{s[0:1]},{s[2:3]},{s[4:5]},{s[6:7]},{s[8:9]},{s[10:11]},{s[12:13]},{s[14:15]},{s[16:17]},{s18},
~{v1},...,~{v151},~{scc},~{memory}[,~{vcc}]
```

P2 不写任何 SGPR（`s18` 只读），不用 `s30–s39`。

### 4.2 伪代码

```asm
    <P1 的地址准备 + 流水，结果在 v[8:15]>
    WMMA_RAW_GUARD

// ---------- rstd ----------
    v_lshrrev_b32    v7, 4, v0
    v_lshlrev_b32    v40, 6, v7                 // voff_rpos = h*64
    v_lshlrev_b32    v7, 5, v7                  // voff_ss = h*32
    global_load_b128 v[16:19], v7, s[8:9] offset:0     // ss[h*8 + 0..3]
    global_load_b128 v[20:23], v7, s[8:9] offset:16    // ss[h*8 + 4..7]
    s_wait_loadcnt   0
.for i = 0 .. 7
    DIV_BY_1280      v[16+i], v[16+i]           // 照抄原生 fdiv(ss, 1280.0) 的指令序列（步骤 1）
    v_add_f32        v[16+i], 0x1e3ce508, v[16+i]   // + 1e-20（f32 位模式）；加法顺序以原生为准
    v_rsq_f32        v[16+i], v[16+i]
    v_mul_f32        v[8+i],  v[8+i], v[16+i]   // cv[i] = acc[i] * rstd[i]（乘法顺序以原生为准）
.endfor

// ---------- 存储偏移 ----------
    v_and_b32        v4, 15, v0                 // r
    v_lshrrev_b32    v6, 4, v0
    v_lshlrev_b32    v6, 17, v6                 // h*131072
    v_lshl_add_u32   v6, v4, 1, v6              // voff_q = h*131072 + r*2

    s_cmp_lt_u32     s18, 448
    s_cbranch_scc1   .Lplain                    // 不是 RoPE 列，跳过

// ---------- RoPE 路径（nmod ∈ {448, 464, 480, 496}） ----------
    v_add3_u32       v41, s18, v4, -448
    v_and_b32        v41, -2, v41               // fi*2（字节）
    v_and_b32        v5, 1, v0
    v_xor_b32        v5, 1, v5
    v_lshlrev_b32    v5, 31, v5                 // 偶数 lane = 0x80000000，奇数 lane = 0
    global_load_b128 v[24:27], v40, s[12:13] offset:0
    global_load_b128 v[28:31], v40, s[12:13] offset:16
    global_load_b128 v[32:35], v40, s[12:13] offset:32
    global_load_b128 v[36:39], v40, s[12:13] offset:48 // rpos[h*8 + 0..7]
    s_wait_loadcnt   0
.for i = 0 .. 7
    v_lshl_add_u32   v[64+i], v[24+2i], 6, v41  // pos*64 + fi*2（host 端保证 pos < 2^25）
    global_load_u16  v[48+i], v[64+i], s[14:15] // cs 的 bf16 位
    global_load_u16  v[56+i], v[64+i], s[16:17] // sn 的 bf16 位
.endfor
.for i = 0 .. 7                                 // 加载期间先算 x、y
    v_cvt_pk_bf16_f32 v[72+i], v[8+i], v[8+i]
    v_lshlrev_b32    v[72+i], 16, v[72+i]       // x = f32(bf16(cv))
    v_mov_b32_dpp    v[80+i], v[8+i] quad_perm:[1,0,3,2] row_mask:0xf bank_mask:0xf   // cv[lane^1]
    v_cvt_pk_bf16_f32 v[80+i], v[80+i], v[80+i]
    v_lshlrev_b32    v[80+i], 16, v[80+i]       // y = f32(bf16(cv[lane^1]))
    v_xor_b32        v[80+i], v5, v[80+i]       // 偶数 lane：y → -y（精确）
.endfor
    s_wait_loadcnt   0
.for i = 0 .. 7
    v_lshlrev_b32    v[48+i], 16, v[48+i]       // cs → f32
    v_lshlrev_b32    v[56+i], 16, v[56+i]       // sn → f32
    v_mul_f32        v[88+i], v[80+i], v[56+i]  // (±y)*sn，与 ±(y*sn) 位模式相同
    v_mul_f32        v[64+i], v[72+i], v[48+i]  // x*cs
    v_add_f32        v[88+i], v[64+i], v[88+i]  // 奇数 lane：x*cs + y*sn；偶数 lane：x*cs - y*sn
.endfor                                         // 如果原生把这一步收缩成 v_fma，这里同样改成 v_fma（步骤 1）
    s_branch         .Lstore_rope

.Lplain:
    v_mov_b32        v[88:95], v[8:15]          // 非 RoPE：res = cv（未经 bf16 舍入的 fp32）
.Lstore_rope:
// ---------- bf16 存储（8 行，每行 1 个 bf16） ----------
.for p = 0 .. 3
    v_cvt_pk_bf16_f32 v[96+p], v[88+2p], v[88+2p+1]
    global_store_b16      v6, v[96+p], s[10:11] offset:(2p)*16384   scope:SCOPE_DEV   // 第 h*8+2p 行
    global_store_d16_hi_b16 v6, v[96+p], s[10:11] offset:(2p+1)*16384 scope:SCOPE_DEV // 第 h*8+2p+1 行
.endfor
    s_wait_storecnt  0  // 可选：mono 在随后的 handoff 前本来就会等 storecnt；这里保守地等完
// 结束，接 FlyDSL 后续代码
```

说明：

- `v_mov_b32 v[88:95], v[8:15]` 是伪写法，实际是 8 条 `v_mov_b32`。
- `.for/.macro` 和形如 `v[16+i]` 的写法都是伪代码，正式 `.s` 由 `build_fragment.py` 展开。
- 4.2 新用到的 `v_add3_u32`（带 SGPR 和负数字面量）、`global_load_u16`、带 `scope:SCOPE_DEV` 的 `global_store_d16_hi_b16`、`offset:114688` 的存储、`0x1e3ce508`（= f32(1e-20)）的字面量 `v_add_f32` 也都已用 `llvm-mc` 汇编通过。
- 分支标签在嵌入时改成数字局部标签（`1:`/`1f`），避免和 kernel 其他部分重名。

### 4.3 逐位一致的注意点

> 原生 ISA 已经摘录到 [notes/native_stage_c.md](notes/native_stage_c.md)，和本节伪代码有出入时以它为准。最重要的一点：原生用 `v_fma_mixlo_bf16(acc, rstd)` 计算 x，只舍入一次；除法是完整的 IEEE 序列，需要 VCC 和 SGPR 临时寄存器。

1. **`DIV_BY_1280`、`+eps`、`rsq`、`acc*rstd` 的运算顺序和指令必须照抄原生**（步骤 1）。LLVM 对 `fdiv f32` 的默认展开和是否允许倒数近似，取决于 FlyDSL 设置的 fast-math 标志，不能猜。
2. **RoPE 用的是舍入后的 x/y，非 RoPE 列用的是未舍入的 cv**，和 `attention.py:325–328` 一致。y 先取邻居 lane 再舍入，和原生 `cv.shuffle_xor(1).to(BF16)` 等价（两种顺序得到的位模式相同）。
3. **偶数 lane 的减法用"对 y 取反再相加"实现。** IEEE 下 `a - b == a + (-b)`，`(-y)*sn == -(y*sn)`，都是精确的，所以位模式与原生的 `x*cs - y*sn` 相同。前提是原生没有收缩成 FMA；收缩了的话改成 `v_fma_f32 x, cs, (±y)*sn`，并以原生的乘积顺序为准。
4. **bf16 转换用 RNE**（`v_cvt_pk_bf16_f32`），要和原生的 `.to(BF16)` 指令确认一致。

## 5. 审核清单（`build_fragment.py` 自动检查）

- 写到的 VGPR/SGPR ⊆ clobber，输入寄存器（`v0`、`s0–s18`）只读。
- 不出现 `s30–s39`、TTMP、M0、EXEC、MODE 的写入，也不出现 `s_endpgm`、`s_setpc`、`s_set_vgpr_msb`。
- 所有 VGPR < 256；P1 不用 SGPR 临时寄存器，P2 只用 SCC（如有需要再加 VCC）。
- load/store 只用 saddr 形式，基址来自输入 SGPR，偏移都在 24 位立即数范围内。
- 字节数、SHA-256、约束字符串写进 `contract.json`；包装函数加载时重新校验（与 mono_test10 的 `audit.py` 相同）。
