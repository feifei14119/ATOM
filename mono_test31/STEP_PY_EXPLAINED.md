# 原始 step.py 的 body 伪代码与行号对照

body 伪代码（原 L214–475）：[step_py_pseudocode.hip.cpp](step_py_pseudocode.hip.cpp)。原文件：[step.py](../atom/models/deepseek_v41/mono/gfx1250/kernels/step.py)。

全部 FlyDSL 片段与原函数的完整对应表见 [FLYDSL_SOURCE_MAP.md](FLYDSL_SOURCE_MAP.md)，包括公共上下文和额外适配逻辑。

伪代码仅保留 `body`，采用与之前 ASM 说明相同的 HIP/C++ 风格，按 **原始 Python 的结构和位置** 表达逻辑。`PY Lx-Ly` 指原始 `step.py` 行号；`ASM Lx-Ly` 才指 `step.s`。不要把这两套行号混用。

本次读取的 `step.py` 共 486 行，SHA256 为 `1ef733d1ed0664a3a0618e53e05d9779b44825686bcf6225373d0a64dbd9d7d1`。源文件有改动时，应重新核对注释。本次仅新增说明和核对行号，没有修改 kernel、构建或执行测试。

## 1. 阅读约定

| 伪代码记号 | 含义 |
| --- | --- |
| `if constexpr` | 对应 `fx.const_expr` 等 tracing 条件，按构建配置保留逻辑。 |
| `for_constexpr` | 对应 tracing 时的展开，例如 `range_constexpr(len(SEGS))`。这是解释性记号，不是 C++ 关键字。 |
| 普通 `for` / `if` | `body` 中的设备运行时循环或条件。 |
| `cond ? x : y` | 对应 FlyDSL `.select` 的值选择；不说明后端一定生成分支或一定只求值某一侧。 |
| `logical_cta_id()` / `thread_id()` | 原 `fx.block_idx.x` / `fx.thread_idx.x`，不指定手写汇编寄存器。 |
| `Context` / `with_fields` / `make_*` | 对原 dict、LazyC、cwith 的参数打包缩写。来源行号在调用处标明；它们简写参数打包，不替代计算阶段。 |
| 原名计算 helper | 保留 `stage_A`、`FS.front_any` 等名字；对应源码中的计算调用，不在本文展开其其他文件的内部算法。 |

这是解释性伪代码，未定义完整类型、上下文或外部 helper，不能直接用 hipcc 编译。具名参数和 tracing 变量保留为阅读记号；build、launch 和 helper 的定义未展开。

## 2. body 的九个参数

原函数签名在 L215–216，原 launch 的参数说明在 L480–481。除了 `scale`，其余参数都用 Int64/u64 承载设备虚拟地址；地址本身不是 tensor 数据。

| 参数 | 含义 | 在 body 中的用途 |
| --- | --- | --- |
| `recv0` | 当前 GPU 可访问的 rank0 接收缓冲区基址。 | 与其他 recv 合成数组，按 epoch 选择通信半区，L217–219。 |
| `recv1` | 当前 GPU 可访问的 rank1 接收缓冲区基址。 | 同上。 |
| `recv2` | 当前 GPU 可访问的 rank2 接收缓冲区基址。 | 同上。 |
| `recv3` | 当前 GPU 可访问的 rank3 接收缓冲区基址。 | 同上。 |
| `cnt` | 本 decode step 的同步计数器区基址，host 按 step 准备并清零。 | `lc=cnt+Ly*LCB` 定位每层，尾部/入口用 `cnt+(NL+NDR)*LCB`，L231/L247/L274。 |
| `st` | 时间戳缓冲区基址。每 CTA 有 32 个 8-byte 槽，即 256 字节。 | `stp=st+b*256`，记录 layer 起止和尾部时间戳，L292–303/L457/L463/L471。 |
| `scale` | attention softmax 的数值缩放系数。 | 传入 attention 上下文 c，L283；具体使用在 attention helper 中。 |
| `fp` | 主体设备表基址，按顺序包含 FPTRS、ATAB、每层 LKEYS 行。 | 查找权重、激活、KV/索引计划、位置元数据、epoch 等地址或每层标量。 |
| `tp` | 尾部设备指针表基址，字段顺序由 tail.TPTRS 定义。 | head、sampling、verification、draft 使用；例如 verdict、anc、dh，L251/L257/L260/L399/L464/L472。 |

`recv0..3` 是通信区，TP allreduce 和尾部跨 rank 交换使用其中的相应区域。入口 `tp_epoch_begin` 按 `epoch&1` 选择当前半区，并清理当前 rank 的下一步半区。

