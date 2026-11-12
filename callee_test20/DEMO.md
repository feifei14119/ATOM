# 可运行的 ASM 内嵌 HIP demo

日期：2026-11-12。目标：gfx1100 / wave32，工具链：ROCm 7.2 的 AMD Clang/LLVM 22。

本目录现在有完整混合 ASM 源文件、预处理器、离线构建产物和测试源码。已完成两个 HIP 片段、完整 ASM code object 和 host 测试程序的编译。**没有运行 CPU 单测、离线验收测试或 GPU 测试；没有数值正确性或性能结论。** 原来的 [README.md](README.md) 和 [IMPLEMENTATION.md](IMPLEMENTATION.md) 保留通用后端设计，当前 demo 实现的是一个受限子集。

## 直接在 ASM 文件写 HIP

用户维护 [kernel.s](kernel.s)，参数加载、ID、global load/store、kernel descriptor 和 metadata 都写在 ASM 中。计算部分：

```asm
.hip.begin mul_add
    .hip.in f32 a = v0
    .hip.in f32 b = v1
    .hip.out f32 c = v2
    .hip.temp vgpr = v[32:35]
    .hip.fp_contract off
    .hip.fast_math off
    .hip.code
        c = a + b * a;
.hip.end

.hip.begin sub_div
    .hip.in f32 a = v0
    .hip.in f32 b = v1
    .hip.out f32 d = v7
    .hip.temp vgpr = v[40:63]
    .hip.allow_clobber vcc
    .hip.fp_contract off
    .hip.fast_math off
    .hip.code
        d = a - b / a;
.hip.end
```

`.hip.begin/end` 是 `mixed_asm.py` 识别的预处理指令。Clang 和 `llvm-mc` 只接收工具生成的 HIP 或纯 ASM；它们不直接解析混合文件。

每块声明两个只读输入、一个输出和连续临时 VGPR 池。输入 v0/v1 保留，块内计算发生在授权池中，结果在出口复制到 v2/v7。外围 ASM 随后使用指定输出寄存器。若改变输出绑定，也要改变相应外围 ASM 的消费者。

## 构建方式

```bash
cd /home/feifei/repo/ATOM/callee_test20

# 只编译：生成 demo.co 和 host 测试程序，不执行测试。
make

# 单独编译 kernel。
make build

# 后续需要执行测试时：
make unit-test    # Python 合约/拒绝路径单测，不需要 GPU 或编译器
make inspect      # 重新构建并执行 ELF/片段字节/descriptor 验收
make check        # 构建、CPU 单测、离线验收和 gfx1100 GPU 数值测试

# 可指定工具链、输出目录和 HIP device ordinal。
make check LLVM=/opt/rocm/lib/llvm/bin BUILD=build DEVICE=0
```

默认 `make` 不运行测试。构建报告状态为 `BUILT_NOT_TESTED`；只有实际执行 `verify.py` 或 host GPU 测试并通过，才分别生成 `static_report.json`、`gpu_result.json` 中的 `PASS`。

## 当前编译结果

`mul_add` 的核心 native 指令经临时寄存器映射后为：

```asm
v_mul_f32_e32 v33, v32, v33
s_delay_alu instid0(VALU_DEP_1)
v_add_f32_e32 v32, v32, v33
```

前后还有输入/输出 COPY 和保守的边界间隔。`fp_contract=off` 保留用户表达式的独立乘法和加法。

`sub_div` 在当前工具链上使用 v40..v46，包括 `v_div_scale_f32`、`v_rcp_f32`、迭代 FMA、`v_div_fmas_f32` 和 `v_div_fixup_f32`，最后执行减法并将结果送到 v7。这里的 FMA 用于实现除法，与用户表达式是否允许乘加融合是两个问题。

该除法序列会改写 VCC，故需要显式授权。两个块都不使用计算 SGPR、scratch、函数调用或源级分支；SCC、EXEC 和 MODE 保持不变。VCC 在 `mul_add` 块保留，`sub_div` 块允许污染。

