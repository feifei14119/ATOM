# mono_test31：ASM 主体内嵌 FlyDSL 计算片段

这个目录将 `atom/models/deepseek_v41/mono/gfx1250/kernels/step.py` 的外层 Mono 调度写成 gfx1250 ASM，计算阶段通过 `callee_test21` 风格的预处理器嵌入。用户维护的主文件是 `step.s`。

当前交付的是实现源码、构建工具和单测文件。**本次只做静态语法检查，没有执行单测、完整 kernel 构建或 GPU 测试，也没有生成已验证的 `.co`。** 完整编译链路、gfx1250 上的计算正确性、cluster 进度和资源占用仍需后续验证。

## 文件与职责

| 文件 | 内容 |
| --- | --- |
| `step.s` | ASM 入口、cluster CTA ID 解码、target/draft 切换、layer/hf/pi 循环、lflags 分支、前端 CTA 范围和阶段顺序。 |
| `fragments.py` | 从经过 SHA256 固定的 `step.py` 提取计算阶段，保留原来的 LazyC、front callbacks 和复杂表达式。 |
| `export.py` | 在 FlyDSL 编译期间捕获 tracing container，转成普通 LLVM CCC 函数，替换内层 helper 的 thread/CTA ID，然后由 LLVM 编译。 |
| `native.py` | 提取完整 native 函数体，保留寄存器保存/恢复与 scratch，重命名局部标签，将 return 改为片段出口跳转。 |
| `build.py` | 展开 `.flydsl.*`，合并资源，生成 descriptor/metadata，汇编、链接并输出构建报告。 |
| `contract.py` | 72 字节显式 kernarg ABI、源文件表布局、counter 和 LDS 预算。 |
| `elf.py` | 检查最终 ELF 的 descriptor、metadata、未定义符号和 relocation。 |
| `host.py` | 对接真实 AITER module-load/cluster-launch，打包已准备输入并检查 residency 容量上界。 |
| `tests/` | CPU 调度/ABI/片段检查、可选完整离线构建测试、可选 TP4 gfx1250 模型对照。 |

## 预处理与 ABI

主文件中的一段：

```asm
.flydsl.begin attention_A
    .flydsl.function fragments.py:attention_A
    .flydsl.segment both
    .flydsl.abi leaf-ccc-inline
.flydsl.end
```

`.flydsl.begin/end` 是本目录预处理器的指令，LLVM assembler 不认识它们。`build.py` 先编译 target/draft 形状所需的 FlyDSL 计算片段，再将其 native ASM 插入 `step.generated.s`。最终只有 `mono_step31` 一个可启动 kernel，没有对整个 `step.build` 的调用，也没有计算阶段的 trap 占位。构建遇到缺失的可达阶段会失败。

`callee_test21` 的小表达式可通过限定寄存器池重映射。Mono 的计算片段有复杂分支、矩阵指令、LDS 和 spills，因此这里使用 LLVM 普通 AMDGPU CCC ABI：

```text
void(record:i64, bid:i32, tid:i32, layer:i32, hf:i32, pi:i32, epoch:i32)

v[0:1] = record（指向 StepArgs 的 kernarg 地址）
v2     = bid
v3     = tid
v4     = layer
v5     = hf
v6     = pi
v7     = epoch
```

这是普通 device 函数的编译接口，函数的 prologue、epilogue 和 callee-saved 保存全部保留。展开时不做全局寄存器重映射。return 改成内联片段结束跳转，最终不保留 callable stage symbol。

ASM 持续状态使用 LLVM 默认 CCC 的 callee-saved 寄存器：`s36:s37` 保存 kernarg，`s38/s39` 保存 CTA/layer，`s48..s55` 保存 epoch、hf、pi、pass 数、segment、end、lflags 和 TRx，`v40` 保存 tid。`s32` 是从零初始化的设备栈偏移；scratch 字节数从实际编译报告取最大值，并向上对齐。vgpr、sgpr、VCC 和 named barrier 数量也由 native 结果合并，包含 ASM 自身需要的寄存器。

内层 helper 的 thread/CTA builtins 在 LLVM 优化前替换为显式参数，CTA 参数经过 readfirstlane 保持 wave-uniform。tracing 期间将 `hx.lds_base()` 暂时改为 byte offset 0，最终 descriptor 固定 LDS 为 0，host 传入整个动态 LDS。原阶段的 LDS 预算之后另加 256 字节 scheduler 区域，用来交接 epoch，避免覆盖 residual、front、attention 或 MoE 的 LDS。

整层展开可能超过普通分支范围，所以 ASM scheduler 和片段出口使用 `STEP_JMP/STEP_CJMP` 的局部 `rel64` 远跳转，暂用 caller-saved `s0:s1`。native 内部已有分支保留。编译器若产生外部数据、未桥接的隐式 dispatch 参数、函数调用、动态栈、间接调用或不支持的 PC-relative native 代码，构建会报告错误，不能静默替换阶段。

