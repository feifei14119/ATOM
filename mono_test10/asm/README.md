# dq_convert 的原始 ASM 与 inline 适配

来源：`/home/feifei/repo/ATOM/mono_read/mono_test1/atom`。本目录保留：

- `dq_convert.original.s`：原始独立 kernel，含 kernel descriptor/metadata，未改动。
- `dq_convert.inline.s`：可提取进 Mono 的指令片段，无独立 kernel descriptor。
- `dq_convert_args.h`、`dq_convert_inline.h`：原 C++ 参数布局及 clobber 声明，作为接口对照。

原件 SHA-256：`4050f8e1eacf2463c98adeb8f2aeee2ca93e2792de3a43e58088cbd36a05a711`。

实际编译器可见边界在 [dq_inline.py](../mono1250/kernels/dq_inline.py)。它使用与该 header 相同的三个只读固定输入：

| 输入 | 固定寄存器 | 来源 |
| --- | --- | --- |
| 240 字节参数块的 GPU 全局地址 | `s0:s1` | `dq_args + task * 240`，readfirstlane 成 wave-uniform 值 |
| lane | `v0` | `tid & 31` |
| CTA 内 wave ID | `s24` | `readfirstlane(tid) >> 5` |

净 clobber 为 `s2–s23, s25–s29, s40–s48, v4–v45, SCC, memory`。`s0:s1/s24/v0` 只读，不重复列入 clobber。特殊状态约束：完整 wave32 EXEC 进入/退出；MODE 低 8 位在 `.s` 内保存/恢复；VCC、M0、TTMP、`s30–s39` 和 VGPR bank 字段不被该片段改写。

适配保留了原有计算体，主要改动如下：

1. 参数指针来自普通 global 内存，删除原 kernarg 高位截断。
2. lane/wave 由外层传入，不再从独立 kernel 启动状态读取。
3. 原 workgroup x/y/z 改为 0；每个任务用独立指针表示自己的 tile。
4. `s30–s38` 重命名为 `s40–s48`，避开当前 LLVM 的栈/返回地址相关寄存器。
5. 加入前后等待、wave>=4 跳过分支、MODE 低 8 位的保存/恢复。
6. 删除末尾 `s_endpgm`，执行完落入 Mono 的后续代码。

输入仍使用原供应方布局。若逻辑输出是 `X[r,c]`，应将其 FP32 输入写到：

```text
sr = 16*(r//16) + 8*((c//16)%2) + r%8
sc = 32*(c//32) + 16*((r//8)%2) + c%16
packed[sr*64 + sc] = X[r,c]
```

参数仍为原 240 字节布局，保留字段全部为 0；stride 单位是字节：

| Offset | 字段 | 本单测值 |
| --- | --- | --- |
| `0x00` | `ptr_dq_acc`，u64 | 当前 task 的 packed FP32 tile 地址 |
| `0x10` | `ptr_dq`，u64 | 当前 task 的 BF16 tile 地址 |
| `0x20/0x30` | `Hs_dq_acc/BAs_dq_acc`，u64 | 16384 |
| `0x40` | `Seqs_dq_acc`，u32 | 256 |
| `0x50/0x60` | `Hs_dq/BAs_dq`，u64 | 8192 |
| `0x70` | `Seqs_dq`，u32 | 128 |
| `0x80/0x90/0xc0` | `seqlen_q/head_dim/max_seqlen_dq`，u32 | 64 |
| `0xa0/0xb0` | 序列指针，u64 | 0 |
| `0xd0/0xe0` | `nsplit/split_stride`，u32 | 0 |

独立生成修改后的汇编（不编译、不运行）：

```bash
python3 asm/prepare.py --source-only
```

目标机器上仅构建片段（不运行 GPU）：

```bash
python3 asm/prepare.py --llvm-bin /opt/rocm/llvm/bin
```

正常使用直接运行上层 `./run.sh`，它会执行这一步。生成的 `.co`、`.inc`、原始汇编往返对象及契约均放在 `../build/asm/`。`dq_convert.inline.co` 是 ET_REL 提取对象，既不单独 launch，也不作为设备函数链接。

本次沿用已有适配器的 SGPR 重命名和入口/出口修改；新增工作是把其完整 `.long` 和 clobber 接到实际 FlyDSL Mono 中。旧目录的编译检查结果不代表当前新 Mono 已编译或真机通过。
