# AITER gfx1250 二进制接入 ATOM Mono：最小流程验证方案

本文给出下一次实施的具体步骤，采用已经在 `mono_test` 验证过的 **编译器可见边界 + 固定保存集合 + 普通分支** 方法。目标是验证一个真实 AITER `.co` 能在 ATOM Mono 中执行并返回后继阶段，不做性能优化。

**选定二进制：`fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co`。选定替换点：PR #2908 的 target 6 行 K1，`stage_wqkv()` 输出的 BF16 舍入子步骤。** WQKV 矩阵乘仍由原实现完成，转换后的结果通过原 mailbox 交给后面的 Q/KV norm、RoPE 和 Q projection。

这是一个真实计算子步骤的替换，不是整段 WQKV GEMM、attention 或整个 K1 的替换。该二进制虽归属于 backward 目录，但独立指令体只做 FP32→BF16 转换与布局整理，不需要反向传播输入、权重、softmax 或梯度计算。它是本地 gfx1250 目录中最小的 `.co`，适合先打通流程。

## 1. 版本、证据与完成范围

| 项目 | 本次核对结果 |
| --- | --- |
| 阅读日期 | 2026-11-09 |
| ATOM PR | [ROCm/ATOM #2908](https://github.com/ROCm/ATOM/pull/2908) |
| 本文固定的 PR head | `7c925f72b22ee6a815fd6d63734bbcff5fa72a08` |
| PR 本地源码快照 | `/tmp/atom-pr2908-7c925f72/`，供本次阅读；实施时建立正式 checkout |
| 当前 ATOM 工作树 | `1d37f866` 对应的本地主线，没有 PR 的 `mono/gfx1250/` 目录 |
| AITER 本地版本 | `a0c4b69c146d94e393984bbe553b704e8c89a5e4` |
| AITER kernel 路径 | `/home/feifei/repo/aiter/hsa/gfx1250/fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co` |
| 该文件 SHA-256 | `1784adcc12b4c43a0ce49b12033abff49ab01e84d0c96b2c98b8cd79ec1d00b2` |
| 本机工具 | ROCm 7.2 的 LLVM，可识别 gfx1250 指令与 ELF |
| 本机 GPU | gfx1100 / gfx1036，没有 gfx1250 |

本方案初稿完成了候选文件筛选、ELF/metadata/反汇编阅读、host 参数结构核对、PR 调用链定位，以及 4096 个元素的转换地址置换检查。后续已在 [atom/](atom/README.md) 完成算子侧准备：原版完整汇编往返、入口/出口适配及新的 `dq_convert.mono.co`，导出 1576 B 的 `mono_dq_convert_stage`。**真实 ATOM 主体中的编译器边界接入尚未实施，也尚未在 gfx1250 上运行。** 之前的 [compiler_boundary 实验](COMPILER_BOUNDARY_EXPERIMENT.md) 是 gfx1100 验证，不能作为本方案的 gfx1250 运行证据。

本文按已有固定快照制定；本次 GitHub API 重读受到 rate limit，未据此宣称 PR 当前 head 仍未变化。所有 PR 源码链接固定到上述 commit。

## 2. 为什么选这个 kernel

本地 `hsa/gfx1250` 包含 117 个 `.co`，另有 CSV 索引；该目录没有这些算子的汇编源文件。选择非 group、非 deterministic 的 hd64 转换版本，可避开 sequence-prefix、split fold、量化 scale、矩阵乘和 LDS 同步协议。

| 实际二进制性质 | 本次静态核对 |
| --- | --- |
| 文件大小 | 5936 B |
| kernel 符号 | `_ZN5aiter29fmha_bwd_hd64_dq_convert_bf16E` |
| `.text` | 虚拟地址 `0x1900`，文件偏移 `0x900`，段内 section 大小 2048 B |
| 函数符号 `st_size` | **0**，不能按符号 size 直接提取 |
| 最终退出 | `0x1ef4` 的一条 `s_endpgm`；之后是 `s_code_end` 填充 |
| 有效指令体 | 含退出 1528 B / 292 条指令；去掉退出 1524 B |
| 去掉退出的原始指令体 SHA-256 | `d758be8e2e0f5e12990f854466bcc0cb33fe1a3643036b2260b468893da016be` |
| VGPR / SGPR metadata | 46 / 48；这是供应方资源声明，不是主体保存清单 |
| LDS / private | 0 / 0 |
| wave / block | wave32；host 实际 launch 128 线程，metadata 最大 block 128 |
| kernarg | 240 B，字段按 16 B 槽排列，部分字段自身是 64 位 |
| 内部控制流 | 没有 branch、call、提前退出；有 EXEC 掩码切换 |
| 同步与访存 | 没有 CTA barrier、LDS、TDM、WMMA；buffer load/store 与标量参数 load |
| 重定位 | 无 |
| 特殊寄存器 | 读取 TTMP7/8/9，不写 TTMP；修改 EXEC/SCC 等状态 |
| 转换指令 | 16 条 `v_cvt_pk_bf16_f32`；没有额外乘 scale 的浮点运算 |

**需要处理的差异仍有三个：输入布局置换、供应方网格编号、128/256 线程差异。** 这些差异都能局限在一个小适配器中，避免首先接触大 GEMM 的 preshuffle、FP8/FP4 scale 和 tensor descriptor。

参考：[AITER CSV][aiter_csv]、[host 参数结构][aiter_args]、[host 实际 launch][aiter_launch]。

## 3. 固定最小 ATOM 范围

第一版只接受下面的构建条件；其他条件使用原实现：

```text
target 路径，tokens=6，TP=4
fold=False，feeds_index=False，aux=False
tok_par=False，index_fp4=False，kv_fp8=False
timeline=False，diag_off=-1
grid=256 CTAs，block=256 threads，wave32
```

`tokens=6` 是 1 请求、5 draft token 的 target verification 宽度。先在独立 harness 构建这个 K1 key，使用合成数据或捕获的输入；进入 runner 后，只对满足条件的 layer key 启用实验。记录命中的 key 和实际边界执行次数；若所用模型没有这个完整 key 组合，就先以独立真实 K1 harness 验收，不能把始终走原实现的 runner 结果算作接入成功。

实际调用链：

```text
dspark_runner.py::_rows_build(s=6)
  → dspark_dynamic_k1.py::build_dspark_k1(key)
  → attn_pre 的 k1.wqkv_a 分派
  → stage_wqkv(c, task, ops, t0=0, n=6)
```

该配置中 `ROWS=16`，一个 WQKV task 输出 `16*6=96` 个值，WQKV 共 112 个 task，每个参与 CTA 至多一个。原步骤见 [stage_wqkv][stage_wqkv]：

```python
reference_fp8_matrices_rows(matrix, HIDDEN, ops)
if c['tid'] < ROWS * n:
    row, tl = c['tid'] % ROWS, c['tid'] // ROWS
    value = row_sum(c['red'], row, tl)
    c['put'](c['qkv'], (t0 + tl) * QKV_ROWS + task * ROWS + row,
             bf16_round(value))
gpu.barrier()
```

替换后：

```text
原 reference_fp8_matrices_rows / row_sum
    ↓ 将 96 个 FP32 值按供应方输入布局写入临时 global buffer
编译器可见的 ASM 边界
    ↓ 保存小集合；4 个物理 wave 执行 AITER 转换
恢复主体寄存器
    ↓ 从输出读取 BF16，精确扩展成 FP32
原 c['put'] 发布 QKV 的 payload + tag
    ↓
原 stage_gate、stage_qkv、stage_wqb 等后继继续执行
```

`bf16_round()` 的原语义是 FP32→BF16→FP32。因此接收 AITER 的 BF16 后必须扩展为 FP32，再传给原 `c['put']`；不能把 BF16 的 16 位编码直接当 FP32 mailbox payload。

边界要放在 `if tid < 96` **之外**。前面的 96 个线程生成数据，随后完整 256 线程 CTA 到达边界。WQKV task 的外层 `if task < WQKV_TASKS` 是 CTA uniform，可以保留。

参考：[builder 分流][runner_build]、[WQKV 分派与后继][wqkv_dispatch]、[bf16_round][bf16_round]。

## 4. 第一步：冻结输入并做独立算子基线

### 4.1 建立实验 checkout 与审计目录

下面是后续实施命令，本次没有执行 checkout 或改动生产代码：

```bash
cd /home/feifei/repo/ATOM
git fetch origin pull/2908/head
# 确认 FETCH_HEAD；按本文复现时固定到下述 commit。
git worktree add /home/feifei/repo/ATOM-pr2908-asm-poc \
  7c925f72b22ee6a815fd6d63734bbcff5fa72a08

mkdir -p /home/feifei/repo/ATOM/mono_test/gfx1250_aiter_poc/audit
```

在实验目录内复制供应方 `.co` 与对应 CSV 行，记录 AITER commit、文件 SHA、工具版本、完整 descriptor、metadata、符号表和反汇编。不要修改 `/home/feifei/repo/aiter/hsa/` 中的原件。

可直接用于审计的命令：

```bash
/opt/rocm/llvm/bin/llvm-readelf -h -S -s -r -n \
  /home/feifei/repo/aiter/hsa/gfx1250/fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co

/opt/rocm/llvm/bin/llvm-objdump -d --mcpu=gfx1250 \
  /home/feifei/repo/aiter/hsa/gfx1250/fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co
```

旧 `clobber/generate.py::extract()` **不能直接复用**：它固定 gfx1100，要求非零符号 size 和全寄存器 poison。新提取器只针对本文固定 SHA 的候选实现：在 `.text` 范围内从 entry 解码，验证唯一终止指令、连续指令边界、退出之后全部为允许的填充，并核对上述字节哈希。

### 4.2 第一次独立 launch 的参数

第一次固定一个完整的 `64×64` tile，grid `(1,1,1)`，block `(128,1,1)`，不测试尾部。input 是 4096 个 FP32，output 是 4096 个 BF16；两侧加 guard。

按 240 B 参数 buffer 显式写字段，全部 padding 清零：

| byte offset | 字段 | 大小 | 首次基线取值 |
| --- | --- | --- | --- |
| `0x00` | `ptr_dq_acc` | 8 | 已做布局置换的 FP32 input 指针 |
| `0x10` | `ptr_dq` | 8 | BF16 output 指针 |
| `0x20` | `Hs_dq_acc` | 8 | `64*64*4 = 16384` |
| `0x30` | `BAs_dq_acc` | 8 | 16384，batch/head 均为 1 |
| `0x40` | `Seqs_dq_acc` | 4 | `64*4 = 256` |
| `0x50` | `Hs_dq` | 8 | `64*64*2 = 8192` |
| `0x60` | `BAs_dq` | 8 | 8192 |
| `0x70` | `Seqs_dq` | 4 | `64*2 = 128` |
| `0x80` | `seqlen_q` | 4 | 64 |
| `0x90` | `head_dim` | 4 | 64 |
| `0xa0` | `ptr_qseq` | 8 | 0，非 group 版本 |
| `0xb0` | `ptr_qseq_padded` | 8 | 0 |
| `0xc0` | `max_seqlen_dq` | 4 | 64 |
| `0xd0` | `nsplit` | 4 | 0，按非 deterministic host 约定 |
| `0xe0` | `split_stride` | 4 | 0 |

这些 stride 是**字节数**。不能把一个紧凑的普通 C struct 当成此参数块；使用明确 padding/static_assert，或者 `bytearray(240)` + 指定 offset 的打包函数。没有 scale 参数，不需要填入 softmax scale。

独立基线使用 `hipModuleLoad`、上述 mangled symbol、`hipModuleLaunchKernel`。若使用 `HIP_LAUNCH_PARAM_BUFFER_POINTER/SIZE`，传递完整的 240 B buffer；host wrapper 可参考 AITER 的 `post_args`。

### 4.3 输入布局：必须先 pack

该 kernel 不是把相同线性位置的 FP32 直接写成 BF16。根据实际 load/store 地址，若希望输出为行主序 `Y[r,c]`，输入应这样放置：

```python
# 0 <= r,c < 64，固定 head_dim=64 / 完整 64 行 tile。
sr = 16 * (r // 16) + 8 * ((c // 16) % 2) + (r % 8)
sc = 32 * (c // 32) + 16 * ((r // 8) % 2) + (c % 16)
input_fp32[sr * 64 + sc] = X[r * 64 + c]
# 独立 launch 后，应得到：
# output_bf16[r * 64 + c] == bf16(X[r * 64 + c])
```

本次 CPU 检查已验证此映射覆盖 4096 个地址且一一对应。核对依据是每个 wave/lane 的 8 次 FP32×4 load 与 BF16×4 store，不是仅凭参数结构的 shape 注释猜测。

在 K1 中令 `X.flat[0:96]` 为 `row_sum` 输出，其余元素置零。仍执行完整 64×64 转换，接收时只读取前 96 个元素。这会多做工作，但省去了首次验证的尾部/OOB/部分行条件。

**阶段验收：** 在 gfx1250 上，完整 output 与 FP32→BF16 参考一致，guard 不变。使用非重复位置模式、正负数、舍入临界点、±0；NaN payload、次正规数等另核对原 K1 的 MODE 与转换语义。有限正常值通过后再扩大输入范围。

## 5. 第二步：将供应方入口改成可嵌入片段

### 5.1 不能直接使用 Mono 的网格编号

候选入口使用：

```asm
s_mov_b32 s2, ttmp9                  // 供应方 grid x
s_and_b32 s3, ttmp7, 0xffff          // 供应方 grid y
s_bfe_u32 s4, ttmp7, 0x100010        // 供应方 grid z
s_bfe_u32 s24, ttmp8, 0x50019        // waveIDinGroup
```

在 Mono 内，一个实际 CTA 负责某个 WQKV task，而适配器给它的输入/输出指针已经指向该 CTA 的独立 tile。因此供应方应该看到**虚拟 grid `(0,0,0)`**。否则物理 CTA 编号会再次参与 pointer offset，造成越界。

推荐仅替换前三处“把硬件 block id 装入普通 SGPR”的指令；保留原 TTMP，不通过写 TTMP 伪造硬件身份。

| entry 相对 offset | 必须匹配的原始指令字 | 适配结果 |
| --- | --- | --- |
| `0x64` | `BE820075` | `s_mov_b32 s2, 0`，仍为 4 B |
| `0x68` | `8B03FF73 0000FFFF` | `s_mov_b32 s3, 0` + 一条 4 B NOP，仍为 8 B |
| `0x70` | `9304FF73 00100010` | `s_mov_b32 s4, 0` + 一条 4 B NOP，仍为 8 B |
| `0x78` | `9318FF74 00050019` | 保留：从 TTMP8 读取真实 wave id |
| `0x5f4` | `BFB00000` | 去掉 kernel 退出，接入普通 branch 到 leave |

用 gfx1250 assembler 生成替换指令编码，先校验原字节再 patch；不手工猜机器码。除 3 处共 20 B 的入口映射外，1524 B 原始指令体应保持不变；出口单独处理，`s_code_end` 填充不带入片段。

entry 的 `s_version` 与指针 masking 先保留，使用匹配的 wave32/code-object/FP 模式。这里的修改属于入口和出口适配，不重新编译供应方转换算法。

### 5.2 128 线程片段如何放进 256 线程 Mono

保留 Mono 的 256 线程 descriptor。完整 8 个 wave 到达外层边界，只有物理 wave 0–3 执行供应方指令体，wave 4–7 跳过片段并到达公共 leave：

```text
8 waves：保存主体边界集合
  wave_id < 4：建立 v0=lane_id → 执行适配后的 AITER 片段
  wave_id >=4：跳过片段
8 waves：公共 leave / 等待 / 同步 / 恢复 / 继续
```

这里必须使用 **wave-uniform 标量条件分支**。不能把后 128 个线程 EXEC 清零后仍顺序执行片段，因为片段会反复 `s_mov_b32 exec_lo, -1`，重新激活那些线程。

此方案成立的关键是选中的片段没有 CTA barrier、LDS 或 CTA 范围 tensor 操作。若以后换成内部有 CTA barrier 的算子，不能继续套用“只运行半个 CTA”。

## 6. 第三步：增加编译器可见边界并约束寄存器

### 6.1 优先将完整适配片段直接放进 inline asm

之前的 gfx1100 demo 使用“先编译 marker，再替换最终汇编”。对本次只有 1.5 KB 的片段，可以更直接：在构造 FlyDSL kernel 时读取 `.co`，生成包含 enter、原始指令字、leave 的 **一整个** `llvm.inline_asm`，并同时声明固定输入和净 clobber。

```text
.co + patch manifest + Bank + LDS 布局
         ↓ 构建时生成 asm 字符串
FlyDSL llvm.inline_asm（完整片段 + 输入 + clobber）
         ↓ lowering 到 LLVM，随后寄存器分配
正常的 FlyDSL code-object 编译与 launcher
```

这种方式仍然使用“编译器可见边界”方法，省去了从 FlyDSL 私有 cache 中取出已加载 binary 再替换的步骤。PR 已使用 [llvm.inline_asm][inline_asm_example]，也有[显式内存副作用的等待边界][wait_example]；新增的是寄存器 clobber 和外层保存协议。

以下为**待实现的接口形状**，不是已经存在的 helper：

```python
llvm.inline_asm(
    None,
    [fx.Int64(stage_args_address).ir_value()],
    complete_boundary_asm,      # enter + .long payload + leave
    "{s[0:1]}," + net_clobbers,
    has_side_effects=True,
    is_align_stack=False,
    asm_dialect=llvm.AsmDialect.AD_ATT,
)
```

输入 `s[0:1]` 是 adapter 自己构造的 240 B 参数块地址，不是直接传 Mono 的 kernarg pointer。参数 load 指令可以从约定的 global 参数块读取；在独立嵌入 harness 中先验证这一用法与地址位宽。

供 stage 使用的 `v0=lane_id` 在保存后由适配器建立，不要求它在 LLVM 主体中一直承担此语义。固定 `s0:s1` 输入的搬运发生在边界前，LLVM 负责保护原先占用这些寄存器的其他活跃值。

需要逐层检查：MLIR 的操作有副作用；导出的 LLVM IR 有完整 clobber、`~{memory}` 和恰当的 convergence/no-duplication 约束；优化后片段没有丢失、复制或挪入不完整参与的区域。如果所安装的 MLIR binding 不能表达所需属性，增加一个小的 lowering/IR pass；不依赖未经核对的 Python 关键字。

`.long` 对调度器是不透明的。适配器必须自行处理内部指令依赖、访存等待和出口状态，不能假设 LLVM 会解析每个机器码字的读写。

### 6.2 保存集合与净 clobber

建议第一轮从下面的**候选预算**开始，实际是否足够以完整 K1 编译结果为准：

```text
主体跨边界普通集合：s0–s15、v0–v15
后端保留寄存器：按 gfx1250 工具链实际结果额外保护
特殊状态：入口/出口 full EXEC；VCC/SCC 声明 clobber；TTMP 不写
```

这一配置尚未在完整 K1 验证，不能承诺 16/16 一定放得下。候选算子不修改的大量 GPR，也可被边界**保守声明 clobber**，目的是让主体不要依赖它们跨边界存活。

数学关系是：

```text
R_keep = 固定普通集合 ∪ 必须保留的后端固定状态
net_clobber = 本构建允许分配的 GPR 集合 − R_keep
              + VCC/SCC + memory
```

整个片段对 `R_keep` 的净效果为原值保持，因为 enter/leave 会备份和恢复。供应方仍然可以覆盖其中的低编号寄存器。

必须额外审计 TTMP、MODE、M0、EXEC，以及目标后端涉及的其他隐式资源。这次供应方读取 TTMP 但不写，适配器也不得写；后续换成别的 `.co` 时重新审计。

### 6.3 gfx1250 的 VGPR 上界不能照搬 gfx1100

本地 LLVM 源码的 gfx1250/wave32 支持 **1024 个可寻址 VGPR**。旧脚本硬编码 `range(..., 256)`，不能据此认为 `v256` 以上不存在。

但也不应为一个小算子直接将 `v16–v1023` 全列为固定 clobber：固定 clobber 本身可能抬高最终 VGPR 资源声明，使 persistent Mono 的驻留检查失败。

推荐把两种约束分开实施：

1. 为整个**调用方编译函数**选择 `V_cap`。先记录原 K1 的资源，可从能承载原主体的上界开始；256 只是一个候选值。
2. 在 LLVM IR 中使用该工具链支持的 `"amdgpu-num-vgpr"="V_cap"` 约束分配上限；若前端不能传递该属性，在寄存器分配前的 IR lowering 中添加。
3. 只在允许的分配集合内，将 `R_keep` 之外的 GPR 声明 clobber。SGPR 同样依据实际 allocatable/reserved register set 生成，不从 metadata 的 48 推导。
4. 最终 MIR、汇编和 descriptor 必须确认：没有在范围外保留未保护值，没有后端额外引入的高寄存器、寄存器 bank 状态或 scratch。
5. 如果属性被工具链 clamp、忽略，或者固定 operand/后端临时值超出边界，构建失败；不能只看 IR 上有该字符串就算通过。

这里 `V_cap` 限制可分配的总范围，`R_keep` 限制跨边界存活的位置，两者不同。外部片段和适配器自身用到的寄存器也必须计入最终资源。供应方 metadata 为 46 VGPR，不代表最终 Mono 可以配置成 46。

本次还做了一个静态迁移探针：将旧 gfx1100 示例改用 gfx1250 编译后，得到非零 private（36 B），但 spill count 为 0。它不是完整 K1，也不是本方案的可运行实现；它说明检查时必须同时验证 **private segment 与 spill counts**，不能只看后两项。

## 7. 第四步：LDS 保存、硬件身份恢复与内存隔离

### 7.1 用 TTMP8 恢复原物理 wave，不使用 ticket 置换

本候选保留 TTMP8，其 `[29:25]` 是 waveIDinGroup。供应方本身就在使用这个字段，本地 LLVM 的 `lowerWaveID()` 也采用相同语义。

因此全部普通 GPR 都不可信时，leave 可以：

```asm
s_mov_b32 exec_lo, -1
s_bfe_u32 s_tmp, ttmp8, 0x50019
v_mbcnt_lo_u32_b32 v_lane, -1, 0
; original_tid = 32 * s_tmp + v_lane
; 根据 original_tid 访问原 wave/lane 的保存槽
```

这解决了上次 gfx1100 demo 的原 wave 身份问题。此保证来自**该 gfx1250 片段与适配器均不写 TTMP**，不是任意 ASM kernel 的普遍保证。Mono 的 block id 同样不从供应方改写后的 `s2` 获取。

### 7.2 为保存区保留固定 LDS prefix

供应方 LDS 为 0，但 Mono 原有 LDS 仍有其他活跃数据，不能拿 `red/xl/qxl` 随意覆盖。建议为完整 K1 分配一个单独的、固定 offset 的 LDS 保存区，并把原有 Smem/StageLds 置于其后。

一种布局：

```text
LDS prefix:
  每线程 VGPR 备份：256 * N_v * 4 B
  每物理 wave SGPR 备份：8 * N_s * 4 B
  必要的控制字段 / 对齐
随后：原 Smem 与 StageLds，仍由编译器产生正确地址
```

例如 `N_v=16,N_s=18` 时，寄存器槽共 16960 B，按 256 B 对齐为 17152 B。这只是预算示例；额外两个 SGPR 的具体编号必须由 gfx1250 后端审计确定，不把 gfx1100 的 `s32/s105` 无条件搬过来。

实现上可用一个统一的 LDS aggregate/slab，将保存区作为首成员。**要检查 lowering 后实际 LDS 基址和 offset，不能仅凭“第一个 allocate”推定物理 offset=0。** 若当前 allocator 无法保证常量布局，就在最小 lowering 中建立单一 LDS global 与显式 offset；固定布局确认后，再把恢复 offset 写入 asm 模板。

不依赖某个被供应方覆盖的 SGPR 保存唯一的 LDS 地址。entry/leave 从常量 prefix 地址和未改写的 TTMP8 重新定位槽位。

### 7.3 保存与恢复次序

1. 完整 CTA 到达，确认 full EXEC；等待前面生产的数据和矩阵操作完成。
2. 用集合外临时寄存器计算保存地址，不能覆盖尚未保存的 `R_keep`。
3. 保存每 lane 的 VGPR；每 wave 的 SGPR 由其 lane 0 保存，不把它们误当 CTA uniform。
4. 完成 LDS store、恢复 full EXEC，并进行需要的 CTA rendezvous。
5. wave 0–3 设置供应方 lane 输入并执行；wave 4–7 跳到共同 leave。
6. leave 显式完成供应方的 output store，再恢复原物理 wave/lane 对应的整个保存集合。
7. 全 CTA 同步后，原主体读取转换结果并发布 mailbox。

gfx1250 使用 `s_wait_loadcnt/storecnt/dscnt/kmcnt` 等等待；必要时还要处理 xcnt、tensorcnt 与 ALU hazard。不要把 gfx1100 的 `s_waitcnt vmcnt/lgkmcnt` 和 NOP 间隔原样搬过来。

该供应方在 `s_endpgm` 前只有 `s_wait_loadcnt 0`，**并没有显式 `s_wait_storecnt 0`**。原来结束 wave 的语义不能直接等同于融合后的继续执行；leave 必须补全输出写入完成和随后读取所需的同步、cache scope。

## 8. 第五步：临时 global buffer 与原 mailbox 对接

### 8.1 独立 harness 的 buffer

先使用显式传入的 `poc_context`，按物理 CTA 编号索引。一个 CTA 一个 32 KiB slot 足够用于第一次验证：

| slot byte range | 用途 |
| --- | --- |
| `[0x0000,0x4000)` | 64×64 FP32 packed input |
| `[0x4000,0x6000)` | 64×64 BF16 output |
| `[0x6000,0x6100)` | 240 B 参数块 + 对齐 |
| `[0x6100,0x8000)` | guards / 调试记录 / 预留 |

256 CTA 共 8 MiB global workspace。这个显式 global buffer 与 ELF private scratch 无关；它不会授权编译器产生 private spill。

stage 顺序：

1. CTA 合作清零整个 packed input；barrier 后由 `tid<96` 计算 `row_sum` 并写相应置换地址。
2. 一个线程填写参数块，其他线程不修改它；global store 完成后全 CTA 同步。
3. 全 CTA 进入唯一的编译器边界。供应方虚拟 grid 恒为零，指针已经基于该 CTA 的 slot。
4. 恢复后，原 `tid<96` 读取 output 的线性 `tid` 元素，BF16→FP32，然后调用原 `c['put']`。
5. 保留原阶段结束 barrier。下一个阶段和其他 CTA 通过原 tag/epoch 协议读取结果。

读取另一个 wave 写的 global output，须使用适当的 device scope/cache 策略；不能只加一个编译器 memory clobber 代替硬件可见性。K1 的 mailbox 发布顺序仍使用原 [reference_sync][sync] 实现。

### 8.2 进入真实 runner 时的最小改动

推荐复用 K1 现有 `scratch` **指针参数**，在全局 workspace 的尾部追加 POC 区域，保持 42 个 K1 kernel 参数不变。这里复用的是显式 global allocation，不是 private segment。

实施时：

- 在 host 原先计算 `max(k1,k2a,k2b,k2)` scratch bytes 的位置，计算 `poc_base=align_up(original_nbytes,256)`，追加 `256*32768` B；见 [runner allocation][runner_alloc]。
- 把 `poc_base/slot_bytes` 放入实验 build key，作为编译期布局常量传给新 builder。不能在每个 width 的 builder 中独立重算一个与 host 不同的尾部地址。
- 保留原所有 region offset；给新区域单独定义 layout，不把 raw input/output 当 tagged mailbox cell 放入原 `pair_layout`。
- 每次进入阶段都重新初始化 input 和参数块；跨 layer/step 不依赖旧 POC 数据。
- 保留 runner 的 step fence、workspace 生命周期和 capture 前分配；原 step_begin 已能清零整个扩大的 allocation。

不要挪用 `tl` 参数：此 PR 的 gfx1250 路径已经将它用于独立的 mHC square/state workspace。也不要简单增加第三个 step scratch tensor：现有 gfx1250 step-begin 有 `MAX_SCRATCH=2` 的约束。

## 9. 第六步：编译、资源、缓存与静态验收

### 9.1 需要保存的编译证据

每个 baseline/POC build 都保存：

```text
MLIR（inline asm 操作及副作用属性）
LLVM IR（输入、clobber、convergence、V_cap）
寄存器分配和后端变换后的 MIR
最终 .s / .o / .co
metadata + descriptor 解码
boundary live-in/live-out 报告
供应方原始字节与 patch manifest 的比对结果
```

FlyDSL 正常生成并加载最终 `.co`。`atom.mono.runtime.compile` 中的 `_code_object()`/`launcher_resources()` 可用于检查实际 artifact；它们是读取接口，不能当成“替换了 `_ir_text` 就会更新已加载 GPU module”的保证。

若使用完整 inline asm 的路线，主体、adapter 和原始 `.long` 一起进入正常 assembler/linker。必须仍核对最终资源，因为 `.long` 内的寄存器使用对前面的 compiler accounting 不可见；clobber 中没有涵盖的固定保留寄存器、适配器额外寄存器，需要显式资源约束或最终 descriptor 修正。不能只信 compiler 的局部估计。

### 9.2 保留现有 ATOM 门禁

对该窄 K1，验收至少包含：

```text
private_segment_fixed_size == 0
vgpr_spill_count == 0
sgpr_spill_count == 0
实际 HIP occupancy * device multiprocessor_count >= 256 CTAs
```

PR 的 [check_residency][residency] 对少数 48 行 K2 名称允许有限 SGPR lane spill；**这个例外不适用于本次 6 行 K1**。不能为让实验通过而删除资源或驻留断言。

完整 K1 具有分支和循环，旧 `compiler_boundary/audit.py` 的单基本块检查器不能直接用于它。要么导出 LLVM LiveIntervals/LivePhysRegs 在每个 inline-asm site 的报告，要么扩展为完整 CFG/alias/lane-aware 分析。重点检查所有后继路径的旧值，不是只搜汇编里出现过哪些寄存器。

如果小集合放不下：先将不必长驻的指针/任务字段存入显式 context，在后继重载/重算；其次增大 `R_keep` 并重新测 LDS/occupancy。`sched_barrier`、函数名、Python 字典 `c` 和 `@traced` 都不会自动阻止值跨边界存活。

### 9.3 缓存与唯一标签

已有源码 digest 不会自动覆盖仓库外的 AITER `.co`。新 build identity 至少纳入：

```text
供应方 SHA + patch manifest 版本 + Bank/后端保留集合
V_cap + LDS/global 布局 + 目标架构/工具链 + POC 开关
```

为实验 kernel 名称添加唯一 suffix，并将该身份传入实际 JIT cache key；不要只改日志名称。首次验收关闭 FlyDSL disk cache，之后还要验证 cache hit 运行的是同一个 POC binary。

inline asm 的局部标签必须按展开 site 唯一化，可使用 LLVM inline-asm 的 `${:uid}` 或构建器保证的唯一标签；在 LLVM 优化/复制后核对无重复定义。

### 9.4 二进制与分支检查

- 新片段只允许上述入口映射与最终退出发生变更，其余供应方字节逐字节比对。
- 每个嵌入位置都去掉供应方 `s_endpgm`，不得让物理 wave 提前终止 Mono。
- 新边界使用普通 `s_branch/s_cbranch_*`；没有设备函数 `s_swappc/s_setpc`。
- 检查最终分支范围及 assembler relocation；`.long` 的长度与真实 8/12 B 指令边界正确。
- TTMP 只读；保存前不破坏 `R_keep`，恢复后没有未声明 clobber。
- supplier input/output、LDS 保存区、Mono 原工作区互不重叠；descriptor 覆盖完整 kernel。

## 10. 第七步：按三个层级验证，逐层推进

### A. 原始供应方 `.co` 独立验证

128 线程、1 CTA、64×64 tile、正确 pack，检查完整 4096 个 BF16 与 guards。它确认参数和布局，尚不能证明 Mono 接入。

### B. 独立 256 线程 carrier 验证

用 LLVM/FlyDSL 主体构建 256 线程 carrier：

```text
生成有变化的 FP32 输入与跨边界标量/向量值
  → 同一个编译器边界（8 wave enter，4 wave supplier，8 wave leave）
  → 使用旧存活值和转换结果继续计算
  → 第二次边界，复用同一供应方 .co
  → 后继校验输出
```

测试 1、3、17、256 CTA，多次改变输入、CTA 标识和 seed。检查两个非末尾片段后的旧值、结果、guards 和保存区隔离。

调试变体可在供应方之后增加已声明的普通 GPR poison，再执行同一 leave，用于验证恢复确实依赖保存集合和未改写 TTMP；poison 必须排除本架构不允许任意写的保留/特殊状态，并计入资源。它不替代完整 K1 的活跃性检查。

负例至少包括：漏存一个实际活跃寄存器时 gate/test 失败；过小预算产生 private/spill 时拒绝；错误 pack 被完整元素比对发现；不同 CTA 的 context 不会串用。

### C. 替换真实 target-6 K1 的舍入子步骤

先构建两份相同 key 的 K1：baseline 与 POC，各使用独立 scratch、输出和 cache/ring buffers，从完全相同的输入状态启动。

比较：

1. WQKV 的 `QKV` payload 与 tag/epoch，96 个值/task，覆盖全部 112 个 task。
2. 后继 `QX8/QX8S`、`q_out`、KV ring，以及本 key 实际写入的 residual/gate 输出。
3. 原工作区边界、POC guard、重复 layer/step 后结果。
4. 最终 `.co` 的资源门禁和实际 256 CTA 驻留容量。

baseline 与 POC 必须单独初始化 mailbox epoch，不能让第二次运行读到第一次留下的 ready tag。先用 finite 输入要求舍入子步骤 bitwise 一致；特殊浮点输入依据实际转换语义单独报告。

该 key 关闭 token parallel/index，单 rank 的独立 K1 harness可使用适当的 mock peer 参数验证本地阶段；完整 runner 验证仍按 PR 的 TP=4 配置进行，不能把单 rank harness 当成整模型 TP 验证。

PR gfx1250 配置拒绝 `ATOM_MONO_CHECK/DEBUG/TIMELINE`，因此采用外部 A/B harness；不将这些开关设为 1 作为测试命令。先完成 K1 验收，整模型解码和其他宽度作为后续扩展。

**最小完成标准：** A、B、C 三层通过，最终 K1 实际包含选定 AITER 的适配指令体，原 `bf16_round(value)` 在实验路径已被替换，后继 Q/KV 阶段正确消费其结果，资源/驻留门禁通过。仅独立 launch 成功或仅插入一个未被使用的输出，不算完成接入流程。

## 11. 建议文件与改动清单

下面是完整实施时建议的文件组织。算子侧的提取、适配、汇编与静态检查已先放在 [atom/](atom/README.md)；尚未按此完整目录实施 carrier、编译器边界或 ATOM 生产修改。

| 建议位置 | 工作内容 |
| --- | --- |
| `mono_test/gfx1250_aiter_poc/vendor/` | 固定供应方 `.co`、哈希与原始 metadata |
| `.../extract.py` | size=0 的受限提取、唯一出口检查、原始指令字审计 |
| `.../contract.json` | 架构、block、参数 offset、TTMP/特殊状态、资源与布局契约 |
| `.../patch_manifest.json` | 3 处入口改写及出口处理的原字节/新字节 |
| `.../pack.py` | 64×64 输入置换及 CPU 地址一致性检查 |
| `.../standalone.cpp` | 不依赖 attention wrapper 的原始 `.co` launch 基线 |
| `.../carrier.py` | 256 线程、两次非末尾边界的独立验证 |
| `.../verify.py` | 保存集合、字节、资源、分支与结果检查 |
| PR `gfx1250/kernels/binary_boundary.py` | 基于 contract 生成 inline asm 与固定保存布局 |
| PR `gfx1250/kernels/dspark_dynamic_k1.py` | 仅选定 key 替换 stage_wqkv 舍入、增加 LDS prefix |
| PR `gfx1250/dspark_runner.py` | 实验 builder 路由、global tail allocation 与 build identity |
| 对应 build-key/source-digest 路径 | 纳入外部 binary 与适配协议的哈希 |
| 外部 K1 A/B harness | 实际 QKV mailbox、后继输出和驻留验收 |

实施顺序固定为：**供应方独立基线 → 256 线程 carrier → 真实 K1 子步骤替换 → 原 runtime/caching 路径验证。** 先保持完整 tile、单 key、固定 SHA，避免同时引入 tail 支持、多个算子、多种布局和宽度分流。

本方案会增加 global 往返、LDS 保存、同步和转换填充工作。它的价值是用一个真实小 `.co` 验证接口与编译流程；性能优劣需要后续计时。流程通过后，再考虑换成语义匹配的大算子、减少保存集合、优化存储布局与使用更紧凑的 tile。

[aiter_csv]: https://github.com/ROCm/aiter/blob/a0c4b69c146d94e393984bbe553b704e8c89a5e4/hsa/gfx1250/fmha_v3_bwd/fmha_bwd_dq_convert.csv
[aiter_args]: https://github.com/ROCm/aiter/blob/a0c4b69c146d94e393984bbe553b704e8c89a5e4/csrc/include/mha_bwd.h#L309
[aiter_launch]: https://github.com/ROCm/aiter/blob/a0c4b69c146d94e393984bbe553b704e8c89a5e4/csrc/cpp_itfs/mha_bwd.cu#L730
[stage_wqkv]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L141
[runner_build]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runner.py#L436
[wqkv_dispatch]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L689
[bf16_round]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/mono/device/ops.py#L427
[inline_asm_example]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_sync.py#L268
[wait_example]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_mhtjstest_native_support.py#L21
[sync]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/reference_sync.py
[runner_alloc]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runner.py#L554
[residency]: https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runtime.py#L29
