# gfx1250 dq_convert → ATOM Mono：普通设备函数 ABI 接入步骤

本文使用普通设备函数调用：允许 `s_swappc_b64` / `s_setpc_b64` 和 scratch，不添加调用方 VGPR/SGPR 上限，不修改 call-preserved regmask，不嵌入 `.long`，不修改最终二进制中的算子指令。

本次交付范围是供应方适配：原始 `.s` → 可调用的设备函数 `.s` → 可重定位 `.co`，以及函数声明/参数结构。真实 ATOM 调用点、FlyDSL 编译链接扩展和 gfx1250 GPU 验证属于本文后续步骤，不能把汇编成功等同于完成模型接入。

## 1. 固定输入和替换范围

- 输入：[dq_convert.original.s](dq_convert.original.s)，保留原件。
- 原始汇编 SHA-256：`4050f8e1eacf2463c98adeb8f2aeee2ca93e2792de3a43e58088cbd36a05a711`。
- 原始 AITER 二进制：`hsa/gfx1250/fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co`。
- 原始二进制 SHA-256：`1784adcc12b4c43a0ce49b12033abff49ab01e84d0c96b2c98b8cd79ec1d00b2`。
- 原始入口：`_ZN5aiter29fmha_bwd_hd64_dq_convert_bf16E`。
- 工具：ROCm 7.2，clang `7b800a19466229b8479a78de19143dc33c3ab9b5`，目标 gfx1250 / wave32 / code object v6。
- 本机 GPU 为 gfx1100 和 gfx1036，不能执行此 gfx1250 目标。

原始算子用 128 线程完成 FP32→BF16 和布局整理，无 LDS、CTA barrier、内部调用或 scratch。第一版固定完整 `64×64` tile，所有 stride 使用字节，虚拟 block id 固定为 `(0,0,0)`。