无需修改 LLVM 源码；导出器依赖 FlyDSL 0.4.1 的内部 MLIR 编译接口。LLVM/FlyDSL 升级后需要重新审阅这些接口及 native ABI。导出器的临时编译 hook 和 LDS/timeout 状态在异常时也会恢复。

## 调度覆盖

ASM 包含 target entry、draft meta/state/front、attention A/kv/C/D/E/F、TP1、index/compressor、scorer 和 selection、FFN front、early shared UG、MoE、combine/TP2、下一层 attention front、tap、target tail 和 draft tail。

保留的关键条件包括：

- indexer 由 lflags bit 3 控制，`ibat == 0` 跳过 scorer/selection；REINDEX 优先于 candidate producer，selection 为两遍或四遍。
- 每层 `hf=0` 运行 FFN front 和 MoE，`hf=1` 运行下一层 attention front；只有 front CTAs 等待相应 TP column-group counters。
- Engram bit 7 和 tap bit 4 只在 target 段生效；compressor/ratio1 等内部条件沿用原函数。
- target entry front 使用原来的固定表行 44；draft entry front 使用 `NL + ndr`。
- 每次 launch 恰有一个 epoch begin/end，split 两次 launch 分别推进 epoch。
- 原代码的 `part=all, ndr=0` 不执行 target tail；`part=target` 执行 target tail。零层配置保留原有入口/尾部条件。

分片配置允许 target rows 为 6、12、…、48，draft rows 为每请求 5 行，rank 为 0..3，NL 为 0..40，ndr 为 0..3。launch 固定为 256 CTAs × 256 threads、wave32、每个硬件 cluster 16 CTAs。

## 构建与测试命令

以下命令供后续使用，本次没有执行。默认 `make` 只构建，不自动运行测试。

```bash
cd /home/feifei/repo/ATOM/mono_test31

# FlyDSL 编译环境。已有 mono_test20 venv 含 FlyDSL，但其 CPU torch
# 不能用于 GPU 对照；GPU 测试需另选带 ROCm torch 的 Python。
make build PYTHON=../mono_test20/build/venv/bin/python

# 按配置单独构建，输出目录包含 kernel.co、manifest.json 和审阅材料。
make build PART=target RANK=0 ROWS=6 BUILD_DIR=build/rank0/target
make build PART=draft  RANK=0 ROWS=6 BUILD_DIR=build/rank0/draft

# CPU 单测不需要 torch/FlyDSL，不编译 kernel，不启动 GPU。
make test PYTHON=python3

# 可选：单测中执行完整离线编译和 ELF 检查，仍不启动 GPU。
make test-build PYTHON=../mono_test20/build/venv/bin/python

# 四个 rank 的所有构建；需要 split 时设置 PARTS='target draft'。
make build-tp4 PARTS='all target draft'

# 在真正的 TP4 gfx1250 部署中运行模型对照。
# fixture 工厂约定见 fixture_contract.md。
MONO31_FIXTURE=your_package.fixture:make_fixture \
    make test-gpu GPU_PYTHON=/path/to/rocm-python TEST_MODE=both
```

每个片段保存 `adapted.py`、原始/降低/适配后的 MLIR、LLVM IR、优化后的 IR 和 native ASM。最终保存 `step.generated.s`、resource/constant/metadata includes、反汇编、ELF 信息和 `build_report.json`。只有编译、链接和 ELF 检查全部完成才生成 `manifest.json`，状态为 `BUILT_NOT_TESTED`。失败构建删除旧 `.co` 和 manifest，不会留下旧结果冒充新构建。

CPU 单测的调度解释器实际读取 `step.s` 的统一控制流，覆盖 selection 次数、null scorer、idle front CTAs、target/draft 切换、epoch、零层和 Engram/tap 顺序。它不模拟 GPU 计算或内存同步。GPU 单测直接对照原始 FlyDSL kernel，要求两套独立的可写模型状态，比较完整有效 tensor，并连续运行两个 decode step 检查 epoch 和 draft 持续状态。

## 接入已有 runner

已有 host 准备好本步输入后，可以通过 `prepared_from_runner(runner, rows)` 取得 `PreparedStep`，再用 `load_kernel(manifest, prepared)` 和 `launch_prepared(function, cfg, prepared)`。这三个函数不替代 runner 的模型加载、plans 更新、计数器清零、Engram staging 或 peer allocation 生命周期管理。

保留所有 table/cache/peer owners 至 GPU 完成。split 的 target/draft 之间不重新清 `cnt` 或持续状态；每个 TP rank 都先 enqueue，再等待 GPU。host 用 HIP module occupancy 查询排除 resident CTA 容量明显不足的构建，但这个上界检查不能证明 cluster placement 和全网同步一定正确。

这里编译得到的全 kernel 资源预算是所有内联阶段的最大值。复杂片段的 CCC 保存与 scratch、额外 LDS 和远跳转可能影响 occupancy、代码体积与性能。当前没有 gfx1250 正确性或性能结论，也没有声称它已可替换生产 kernel。
