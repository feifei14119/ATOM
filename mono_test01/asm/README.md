# dq_convert 的 low-context 设备接口

原始文件为 [dq_convert.original.s](dq_convert.original.s)，来自
`../mono_test10/asm/dq_convert.original.s`（相对于本测试根目录），最初来源是
`mono_read/mono_test1/atom` 的 gfx1250 `fmha_bwd_hd64_dq_convert_bf16`。
SHA256：`4050f8e1eacf2463c98adeb8f2aeee2ca93e2792de3a43e58088cbd36a05a711`。

[dq_convert.lowctx.s](dq_convert.lowctx.s) 是单独保留的适配版本。
`prepare.py --source-only` 可复现它，不调用编译器。

## 入口、返回和保持约定

```cpp
void mono_dq_convert_lowctx(const DqConvertArgs* args, unsigned linear_tid);
```

| 值/状态 | 位置或约束 |
| --- | --- |
| args | v0:v1，统一的 generic/global GPU 地址 |
| linear_tid | v2；本例为 1D CTA 的 threadIdx.x |
| 返回地址 | s30:s31；最终 `s_setpc_b64 s[30:31]` |
| lane | 函数入口由 `linear_tid & 31` 生成到 v0 |
| wave | 函数入口由 `readfirstlane(linear_tid) >> 5` 生成到 s24 |
| 参数表地址 | 入口 `v_readfirstlane_b32` 从 v0:v1 生成 s0:s1 |
| grid | 使用虚拟 x/y/z=0；task 已体现在指针与参数记录中 |
| 保持的 VGPR | v40～v47、v56～v63 |
| 保持的 SGPR | s30～s39；含 RA/SP/FP/BP |
| EXEC | 全 wave32 进入/退出；只允许整 CTA 统一调用 |
| MODE | 保存并恢复低 8 位；运算期间低 8 位为 0xc0 |
| VGPR bank | 普通设备调用进入 bank 0；函数不修改 bank 位 |
| CTA | 128/256 threads；本 Mono 单测固定 256 |

参数占用普通设备 ABI 的位置，但保持集合是自定义的，必须运行 `callsite_regmask.py`。
不读取 kernarg 硬件入口寄存器或 TTMP group/wave ID。wave≥4 在修改 MODE 前直接返回。

原始 s30～s38 重命名为 s40～s48；原始 v40～v45 重命名为 v64～v69。
净写集合：s0～s29、s40～s48；v0、v4～v39、v64～v69；SCC 和输出内存。
EXEC 只在内部临时改变，返回 full；MODE 恢复；VCC/M0/TTMP 不写。
所有保留 GPR 都不被改写，所以没有 GPR 保存/恢复 prologue，没有 scratch/private 帧。
返回地址始终留在 s30:s31。

## 原始指令的其他改写

- 原 `s1 &= 0xffff` 改为等长度 NOP，保留普通参数记录指针的高位。
- 原 v0 的 lane 提取由设备入口桥接完成，该原指令改为 NOP。
- 读取 TTMP 的 group x/y/z 改为 0，wave 提取由入口桥接完成。
- 移除独立 kernel 的 descriptor/metadata 与 `s_endpgm`，生成普通函数符号及 `.size`。
- 添加入口/出口等待、MODE 保存恢复、wave≥4 退出和设备函数 return。
- 除这些改写及寄存器重命名，FP32→BF16 转换和 tile 访存算法保持原样。

独立 `.co` 是 ET_REL 可链接对象，不能用 `hipModuleLaunchKernel` 启动。函数公开资源
下限符号：VGPR=70、编号 SGPR=49、LDS/private/AGPR/named barriers=0。
调用方空资源声明和最终资源检查配合这些信息；ELF 链接本身不能替代资源核对。

## 240 字节参数记录

结构定义见 [dq_convert_args.h](dq_convert_args.h)。所有 reserved 字段为 0，stride 为字节。

| 偏移 | 字段 | 本单测值 |
| --- | --- | --- |
| 0x00 | ptr_dq_acc | 本任务 packed FP32 tile 地址 |
| 0x10 | ptr_dq | 本任务 row-major BF16 tile 地址 |
| 0x20 / 0x30 | Hs_dq_acc / BAs_dq_acc | 16384，各 u64 |
| 0x40 | Seqs_dq_acc | 256，u32 |
| 0x50 / 0x60 | Hs_dq / BAs_dq | 8192，各 u64 |
| 0x70 | Seqs_dq | 128，u32 |
| 0x80 / 0x90 | seqlen_q / head_dim | 64，各 u32 |
| 0xa0 / 0xb0 | ptr_qseq / ptr_qseq_padded | 0 |
| 0xc0 | max_seqlen_dq | 64 |
| 0xd0 / 0xe0 | nsplit / split_stride | 0 |

112 个任务使用独立记录；调用地址 `dq_args + task*240`。每任务一个 16 KiB 输入、
8 KiB 输出，两侧均有 256 字节独立 guard，并且所有 workspace 为 uncached GPU 内存。
由于原始 buffer descriptor 的地址位掩码，host 会拒绝超出其 53-bit 范围的 tile 指针。

逻辑输入 `[r,c]` 对应 packed 输入：

```text
sr = 16*(r//16) + 8*((c//16)%2) + r%8
sc = 32*(c//32) + 16*((r//8)%2) + c%16
packed[sr*64+sc] = logical[r*64+c]
```

WQKV 的 16 个有效值放在 row0/col0～15，对应 packed 的前 16 个元素；其余元素由
host 填充随 task/seed 变化的数据。有效槽先填 NaN，必须由 GPU WQKV 覆盖。
全 CTA 在调用前/后等待并同步，之后读取 row-major BF16 前 16 项继续发布 QKV。
完整 tile 的 CPU BF16 逐位检查与所有 guard 检查沿用 `mono_test10`。