ATOM 沿用 [PR #2908 固定版本](https://github.com/ROCm/ATOM/tree/7c925f72b22ee6a815fd6d63734bbcff5fa72a08) 的验证点：`atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py::stage_wqkv()` 中 `bf16_round(value)` 子步骤。它不是整个 WQKV 矩阵乘或 attention 的替代物。首次固定 target `tokens=6, TP=4`，关闭 fold/feeds_index/aux/tok_par/index_fp4/kv_fp8/timeline，`diag_off=-1`；256 CTA、每 CTA 256 线程。

## 2. 为什么不能只修改退出指令

原始入口依赖 kernel ABI：`s0:s1` 是 kernarg 指针，`v0` 是工作项标识，TTMP 提供实际网格编号。普通设备函数的显式指针参数则由本版编译器放到 `v0:v1`，第二个 uint32 参数放到 `v2`。

原指令体还写入 `s30:s31`（普通调用的返回地址）、`s32`（栈指针）、`s33:s38` 和 `v40:v45`。这些寄存器属于默认 ABI 的保持集合。LLVM 不会解析外部 ASM 来发现这些覆盖，供应方必须恢复它们。

本适配器不修改默认 ABI。原体没有使用 `s5`、`s40:s47` 或 `v48:v54`，而这些是本 ABI 允许被调用方破坏的寄存器，因此直接用它们备份，比本小算子另建 scratch 栈帧更简单。此选择不是对 Mono 调用方的寄存器限制。

| 保存对象 | 备份位置 | 返回前操作 |
| --- | --- | --- |
| `s30:s31` | `s40:s41` | 恢复返回地址 |
| `s32:s33` | `s42:s43` | 恢复 SP/FP |
| `s34:s35` | `s44:s45` | 恢复 |
| `s36:s37` | `s46:s47` | 恢复 |
| `s38` | `s5` | 恢复 |
| `v40:v45` | `v48:v53`，逐 lane | 恢复 |
| MODE 的低 8 位 | `v54`，各 lane 同值 | 恢复 FP 舍入和 denorm 模式 |

`s39`、`v46:v47` 及其余 callee-saved 寄存器原样保留。适配器是叶函数，执行原体期间不会使用被临时覆盖的 SP 访问 scratch，也不会调用其他函数。若以后更换会写入备份区域的原体，必须重新设计保存；不能直接复用本表。

## 3. 新的设备函数接口

声明和参数结构见 [dq_convert_api.h](dq_convert_api.h)：

```cpp
extern "C" __device__ void mono_dq_convert_device(
    const DqConvertArgs* args, unsigned linear_tid);
```

- `args` 指向 GPU global 中的只读、至少 16 字节对齐的 240 B 参数块；同一 CTA 的所有线程传同一个指针。
- `linear_tid` 为一维 CTA 的 `threadIdx.x`，不是 blockIdx、任务编号或仅 lane id。
- 支持本方案的 block 128 或 256；完整 CTA 一致到达调用点，进入每个 wave 时 EXEC 必须全开。函数内部反复设置 full EXEC，因此不支持部分 wave 的条件调用。
- 默认设备 ABI；不要把声明标记为 kernel、readnone、readonly 或额外 inreg 参数。
- 函数是有副作用且 convergent 的调用。声明文件对 HIP 编译器加上相应属性；FlyDSL/MLIR 需要生成等价声明。
- gfx1250 普通调用边界按后端约定使用 VGPR bank 0。不能把任意 bank 状态下的原始跳转当作等价设备调用。

进入后，根据 `linear_tid >> 5` 做 wave-uniform 分支：wave 0–3 执行，wave 4–7 直接返回。函数内没有 CTA barrier，未计算的 waves 不会造成 barrier 缺员；完整 CTA 的汇合放在调用方。

## 4. 将原始 .s 改成设备函数

生成 [dq_convert.device.s](dq_convert.device.s)，按以下顺序处理：

1. 删除原 kernel symbol、`.amdhsa_kernel` descriptor、kernel metadata 和 `s_code_end` padding。新目标只定义 `mono_dq_convert_device` 普通函数，并给出正确 `.size`。
2. 加入入口等待，排空普通 load/store、LDS、标量 load 和寄存器依赖；调用方还需完成其自身 TDM/tensor 等异步协议。
3. 用 `v2` 的首 lane 得到 wave id；wave id ≥4 时通过原 `s30:s31` 返回。
4. 按上表保存 callee-saved 寄存器，并保存 MODE 低 8 位。运行供应方期间设置低 8 位为 `0xc0`，对应原 descriptor 的 round32=0、round16/64=0、denorm32=0、denorm16/64=3。不覆盖 MODE 其余位。
5. `v_readfirstlane` 将参数块地址 `v0:v1` 放到 `s0:s1`；由 `v2` 建立 lane id 和 wave id。原体 `s_and_b32 s1, s1, 0xffff` 是 kernarg 入口的高位处理，新接口传入普通 global 指针，因此将它替换为等长 NOP，保留完整地址。
6. 原体的三个 TTMP block id 读取改为 `s2=s3=s4=0`，因为输入/输出指针已经指向本 CTA 的独立 tile。
7. 原体对 TTMP wave id 的读取改为使用显式 `linear_tid` 的 wave id；不依赖 ATOM 的物理任务分配，不写 TTMP。
8. 保留转换和访存主体。原体最后的 `s_endpgm` 去掉，换为等待全部输出 store 完成的 epilogue。
9. 恢复 MODE、SGPR/VGPR，使用 `s_setpc_b64 s[30:31]` 返回。返回时 EXEC 全开，后续 Mono 阶段继续执行。
10. 记录函数资源下界：55 VGPR、48 个编号 SGPR、LDS 0、private 0。它是资源需求，不是限制调用方只能使用这些数量。

`prepare.py` 固定原始 SHA、检查预期指令和备份寄存器未被原体使用，生成适配汇编和资源清单。该脚本只改写供应方文件，不修改调用方或最终模块中的机器指令。

## 5. 汇编成可链接 .co

本目录的 `Makefile` 提供可复现入口：

```bash
cd /home/feifei/repo/ATOM/mono_test0/atom
make
make check  # host/device 头文件、ABI/字节/布局检查，以及 gfx1250 编译链接检查
```

核心命令：

```bash
python3 prepare.py
/opt/rocm/llvm/bin/clang++ --target=amdgcn-amd-amdhsa \
  -mcpu=gfx1250 -x assembler -c dq_convert.device.s -o dq_convert.device.co
/opt/rocm/llvm/bin/llvm-readelf -h -s -r dq_convert.device.co
/opt/rocm/llvm/bin/llvm-objdump --mcpu=gfx1250 -d dq_convert.device.co
```

`dq_convert.device.co` 是 **ET_REL**（可重定位目标，通常也可命名 `.o`），不是可 launch 的独立 HSA 模块。没有 `.kd` 和 kernel metadata 是正常的：最终 `mono_kernel` 的 descriptor/metadata 由调用方提供。

gfx1250 的工具通常将 PC 指令打印为 `s_get_pc_i64`、`s_swap_pc_i64`、`s_set_pc_i64`；这是本方案所说的 getpc/swappc/setpc 调用返回形式。当前汇编接受 `s_setpc_b64` 别名。

普通链接形式为：

```bash
/opt/rocm/llvm/bin/ld.lld -shared --no-undefined \
  mono_kernel.o dq_convert.device.co -o mono_kernel.co
```

输入两个对象必须同为 gfx1250、兼容 wave32/ABI/code-object 版本。不能和父目录 gfx1100 的 `build/mono_kernel.o` 链接，也不能直接把此函数当作父目录 `stage_sub_device` 使用：符号、参数和运算语义都不同。

## 6. 参数块与输入布局

参数结构在声明头文件中逐字段 padding，并对全部 offset、sizeof/alignof 做 static_assert。先在 host 创建 `DqConvertArgs args{}`，所有保留字段为零，再填以下内容并复制到 GPU global。

| 偏移 | 字段 | 字节数 | 完整 64×64 tile 的值 |
| --- | --- | --- | --- |
| 0x00 | ptr_dq_acc | 8 | 已 pack 的 FP32 tile 指针 |
| 0x10 | ptr_dq | 8 | BF16 tile 指针，使用 uint16_t 存储 |
| 0x20 | Hs_dq_acc | 8 | 16384 |
| 0x30 | BAs_dq_acc | 8 | 16384 |
| 0x40 | Seqs_dq_acc | 4 | 256 |
| 0x50 | Hs_dq | 8 | 8192 |
| 0x60 | BAs_dq | 8 | 8192 |
| 0x70 | Seqs_dq | 4 | 128 |
| 0x80 | seqlen_q | 4 | 64 |
| 0x90 | head_dim | 4 | 64 |
| 0xa0 | ptr_qseq | 8 | nullptr，当前变体不读取 |
| 0xb0 | ptr_qseq_padded | 8 | nullptr，当前变体不读取 |
| 0xc0 | max_seqlen_dq | 4 | 64，当前变体不读取 |
| 0xd0 | nsplit | 4 | 0，当前变体不读取 |
| 0xe0 | split_stride | 4 | 0，当前变体不读取 |

目标逻辑矩阵是 `X[r,c]`，输入必须按下面公式打包；输出才是行主序 BF16：

```cpp
unsigned sr = 16 * (r / 16) + 8 * ((c / 16) % 2) + r % 8;
unsigned sc = 32 * (c / 32) + 16 * ((r / 8) % 2) + c % 16;
packed[sr * 64 + sc] = X[r * 64 + c];
// 完成后：out_bf16[r * 64 + c] == bf16(X[r * 64 + c])
```

每个实际 CTA 有自己的 16 KiB input、8 KiB output 和 240 B 参数块，不得多个 CTA 共用同一个输出 tile。参数块由 host 预先构建，算子内只读，避免跨 wave 更新参数块产生标量 cache 一致性问题。

pack → call → consume 之间必须有正确的 global memory fence 和全 CTA barrier。函数只排空本 wave 的访存，不提供跨 CTA 发布，也不能替代 ATOM 原 mailbox 的 release/acquire 和 epoch 协议。

## 7. 编译器如何看到调用，如何生成最终资源

调用方仍由编译器管理跨调用活跃值。默认 ABI 可以使用标准 callee-saved 寄存器、scratch 或重计算，本方案不设置寄存器上限或零 spill 门禁。

正式接入需要在 FlyDSL/MLIR 中生成普通外部设备函数声明与真实 call，经过 LLVM 正常 lowering；不能只在最终 `.co` 中新增符号，也不能在 register allocation 之后才伪造调用。参数 lowering 必须和本接口一致：普通 C calling convention、generic pointer + i32，wave32 下使用 v0:v1 和 v2。

目标 LLVM IR 形状如下，省略其他 K1 参数和控制流；不是把函数声明改成 `amdgpu_kernel` 或把 pointer 加上 `inreg`：

```llvm
declare void @mono_dq_convert_device(ptr, i32) convergent
; %tile_args_global 的类型为 ptr addrspace(1)，同一个 CTA 内一致。
%tile_args = addrspacecast ptr addrspace(1) %tile_args_global to ptr
call void @mono_dq_convert_device(ptr %tile_args, i32 %linear_tid)
; 此后仍然是原 Mono 的汇合、读取结果和后续算子。
```

FlyDSL 的 Python builder 不会直接 include C++ 头文件；`dq_convert_api.h` 是 HIP/C++ 的可编译接口以及供 MLIR 端对照的布局契约。MLIR 端要建立等价的 `llvm.func`/`llvm.call` 和正确地址空间转换。接口不携带只读内存属性，因为设备函数会通过参数块中的指针写 output。

**普通 ELF 链接不会自动从手写 ASM 推导并合并 HSA kernel 资源。** 必须让最终 descriptor 和 metadata 同时覆盖：

```text
VGPR 至少 max(调用方需求, 55)
编号 SGPR 至少 max(调用方需求, 48)，另外正确处理 VCC 等保留寄存器
private / 动态栈覆盖调用方和完整 call graph，本供应方固定 frame 为 0
LDS 保留调用方需求，本供应方不额外使用 LDS
```

增加资源分配的下界不是给寄存器分配设置上限。不可仅修改 YAML 的 `.vgpr_count` 而漏改 `.amdhsa_next_free_vgpr` 对应的 descriptor，也不可仅修改 descriptor 而让 runtime 读取旧 metadata。

本机 ROCm 的调用方汇编含 `amdgpu.max_num_vgpr/sgpr` 等汇总表达式；小型链接检查在汇编成 `.o` 前把这些**资源常量**与 `resources.json` 取 max，并补全 named-barrier=0。此编译器生成的 YAML metadata 数量已提前求值，因此还要同步更新 `.vgpr_count/.sgpr_count`：本次检查调用方保留 VCC，SGPR 总数为 48+2=50。只改 `.set` 会留下旧的 metadata 值。该操作不改 call 指令和寄存器分配。正式实现应在编译进程的资源汇总/序列化阶段合并资源，避免依赖文本格式。

`atom/mono/runtime/compile.py` 读取的是已生成的 `gpu.binary`，这个时点太晚，不能在这里补做调用 lowering。应在生成 AMDGPU relocatable object 后、最终 HSA 链接/`gpu.binary` 序列化前加入 `dq_convert.device.co`。

## 8. 真正替换 ATOM 的最小子步骤

以下为尚待实施的生产接入步骤，不是本次已经修改的代码。

1. 使用固定 PR commit 建立独立 worktree，例如 `git worktree add ../ATOM-pr2908-dq-device 7c925f72b22ee6a815fd6d63734bbcff5fa72a08`，启用一个明确的实验 build key，不影响其他 kernel key。
2. 在 runner 中为每 CTA 分配上述临时 tile 和参数块，并把地址作为新参数传入 K1。将供应方 binary SHA、参数协议、目标架构和编译器版本加入构建缓存 key。
3. 定位 `stage_wqkv()` 原来的 `row_sum → bf16_round → c['put']`。保持 FP8 矩阵乘和 row_sum 不变。
4. 对 target n=6，一个 WQKV task 产生 16×6=96 个有效值。将它们放到逻辑 tile 的前 96 个位置，剩余 4000 个位置置零，再按上式 pack。
5. 完成 global 写入和 CTA 同步。把调用放在 `if tid < 96` **之外**，完整 256 线程调用 `mono_dq_convert_device(args_for_this_cta, tid)`。
6. 函数返回后，全 CTA 完成 global memory 可见性处理与 barrier，确保后 4 个 wave 不会提前消费前 4 个 wave 尚未写完的结果。
7. 仅前 96 个线程读取 BF16 结果，用 `uint32_t(bf16_bits) << 16` bitcast 为 FP32，恢复原 `bf16_round()` 的 FP32 返回语义。
8. 使用原来的 `c['put'](c['qkv'], 原索引, fp32_value)` 发布 payload/tag，保留后继阶段和原有 barrier。
9. 编译产生普通设备调用并链接新目标，合并资源。验证最终模块包含目标函数且 call relocation 已解析，结果确实由新算子参与计算。
10. 在真实 gfx1250 上比较 baseline 与适配路径的 QKV mailbox 和后续 K1 输出；完整 runner 再按 TP=4 配置验证。

## 9. scratch 与 ATOM 现有门禁

用户当前方案允许 scratch，因此此目录不因生成 scratch 而失败。但固定 PR 的 `gfx1250/dspark_runtime.py::check_residency()` 明确断言 scratch 和 VGPR spill 为 0，只有部分 K2 的 SGPR lane spill 有特殊例外。

真实 K1 如果因普通调用生成 scratch，必须为**显式实验 key**制定允许 scratch 的验证路径，保留资源记录和实际 HIP 驻留检查；不得在整个生产配置里静默删除门禁。如果产物恰好没有 scratch，则可以保持原门禁。

无论是否允许 scratch，持久化 Mono 仍需满足 block=256 时 `active_blocks_per_MP * MP_count >= 256`。无法同时驻留的配置不能靠放宽 scratch 检查解决，应调整实验网格及调度设计后重新验证。

## 10. 验证顺序与完成标准

本次可以做的静态检查：

- 原件哈希不变；重汇编原始函数的机器码与行尾原始指令字一致。
- 新函数是有大小的 ET_REL 符号，没有 kernel descriptor 或 `s_endpgm`，能正常汇编。
- 原体除参数指针处理和入口 id 映射外保持指令编码；保存区和原体实际寄存器不重叠。
- SGPR/VGPR 保持集合、返回地址、SP、MODE 的保存/恢复成对且路径完整。
- 用当前 gfx1250 编译器编译声明的真实调用，核对参数寄存器、默认 regmask、call/return 和资源合并，再链接为 ET_DYN。
- CPU 检查 4096 个元素的 pack/load/store 地址映射完整且无重复。

后续必须在 gfx1250 上做：

1. 单 CTA，完整 tile，所有 BF16 位模式与参考匹配，输入/输出 guard 不变。
2. 256 线程，多 CTA，各自独立 tile，包含调用之后继续计算与第二次调用，检查跨调用上下文和 MODE 恢复。
3. 真实 K1 子步骤 A/B；不同 epoch、不共享旧 ready tag，比较 mailbox 和后继输出。
4. 检查最终 descriptor、scratch、占用率和 persistent grid 驻留；检查模块缓存重新编译确实生效。
5. 初期用有限正常值与 ±0；再验证舍入边界、NaN、Inf 和次正规数。原始供应方和 ATOM 的特殊值语义可能不同，不能只凭都是 BF16 就假定完全等价。

只有这些 GPU 和 ATOM 验收通过后，才能称为“已经替换了 ATOM Mono 的子步骤”。本目录的 `.co` 是适配好的链接输入，不是已经完成替换的 ATOM 最终模块。

## 11. 参考

- [当前目录的 ABI 中文参考](../AMDGPU_DEVICE_FUNCTION_ABI.zh-CN.md)。
- [LLVM 普通设备函数 ABI](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-function-call-convention-non-kernel-functions)；官方文档部分历史内容仍需结合当前编译器核对。
- [固定 PR 的 stage_wqkv](https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/kernels/dspark_dynamic_k1.py#L141)。
- [固定 PR 的资源/驻留检查](https://github.com/ROCm/ATOM/blob/7c925f72b22ee6a815fd6d63734bbcff5fa72a08/atom/models/deepseek_v41/mono/gfx1250/dspark_runtime.py#L29)。
