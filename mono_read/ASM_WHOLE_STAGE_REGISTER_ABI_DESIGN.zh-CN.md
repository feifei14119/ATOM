# 用独立 ASM 替换整个 Mono stage：全部输入加载、参数传递与寄存器契约

日期：2026-11-11。

**设计目标：将 WQKV 的全部输入加载、输入就绪等待、内部数据搬运、计算、归约和输出发布完整交给 ASM。具体包括输入 X、输入 scale、权重 W、权重 scale。保留 ATOM Mono 的外层任务调度和现有 tensor/mailbox 布局；Python 层只调用 `stage_wqkv_asm(c, task, t0, n)`，机器层传地址、整数和工作区偏移，由自定义调用契约指定寄存器。**

本次修订取消调用方的全部 WQKV 输入加载步骤：不调用 `gemv_fp8_loads`、`load_x8` 或此前拟议的 `load_x8_words`。ASM 接收 `x8/x8s` 两个 global mailbox 地址，自己检查 tag、读取输入数据和输入 scale。默认实现由 ASM 将 X 搬入已有 `xl` LDS 工作区，将输入 scale 保留在寄存器中；调用方只提供空间，不预先填充数据。

本文是详细接入设计，不是已经完成的整个 WQKV ASM 实现。所有标注为示意的 API、汇编流程和契约扩展都需要后续实现。已有 LLVM 原型的实现范围与验证结果见 [LLVM 外部 ASM 调用契约实现说明](../llvm_asm_contract/README.zh-CN.md)；完整需求见 [调用契约 RFC](AMDGPU_EXTERNAL_ASM_CALL_CONTRACT_RFC.zh-CN.md)。

## 1. 最终选择的边界

原通用 ATOM 调用顺序可以概括为：

```python
wqkv_ops = gemv_fp8_loads(co, wqkv, wqkv_s, HIDDEN, wqkv_task)
load_x8(...)  # 等待输入 mailbox，将输入和 scale 准备到 LDS
stage_wqkv(co, wqkv_task, wqkv_ops, 0, own_n)
```

本设计将这三个步骤合成一个完整的 ASM stage 调用：

```python
stage_wqkv_asm(co, wqkv_task, 0, own_n)
```

职责划分如下：

| 数据或操作 | 来源 | 由谁读取／完成 |
| --- | --- | --- |
| FP8 输入 X | `c["x8"]` global mailbox | ASM 检查 tag 并读取；默认由 ASM 搬到 `c["xl"]` 后用于计算 |
| 输入 scale | `c["x8s"]` global mailbox | ASM 检查 tag、取出 scale code 并组织矩阵指令的 scale 操作数 |
| 权重 W | `c["args"]["wqkv"]` global tensor | ASM |
| 权重 scale | `c["args"]["wqkv_s"]` global tensor | ASM |
| 矩阵计算、归约、舍入、QKV 发布与 stage 同步 | 原 stage 的计算和协议 | ASM |

两种 scale 读取都在 ASM 中，但来源格式不同：权重 scale 是原有打包 tensor；输入 scale 是含 payload/tag 的 mailbox。不能把二者作为相同格式的裸 scale 数组读取。

前面的 norm stage 仍负责生成 FP8 输入及输入 scale，并按现有协议发布。此次移动的是 WQKV 读取端，量化与 scale 的生产过程不变。ASM 从首版就可以安排“先发出权重加载，再等待输入”的顺序，见第 9 节。

“全部加载交给 ASM”指这次 WQKV 计算的数据加载。Mono 入口仍会取得 kernel 参数、线程编号、任务编号和已有地址，前后其他 stage 仍执行自己的逻辑；这些不属于 WQKV 算子输入的预加载。

这仍然是 Mono 入口内部的一次设备函数调用，不额外启动一个 `__global__` kernel，不引入 host 往返，也不需要在每个 stage 调用前写一份全局参数结构体。

## 2. `c` 是什么，实际传递什么

### 2.1 `c` 不是 GPU 上的结构体

现有 `c` 是 Python 构建 IR 时使用的上下文字典，其中既有运行时 IR 值，也有编译期配置、地址包装对象和生成设备代码的 Python 方法。

因此不能把它直接转换成 `WqkvStageArgs*`，也不存在天然的 GPU 地址 `&c`。Python 适配器应在构建 IR 时提取需要的字段，生成标量实参。

| 内容 | 实际存放位置 | 传给 ASM 的形式 |
| --- | --- | --- |
| Python 字典 `c`、`c["args"]` | Python 编译／构建阶段 | 不传字典，编译期提取字段 |
| 权重与权重 scale 数据 | 已有 global tensor | 两个 64 位地址 |
| 输入 X `x8` | 已有 global mailbox | 64 位 mailbox 基地址；ASM 按预期 tag 轮询 |
| 输入 scale `x8s` | 已有 global mailbox | 64 位 mailbox 基地址；按预期 tag 轮询 |
| QKV mailbox | 已有 global workspace | 64 位基地址及 32 位 tag |
| `xl/red` 工作区 | Mono 为本 stage 保留的 LDS 空间，入口内容不可依赖 | 两个 32 位 LDS 字节偏移；ASM 自行写入所需数据 |
| `task/t0/n` | IR 中的整数值，或编译期常量 | 寄存器参数，或针对常量特化 ASM |
| `tid` | 由 Mono 入口获得的线程编号 | VGPR 参数 |
| `HIDDEN`、固定线程配置、布局 | 编译期配置 | 绑定到 ASM 变体及其契约 |
| `put/poll` 等 Python 方法 | Python 构建阶段 | 不作为 GPU 函数指针传递；ASM 实现对应协议 |

