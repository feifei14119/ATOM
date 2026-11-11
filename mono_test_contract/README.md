# gfx1250 Mono：寄存器契约函数（register-contract）接入 ASM

本目录与 `mono_test00` 使用同一份供应方 ASM（`asm/dq_convert.inline.s`）、同样的 Mono 计算和 A/B 单测，
但不再使用标准 ABI 的包装函数，而是把 ASM 打包成**寄存器契约函数**：参数固定在 `s[0:1]` / `v0` / `s24`，
调用点展开为一段带完整 clobber 的 asm，**没有 `s_swap_pc`，没有 scratch，没有 wrapper 代码**。

设计见 [需求文档](../mono_read/ASM_REG_CONTRACT_REQUIREMENT.zh-CN.md)，实现与验证见
[实现文档](../mono_read/ASM_REG_CONTRACT_IMPLEMENTATION.zh-CN.md)。

## 一键运行

```bash
cd /app/ATOM/mono_test_contract
./run.sh                     # 打包契约 + 编译 + 9 组 native/契约 A/B + 资源审计
python3 negative_tests.py    # 5 个负例：打包期 3 个、编译期 2 个（需 PYTHONPATH 指向 overlay）
```

依赖：

- 带契约补丁的 LLVM 构建，默认 `/app/llvm-upstream/build`，可用 `--llvm-dir` 指定；
- 带 `asm_contract` 的 FlyDSL，默认使用 overlay `/app/flydsl_overlay`，可用 `FLYDSL_OVERLAY` 覆盖。

`run_test.py` 会设置 `FLYDSL_COMPILE_LLVM_DIR=<llvm-dir>` 和 `FLYDSL_COMPILE_LLVM_HANDOFF=llvm`。

## 接入一个 ASM 需要写什么

1. ASM 原文 `asm/dq_convert.inline.s`，不需要改。
2. 一份清单 `asm/dq_convert.contract.yaml`：参数寄存器、需要恢复的状态（`preserves`）、是否访存。
   `clobbers` 省略时取 ASM 实际写到的寄存器集合，由 `amdgpu-asm-footprint` 从机器码得出。
3. 调用方 `mono1250/kernels/dq_ffi.py`：

   ```python
   dq_convert = ffi_contract("build/contract/dq_convert.contract.json")
   dq_convert(args=fx.Int64(addr), lane=tid & 31, wave=tid >> 5)
   ```

4. 编译时打开严格无 spill 策略和调用点报告（见 `run_test.py`）：

   ```python
   with CompilationContext.compile_hints({"llvm_options": spill_hints("error", report="build/contract_report.jsonl")}):
       ...
   ```

`build_contract.py` 调用 `flydsl.compiler.asm_contract.pack`，生成三个文件：

- `build/contract/dq_convert.contract.bc`：契约函数；
- `dq_convert.contract.json`：调用方读取的 sidecar；
- `dq_convert.fragment.bin`：机器码，用于审计。

## 验证内容

- **数值：** 契约版与 native 版逐位一致（zero/pattern/random × 3，共 1008 次 ASM 执行）。
- **资源（`contract_audit.py`）：**
  - fragment 机器码在 kernel `.text` 中恰好出现一次，并且 64 字节对齐；
  - 没有 call/return 指令；
  - scratch、VGPR spill 和 SGPR spill 都是 0；
  - 调用点报告只有一个调用点，`status=ok`。
- **负例（`negative_tests.py`）：**
  - 漏声明 clobber、MODE 未恢复、改写了输入寄存器，打包时报错；
  - 改写集合超过 512 个 VGPR、改写集合导致 spill，编译时报错。

## 与 mono_test00 的差异

删除了 `build_wrapper.py`、`wrapper_audit.py`、`asm/dq_wrapper.{cpp,h}`、`asm/dq_convert_inline.h`，以及
`dq_convert_inline.h` 中手写的 78 个 clobber 和 readfirstlane 桥接代码；新增了上面提到的清单、`build_contract.py`、
`contract_audit.py` 和 `negative_tests.py`。其余文件（Mono 计算、参考实现、HIP runtime）与 mono_test00 相同。
`ORIGIN_README.md` 等溯源文件原样保留。
