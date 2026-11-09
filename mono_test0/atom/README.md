# dq_convert 普通设备函数交付

完整接入步骤见 [INTEGRATION_STEPS.md](INTEGRATION_STEPS.md)。这里采用普通设备函数 ABI，不使用 inline asm、不修改 regmask，也不限制调用方寄存器数量；允许 PC call/return 和 scratch。

| 文件 | 用途 |
| --- | --- |
| [dq_convert.original.s](dq_convert.original.s) | 用户提供的原件，未修改 |
| [dq_convert.device.s](dq_convert.device.s) | 可独立汇编的新设备函数，保存/恢复代码直接在其中 |
| [dq_convert.device.co](dq_convert.device.co) | **交给链接器的 ET_REL 目标**，不是独立 launch 的 kernel |
| [dq_convert_api.h](dq_convert_api.h) | 240 B 参数结构、全部 offset 检查和设备函数声明 |
| [resources.json](resources.json) | 资源需求、ABI、保存集合和原体修改清单 |
| [verification.json](verification.json) | 当前静态检查及编译链接结果 |
| [dq_convert.device.disasm.txt](dq_convert.device.disasm.txt) | 实际 `.co` 的反汇编 |
| [prepare.py](prepare.py)、[Makefile](Makefile) | 从固定原件重新生成、编译 |
| [verify.py](verify.py) | ABI/字节/布局/头文件和真实调用链接检查，不执行 GPU |

```bash
cd /home/feifei/repo/ATOM/mono_test0/atom
make
make check
```

接口：

```cpp
#include "dq_convert_api.h"
// 位于调用方 kernel 的 CTA 一致控制流中，前后具备 global fence/CTA barrier：
mono_dq_convert_device(args_for_this_cta, threadIdx.x);
```

参数块必须在 GPU global，指针在 CTA 内一致；完整 128 或 256 线程 CTA、wave32、全 EXEC 调用。256 线程时前四个 wave 计算，后四个直接返回；调用方负责全 CTA 汇合。输入固定为经过指定置换的完整 64×64 FP32 tile，输出为行主序 BF16；它不是逐地址线性 cast。

新 `.s` 备份并恢复 `s30:s38`、`v40:v45` 和 MODE 低 8 位，避免原 ASM 覆盖返回地址、SP 和默认 ABI 的 callee-saved 状态。备份使用原体未使用的 caller-saved 寄存器，不增加 scratch；调用方仍可由编译器按需使用 scratch。

设备函数资源下界为 **55 VGPR、48 个编号 SGPR、LDS/private 0**。这些需求必须合并到最终 Mono 的 descriptor 和 metadata。当前静态调用方保留 VCC，因此最终 metadata 为 VGPR 55、SGPR 50；只做 ELF 符号链接不会自动完成这项资源合并。

2026-11-09 在 ROCm 7.2 完成的检查：

- 原始函数 1528 B 的重汇编字节与输入注释中的机器码一致。
- 新函数 1756 B；原 payload 的 1488 B 保持原编码，36 B 入口处理被适配，原 `s_endpgm` 被返回流程取代。
- 核对已安装 llc 的默认保持掩码；对当前固定入口/出口做符号值保存恢复检查通过。此检查不模拟 GPU 调度、访存或指令时序。
- host/device 均编译通过声明头文件及所有 offset 检查；4096 元素地址映射覆盖完整。
- gfx1250 编译产生真实外部设备调用，参数位于 v0:v1/v2；调用方将跨调用值放在 v41，新函数会保存并恢复它。
- 链接检查通过、无未解析符号和剩余重定位；链接前后供应方函数字节一致。检查用 caller 位于 `build/`，其指令没有改写，只合并了资源描述。

**本机没有 gfx1250 GPU，尚未进行此算子的 GPU 验证，也未修改或替换实际 ATOM Mono。** `build/link_check.co` 只是编译链接检查模块。真实接入位置、布局转换、同步、FlyDSL 链接阶段、缓存和 ATOM 的 scratch/驻留门禁处理，均在步骤文档中列明。
