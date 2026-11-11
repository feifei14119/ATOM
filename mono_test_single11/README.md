# stage_C 的 GEMM 主循环换成 SP3 汇编（inline 接入 mono）

本目录是把 mono step kernel 的 stage_C（`kernels/attention.py:300`，`wq_b` GEMM + q_norm rstd + RoPE）换成手写汇编的试验。目前完成的是 **P1**：GEMM 主循环（10 步 K128 MXFP8 WMMA）改用 SP3 写的 inline 片段，尾部仍是原生 FlyDSL。方案见 [PLAN.zh-CN.md](PLAN.zh-CN.md)，伪代码见 [ASM_PSEUDO.zh-CN.md](ASM_PSEUDO.zh-CN.md)，原生指令摘录见 [notes/native_stage_c.md](notes/native_stage_c.md)。`/app/ATOM` 下的原有源码和已安装的 FlyDSL 都没有改动。

## 结果

| 测试 | 结果 |
|---|---|
| 单元 kernel（`unit_stage_c.py`，256 CTA，原生与 asm 在同一 launch 内）：rows 48/16/6 × 2 个 seed × {普通输入, NaN/Inf/下溢/ss=0 特殊输入} | **12/12 逐位一致** |
| mono dual 模式，48 行 × 4 层 × 3 次 launch | **每层逐位一致**（每次 launch 1572864 个 q 元素，0 差异），PASS |
| mono dual 模式，48 行 × 40 层 × 2 次 launch | **40/40 层逐位一致**（每次 launch 15728640 个元素），PASS |
| mono dual 模式，6 行（MT=1）× 4 层 × 2 次 launch | 逐位一致，PASS |
| mono asm 模式（真正替换），4 层 × 3 次、8 层 × 3 次 | 无超时、数值健康，PASS |
| 反向验证：片段的 B scale 偏移改坏 | 单元 kernel 和 mono dual 都判 FAIL（mono 中 3040 处不一致） |
| 整个 kernel 的资源（`build/isa/mono_*.s`） | native / asm / dual 都是 358 VGPR、105 SGPR；scratch：native 20 B（15 条），asm 8 B（9 条） |

## 目录

| 路径 | 内容 |
|---|---|
| `sp3/ref/MXFP8_GEMM_1TG_4W_128mx2_128nx2.sp3` | 参考源码，拷自 `/app/poc_kl_sim/src/mi400/mxfp8fp4gemm/shaders/`（poc_kl_sim `45e97bf`，sha256 `d0fa56a1…`），未改 |
| `sp3/stage_c_gemm.sp3` | 改写后的 P1 片段：保留参考的 `v_wmma_scale_f32_16x16x128_f8f6f4` 核心与写法；去掉 TDM→LDS、256×256 tile、kernarg、`s_endpgm`；改为 global 直接取数、4 级流水、mono 的操作数顺序（参考 kernel 把 A/B 互换算的是 D 的转置） |
| `asm/build_fragment.py` | `sp3 compile:`（`/app/sp3cvt/sp3`，asic=MI450）→ 去掉开头的 `s_version` 和末尾的 `s_code_end`/零填充 → `llvm-mc` 反汇编回读 → 审核寄存器 → 输出 `build/asm/*.inc`、`*.disasm.txt`、`*.contract.json` |
| `kernels/stage_c_asm.py` | FlyDSL 包装函数：原 guard 与 tile 坐标、`readfirstlane` 后经固定寄存器传给 inline asm，接原生尾部 |
| `unit_stage_c.py` | 单元 kernel（几秒即可编译完） |
| `run_test.py`、`run.sh` | mono 单卡测试（拷自 `../mono_test_single_origin`），增加 `--stagec {native,asm,dual}` |
| `build/isa/` | 最终 ISA：单元 kernel 与 mono 三种模式 |

## 寄存器约定（P1）

| 寄存器 | 方向 | 内容 |
|---|---|---|
| `v0` | 输入 | lane |
| `s[0:1]` | 输入 | `qr8 + mi*16*1280` |
| `s[2:3]` | 输入 | `wqb + n0*1280` |
| `s[4:5]` | 输入 | `qrs + mi*16*40` |
| `s[6:7]` | 输入 | `wqb_s + (n0/32)*40` |
| `v[8:15]` | 输出（`={v[8:15]}`，`vector<8xf32>`） | 累加结果，排布和 `wmma_mx` 相同 |
| `v1–v4`、`v16–v151` | clobber | 地址、4 个流水槽（逐个列出；区间写法会被 LLVM 忽略） |

另外：不写 SGPR/VCC/SCC/EXEC/M0；进入时 EXEC 为全 1（guard 对整个 wave 统一）。片段内部自己处理 hazard，因为 LLVM 不检查 inline asm 内部：入口执行 `s_wait_xcnt 0`（LLVM 不会为 inline asm 的 clobber/输出插入这个等待），末尾放 4 个 `v_nop`（WMMA 结果被 VALU 读取前需要的 4 个 wait state）。

## 运行

```bash
cd /app/ATOM/mono_test_single11
python3 asm/build_fragment.py                         # SP3 -> 片段 + 审核（每次改 sp3 后执行）
PYTHONPATH=/app/ATOM python3 unit_stage_c.py          # 单元 kernel：原生 vs asm 逐位对比
./run.sh                                              # mono，默认 --stagec dual，48 行 × 4 层
./run.sh --stagec dual --layers 40 --repeat 2
./run.sh --stagec asm                                 # 真正替换
./run.sh --stagec native                              # 对照组
```

## 需要注意的地方

- **JIT 缓存：** FlyDSL 的缓存 key 不包含模块级的片段文本。包装模块导出 `FRAGMENT_TAG`（片段 SHA-256 的前 16 位），单元 kernel 把它作为闭包标量，mono 把它拼进 `sources`，所以改了片段一定会重编。
- **dual 模式怎么取到层号：** stage_C 的上下文里没有 `Ly`，包装函数用 `kring_off // (8*133)` 反推。这个关系只在本测试的表里成立（本测试把每层的 `kring` 设为 `Ly*8*133`）。
- **run-to-run 判定：** 本 kernel 由于 atomic，本身不逐位可重复，`kv_rows` 的噪声还是长尾的：native 模式 4 层实测 0.08–0.27，原来的默认容差 `0.05·√L` 连基线都会时过时不过。所以本目录的 run-to-run 和 golden 对比默认只报告，给 `--rtol` 时才判定。asm 正确与否以 dual 的逐位对比为准。
- **P2（尾部也换成 asm）尚未实现。** 尾部要照抄的原生指令形式已记在 `notes/native_stage_c.md`，包括 `v_fma_mixlo_bf16` 只舍入一次，以及用到 VCC 的完整除法序列。