当前完整 kernel 为 `asm_hip_demo`，只有一个可启动 descriptor，24 字节 kernarg 对应三个指针：a、b、输出记录。固定 LDS 和 private memory 均为 0，metadata 为 64 VGPR、20 SGPR、wave32。实际片段可用到 v46，但 descriptor 覆盖用户声明的整个 v40..v63 临时池。

## 实现边界

这里复用普通 HIP helper 的代码生成，然后严格检查整个 native 函数。检查通过后移除已识别的等待 prologue 和 `s_setpc_b64 s[30:31]` return，把支持的标量 VALU 指令插入 ASM。最终没有 linked HIP helper 或 device call。

这条路径成立的前提是 helper 的计算体没有普通函数 ABI 的保存/恢复、栈、spill、隐式 dispatch 依赖或额外代码。预处理器检查指令白名单、显式/隐式 VCC 使用、寄存器定义与读取、native 资源报告和返回 ABI；出现不支持的 lowering 会失败，不会未经检查删除 prologue/epilogue。

当前支持：

- 顶层多个代码块；每块两个 f32 输入和一个 f32 输出。
- 单个输出赋值，表达式使用输入、数值常量、`+ - * /`、括号和一元正负号。浮点字面量需用 `f` 后缀。
- 连续、基址按 8 个寄存器对齐的 VGPR 临时池；映射保留 native 编号的相对间隔与 bank/parity。
- 固定 `fp_contract=off`、`fast_math=off`，与 kernel FP MODE 配置匹配。
- 已审阅的 gfx1100 标量 VALU 和内部 hazard 指令；只允许声明 VCC clobber。

当前不支持其他架构、SGPR 临时池、其他数据类型、inout、多个输出、局部变量声明、调用、访存、循环、条件语句、barrier 或在 ASM macro/条件汇编中定义 HIP 块。合法 C++ 若降低到不支持的机器指令，也会被拒绝。

这是适用于小表达式的受限实现。原设计中的任意寄存器契约、复杂控制流和通用 fragment codegen 仍需扩展 LLVM 后端；不能把本 demo 的文本寄存器映射推广到任意 HIP 函数。

Clang 自动生成的 HIP compilation-unit identity global 经过严格布局和使用检查后被移除；计算函数保持原有 float(float,float) ABI。生成的原始 IR 和规范化 IR 都保存，便于审阅。

## 测试与产物

| 文件 | 作用 |
| --- | --- |
| `kernel.s` | 用户入口：ASM 与两个 HIP 代码块。 |
| `mixed_asm.py` | 分段、合约检查、Clang 编译、native 检查、寄存器映射和最终链接。 |
| `test_mixed_asm.py` | CPU 单测：绑定、重叠、预算、注释中的 end、源级非法代码、native ABI、scratch、clobber 和临时池不足。 |
| `verify.py` | 离线验收：独立汇编每个片段，比较最终 ELF 中的插入字节、写寄存器范围和真实 descriptor。 |
| `test.cpp` | Host HIP API 加载 ASM kernel，逐条比较全部输出与寄存器/内存 guard。 |

GPU 测试包含 1、13、32 threads，四类输入，每类重复三次，共 36 次 launch、552 条记录，每条检查 14 个字段。覆盖零值、正负和 signed zero、随机尾数、NaN/Inf、subnormal、最大有限数和乘加融合敏感输入。输入内存与 padding、输出前后 guard 都检查。

CPU reference 用 volatile 中间结果分别计算乘法/加法和除法/减法。`c` 有限值要求精确位匹配，`d` 有限非零值允许最多 2 ULP；零的符号和 Inf 精确匹配，NaN 检查类别而不比较 payload。这些是测试的验收条件，尚未执行测试，不能视为已测出的误差范围。

每个块保存 `fragment.hip.cpp`、`fragment.raw.ll`、`fragment.ll`、`fragment.native.s`、`fragment.inc`。完整构建保存 `kernel.generated.s`、`kernel.o`、`demo.co`、反汇编、ELF 信息和 `build_report.json`。重建会删除旧 code object 和旧测试报告，避免失败构建留下旧成功结果。