这里“已有 global workspace”包括代码中名为 `scratch` 的 mailbox 工作区。它与 LLVM 为上下文保存生成的 private scratch 是不同概念。

### 2.2 权重、scale 和 mailbox 地址已经存在

通用 ATOM 的 `attn_pre` 入口接收 `wqkv/wqkv_s`，构造 `c` 时已经保存为：

```python
c["args"]["wqkv"]
c["args"]["wqkv_s"]
```

输入 X 和输入 scale 的 mailbox 地址分别来自 `c["x8"]`、`c["x8s"]` 的 `Addr.value`。`c["xl"]` 是可供 ASM 搬入 X 的 LDS 工作区；`c["xsl"]` 是原代码使用的 scale LDS 区域，本版默认不使用。

适配器取出这些 IR 值即可。不需要 host 再上传一个指针表；不需要每次调用都把地址写回 global memory。提取 `Addr.value` 时还要保留第 4.3 节的 plan 效果记录。

gfx1250 C1 单测中，入口参数名为 `weight/scale`，目前没有放入 `c["args"]`。可以在其构建 `c` 的位置加入：

```python
# 构建 IR 时增加字段，不是 GPU store。
c["args"]["wqkv"] = weight
c["args"]["wqkv_s"] = scale
```

### 2.3 Python 参数少，不意味着所有参数都是立即数

建议的 Python 接口为：

```python
stage_wqkv_asm(c, task, t0, n)
```

`task` 通常由 CTA 的任务分配计算得到；`t0/n` 可能是运行时值，也可能是编译期常量。C1 可以采用专用变体，将 `t0=0、n=1` 编入 ASM。

如果独立对象仍声明 `t0/n` 为入口寄存器参数，即使调用时写了字面量 `0/1`，LLVM 也可能生成设置寄存器的指令。要省去这两个机器参数，需要另行定义并绑定不含它们的专用变体，而不是期待链接器自动修改手写 ASM。

## 3. 建议的参数 ABI

下表定义一个便于理解的通用入口。它是拟议寄存器布局，可根据实际 ASM 调整，不是标准 AMDGPU device ABI 的固有规则。

| 顺序 | 参数 | 类型 | 入口寄存器 | 来源及语义 |
| --- | --- | --- | --- | --- |
| 0 | `qkv_base` | u64 | `s[0:1]` | 原 QKV mailbox 区域的基地址 |
| 1 | `tag` | u32 | `s2` | 本次 X／输入 scale 等待及 QKV 发布使用的 tag |
| 2 | `xl_offset` | u32 | `s3` | 供 ASM 写入输入 X 的 LDS 工作区字节偏移；入口未准备数据 |
| 3 | `red_offset` | u32 | `s4` | 部分和／归约区的 LDS 字节偏移 |
| 4 | `task` | u32 | `s5` | 逻辑 WQKV 输出行组编号 |
| 5 | `t0` | u32 | `s6` | token 起点，语义与原 stage 一致 |
| 6 | `n` | u32 | `s7` | 本次处理的有效 token 数 |
| 7 | `weight_base` | u64 | `s[8:9]` | 已打包 WQKV 权重的 global 基地址 |
| 8 | `weight_scale_base` | u64 | `s[10:11]` | 已打包权重 scale 的 global 基地址 |
| 9 | `input_scale_mailbox_base` | u64 | `s[12:13]` | `c["x8s"].value`，包含 tag 的输入 scale mailbox |
| 10 | `input_mailbox_base` | u64 | `s[14:15]` | `c["x8"].value`，包含 tag 的 FP8 输入 mailbox |
| 11 | `tid` | u32 | `v0` | CTA 内线性线程编号，每 lane 不同 |
| — | 返回 PC | u64 | `s[30:31]` | 调用序列生成，ASM 返回时使用 |

约束与解释：

1. 64 位参数低 32 位在较小编号寄存器，高 32 位在较大编号寄存器。
2. SGPR 实参必须 wave 内一致，且通过编译器的 uniformity 检查。语义上相同但编译器无法证明的值，需要合法的证明机制或改用 VGPR；不能静默 `readfirstlane` 丢失 lane 差异。
3. 地址并不强制必须用 SGPR。若供应方 ASM 需要 `v[0:1]` 传某个指针，可以修改契约，并为 `tid` 选择其他位置。
4. `s[0:1]` 在本接口里是 QKV 地址，不是 HSA kernel 入口的 kernarg 指针，也不是 workgroup x/y。独立 kernel 的隐式寄存器假设必须改写成此函数的显式输入。
5. 当前 WQKV 已有 `task`，不必重复传 workgroup ID。其他 stage 真正需要时，可以增加 `block_x/block_y` 参数；物理 CTA ID、Mono task ID 和算子 tile ID 不能混用。
6. 对 gfx1250 的 256 线程、wave32 变体，可以用 `lane=tid%32、wave=tid//32`。512 线程变体的逻辑分组不同，必须使用它自己的映射，不能直接套用。
7. LDS 偏移单位是字节。FlyDSL 原表达式如果按 i32 元素寻址，ASM 需显式乘 4。
8. 普通返回类型为 `void`；结果通过原 mailbox 发布，不要求增加寄存器返回值。
9. 现有 LLVM 原型还保留 `s30:s39` 等调用所需位置。实际契约应遵守工具链的完整保留规则，不能只避开返回地址对。
10. 本表用同一个 tag 等待 X／输入 scale、发布 QKV，对应当前 stage 使用同一 mailbox 对象的行为。若后续版本各端协议不同，应分开传值，不能强行复用。

