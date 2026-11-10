# 外部 ASM 调用契约最小单测

本目录验证修改后的 LLVM AMDGPU 后端，不依赖 ATOM/AITER 的算子实现。FlyDSL 版本见上级 [test_flydsl.py](../test_flydsl.py)，两条路径使用完全相同的 `stage.s`。

## 调用协议

| 内容 | 寄存器 |
| --- | --- |
| workgroup x / y | s0 / s1 |
| factor，本例传 37 和 0xa13579bd | s2 |
| 当前 lane 的 global record 地址 | v0:v1，低位在 v0 |
| thread x / y | v2 / v3 |
| 返回计算结果 | v4 |
| 返回 PC | s30:s31 |

被调函数会覆写 `s4:s6,s40,s48,s63,v4:v9,v64,v72,v95,SCC`。其中包含默认 ABI 的 callee-saved 寄存器，但本函数遵守 manifest 指定的自定义契约，没有默认 ABI scratch 序言。

每个 CTA 为 32×8 线程，全部进入同一条调用路径，物理 wave32/full EXEC。`amdgpu-asm-full-wave-calls=true` 是调用方对该事实的显式承诺，不是后端对任意控制流的证明。FlyDSL 适配器要求显式传 `assert_full_wave_calls=True`。

## 测试计算

每 lane 对应 16 个 u32 的 record。caller 先读取输入和 uniform seed 的 volatile 快照，再连续调用 ASM 两次。每次 ASM 将输入改为 `(input ^ 0x9e3779b9) + factor`。两个不同的 factor 使最终输入也不同于原输入，调用者不能通过调用后的简单重载冒充保存了旧上下文。

ASM 计算：

```text
result = ((input ^ 0x13579bdf) + factor + tx + (ty << 8)
          + (bx << 16) + (by << 24)) ^ (bx ^ by)
```

所有运算按 u32 模 2^32。ASM 同时记录参数，caller 在调用后记录两个返回值和原上下文。host 验证所有字段、每个 record 的 guard 和整个缓冲区两端的 guard。

## 构建与运行

在 ATOM 根目录：

```bash
python3 llvm_asm_contract/demo/build.py
python3 llvm_asm_contract/demo/test_audit.py \
  --llvm-bin /home/feifei/repo/llvm-project-asm-contract/build-contract/bin

mono_test20/build/venv/bin/python llvm_asm_contract/test_flydsl.py
```

三个脚本均不启动 GPU。可以通过 `--llvm-bin` 指定本次修改后的 LLVM 工具目录；构建器会用无效版本契约探测后端能力，旧 LLVM 的“忽略未知属性”行为会被拒绝。

host 测试只使用普通 C++ 编译器：

```bash
c++ -std=c++17 -O2 -D__HIP_PLATFORM_AMD__ -I/opt/rocm/include \
  llvm_asm_contract/demo/test.cpp -L/opt/rocm/lib \
  -Wl,-rpath,/opt/rocm/lib -lamdhip64 -o llvm_asm_contract/build/host

llvm_asm_contract/build/host llvm_asm_contract/build/demo/kernel.co
llvm_asm_contract/build/host llvm_asm_contract/build/flydsl/kernel.co contract_flydsl
```

host 会寻找 gfx1250；没有对应 GPU 时返回 2，不尝试在其他架构上加载。9 个案例来自 3 种二维 grid × 3 个 seed，block 固定 32×8。

## 产物与验证边界

- `stage/stage.co`：真正的独立 ET_REL 设备函数；`stage.contract.json` 绑定此对象的 SHA256。
- `caller.o`：修改后的 `llc` 原生生成，未修改 MIR 或寄存器分配后的代码。
- `kernel.co`：`ld.lld` 静态链接结果，callee 的函数字节与输入对象一致。
- `backend.resources.json`：LLVM 输出的真实 spill、private、ABI 保存、调用点保持寄存器报告。
- `result.json`：包装、链接、最终 metadata 与后端报告的汇总。
- `caller.s` / `kernel.dis.s`：调用方代码生成和最终反汇编，便于检查实际参数位置及 call/return。

2026-11-10 使用修改后的 LLVM 24 离线构建，两条路径均为 96 VGPR / 66 SGPR、private=0、LDS=0；两条真实设备调用，后端报告所有 spill、ABI memory save 和 SGPR lane save 为 0。66 个 SGPR 是最终调用者与 callee 合并后的编号资源，不能把它简单解释成“64 个编号 SGPR + VCC”：本次 `uses_vcc=0`。

本机没有 gfx1250，因此尚未验证 GPU 执行结果。对象审计只支持本例的线性、叶子、限定指令集合，不宣称能够验证任意黑盒 ASM。
