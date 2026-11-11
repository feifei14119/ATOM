# gfx1250 DS V4.1 mono step kernel：单卡单元测试

在**一张** gfx1250 上运行 `atom/models/deepseek_v41/mono/gfx1250/kernels/step.py` 的层循环。kernel 源码不做任何修改，权重是合成的，不需要 checkpoint，也不需要 TP 进程组。

## 运行

```bash
cd /app/ATOM/mono_test_single_origin
./run.sh                                  # 48 行、4 层、3 次 launch
./run.sh --rows 6 --layers 1              # 最小配置
./run.sh --layers 40 --repeat 2           # 完整 40 层（只做健康检查，见下）
./run.sh --layers 2 --golden build/golden_l2.pt   # 第一次写 golden，之后与它比较
./run.sh --device 1 --no-engram --seed 7
```

结果写到 `build/result.json`，日志写到 `build/run.log`。退出码：0 表示 PASS，1 表示 FAIL，124 表示超时。

## 怎么在单卡上跑 TP4 kernel

- **构建方式：** `step.build(TR, rank=0, NL=n, ndr=0, part="all")`，这是 kernel 自带的 bring-up 构建。它只包含 target 入口和 n 层 target，不跑 head、采样和 draft（`step.py` 第 458、466 行的条件都不成立）。
- **TP all-reduce 回环：** 推送地址是 `recv[o] + src·TP_TG·16`，轮询地址是 `recv[rank] + o·TP_TG·16`。取 rank = 0，令 `recv[o] = recv[0] + o·TP_TG·16`，rank 0 推给“对端 o”的数据就正好落在自己接收区的第 o 个槽，所以只需要一组指针别名，kernel 不用改。
- **由此带来的语义：** 测到的是“4 个 rank 持有同一份分片”的 TP4 网络。kernel 的计算、同步和协议都会被完整执行，但数值不等于真实模型的输出。
- **尾部为什么不测：** 采样和 Markov 交换的 src 步长分别是 196608 B 和 128 B，和 TP 的 655360 B 不同，一组别名满足不了三种布局。要测尾部，只能拷一份 kernel 并加测试用的回环开关。

## host 侧准备了什么

| 内容 | 来源 |
|---|---|
| scratch | `buffers.scratch_bytes`，与 runner 相同 |
| `fp` 表 | `FPTRS` + `ATAB` + 层表（`LKEYS`）；入口行固定是第 `TARGET_ENTRY_ROW`（44）行，所以表至少有 45 行 |
| attention 权重 | FP8 e4m3（来自 N(0,1)），32×32 块的 E8M0 scale 取约 1/√K，形状与 `weights/layer.py` 的 `ATTN_SHAPES` 一致 |
| mHC、norm、router | `hi_lo` 打包的 fn、hsc/hbs、norm 权重、`gate` [384][5120]、`gbias` |
| 路由专家 | 随机字节作为 MXFP4（每个字节都是合法的 e2m1 对），scale 取常数；所有层共用一份（约 2 GB） |
| 共享专家 | `planes.pack_shared_local` 打包随机 FP8 |
| Engram | 第 0、13 行（`lflags` bit7），engw [25600][6144] |
| tap | 第 NL-4..NL-2 行（`lflags` bit4） |
| KV / 窗口 | 8 个请求的 ring（133 行）预填随机值；请求 q 的上下文长度为 `ctx + 41q`，包含 ring 回绕的情况；`kmeta`/`kvw`/`rpos` 按因果窗口（≤ 128 个 key）生成 |

**没有覆盖到的：** indexer、compressor、REINDEX 层（层表里 `lflags` bit1/3/5/6 都是 0，所有层都是 WINDOW 层），以及 head、采样、verify、draft。

## 判定标准

1. **没有轮询超时**（`cyc` 计数为 0）。反向验证：把 ATAB 里的 `recv0..3` 改成没有别名，会记录到 10240 次超时（site 6，TP 轮询），判 FAIL。
2. `xh`（head 输入）、`aRout`（最后的 4 路残差）和本步写入的 KV ring 行都满足：有限；`|x| ≤ --absmax`；rms 不为 0，且没有整行为常数。
3. **运行间一致性**（以及可选的 golden 比较）：相对 L2 不超过 `0.05·√层数`，只在 ≤ 8 层时检查；更深的构建只记录，除非显式传入 `--rtol`。

这个 kernel **两次运行不会逐位一致**，原因如下：

- **源头：** `stage_A` 用 f32 原子加把 q 和 kv 的平方和累加进 `ss`（`attention.py:250`），每次加的顺序不同。
- **逐阶段实测（1 层、48 行）：** `qkv`/`qr8`/`kvn` 逐位一致；`q` 的相对差异约 1e-5，只有 1 到 6 个字节不同；经过 MXFP8 量化（e4m3 的 1 ulp 约等于 6% 到 12%）之后，`out`/`y1` 约 1e-3，`y2`/`xh` 约 1e-2。
- **路由翻转：** top-6 路由中，第 6 名和第 7 名一旦换位，那一行就会出现百分之几的差异。
- **各层数的运行间差异：** 1 层约 0.01，4 层约 0.06，8 层约 0.09，12 层约 0.10，40 层在 0.19 到 0.34 之间（两次运行的轨迹已经不相关）。

## 本机实测（gfx1250，256 CU）

| 配置 | 每次 launch 的层耗时（设备时间戳） | 结果 |
|---|---|---|
| 48 行 × 1 层 | 约 10–12 ms | PASS |
| 48 行 × 4 层 | 约 58 ms | PASS |
| 48 行 × 8 层 | 约 105 ms | PASS（运行间差异 0.094，容限 0.141） |
| 48 行 × 40 层 | 约 510–520 ms | PASS（只做健康检查） |
| 6 行 × 1 层，golden 写入后再比较 | — | PASS |

**每层约 10 ms 是这台机器的特性，不是测试的问题。** 用 `sync_bench.py` 实测，配置和 step kernel 一样（256 CTA，cluster 16）：

| 操作 | 每次耗时 |
|---|---|
| workgroup 屏障 | 0.02 µs |
| cluster 屏障（含 fence） | 0.10 µs |
| 普通 global load | 0.07 µs |
| nontemporal load | 0.17 µs |
| 原子加（256 个 CTA 加同一个地址） | 2.2 µs |
| **`global_load_b32 … scope:SCOPE_DEV`** | **32.6 µs** |
| `device.handoff` | 109 µs |

kernel 的 handoff、`gwait`、TP tag 等所有轮询，每一圈都是一次 `scope:SCOPE_DEV` load。在 GPU 0 和 GPU 1 上，开或关 `HSA_XNACK`，结果都一样。

```bash
PYTHONPATH=/app/ATOM python3 sync_bench.py 0                      # 全部原语
PYTHONPATH=/app/ATOM python3 sync_bench.py 0 load_agent,handoff   # 只测部分原语
```

## 文件

| 文件 | 用途 |
|---|---|
| `run.sh` | 入口：设置 PYTHONPATH，加超时，记日志 |
| `run_test.py` | 合成权重和输入、构建 `fp` 表、配置回环、launch、执行检查 |
| `sync_bench.py` | 同步原语的微基准 |