本版新增 `input_mailbox_base`，不传 `xsl_offset`。`xl_offset` 的语义是可写工作区，不是“已经加载好的输入”。ASM、声明、适配器、契约必须一起更新版本，不得将新版调用方与旧版对象混合链接。

这个表规定的是调用瞬间的物理位置，不要求整个 Mono 始终固定使用这些寄存器。固定输入位置也不等于 callee 返回后保持这些位置的值；是否保持由污染契约另行规定。

表中列出计算与 tag 协议的核心参数，未列可选诊断字段。现有 gfx1250 C1 使用 diagnostic mailbox；要保持它的超时／失败记录行为，还需为 ASM 轮询传入相应 diag/failure 地址、region ID、CTA ID 等，或采用明确的诊断变体契约。不能直接删掉原有诊断后声称行为完全相同。

## 4. 调用方和适配器示例

### 4.1 通用 ATOM 的最小改动

构建原有上下文时显式暴露 tag：

```python
# 既有逻辑：mb = mailbox(...); c = {...}
c["mailbox_tag"] = mb.tag
```

这是一条 Python 字典赋值，复用现有 IR 值，不增加 GPU 内存写入。若随后生成 `co = own_view(c, ...)`，需确保该字段随上下文传入，同时保留原视图的区域地址与 token 语义。

调用位置改成：

```python
# 示意：沿用原 task 计算、有效任务条件和 token tile 范围。
if wqkv_task < WQKV_TASKS:
    stage_wqkv_asm(co, wqkv_task, 0, own_n)
```

调用方不再准备任何 WQKV 输入 payload，不再调用原 `poll_copy` 搬运输入，也不设置“输入已经就绪”的隐含前提。ASM 实现原加载、轮询、内部搬运以及必要的 barrier。其他 stage 使用的原 `load_x8` 可以保持不变，无需全局删除公共函数。

为了尽量不动原有 LDS union，首轮可以保留 `xsl` 的分配和上下文字段，但本 stage 不读取、不传递它。这种保留不会自动降低 LDS 资源占用；后续若删除分配，必须重新检查所有相关布局与使用者。

`xl/red` 仍可以由 Mono 的 SharedAllocator 统一保留空间、确定布局并更新资源描述。传递其偏移不触发数据加载；ASM 不得依赖它们的入口旧内容。原 stage union 的释放和复用条件仍要成立。

多 tile 分支同样删除 `wqkv_ops` 列表生成和 WQKV 的外部 `load_x8`，保留 task/tile 的计算和有效性条件，对每次调用传递原来的 `t0/n`。gfx1250 C1 对应删除 `reference_fp8_loads` 和 `reference_load_x8_c1` 的这处调用。不能只修改其中一条路径后就宣称覆盖全部 Mono。

### 4.2 编译期适配器

以下 `record_put_and_get_address`、`record_poll_and_get_address`、`lds_byte_offset`、`asm_wqkv` 是说明职责的伪 API，不是现成可执行代码：

```python
@traced
def stage_wqkv_asm(c, task, t0, n):
    # 构建期记录 plan 效果，再提取实际地址；这里不发出 GPU poll。
    qkv_base = record_put_and_get_address(c["qkv"])
    input_scale_base = record_poll_and_get_address(c["x8s"])
    input_base = record_poll_and_get_address(c["x8"])

    asm_wqkv(
        qkv_base,
        c["mailbox_tag"],
        lds_byte_offset(c["xl"]),
        lds_byte_offset(c["red"]),
        task,
        t0,
        n,
        c["args"]["wqkv"],
        c["args"]["wqkv_s"],
        input_scale_base,
        input_base,
        c["tid"],
    )
```

`lds_byte_offset` 的 lowering 应保留地址空间语义，将 AMDGPU local/AS3 指针转换为 32 位 LDS 地址。不能把 local 指针当成 64 位 global 地址，也不能把此处变成一次 LDS 数据复制。适配器传出的 `xl/red` 仅用于授予相应工作区，内容准备完全发生在 ASM 内。

适配器是 Python/MLIR 构建层：最终应直接生成对独立 ASM 符号的契约调用，不增加一个遵守默认 ABI 的 `noinline __device__` 包装层。后者仍可能因默认 callee-saved 义务生成 scratch 保存。

### 4.3 保留两类效果信息

完整 stage 变成不透明 ASM 后，至少要保留两层信息：