`fp` 和 `tp` 都是“表的地址”：例如 `fptr(fp,"emb")` 从 fp 表读出 embedding 数据地址；`ST.tptr(tp,"verdict")` 从 tp 表读出 verification 结果区地址。字段项还可能引用权重、输入、输出、scratch 或持续状态，因此这两个参数不能理解为单一输入 tensor。

`rank`、`TR/TRD`、`NL/NDR`、`part` 等没有出现在这九个参数中，因为它们来自 `build` 的闭包/编译配置。`SEGS`、`L/LD`、`stx` 和 `keyed` 也由外层准备。伪代码保留这些名字供 body 使用，不把它们改成新增运行时参数。

body 内部的分段为：L214–266 是入口，L267–457 是 layer body，L458–475 是尾部和 epoch 结束。

## 3. 三种循环及 target tail 的原位置

L209 的 `SEGS` 是构建侧列表：

```cpp
SEGS = (part != "draft" ? [(0, NL, 1)] : [])
     + (ndr && part != "target" ? [(NL, NL + ndr, 4)] : []); // PY L209
```

L220 在 tracing 时展开这个列表。target kind=1，draft kind=4，`DRS=(kind&4)!=0`。每个 segment 内用 L267 的设备循环遍历 `[seg_lo,seg_hi)`。L362 的 selection `pi` 循环和 L379 的 front `hf` 循环嵌套在 layer 内。

这与 `step.s` 中运行时 `s52=0/1` 的段切换写法不同：Python 在 tracing 时构建各段及其形状，ASM 则复用一个外层 layer 调度区，并选择编译好的片段变体。

原源码的 target tail 有两个调用位置：

```cpp
for_constexpr (segment : SEGS) {                  // PY L220-L221
    if constexpr (DRS) {                         // PY L243
        if constexpr (part == "all") {
            ST.target(...);                      // PY L248-L251，进入 draft 工作之前
        }
        draft_entry_work(...);                   // PY L256-L266
    }
    for (Ly = seg_lo; Ly < seg_hi; ++Ly) { ... }   // PY L267-L457
}
if constexpr (part == "target") ST.target(...);  // PY L458-L465
if constexpr (NDR > 0 && part != "target") ST.draft(...); // PY L466-L472
```

因此 all 且有 draft 层时，target tail 出现在 draft segment 入口；all 且 `ndr=0` 时根本没有 draft segment，也不满足外面的 target 条件，故没有 target tail。split target 则在所有 target 层之后执行尾部。

## 4. layer body 保留了哪些细节

伪代码按原位置标出了以下工作：

- L277–291：用 LazyC 构建 attention 上下文。带 thunk 的字段每次访问重新产生表读取，不能把它理解成统一提前加载并缓存所有指针。`ksel/knsel` 最终用每层表覆盖共享表的默认 thunk。
- L300–314：第 0/1 层时间戳、target-only Engram embedding 量化、attention A 后的两次权重预取和 handoff、Engram KV。
- L315–329：KV/C、可选 IQ/IW 和 compressor GEMM。`hascomp` 来自 bit1，`r1` 来自 bit2；KV/C handoff 始终执行。
- L330–366：量化、可选 compressor rows/ring、`ibat!=0` 时的 scorer 和 selection。保留 `lfl/lfl2/lfl3` 的分别读表及 `pi` 的 mode/level 计算。
- L367–377：attention D/E 后的数据预取、F 后的 CTA barrier、TP1 allreduce 和 group 发布。
- L379–450：两遍 front、early shared 和 hf0 的 MoE/combine/TP2，详见下一节。
- L451–457：layer end handoff、target-only tap、结束时间戳；没有添加 tap 后的同步。

selection 的公式直接对应 L361–364：

```cpp
npass = isrx ? IDX_LEVELS : (iprod ? 2 * IDX_LEVELS : IDX_LEVELS); // PY L361
for (pi = 0; pi < npass; ++pi) {                                // PY L362
    pmode = isrx ? MODE_RX : (pi < IDX_LEVELS ? MODE_SEL : MODE_BLK); // PY L363
    plev = pi % IDX_LEVELS;                                    // PY L364
}
```

当前 `IDX_LEVELS=2`（L66），REINDEX 选择两遍 RX；普通路径是两遍 SEL；candidate producer 且不是 REINDEX 时是两遍 SEL 再两遍 BLK。

## 5. front 内部为什么复杂

`hf=0` 是 FFN front，`hf=1` 是下一层 attention front。源码用同一段 front 代码和运行时选择复用这两种行为。

