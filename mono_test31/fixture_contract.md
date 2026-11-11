# gfx1250 模型对照 fixture

`tests/test_gpu.py` 使用原始 `step.build` 作为 reference，并调用 `host.py` 加载 ASM kernel。
测试不生成虚构的模型权重，也不把执行完占位 kernel 当作通过。

运行环境需要四张 gfx1250、ROCm PyTorch、FlyDSL 0.4.1、当前仓库的 AITER，以及 ATOM 的模型权重、权重打包和真实 host 输入准备。四个进程通过 Gloo 协调，GPU 只运行被比较的计算。

通过 `MONO31_FIXTURE=your_package.fixture:make_fixture` 指定工厂。工厂签名：

```python
def make_fixture(*, config, mode, rank, device):
    # 完成模型/权重加载、两个测试状态的分配与 TP4 peer mappings。
    # 不启动 Mono kernel；不初始化另一个会占用 GPU 的通信 kernel。
    return fixture
```

返回对象需要提供：

| 属性 / 方法 | 约定 |
| --- | --- |
| `baseline`, `asm` | 两个 `host.PreparedStep`；各自有独立的可写资源和四个 peer receive 地址。只读权重可以共享。 |
| `mutable_ranges(path)` | `{name: (GPU_VA, size_bytes)}`；完整列出该路径的可写分配，包括 KV/index/compressor 状态、scratch、table、tail、peer receive buffer。用于检查两路径之间的地址重叠。 |
| `covered_features` | 实际由 fixture 输入触发的功能集合，至少包含下文列出的功能。不能把没走到的功能写成已覆盖。 |
| `prepare_step(path, iteration)` | 按原 runner 准备该路径的本步数据：token/position、index/compressor plans、sampling RNG、dgeom、Engram H2D 和 stream join 等。每个 decode step 开始清一次 `cnt`；split 的 target/draft 之间不清。 |
| `observables(path)` | `{name: tensor}`；返回所有有语义的可观察输出，见下文。测试逐 tensor 比较完整有效区域。 |
| `initial_epochs` | `{epoch_observable_name: initial_value}`，用于验证每次 launch 正确累加 epoch。 |
| `timeout_count(path)` | 返回累计 polling timeout 数；两条路径均必须为零。 |
| `close()` | 所有 GPU 工作完成后释放长期持有的资源。 |

`path` 是 `"baseline"` 或 `"asm"`。两条路径的初始内容、sampling RNG 和每轮 host 输入相同。不能先运行 baseline，然后让 ASM 使用 baseline 改写过的缓存或 epoch。第二轮保留第一轮产生的 `tpep`、draft logits、draft ids、KV 和 compressor 状态。

需要实际覆盖的功能集合：

```python
{
    "entry", "attention", "front", "moe", "index", "compressor", "engram",
    "tap", "tail", "epoch", "ratio1", "candidate_producer", "reindex", "shared_early",
}
```

`observables` 名称用 `category/name`。至少提供 `attention/`、`kv/`、`index/`、`compressor/`、`moe/`、`tail/`、`epoch/` 分类；同时应包含 front/router、Engram 和 tap 的有效结果。例如：

```text
attention/output             front/normalized
front/router_ids             front/router_weights
kv/window_ring               kv/selected_rows
index/ilog                   index/isel
index/irow                   index/candidates
compressor/main_cache        compressor/state
moe/output                   engram/kv
tap/aux8                     tail/outtok
tail/verdict                 tail/mids
tail/qlog                    tail/qids
epoch/tpep
```

这些名字只是示例；每类可提供多个 tensor。返回完整有效区域，不只抽样前几个元素；未写入的容量部分、裸指针 table 和时钟时间戳不用于数值对照。量化编码、token、索引和计数器按整数精确比较。float32 默认 `rtol=atol=1e-4`，float16/bfloat16 默认 `1e-2`，浮点结果还要全部有限。若要验证 FP8，返回底层编码字节或解码后的 float32。

测试会运行两个 decode step。`all` 每步 epoch 加一，`split` 每步加二；每个 rank 独立检查。测试结束前同步 GPU，跨 rank 的 enqueue 不能串行等待。

已有 `SingleStepRunner` 的 `prepared_from_runner()` 可以提取接入参数，但工厂仍须建立两个独立模型状态，沿用 runner 的真实 prepare 逻辑。这份目录没有附带模型 checkpoint 或完整 fixture 工厂，因此模型对照需要在现有 ATOM 部署环境中提供该工厂。