- **Mono plan 的构建期读写记录。** 适配器必须显式记录 `qkv` 的写入、`x8` 与 `x8s` 的读取／等待。原 `put/poll` 通过 `Addr` 和 `_noted` 一类机制记录这些效果。现在不能再依赖外部 `load_x8` 替 ASM 记录任何输入读取。
- **编译器的访存和同步语义。** 不能把调用标为纯函数、`readnone` 或只读。它读取 global/LDS、写入 LDS/global 并执行同步。即使传的是整数形式的地址，也不能错误地假设它无法访问外部 LDS/global 对象；应保守表达效果，并检查 lowering 后的排序。

plan 记录不能代替 LLVM memory effects，`convergent` 也不能代替正确的访存依赖。

## 5. ASM 如何读取：gfx1250 C1 的具体例子

### 5.1 固定示例配置

以下公式仅对应现有 gfx1250 C1 reference 的这一变体：

```text
HIDDEN = 5120
每个 task 输出 16 行
256 线程 / CTA，wave32，8 个 wave
t0 = 0，n = 1
采用 reference_projection.py 的权重打包布局
```

每个 wave 的 K step 为 `st=wave+8*i`，其中 `i=0..4`，共 40 个 K128 step。本例维度整除 128；通用尾部处理必须另行按原实现移植。

原接口预先构造 5 组 `(16 个 i32 权重值, 1 个 i32 权重 scale)`，共 85 dword/lane。本接口对这部分只传权重和权重 scale 的两个地址，85 个值不再跨函数边界传递；另外传入 X 和输入 scale 的两个 mailbox 地址。

它们在加载后仍需实际寄存器容纳。ASM 可以按 step 加载或流水化，不能把“减少参数”直接解释成“最终减少 85 个 VGPR”。

### 5.2 权重和权重 scale 地址

定义：

```text
lane   = tid % 32
wave   = tid // 32
lane16 = lane % 16
half   = lane // 16
st     = wave + 8*i
```

当前 reference 的四次 16-byte 权重加载，对应字节地址：

```text
weight_base
    + task * HIDDEN * 16
    + st * 2048
    + half * 256
    + lane16 * 16
    + j * 512                         # j = 0,1,2,3
```

该 step 的权重 scale 为一个打包的 32 位字：

```text
weight_scale_base + 4 * ((task // 2) * (HIDDEN // 128) + st)
```

这些公式是对当前 reference 的访存地址换算，并非一般 GEMM 的行主序寻址。若实际 ASM 使用另一种权重打包布局，必须转换权重或重写访存，ABI 本身不会解决布局差异。

具体取 `task=3、tid=49、i=0`：

```text
lane=17，wave=1，half=1，lane16=1，st=1
四个权重块的字节偏移：248080、248592、249104、249616
权重 scale 的字节偏移：164
```

ASM 使用 `s[8:9]`、`s[10:11]` 中的基地址与这些偏移访问 global memory。权重及其 scale 是按现有 launch 依赖保证可读的 tensor，这部分没有输入 mailbox 的逐元素 tag。若选择 buffer 指令，需要自行构造正确的四 dword resource descriptor；一个两 dword 指针不等于完整 buffer descriptor。也可使用目标支持的其他 global 寻址形式。

### 5.3 输入 X：ASM 从 mailbox 读取并自行准备 LDS

`s[14:15]` 指向 `x8` mailbox。一个逻辑元素的 payload 打包四个 FP8 数值，与自己的 tag 组成 8-byte pair：

```text
words = HIDDEN // 4
u = tile 内的逻辑 i32 元素编号，0 <= u < n * words
local_token = u // words
col_word = u % words
pair_index = (t0 + local_token) * words + col_word

input_mailbox_base + pair_index * 8 + 0：四个 FP8 数值打包成的 i32
input_mailbox_base + pair_index * 8 + 4：i32 tag
```

ASM 读取 payload/tag，按原作用域和轮询规则检查 tag。匹配后将 payload 写入自己的工作寄存器或 LDS，tag 不参与矩阵计算。

默认实现继续采用现有 LDS 输入布局，以复用 reference 的矩阵寻址：

```text
lds_row(words) = words + 4                    # 当前原布局的行 padding
destination = xl_offset + 4 * (local_token * lds_row(words) + col_word)
```

CTA 的线程 `tid` 可以分工处理 `u=tid、tid+threads、tid+2*threads、……`。分批轮询并及时写入，避免将所有输入临时保留在寄存器里；所有有效输入写入完成后，由 ASM 执行所需的等待和 CTA barrier，再让矩阵计算读取 LDS。

C1 的 `HIDDEN=5120、n=1` 有 1280 个 payload word。取 `tid=49、threads=256`，该线程搬运的示例为：

| 逻辑 word `u` | Global pair 字节偏移 | Tag 字节偏移 | 写入 LDS 相对 `xl_offset` 的字节偏移 |
| --- | --- | --- | --- |
| 49 | 392 | 396 | 196 |
| 305 | 2440 | 2444 | 1220 |
| 561 | 4488 | 4492 | 2244 |
| 817 | 6536 | 6540 | 3268 |
| 1073 | 8584 | 8588 | 4292 |