| 原行号 | front 的内部行为 |
| --- | --- |
| L384–385 | front CTAs 按 hf 选择等待 TP1 或 TP2 column-group counter；其他 CTA 跳过。 |
| L389–403 | 选择输入、输出和 scratch 指针：R/Rout、y1/y2、xn/axn、fx8/attention x8 等。 |
| L399 | hf1 且是当前段末层时，将 `xn` 输出改为 target 的 xh 或 draft 的 dh。 |
| L404–406 | 按 hf 从当前层表读取 front 权重，覆盖前面共享表的默认字段。 |
| L409–410 | LDS 残差区 `rk`；`first` 和 `last` 标志。保留原 `last` 公式，没有改写成通用的“当前段末层”。 |
| L412–414 | target 编译变体才带 Engram gate；运行时还要求 hf1 且本层 bit7。 |
| L415–421 | front 的 k=5 callback 在 early shared 启用时，由 hf0 front CTA 发布 X8_PUB。 |
| L423–434 | eligible idle CTAs 等待所有 front CTA 的 X8 发布，再做 early shared UG。 |
| L435–450 | 只有 hf0 执行 front handoff、MoE、combine 和 TP2。 |

L399 的段末 head 输入条件和 L410 的残差 `last` 条件是两个独立公式，伪代码都保留。例如 L410 明确使用 `Ly==NL-1` 及 target tap 层范围，而没有统一替换为 `Ly==seg_hi-1`。

`FIRST_LY=-1`（L223），所以在通常的非负层号配置下，layer 内 `first=isf && Ly==FIRST_LY` 为假；入口 `entry_front` 独立传入 `first=true`（L143）。

## 6. 与之前 step.s 说明的阶段对照

下表便于在两份伪代码之间定位同一阶段；它是源码结构映射，不是已执行的正确性验证。

| 行为 | 原 step.py | step.s |
| --- | --- | --- |
| epoch begin | L219；helper L76–91 | L84–95，额外用 scheduler LDS 交接 epoch |
| target state / handoff | L232–235 | L109–118 |
| target entry front / handoff | L236–238 | L119–131 |
| all 的 target tail | L248–251，在 draft 入口内 | L400–408，在 target segment tail |
| draft metadata | L256–259 | L139–145 |
| draft state / handoff | L260–263 | L147–156 |
| draft entry front / handoff | L264–266 | L157–169 |
| layer 起始时间戳 | L300–303 | L177–181 |
| Engram Q | L304–306 | L182–190 |
| attention A / 预取 / handoff | L307–310 | L192–201 |
| Engram KV | L311–314 | L202–210 |
| KV/C | L315–316 | L212–216 |
| index prepare，含 compressor GEMM | L317–328 | L217–225 |
| KV/C handoff | L329 | L227–231 |
| index quant，含 compressor rows/ring | L330–344 | L232–240 |
| quant handoff | L345 | L241–245 |
| ibat 判断 / score / handoff | L346–360 | L246–259 |
| selection 与逐遍 handoff | L361–366 | L260–280 |
| attention D/E/F 和 TP1 | L367–377 | L282–311 |
| 两遍 front 和 front 等待 | L379–422 | L313–336 |
| early shared | L423–434 | L338–344，外层先判断 hf0 |
| MoE、combine、TP2 | L435–450 | L345–368；hf0 分支为 L338–339 |
| layer end、tap、结束时间戳 | L451–457 | L373–395，含显式层循环回边 |
| split target tail | L458–465 | L400–405，构建条件控制 |
| draft tail | L466–472 | L413–418 |
| epoch end | L473；helper L95–100 | L421–426 |

原 `step.py` 用九个显式 kernel 参数（L215–216），`tep` 直接由 `tp_epoch_begin` 返回。手写 ASM 版本的 kernarg record 和新增 scheduler LDS 交接不属于原源码，因此未加入这份伪代码。

原 `build` 的 `TRD` 默认等于 `TR`（L211），只有传入 `trd` 才覆盖。`mono_test31` 的 host/config 所选 draft rows 是另一层配置，不能反过来改写原文件的默认公式。

## 7. 同步与边界

`handoff(...,True)` 与 `handoff(...,False)` 的实现来自 `device.py`，两者默认都是等待 256 CTAs 的 device-wide handoff。True/False 表示不同的内存顺序方案，不能把 False 当作单 CTA 同步。伪代码只把源码中的 `gpu.barrier()` 写成 `__syncthreads()`。

`gpub/gwait`（L148–161）则按 column group 发布/等待 16 个 TP CTA。`wait_count` 是带超时记录的轮询 helper，本文没有把它简化成无限等待。

每次 launch 只有一个 epoch begin/end，包括没有任何 segment 的 `part=draft,ndr=0`。零 target 层仍有 target 入口；是否执行 target tail 取决于 part/ndr 条件，而不是 layer body 是否运行。
