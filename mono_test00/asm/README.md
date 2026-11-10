# 供应方片段与标准 ABI 包装器

- `dq_convert.original.s`：保留供应方独立 kernel，SHA256 为
  `4050f8e1eacf2463c98adeb8f2aeee2ca93e2792de3a43e58088cbd36a05a711`。
- `dq_convert.inline.s`：继承 test10 的适配指令。s30～s38 重命名为 s40～s48，
  将独立 kernel 的参数/grid/wave 入口改为显式输入，去掉 `s_endpgm` 和 descriptor。
  EXEC/MODE 在片段内部恢复，片段末尾自然继续执行包装器的编译器生成尾部。
- `dq_convert_inline.h`：读取生成的 `.words.inc`，声明 s0:s1、v0、s24 输入，
  以及 s2～s23、s25～s29、s40～s48、v4～v45、SCC、memory 污染。
- `dq_wrapper.cpp/.h`：使用标准设备 ABI 的 noinline/convergent 包装函数。
  它编译成 `.bc`，让最终 LLVM 根据 clobber 生成 GPR 保存和恢复。

从本测试根目录运行 `python3 build_wrapper.py` 构建；`python3 asm/prepare.py --source-only`
仅重生成适配 `.s`。所有构建产物位于 `build/asm` 和 `build/wrapper`。

片段的 `.co` 是指令提取中间产物。最终交给 FlyDSL `link_extern` 的是包装器 `.bc`。
原始 `.co`、片段 `.co` 和 `.bc` 不是同一种格式，也不能互相改扩展名使用。

## 参数记录与执行约定

接口 `mono_dq_convert_wrapper(uint64_t args_address, uint32_t linear_tid)` 接收一个统一的
240 字节 GPU 全局参数记录地址。`dq_convert_args.h` 定义布局，reserved 字段均为 0。
输入 tile 为 64×64 packed FP32，输出 tile 为 64×64 row-major BF16：

| 偏移 | 字段 | 本单测值 |
| --- | --- | --- |
| 0x00 / 0x10 | 输入 / 输出指针 | 每 task 独立 tile |
| 0x20 / 0x30 | 输入 head / batch stride | 各 16384 字节，u64 |
| 0x40 | 输入 row stride | 256 字节，u32 |
| 0x50 / 0x60 | 输出 head / batch stride | 各 8192 字节，u64 |
| 0x70 | 输出 row stride | 128 字节，u32 |
| 0x80 / 0x90 / 0xc0 | seqlen / head_dim / max_seqlen | 各 64 |
| 其他 | 可选参数 / reserved | 0 |

输入布局映射：

```text
sr = 16*(r//16) + 8*((c//16)%2) + r%8
sc = 32*(c//32) + 16*((r//8)%2) + c%16
packed[sr*64+sc] = logical[r*64+c]
```

有效 WQKV 结果占 row0/col0～15，恰好对应 packed 的前 16 项。每 task 输入 16 KiB、
输出 8 KiB，两侧各有 256 字节独立 guard。host 使用 uncached 分配，并拒绝不满足原始
buffer descriptor 53-bit 地址范围的 tile 指针。

Mono 固定 256 threads/CTA、wave32；全 CTA 统一到达包装器调用，调用前后有等待和 barrier。
供应方前四个 wave 执行转换，其他 wave 跳过；全 wave 的 EXEC 与 MODE 要满足入口/出口约定。
参数对应的虚拟 grid x/y/z 都是 0，真实 task 已由指针和参数记录选定。

本机 `.bc` 和离线包装器汇编已生成；完整 Mono 编译与 GPU 结果尚未验证。详见
[主说明](../README.md) 中的构建证据和目标机器检查步骤。