这里的 global 偏移按 8-byte pair 计算，LDS 偏移只按 4-byte payload 计算。不能直接把含 tag 的原始 mailbox 字节流当作连续 FP8 tensor 使用。

完成由 ASM 执行的搬运和同步后，同一 C1 变体的四个输入块，每块 16 bytes，对应计算阶段的 LDS 字节地址：

```text
xl_offset + 4 * (st * 32 + half * 4 + j * 8)    # j=0..3
```

第 5.2 节的 `tid=49、st=1` 对应 `xl_offset + {144,176,208,240}`。这些数据可能由其他线程搬入，因此不能省掉 CTA 内的数据就绪同步。

本例 `n=1`，没有多行下标混淆。多 token 时必须区分 global 的 `t0+local_token` 和 LDS 中从 0 开始的本地行，只轮询有效 word；padding 不要求从 mailbox 读取。维度尾部、所需额外 LDS 空间和无效矩阵元素的补齐应按原布局处理。

如果另一个 ASM 变体直接从 mailbox 组织矩阵操作数，允许不使用 `xl`。这需要该变体自行解决线程／wave 数据布局、重复读取与资源问题，并更新 ABI 和 LDS 契约；本设计默认用 ASM 内部搬运到 LDS 的方式，保证接入边界明确且布局便于对照。

### 5.4 输入 scale：ASM 直接轮询 mailbox

输入 scale 则从 `s[12:13]` 指向的 global mailbox 读取。每个 token 包含 `HIDDEN/32` 个逻辑 scale code，每个 code 在 mailbox 中占用 8 bytes：

```text
groups = HIDDEN // 32
token = t0 + local_token
group = st * 4 + j                            # j=0..3，本例无尾部
pair_index = token * groups + group

input_scale_mailbox_base + pair_index * 8 + 0：i32 scale code
input_scale_mailbox_base + pair_index * 8 + 4：i32 tag
```

C1 的 `t0=0、local_token=0、st=1` 对应 pair 起始字节偏移 `{32,40,48,56}`，各 tag 的偏移为 `{36,44,52,60}`。这些是 **global mailbox 偏移**，不能套用旧版 `xsl` 的 LDS 偏移 `{16,20,24,28}`。

ASM 的读取流程示意如下。它是协议伪代码，不是可直接编译的汇编：

```text
repeat:
    成对读取所需的四组 [scale_code, tag]
    等待这些 global load 完成
    如果任一 tag 不等于预期 tag，按原 poll 协议重读
until 所需 pair 的 tag 全部匹配

xs = code[0] | (code[1] << 8) | (code[2] << 16) | (code[3] << 24)
将 xs 作为该 K128 step 的输入 scale 操作数
```

必须复现原 mailbox 的缓存／作用域语义，检查数据与 tag 的同一批读取结果；有诊断配置时还要保留超时与失败处理。ASM 对 X 的轮询成功或内部 LDS barrier 都不证明 `x8s` 已发布，两种 mailbox 的有效性必须分别检查。

默认设计为 **global mailbox → ASM 寄存器 → 矩阵指令**，无需先搬到 `xsl`。如果 ASM 选择先写 LDS 共享 scale，这属于 ASM 内部优化，需要显式增加相应 LDS 分区契约和同步；不能暗中借用未声明的 `xsl`。

本例每个 wave 使用相同 token 和自身 K step 的 scale。最直接实现可以由参与 lane 读取并得到相同操作数；若优化为少数 lane 读取再广播，必须同时正确广播有效值与就绪条件。通用多 token 变体需要按真实矩阵映射选择 `local_token`，只轮询有效 token/K group，处理原来的尾部和 unit-scale 补齐，避免等待不存在的 mailbox 项。

### 5.5 归约与输出索引

完成矩阵计算后，各 wave 将部分和写入现有 `red` 区域，按原 barrier 顺序归约。C1 的线程 `tid<16` 最终写出逻辑元素：

```text
output_index = task * 16 + tid
```

通用 stage 则使用原来的：

```text
r = tid % 16
t = t0 + tid // 16
output_index = t * QKV_ROWS + task * 16 + r
```

通用版本还必须保持原输入 LDS 行跨度、有效 token 数与 wave 映射；不能只更改输出下标就把 C1 ASM 用作通用版本。

### 5.6 mailbox 输出不是裸 BF16 数组

当前对应的 `put` 协议将每个逻辑值表示为：

```text
qkv_base + output_index * 8 + 0：32 位 payload
qkv_base + output_index * 8 + 4：32 位 tag
```

WQKV 的 payload 是 `bf16_round(total)` 返回的 FP32 位模式，值已按 BF16 精度舍入，并非只存 16 位 BF16。

ASM 要复现原 `put` 的成对写入、作用域、缓存策略和后续消费者依赖的可见性规则。布局说明不意味着任意拆成两条无序 store 都与原协议等价。舍入和特殊浮点值的处理也应对齐原 `bf16_round`。

## 6. 组织者、读取者和运行时生命周期

