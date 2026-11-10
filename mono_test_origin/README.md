# gfx1250 单卡 Mono 数值单测

本目录测试 ATOM PR #2908 中的真实局部融合路径：**一次 kernel launch 内执行 `slice → RMSNorm/FP8 → WQKV`，通过跨 CTA 的 tagged mailbox 交接。** 不加载模型权重文件，不启动模型服务，也不初始化分布式通信。

**当前状态：已编写，尚未编译或运行。** 按要求，本机只做源码生成、Python AST 语法检查、Bash 语法检查和源码清单检查。没有执行 `run.sh`，没有运行 CPU 数值测试，也没有编译或运行 GPU kernel。下文的 PASS 是目标机器执行后的验收条件，不是已取得的结果。

固定来源：[ROCm/ATOM PR #2908，commit `7c925f72b22ee6a815fd6d63734bbcff5fa72a08`](https://github.com/ROCm/ATOM/tree/7c925f72b22ee6a815fd6d63734bbcff5fa72a08)。这里使用其 `reference_projection.py::build_projection_c1`，不是完整模型默认使用的六行 DSpark K1。

## 一键运行

在 gfx1250 机器的 ROCm / AITER / FlyDSL Python 环境中：

```bash
cd /home/feifei/repo/ATOM/mono_test_origin
./run.sh
```

可将整个 `mono_test_origin` 目录复制到其他位置运行。运行不依赖外层 ATOM checkout、Git、网络或 `/tmp` 中的历史文件。

选择设备或 Python：

```bash
# 已激活环境时，默认使用 python3 和逻辑设备 0。
./run.sh --device 1

# 也可只让进程看到一张卡，此时其逻辑编号是 0。
HIP_VISIBLE_DEVICES=2 ./run.sh

# 指定已有的 Python 环境。
PYTHON=/path/to/venv/bin/python ./run.sh
```

默认运行三类输入，每类三次，共 **9 次融合 kernel launch**：

- `zero`：residual 为零，验证零值归一化、量化和输出。
- `pattern`：随 stream、输入列和输出行变化的有正有负的数据，验证布局和寻址。
- `random`：随机 BF16 residual、混合投影权重及 FP8 WQKV 权重。

每次重复更换 seed，复用相同的 GPU 分配；清理 mailbox 后重新使用 `layer=0 / tag=1`。这样校验会覆盖跨次残留数据问题。第一次实际 launch 也参与校验，没有跳过校验的 warmup。

可缩短或增加测试：

```bash
./run.sh --cases pattern --repeat 1
./run.sh --cases zero pattern random --repeat 5 --seed 123
MONO_TEST_TIMEOUT_SECONDS=1800 ./run.sh
```

shell 默认总超时 900 秒，覆盖 JIT 编译和数值测试。kernel 内另启用了 PR 已有的有界 mailbox 等待诊断。超时、架构不匹配、缺少依赖、编译失败和数值错误都会返回非零退出码，不会当作 skip/PASS。

## 目标机器需要的环境

- Linux、可见的 **gfx1250** GPU，ROCm runtime 和兼容 gfx1250 的编译工具链。
- ROCm 版 PyTorch，提供 BF16 和 OCP `torch.float8_e4m3fn` 的 CPU 转换。参考计算在 CPU 上进行。
- 兼容这个 PR 的 AITER 和 FlyDSL。具体会使用 `aiter.ops.flydsl.kernels.buffer_ops`、`dpp_utils`、`kernel_signature`、FlyDSL `ASTRewriter` 和 `rocdl.WMMAScale(16,16,128,...)`。
- NumPy（固定 PR 的 plan 模块使用）和 `timeout`（GNU coreutils）。

优先使用目标机器已有的 gfx1250 ATOM 开发环境。脚本不会自动安装、升级依赖或下载编译器。仅安装 CPU 版 PyTorch，或仅设置 `ARCH=gfx1250`，不能代替目标硬件和上述工具链。

若有 `llvm-objdump`，脚本附带导出反汇编；找不到它不会阻止数值测试。PyTorch、AITER、FlyDSL 的版本/路径和实际加载的 HIP 库会记录到结果文件中。尚未经过目标环境验证，因此这里不承诺任意 AITER/FlyDSL 版本都兼容。

## 文件入口

| 文件 | 用途 |
| --- | --- |
| [run.sh](run.sh) | 一键入口、总超时、保存日志 |
| [run_test.py](run_test.py) | 编译、资源检查、分配、单次 launch、读取输出、测试循环 |
| [reference.py](reference.py) | CPU 输入生成、权重打包、独立数值参考和误差判定 |
| [hip_runtime.py](hip_runtime.py) | HIP 分配/拷贝、内存 guard、实际二进制的 occupancy 查询 |
| [mono1250/kernels/reference_projection.py](mono1250/kernels/reference_projection.py) | Mono 主体及 WQKV stage |
| [mono1250/kernels/reference_k1.py](mono1250/kernels/reference_k1.py) | gfx1250 slice stage |
| [mono1250/kernels/reference_norm.py](mono1250/kernels/reference_norm.py) | gfx1250 RMSNorm / FP8 stage |
| [mono1250/kernels/reference_sync.py](mono1250/kernels/reference_sync.py) | gfx1250 mailbox 发布、轮询和超时诊断 |
| [mono1250/kernels/attn_helpers.py](mono1250/kernels/attn_helpers.py) | 从固定 `attn_pre.py` 抽取的原始 helper 定义 |
| [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) | 来源路径、commit、SHA-256、helper 原始行号和适配记录 |
| `upstream_sources.tar.gz` | 18 个来源文件的未修改原件，供离线核对 |
| [vendor_sources.py](vendor_sources.py) | 从本地 Git 对象重新生成隔离源码；运行单测不调用它 |
| [UPSTREAM_LICENSE](UPSTREAM_LICENSE) | 固定 ATOM 版本的许可证 |

`mono1250/` 是独立 Python 包，内部不导入外层 `atom.*`。原始 ATOM 源码无需修改，也不需要混用本地主线和 PR 的模型模块。

## 构建和执行顺序

1. 检查所选 GPU 的真实 `gcnArchName`，只接受 gfx1250。只使用这一张设备，不要求进程只能看见一张卡。
2. 构造原始 builder：

   ```python
   build_projection_c1(
       front=True,
       fold=False,
       feeds_index=True,
       threads=256,
   )
   ```

   `front=True` 把 slice、norm 和 WQKV 放入同一次 launch；`fold=False` 使用已经就绪的 residual，不读取上一层 pending 输出。

   **此 builder 中的 `feeds_index=True` 只让 norm 多写 BF16 `normed` 和 `NB` mailbox，便于独立验证量化前的数值。它没有添加 indexer kernel 或 indexer stage。** 相比之前建议的 `False`，这是测试可观测性的选择。

3. 在 `COMPILE_ONLY=1` 的作用域内调用一次 launcher，只构建，不执行。导出其内存缓存中的实际 ELF 和 MLIR。磁盘 JIT cache 关闭，避免误用历史二进制。
4. 读取 code object 的 VGPR、SGPR、private/scratch、LDS、spill 和 wavefront 信息，要求 wave32。通过 `hipModuleOccupancyMaxActiveBlocksPerMultiprocessor` 对**这个二进制**查询 256 线程 CTA 的驻留数量，检查：

   ```text
   每 CU 可驻留 CTA 数 × 实际 CU 数 >= 256 个 CTA
   ```

   不满足就停止，不启动这个有跨 CTA 等待的 kernel。这里没有限制 VGPR/SGPR，也没有仅因存在 scratch 而拒绝运行；实际 occupancy 才是本单测的驻留判据。这个容量计算假定其他长 kernel 没有同时占据所选 GPU。

5. 在 CPU 生成并打包输入，用 HIP 分配 GPU 缓冲区。scratch 和诊断区采用 ATOM 同样的 `hipExtMallocWithFlags(..., 3)` uncached 分配。每个缓冲区前后各有 256 字节 guard。
6. 初始化全部 mailbox 和诊断区，在当前设备 stream 上调用原 FlyDSL launcher 一次，完成后同步。再核对其使用的 code object 与驻留检查的二进制 SHA-256 相同。
7. 拷回结果，检查计算值、tag、guard、只读输入及未使用区域。所有参考计算均在 CPU 上完成，不调用另一个 GPU 算子作为参考。

## 输入、输出和布局

固定一个 token：`HIDDEN=5120`、4 个 HC stream、WQKV 输出 1792 个值（1280 个 Q latent + 512 个 KV）。网格保留原 plan 的 256 CTA，每 CTA 256 线程，物理 wave32。

| 数据 | 逻辑形状 / 类型 |
| --- | --- |
| residual | `[4, 5120]`，BF16 |
| pre | `[4]`，FP32，固定为 `[1/8, 1/4, -1/8, 1/2]` |
| hc_fn | `[24, 4*5120]`，FP32 |
| norm weight | `[5120]`，BF16 |
| WQKV weight | `[1792, 5120]`，OCP E4M3FN；上传前做 16x16 preshuffle |
| WQKV weight scale | `[1792/32, 5120/32]`，E8M0 字节，每个 32x32 tile 一个 scale，按行连续，不做 scale preshuffle |
| LIN / NB | 5120 个 BF16，各两个值打包为一个 mailbox payload |
| PMIX | `[160, 25]`，每个 slice 的 24 个 mix dot 和一个平方和 |
| X8 / X8S | 5120 个 FP8 字节 / 160 个 E8M0 scale code |
| normed | `[5120]`，独立 BF16 输出 |
| QKV | `[1792]`，FP32 payload，值已按 BF16 舍入 |

mailbox 的物理格式均为 `int32[value_bits, tag]`，每对 8 字节。偏移取自 `C1ReferencePlan.k1_scratch_layout()`，不使用手写偏移。

plan 的默认 `tp=2` 会构造其他未执行阶段的维度，但这里的 slice/norm/WQKV 数量与这些维度无关，所选 launcher 没有 peer 参数或通信。因此本测试验证的是单卡局部路径，并不宣称完整 TP2/TP4 runner 可以在单卡执行。

## 数值判定

不仅检查 kernel 是否返回：

- **LIN**：与按四个 stream 顺序求和、再转 BF16 的 CPU 结果逐位比较。
- **PMIX**：按原算法的 BF16 hi/lo 权重重建规则，用 FP64 计算 mix dot 和 residual 平方和，给 FP32 累积留明确的误差界。
- **normed**：与 CPU FP64 RMSNorm 比较，误差界包含一次 BF16 舍入以及 FP32 reduction / 近似 `rsq` 的小误差。
- **NB**：与独立 `normed` 输出逐位一致。
- **X8 / X8S**：对已经独立校验过的 `normed` 做 CPU OCP FP8 量化，字节和 scale code 必须完全一致。这样不会把 RMSNorm 舍入边界误判为量化布局错误。
- **QKV**：用逻辑权重的 FP64 解量化矩阵乘法计算参考。误差界覆盖八路 FP32 K-split 累积和最终 BF16 舍入；另检查独立 RMSNorm 参考一路传播到 QKV 的端到端误差。
- **内存协议**：所有已写区域的 tag 都必须为 1；未使用区域和只读输入必须不变；所有 guard 必须不变；诊断区必须全零。

这些误差界和每项最大误差都会写入结果文件。FP8 权重的打包还会在上传前，用独立逐元素地址公式检查边界及随机坐标。

## 运行产物与验收

所有测试产物放在本目录的 `build/`：

| 产物 | 内容 |
| --- | --- |
| `run.log` | 完整标准输出和错误输出 |
| `result.json` | PASS/FAIL、设备/软件版本、源码指纹、每次 seed、各项误差和完成次数 |
| `kernel.co` | 这次编译并执行的实际 code object |
| `kernel.mlir` | FlyDSL artifact，包括嵌入的 ELF |
| `kernel.disasm.txt` | 有 llvm-objdump 时导出的反汇编 |
| `resources.json` | 寄存器、LDS/private/spill 及实际 occupancy |
| `failure.pt` | 数值/执行检查失败时尽可能保留的 CPU 输入和输出 |
| `mailbox_failure.json` | mailbox 诊断非零时的记录 |
| `cache/` | 此进程的 FlyDSL/AITER/Triton/Torch 等缓存路径 |

一次新的运行会覆盖同名报告。只有**脚本退出码 0、最后打印 `[PASS]` 且本次 `result.json` 的 `status` 为 `PASS`**才表示成功。超时导致报告停留在 `RUNNING` 时也不算通过。默认应报告 9 个通过的 case 和 9 次完成的融合 launch。

## 对固定 PR 源码做了什么

1. 将内部 import 名称从 `atom.*` 改为本目录的 `mono1250.*`，使用最小包初始化文件，避免引入模型/服务入口。
2. 从 `attn_pre.py` 选择 slice/访存所需的常量、完整函数及其依赖；保留函数体原文和装饰器。没有复制 attention、MoE、deployment 等不相关入口。选取行号记录在 manifest 中。
3. 在 `reference_projection.py` 的 `reference_mailbox` 调用中增加 `diagnostic=True`，启用 PR 自带的有界等待。没有改变三个 stage 的计算主体或任务分配。
4. 运行时选择 builder 已有的 `feeds_index=True`，用于校验 normed/NB。没有伪造模型配置、屏蔽整网架构检查或修改原始 ATOM 文件。

若要核对原文：

```bash
mkdir -p build/upstream
tar -xzf upstream_sources.tar.gz -C build/upstream
```

仅在维护隔离源码时，且外层 Git 仓库含上述 commit，才需要运行 `python3 vendor_sources.py`。它会重新生成 `mono1250/`，覆盖这里的手动改动；正常单测和将来 ASM 实验不需要运行它。

后续替换 ASM 时，可从 `reference_projection.py::stage_wqkv_c1` 或 `reference_norm.py::stage_norm_c1` 入手。应先在目标 GPU 上保留本版本的成功报告与 `kernel.co`，再修改独立副本用于 A/B 比较。