| 层次 | 职责 |
| --- | --- |
| 原 host / launcher | 继续分配并传入已有 tensor、mailbox、layer 等参数 |
| 原 Mono 入口 | 接收 kernel 参数，获得 tid/bid，分配 LDS，建立 task 与上下文 IR 值 |
| 原调用方 | 保留任务调度及调用条件，提供已有地址和可用 LDS 空间，直接调用 stage |
| Python stage 适配器 | 编译期选择字段、转换地址表示、记录 plan 效果、生成标量调用 |
| ASM 契约 | 规定各参数的位置、污染集合、状态和资源条件 |
| LLVM | 准备参数寄存器、分配跨调用值、生成调用与必要的移动、检查严格策略 |
| ASM 函数 | 加载全部四类输入，轮询两个输入 mailbox，自行搬运／同步，完成计算和发布 |

运行时可概括为：

```text
Mono 入口获得已有参数
    → 原调度计算 task
    → LLVM 生成的参数准备序列
    → 调用独立 ASM 函数
    → ASM 发出权重及权重 scale 加载
    → ASM 轮询 x8/x8s，读取输入 X 和输入 scale
    → ASM 搬运 X 到 LDS 并完成所需同步
    → ASM 矩阵计算、归约、发布 qkv
    → 返回 Mono，继续后续 stage
```

没有运行时 Python 字典访问，没有自动构建的 `WqkvStageArgs` global 对象。编译期选择字段不等于运行时完全零指令：地址计算、常量装入和必要寄存器移动仍可能存在。

## 7. 上下文保持和资源契约

### 7.1 参数位置、污染集合与资源数量分别声明

ASM 除了入口参数，还应提供：

- 输入参数和返回 PC 的位置与宽度。
- 返回后不保证原值的 SGPR/VGPR，以及 SCC/VCC 等特殊状态的污染集合。
- 全部使用的寄存器范围，包括临时访问但最终恢复的寄存器。
- EXEC、MODE 等执行状态的保持要求；按所支持的契约也要覆盖 M0、TTMP、bank 状态等。
- 所需目标架构、wave 大小、CTA 形状、LDS 区域布局／大小／对齐及 barrier 条件。
- X 和输入 scale 两个 mailbox 的 pair 布局、预期 tag、可访问 token/word/group 范围、作用域与诊断变体。
- private memory 为零、叶函数等约束；真实访存效果和对象身份。

“使用过的寄存器”不等于“返回后被污染的寄存器”。最高编号决定资源覆盖范围，精确污染集合决定哪些值可以跨调用保持。

不能在没有 ASM 本体时先随意填一个低资源数或少量 clobber。应从真实函数得到描述并审核所有控制路径，最终与链接对象绑定。

### 7.2 LLVM 如何维护调用方

假设 ASM 会污染 `v64` 及以上的一段寄存器，LLVM 通过该调用点的 regmask 知道这些位置不能保存跨调用值，可以将仍需使用的值分配到实际保持的寄存器中，或安排普通寄存器复制和合法重算。

参数只在入口读取，并不天然要求 callee 保持。若权重基地址等还会在 Mono 后续调用中使用，LLVM 同样需要保护它们，除非 ASM 契约保证原值保持。

该约束针对调用点，不是要求所有 stage 的所有计算都永久限制在同一段寄存器。全 kernel 的资源上界与调用点 regmask 也是两种不同约束。

### 7.3 无 spill 是可检查的条件，不是无条件保证成功

严格要求：

```text
GPR spill = 0
private/scratch memory = 0
默认 ABI 保存造成的隐藏 spill = 0
不通过 global/LDS 临时区暗中保存调用者上下文
```

可以生成普通寄存器移动、必要的常量装入和 call/return。若所有合适的保持位置都不足，编译失败并报告原因；不能退回 scratch，也不能把调度和参数契约描述成可以凭空保存任意上下文。

原算法的 LDS 归约区和 global mailbox 是合法算法数据，并不因为严格无 spill 就要删除。

最终报告应覆盖固定参数、真实调用点的 live-through 物理寄存器、保持／污染集合、最终 SGPR/VGPR 资源、private 大小、普通及 ABI spill、LDS 范围。不能仅凭 spill metadata 为零就断言完全没有 scratch。

## 8. 执行状态、LDS 和 barrier 的边界要求

完整 WQKV stage 不是普通逐 lane 的纯算术函数。其正确性还取决于：

1. 所需 CTA 线程按相同的 barrier 序列参与。`if task < limit` 必须对参与 CTA 的线程具有所需一致性，不能让部分 wave 提前返回后其他 wave 进入 CTA barrier。
2. 调用满足契约的 full EXEC 前提；ASM 内部允许的分歧与 EXEC 临时修改，需在后续同步和返回边界恢复。`convergent` 属性本身不是这些条件的证明。
3. ASM 使用传入的既有 LDS 分区，复用原来的 stage union 生命周期；必须先自行写入输入数据和部分和，再读取它们。入口没有“xl 已经填好”的保证，不能自行认为它拥有另一块 LDS 基址为零的私有空间。
4. LDS 契约应描述传入区间的大小、布局和同时使用关系。最终 kernel descriptor 要覆盖实际范围；复用同一块区域时不是把 caller 与 callee 的 LDS 大小盲目相加。
5. global/DS/矩阵指令需要的 wait 与 barrier 必须按 gfx1250 ISA 和原算法安放。函数调用／返回不是自动完成所有异步访存的通用 fence。
6. 返回前要处理可能在返回后继续写入寄存器的异步加载，避免调用者复用寄存器时被延迟结果覆盖；输出 store 的完成策略则必须满足 mailbox 协议，不能仅凭“函数返回了”推导可见性。
7. ASM 通过约定的返回 PC 返回，不能保留原独立 kernel 的 `s_endpgm`。普通设备函数不拥有独立 kernel 启动环境。
8. X 和输入 scale 轮询中的活跃 lane 和退出条件必须与后续矩阵指令、CTA barrier 相容。诊断超时路径不能让部分 wave 提前退出而使其他 wave 永远等待 barrier。
9. 原 `load_x8` 的末尾 barrier 现在属于 ASM 内部。调用入口仍需满足原 stage union 可复用条件；不能把“删除外部 helper”误解为同时删除原算法所需的同步。

首版使用单卡 C1、固定形状降低范围。多卡 peer 作用域、不同 token 视图和额外诊断信息，需要按各版本的原实现扩展参数或特化，不能默认用单卡的作用域替代。

## 9. ASM 内部的完整流程与预取顺序

原实现刻意先加载权重，再进行输入 mailbox 等待：

```text
原实现：
发出权重／权重 scale 加载 → 等待 x8/x8s 并准备 LDS → 矩阵计算

本设计：
进入 ASM → 发出权重／权重 scale 加载
    → 等待 x8/x8s，读取数据并按需准备 LDS → 矩阵计算
```

WQKV 的全部输入访问现在都在同一个 ASM 函数中，可以从首版就保留原来权重加载与输入等待的重叠，不再需要先在 FlyDSL 等完输入。重叠效果仍取决于实际指令安排、目标 wait-counter 语义和寄存器资源；接入边界本身不保证性能。

推荐的 ASM 内部职责顺序：

```text
发出权重／权重 scale 加载
    → 轮询 x8s 并将输入 scale 保存在寄存器
    → 轮询 x8 并复制 FP8 输入到既有 LDS
    → 必要的等待和 CTA 同步
    → 矩阵计算、归约
    → 发布 qkv
    → 返回
```

这里的两种 mailbox 轮询顺序仅为示意，可以按批次交错安排。若先读出的权重或 scale 需要长时间保留，应纳入寄存器资源评估；不要求一次性预取所有数据。

完整实现必须同时移植输入数据和输入 scale 的 poll、作用域、超时诊断，以及输入搬运和同步；适配器记录两者的 plan 效果。这些是本版的必要工作，不是以后再合入的扩展。

多 task／多 tile 路径还要考虑复用：原代码有的路径会先准备一次 X，再对多个 task 调用计算。采用“每次完整 stage 调用都自行加载输入”的简单接口，可能重复读取同一 X，产生额外访存。初版应先明确每次调用独立准备自己的输入；若后续优化复用，需要显式规定工作区有效期和同步，不能暗中依赖上次调用留下的 LDS 内容。

验收时分别测量调用开销、寄存器占用、等待重叠和重复读取。不能仅凭“所有加载放在一起”就推断性能一定提升。不引入“ASM 预取函数返回大量权重寄存器，再调用另一个 ASM 计算函数”的拆分，以免重新产生 `ops` 跨函数边界的问题。

## 10. 编译和链接的目标流程

```text
wqkv_stage.s
    → llvm-mc
    → wqkv_stage.co                  # 含设备函数的 ELF ET_REL
    → 寄存器／指令／资源审计和对象 hash 绑定
                                      │
FlyDSL stage 适配器 + 调用契约          │
    → 带契约的 LLVM 声明与直接 call    │
    → LLVM bitcode                    │
    → 修改后的 llc                    │
    → caller.o ─────────── ld.lld ────┘
    → 最终 Mono kernel code object
```

本设计使用独立目标静态链接与真实设备调用，不使用 `.long` 内嵌函数体，不对最终机器码逐行替换，也不要求用户修改 MIR regmask。

`.co` 扩展名本身不决定对象类型。已有可启动 `.hsaco` 或 ET_DYN kernel 对象不能直接当作此处的可调用函数使用；要适配入口、返回、参数、资源和隐式执行状态，再生成链接流程接收的目标。

推荐后续实现文件组织如下，文件名为规划，不表示本文已创建这些文件：

```text
whole_stage_demo/
  wqkv_stage.original.s       # 若有供应方原始汇编，保留它
  wqkv_stage.s                # 按本 ABI 适配的设备函数
  wqkv_stage.contract.json    # 参数、污染、资源、LDS、效果、hash
  stage_adapter.py           # 编译期字段提取与调用
  build/                     # co、caller.o、最终对象、反汇编、报告
```

## 11. 当前工具链已经具备什么，还缺什么

已有独立 LLVM 原型实现固定寄存器实参、自定义 call-preserved regmask、严格 spill/private 检查、callee 寄存器资源合并、独立对象链接和简单 FlyDSL 示例。

但不能仅把本文参数表写进现有 manifest，就宣称完整 WQKV 已经接入。还需至少完成：

| 工作 | 原因 |
| --- | --- |
| 实现全部输入加载与完整 WQKV ASM 本体 | 包括权重／权重 scale 加载、X／输入 scale 轮询、内部搬运、矩阵计算和发布 |
| 将调用方 WQKV 预加载序列替换为单次调用 | 同时移除该路径的权重预取和输入搬运，不保留隐藏的外部数据准备 |
| 增加已有 LDS 分区的导入／范围契约 | 当前原型限定 callee 无 LDS，完整 stage 明确使用 LDS |
| 扩展对象审计 | 当前白名单面向简单线性叶函数，不能覆盖完整矩阵、分支、DS 与 barrier |
| 完善 void 调用的 FlyDSL 适配 | LLVM 接口可表示 void，但当前 Python 适配器使用 `result.owner`，需要从 call op 处理无结果调用 |
| 表达并核查完整 memory/sync effects | 防止 LDS 准备、global 访问和 barrier 被错误优化或排序 |
| 接入实际 plan 的读写记录及诊断参数 | 保留 `x8/x8s` 等待、`qkv` 发布和原有超时／失败行为的可见性 |
| 检查最终 descriptor、对象身份和调用序列 | 单独函数契约不等于最终 kernel 资源与机器码已验证 |
| 在 gfx1250 单测上验证 | 已有简单 ABI 示例的离线成功不能代替整个 stage 的硬件结果 |

当前原型支持范围是 gfx1250、wave32、SelectionDAG、直接静态叶函数调用。不能把这里的设计理解为已在上游 LLVM/FlyDSL 发布的通用 ABI。

## 12. 建议落地与验收顺序

1. 固定单卡 gfx1250 C1、256 线程、HIDDEN=5120 及当前权重布局，建立完整 stage 的参考输入输出。
2. 将 WQKV 的全部加载和计算替换为一个 ASM 调用；由 ASM 实现四类输入读取、两个 mailbox 的轮询、内部数据搬运和计算。确认调用方不再预取权重或读取 `x8/x8s` payload。
3. 建立本版少量标量参数的自定义 ABI，传入 `x8/x8s` 地址、权重及其 scale 地址、tag 和未填充的 LDS 工作区偏移；保留 plan 效果与诊断，补齐 void/LDS/审计等工具链支持。
4. 汇编生成独立目标，并将参数、所有路径的寄存器行为、执行状态、资源与目标对象绑定。
5. 编译真正的 Mono 调用主体并静态链接，检查参数布局、call/return、实际跨调用值、最终 descriptor，以及完整的无 spill/private 条件。
6. 在 gfx1250 上比较完整 WQKV 输出，包括 X、两类 scale、舍入、tag 和边界保护；确认后续 stage 能消费结果。测试多个 task、重复 launch/tag 更新、X 与输入 scale 分别延迟发布／旧 tag、LDS 入口旧数据和调用后的上下文，确认没有读取过期输入、访问无效 word/group 或破坏等待协议。
7. 基于正确性结果测量延迟、寄存器压力与占用率，核查 ASM 内部的预取重叠，以及完整调用是否增加了多 task 场景的重复加载。
8. 在这一完整边界上扩展多 token、不同线程绑定和其他 stage；按需要优化 ASM 内部流水与复用，不重新要求调用方准备输入。

成功标准是：完整 Mono 单测正确、原数据流和协议一致、契约与对象相符、严格无 spill/private 检查通过。无法满足资源约束时允许明确编译失败，不承诺任意大 ASM 均能无 spill 接入。

## 13. 本地代码依据与相关文档

本文按当前本地源码整理；通用 ATOM 与 gfx1250 reference 的布局和线程映射应分别核对，不混用：

- [通用 attn_pre.py](../atom/models/deepseek_v41/mono/kernels/attn_pre.py)：`attn_pre` 的参数和 `c["args"]`，`gemv_fp8_loads`，`load_x8`，`stage_wqkv`，单 tile／多 tile 调用顺序。
- [gfx1250 reference_projection.py](../mono_test_origin/mono1250/kernels/reference_projection.py)：`_weight_step`、`reference_fp8_loads`、`reference_fp8_matrices_c1`、`stage_wqkv_c1` 与 `projection`。
- [gfx1250 dims.py](../mono_test_origin/mono1250/kernels/dims.py)：本例 HIDDEN=5120 等维度。
- [gfx1250 reference_sync.py](../mono_test_origin/mono1250/kernels/reference_sync.py)：tag、`put` 的成对 payload/tag 布局、作用域与诊断。
- [通用 device/sync.py](../atom/mono/device/sync.py)：`Addr`、mailbox 与计划访问记录相关接口。
- [外部 ASM 调用契约 RFC](AMDGPU_EXTERNAL_ASM_CALL_CONTRACT_RFC.zh-CN.md)：完整需求、寄存器契约与严格策略。
- [LLVM 原型说明](../llvm_asm_contract/README.zh-CN.md)、[FlyDSL 适配器](../llvm_asm_contract/flydsl_adapter.py)：实际已实现接口和当前限制。
- [已有三种接入方式比较](ASM_MONO_INTEGRATION.zh-CN.md)：标准 ABI、调用点 regmask 和 inline ASM 路径的对照。

本次仅修订设计文档，没有改写 Mono、ASM 或 LLVM 代码，也没有编译或运行新的 GPU 测试。
