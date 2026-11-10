# AMDGPU 设备函数 ABI：调用约定中文译文

本文翻译 LLVM《AMDGPU Usage》的 **Call Convention（调用约定）** 一节，重点为 **Non-Kernel Functions（非 Kernel 函数，即普通设备函数）**，同时保留前面的 Kernel Functions 小节，以明确两种入口的区别。

这是技术文档译文，不是 AMD/LLVM 官方中文规范。第 2 节忠实保留原文的规则、历史描述、TODO 和不确定性；第 3 节是独立的译者注及当前 ROCm 实现对照，不属于原文。

## 1. 来源、版本与术语

- 在线文档：[LLVM AMDGPU Usage — Call Convention](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-function-call-convention)。
- 设备函数章节：[Non-Kernel Functions](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-function-call-convention-non-kernel-functions)。
- 翻译依据：本机 `/home/feifei/repo/llvm-project/llvm/docs/AMDGPUUsage.rst`，从 `amdgpu-amdhsa-function-call-convention` 标记到下一节 `AMDPAL` 之前，原文件第 16631–17039 行。
- 本机文档仓库提交：`04f968b02917316c33f4eace2bc01bf6f78873f9`；翻译时该文档没有本地修改。在线文档可能随时间更新，以本目录英文快照为此次翻译依据。
- 英文快照：[AMDGPU_DEVICE_FUNCTION_ABI.en.rst](AMDGPU_DEVICE_FUNCTION_ABI.en.rst)。
- 英文快照 SHA-256：`f8c6f6affc62fa90b4b4fc370a5b40712ce39c8e24e324e57b47c589bc148aee`。
- 翻译日期：2026-11-09。

本机文档仓库的提交与已安装 ROCm 编译器的提交不同；第 3 节对实现的说明单独引用已安装 ROCm 7.2 编译器对应版本的源码。

为便于阅读，本文使用以下译法；此术语表是译者补充：

| 原词 | 本文译法或含义 |
| --- | --- |
| caller / callee | 调用方 / 被调用方 |
| preserved / callee-saved | 返回时保持原值 / 被调用方负责保存 |
| clobbered | 允许被覆盖，调用方不能假定原值仍然存在 |
| scratch | 保留英文；用于 private 内存、栈及寄存器溢出等的存储 |
| spill / reload | 寄存器溢出保存 / 重新加载 |
| swizzled / unswizzled | 交错 / 非交错；具体地址含义以原文对应章节为准 |
| wavefront / lane | 波前 / 波前中的 lane |
| RA / SP / FP / BP | 返回地址 / 栈指针 / 帧指针 / 基址指针 |
| CFI / CFA | 调用帧信息 / 规范帧地址 |
| TBA / TBD / TODO | 待补充 / 待确定 / 待办事项 |

## 2. 原文翻译

### 2.1 调用约定（Call Convention）

> **原文注意事项：** 本节目前尚不完整，并存在不准确之处。它仍在编写中（WIP），将在相关信息确定后更新。

有关交错地址（swizzled address）的信息，请参阅 [DWARF Address Space Identifier](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-dwarf-address-space-identifier)。非交错地址（unswizzled address）就是普通的线性地址。

### 2.2 Kernel 函数（Kernel Functions）

本节描述最外层 kernel 函数的调用约定 ABI。

关于 kernel 的调用约定，请参阅 [Initial Kernel Execution State（Kernel 初始执行状态）](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-initial-kernel-execution-state)。

以下内容不属于 AMDGPU kernel 调用约定本身，而是描述 AMDGPU 如何实现函数调用：

1. Clang 决定 kernarg 的布局，使其符合 *HSA Programmer's Language Reference（HSA 程序员语言参考）*。

   - 所有结构体都直接传递。
   - Lambda 值的传递方式：待补充（TBA）。

   > **原文 TODO：** 这是否真的遵循 HSA 规则？还是说，大于 16 字节的结构体会作为按值传递的结构体传递？Lambda 值的 ABI 是什么？

2. Kernel 在入口序言中执行某些初始化，具体参见 [Kernel Prolog（Kernel 入口序言）](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-kernel-prolog)。

### 2.3 非 Kernel 函数（Non-Kernel Functions）

本节描述最外层 kernel 函数以外的其他函数的调用约定 ABI。

如果 kernel 包含函数调用，就总会分配 scratch，并将其用于调用栈。调用栈使用交错的 scratch 地址空间，从低地址向高地址增长。

> **译者注索引：** 上述“总会分配 scratch”的原文表述与具体生成的 spill 指令、kernel metadata 不是同一个层面的结论；参见第 3.2 节。

#### 2.3.1 进入函数时的状态

1. `SGPR0–3` 中包含一个具有以下属性的 V# 描述符，参见 [Private Segment Buffer（Private 段缓冲区）](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-kernel-prolog-private-segment-buffer)：

   - 基地址指向该 wavefront 的 scratch 后备内存起始位置。
   - 采用交错布局，元素大小为一个 dword，步长为 wavefront 大小个元素。

2. `FLAT_SCRATCH` 寄存器对已经设置完毕。参见 [Flat Scratch](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-kernel-prolog-flat-scratch)。

3. 对于 GFX6–GFX8，`M0` 寄存器设置为 LDS 的大小，单位为字节。参见 [Kernel Prolog — M0](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-kernel-prolog-m0)。

4. `EXEC` 寄存器被设置为函数入口处处于活动状态的 lane 掩码。

5. `MODE` 寄存器：待确定（TBD）。

6. `VGPR0–31` 和 `SGPR4–29` 用于传递函数输入参数，具体规则见下文。

7. `SGPR30–31` 保存返回地址（RA），即函数执行完成后必须返回的代码地址。如果函数不返回（no return），该值未定义。

8. `SGPR32` 用作栈指针（SP）。它是一个非交错的 scratch 偏移，相对于该 wavefront 的 scratch 后备内存起始地址。

   非交错 SP 可以作为非交错的 SGPR 偏移，结合 `SGPR0–3` 中的 scratch V# 描述符，使用 buffer 指令以交错方式访问栈。

   非交错 SP 值可以通过下式转换成交错 SP 值：

   ```text
   交错 SP = 非交错 SP / wavefront 大小
   ```

   该结果可以用于获得栈对象在 private 地址空间中的地址；再加上 flat scratch aperture 的基地址，就可以将其转换为 flat 地址。

   在 `r600` 架构上，交错 SP 值始终按 4 字节对齐；在 `amdgcn` 架构上，始终按 16 字节对齐。

   > **原文说明：** 为 `amdgcn` 选择这一对齐值，是为了避免 OpenCL 语言需要动态栈对齐；OpenCL 定义的最大基本类型为 16 字节。

   进入函数时，交错 SP 值是第一个通过栈传递的函数参数的地址。其他栈参数位于相对于入口交错 SP 的正偏移处。

   函数可以在最后一个栈参数之后的正偏移区域中，为局部变量和寄存器溢出槽分配栈空间。必要时，可以为这些对象使用大于 16 字节的对齐。在这些对象之后，函数还可以动态分配空间，例如为大小在运行时确定的 `alloca` 局部分配预留空间。

   如果该函数调用另一个函数，它会把通过栈传递的参数放在最后一个局部分配之后，并将 `SGPR32` 调整为最后一个局部分配之后的地址。

9. 其他所有寄存器的状态均未规定。

10. 已执行所有必要的 `s_waitcnt`，以确保内存可供被调用函数使用。

11. 在 C ABI 中，对结构体参数使用按引用传递（`byref`），而不是按值传递（`byval`）。被调用方负责分配栈内存，并在需要修改结构体时复制其值。注意，后端仍然支持结构体参数的 `byval` 形式。

#### 2.3.2 退出函数时的状态

1. `VGPR0–31` 和 `SGPR4–29` 用于传递函数返回结果，具体规则见下文。用于传递结果的寄存器都被视为允许覆盖的寄存器。

2. 以下寄存器或状态必须保持，其值与函数入口时相同：

   - `FLAT_SCRATCH`。
   - `EXEC`。
   - GFX6–GFX8 上的 `M0`。
   - 除允许覆盖的 `SGPR4–31` 之外的所有 SGPR。
   - `VGPR40–47`。
   - `VGPR56–63`。
   - `VGPR72–79`。
   - `VGPR88–95`。
   - `VGPR104–111`。
   - `VGPR120–127`。
   - `VGPR136–143`。
   - `VGPR152–159`。
   - `VGPR168–175`。
   - `VGPR184–191`。
   - `VGPR200–207`。
   - `VGPR216–223`。
   - `VGPR232–239`。
   - `VGPR248–255`。

   > **原文说明：** 除参数寄存器外，允许覆盖的 VGPR 和需要保持的 VGPR 按固定间隔交替分布。这样，无论分配了多少 VGPR，两类寄存器都能保持近似的比例。

   - GFX90A 上，除允许覆盖的 `AGPR0–31` 之外的所有 AGPR。
   - 调用点处于非活动状态的 lane，在所有 VGPR 中对应的值。

   对于 AMDGPU 后端，如果跨过程寄存器分配优化（IPRA）能够确定被调用函数没有改变某些寄存器的值，就可能把原本允许覆盖的部分 SGPR 和 VGPR 标记为需要保持的寄存器。

3. PC 被设置为入口处提供的返回地址 RA。

4. `MODE` 寄存器：待确定（TBD）。

5. 其他所有寄存器均允许被覆盖。

6. 已执行所有必要的 `s_waitcnt`，以确保该函数访问的内存可供调用方使用。

> **原文 TODO：** 函数结果如何返回？结构化类型通过引用传递其地址，但其他类型如何处理？

> **译者注索引：** 本小节 SGPR 保持集合的原文描述与当前 ROCm 实现不同；参见第 3.1 节。不要将这份历史描述直接作为本机汇编适配层的保存清单。

#### 2.3.3 显式参数、结构体参数与返回值

函数输入参数由源语言显式声明的形式参数，加上实现所使用的隐式输入参数组成。

源语言输入参数的顺序为：

1. 源语言隐含的 `this` 或 `self` 参数最先出现，其类型为指针。
2. 随后是函数形式参数，顺序与源代码中从左到右的顺序一致。

源语言结果参数为函数的返回结果参数。

对于源语言中大小小于或等于 16 字节的输入或结果结构体参数，会递归分解为基本类型字段，并把每个字段视为独立参数传递。对于输入参数，如果被调用函数要求该结构体位于内存中，例如需要取得其地址，则函数体负责分配栈位置，并将字段参数复制进去。Clang 将这种方式称为 **direct struct（直接传递的结构体）**。

对于大小大于 16 字节的源语言输入结构体参数，采用按引用传递。调用方负责分配一个栈位置，复制结构体的值，并将该位置的地址作为输入参数传递。被调用函数在访问该输入参数时负责解引用。Clang 将这种方式称为 **by-value struct（按值传递的结构体）**。

对于大小大于 16 字节的源语言结果结构体参数，采用按引用返回。调用方负责分配一个栈位置来保存结果值，并把该地址作为最后一个输入参数传递，位置在隐式输入参数之前。这种情况下没有结果参数。被调用函数在写入结果时负责解引用。Clang 将这种方式称为 **structured return，简称 `sret`（结构化返回）**。

> **原文 TODO：** 修正 `sret` 的定义。
>
> 上述定义是否正确？还是说，只有通过寄存器传递时才使用 `sret`，而通过栈传递时，会把结构体作为未分解的栈参数传递？或者采用其他方式？
>
> 该内存位置是在调用方的栈帧中，还是属于栈上传递的参数，因此无需传递地址，调用方可以直接写入参数栈位置？但这样一来，该栈位置在返回后仍然存活。如果它属于参数栈位置，那么是第一个栈参数还是最后一个栈参数？

Lambda 参数类型被视为结构体类型，其字段集合由实现决定。

> **原文 TODO：** 需要明确 AMDGPU 上 Lambda 类型的 ABI。

对于 AMDGPU 后端，所有源语言参数，包括结构体分解后的参数，都通过 VGPR 传递；如果参数标记为 `inreg`，则通过 SGPR 传递。

#### 2.3.4 隐式输入参数

AMDGPU 后端从叶函数开始遍历函数调用图，以确定使用了哪些隐式输入参数，并将这些需求传播到各个调用方。使用到的隐式参数按以下顺序追加到源语言参数之后：

> **原文 TODO：** 是否支持递归或外部函数？

1. **Work-Item ID（工作项 ID，1 个 VGPR）**。

   X、Y、Z 工作项 ID 按以下布局打包到一个 VGPR 中。只有函数实际使用的字段会被设置，其他位未定义。

   这些值来自 kernel 初始执行状态，参见 [Initial Kernel Execution State](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-initial-kernel-execution-state)。

   | 位范围 | 大小 | 字段 |
   | --- | --- | --- |
   | `9:0` | 10 位 | X Work-Item ID |
   | `19:10` | 10 位 | Y Work-Item ID |
   | `29:20` | 10 位 | Z Work-Item ID |
   | `31:30` | 2 位 | 未使用 |

2. **Dispatch Ptr（Dispatch 指针，2 个 SGPR）**。

   值来自 kernel 初始执行状态，参见 [SGPR Register Set-Up Order（SGPR 初始化顺序）](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-amdhsa-sgpr-register-set-up-order-table)。

3. **Queue Ptr（队列指针，2 个 SGPR）**。

   值来自 kernel 初始执行状态，参见上述 SGPR 初始化顺序表。

4. **Kernarg Segment Ptr（Kernarg 段指针，2 个 SGPR）**。

   值来自 kernel 初始执行状态，参见上述 SGPR 初始化顺序表。

5. **Dispatch ID（Dispatch 标识，2 个 SGPR）**。

   值来自 kernel 初始执行状态，参见上述 SGPR 初始化顺序表。

6. **Work-Group ID X（X 方向工作组 ID，1 个 SGPR）**。

   值来自 kernel 初始执行状态，参见上述 SGPR 初始化顺序表。

7. **Work-Group ID Y（Y 方向工作组 ID，1 个 SGPR）**。

   值来自 kernel 初始执行状态，参见上述 SGPR 初始化顺序表。

8. **Work-Group ID Z（Z 方向工作组 ID，1 个 SGPR）**。

   值来自 kernel 初始执行状态，参见上述 SGPR 初始化顺序表。

9. **Implicit Argument Ptr（隐式参数指针，2 个 SGPR）**。

   该值通过给 Kernarg Segment Ptr 加上一个偏移计算得到，是指向第一个 kernarg 隐式参数的 global 地址空间指针。

#### 2.3.5 参数的寄存器与栈分配

输入参数和结果参数按照以下方式依次分配：

> **原文注意事项：** 以下描述可能存在一些需要修正的错误和遗漏。
>
> **原文 TODO：** 检查 Clang 源码，弄清楚函数参数和返回结果的处理方式，同时检查 AMDGPU 使用的特定值。

- VGPR 参数从 `VGPR0` 开始依次分配到连续的 VGPR，直到 `VGPR31`。

  如果这些寄存器容纳不下所有参数，剩余参数按顺序分配到栈上的自然对齐地址。

  > **原文 TODO：** 具有超常对齐要求的结构体如何在栈上分配？

- SGPR 参数从 `SGPR0` 开始依次分配到连续的 SGPR，直到 `SGPR29`。

  如果这些寄存器容纳不下所有参数，剩余参数按顺序分配到栈上的自然对齐地址。

注意，分解后的结构体参数可能有一部分字段通过寄存器传递，另一部分通过内存传递。

> **原文 TODO：** 如果一个结构体的部分字段能够作为分解后的寄存器参数传递，那么剩余字段是否作为分解后的栈元素传递？而对于一开始就无法放入寄存器的参数，是否不再分解，而是作为未分解的栈值传递？

#### 2.3.6 AMDGPU 的函数调用实现方式

以下内容不属于 AMDGPU 函数调用约定本身，而是描述 AMDGPU 如何实现函数调用：

1. 必要时使用 `SGPR33` 作为帧指针（FP）。与 SP 一样，它也是非交错的 scratch 地址。只有使用了大小在运行时确定的 `alloca`，或者满足 `SIFrameLowering` 中定义的其他条件时，才需要帧指针。

2. 支持运行时栈对齐。`SGPR34` 用作基址指针（BP），用于在函数中访问传入的栈参数。只有函数需要运行时栈对齐时，才需要 BP。

3. 不支持将 SGPR 参数分配到栈上。

4. 当前不生成 CFI。参见 [Call Frame Information（调用帧信息）](https://llvm.org/docs/AMDGPUUsage.html#amdgpu-dwarf-call-frame-information)。

   > **原文说明：** 将生成 CFI，把 CFA 定义为最低地址的栈分配局部变量的非交错地址；该地址位于非交错的 private 地址空间中，并相对于 wave 的 scratch 基地址。
   >
   > `DW_AT_frame_base` 将通过把 CFA 除以 wavefront 大小，定义为交错 private 地址空间中的交错地址。原因是 CFA 至少按 dword 对齐，与 scratch 交错元素大小一致。
   >
   > 如果没有执行动态栈对齐，那么栈参数通过相对于 `DW_AT_frame_base` 的负偏移访问，局部变量和寄存器溢出槽通过相对于 `DW_AT_frame_base` 的正偏移访问。

5. 参数传递的实现方式是：进入函数时，把输入物理寄存器复制到虚拟寄存器。必要时，寄存器分配器可以进行溢出保存。在调用点，这些值会被复制回物理寄存器。因此，每次函数调用中，这些值都可能位于完全不同的位置。IPRA 可以帮助避免参数寄存器之间的搬运。

6. 调用点的实现方式是：在相对于 SP 的正偏移处设置参数；随后，在调用前增加 SP，以计入已知的栈帧大小；调用返回后再减小 SP。

   > **原文说明：** CFI 会反映从 SP 计算 CFA 所需的计算方式变化。

7. 栈帧中使用 4 字节的寄存器溢出槽，并分配一个紧急溢出槽。栈访问使用 buffer 指令，而不是 `flat_scratch` 指令。

   > **原文 TODO：** 解释何时使用紧急溢出槽。

#### 2.3.7 原文列出的潜在问题与待办事项

> **原文 TODO：可能存在问题的地方。**

- 栈参数必须满足所要求的对齐。
- 栈的对齐为 `max(16, 所有形式参数的最大对齐要求)`。
- 小于 64 位的直接传递参数应检查寄存器预算。
- 计算寄存器预算时，应考虑 `inreg` 对 SGPR 的要求。
- 没有处理 SGPR 容量溢出。
- 展开仅有一个成员的结构体时，没有检查该成员的大小。
- `sret` 位于 `this` 指针之后。
- 调用方没有实现栈重新对齐，需要一个额外指针。
- 应该说明 AMDGPU 传递的是 FP，而不是 SP。
- CFI 应该把 CFA 定义为局部变量的地址，还是参数的地址？实现动态对齐后，这一区别会变得明显。
- 如果 `SCRATCH` 指令允许负偏移，就可以把 FP 设置为栈帧的最高地址，并使用负偏移访问局部变量。这样可以让 SP 与 FP 相同，也可以支持类似信号处理函数的行为，因为此时有一个真正指向栈顶的 SP。
- `sret` 如何通过栈传递？位于参数栈区域吗？它能否与参数区域重叠？

**原文翻译到此结束。** 以下内容是译者注和当前实现对照。

## 3. 译者注：与当前 ROCm 设备函数调用的对应关系

### 3.1 SGPR 保持集合应核对当前编译器源码

第 2.3.2 节原文写的是“除 SGPR4–31 外的所有 SGPR 都保持”，这是忠实翻译，并不表示它与本机 ROCm 7.2 的普通设备函数 ABI 一致。

本机已安装编译器为 ROCm 7.2，`clang --version` 给出的源码提交是：

```text
7b800a19466229b8479a78de19143dc33c3ab9b5
```

该版本 [AMDGPUCallingConv.td](https://github.com/ROCm/llvm-project/blob/7b800a19466229b8479a78de19143dc33c3ab9b5/llvm/lib/Target/AMDGPU/AMDGPUCallingConv.td#L71) 的普通设备函数 callee-saved 集合定义如下：

```text
CSR_AMDGPU_SGPRs:
  s30–39, s48–55, s64–71, s80–87, s96–105

CSR_AMDGPU_VGPRs:
  v40–47, v56–63, v72–79, v88–95,
  v104–111, v120–127, v136–143, v152–159,
  v168–175, v184–191, v200–207, v216–223,
  v232–239, v248–255
```

返回地址 `s30:s31`、栈指针 `s32` 以及其他特殊用途寄存器，还受到调用序列、保留寄存器和栈管理规则的约束。不能把“某寄存器不在以上集合中”直接理解为“原 ASM 可以随意改写它且不影响调用”。

此处讨论的是我们示例采用的普通设备函数调用。LLVM 还有 `AMDGPU_Gfx`、chain 等其他 calling convention，不能混用它们的规则。

### 3.2 “存在函数调用”不代表一定生成 scratch 保存指令

原文“总会分配 scratch 用作调用栈”的表述，不能推导为“每个调用都一定需要把活跃值写入 scratch”，也不能推导为“每个含调用的 kernel，其 `.private_segment_fixed_size` 都大于 0”。

本目录当前使用普通设备函数 ABI，不设置寄存器上限，也不修改调用点掩码。当前最小 Mono 的固定 private segment 为 0，VGPR/SGPR spill count 均为 0；这只是本例编译结果，构建允许 scratch。`.uses_dynamic_stack` 为 true，不能据此断言运行时没有分配 scratch 后备内存。

调用方编译器可以把活跃值放到 callee-saved 寄存器、进行 spill/reload，或者在允许的情况下重新计算。保存方式取决于当前实现、活跃值和资源压力。自动处理调用边界不等于保存全部物理寄存器的完整快照。

### 3.3 栈访问指令和隐式参数布局也需要版本核对

原文包含“SGPR0–3 始终持有 scratch V#”“使用 buffer 指令访问栈”“当前不生成 CFI”等历史描述。它们不能作为所有 GPU 世代、所有 ROCm 版本均成立的结论。

早期 gfx1100 独立验证曾实际生成以下 scratch 指令：

```asm
scratch_store_b32 off, v1, off offset:4
; 参数准备等指令
s_swappc_b64 s[30:31], s[16:17]
; 返回后的控制流和其他恢复指令
scratch_load_b32 v1, off, off offset:4
```

以上指令来自早期实验，仅用于说明 scratch 的实际指令形式。当前目录已清理独立 probe 和自定义 regmask 流程，改为最简单的普通设备函数调用。执行 `make inspect` 后，可阅读 `build/mono_kernel.s` 和 `build/mono_kernel.disasm.txt`。第 2 节原文译文保持不变。

隐式参数也应结合当前后端和具体调用方检查。例如，我们指定的 `stage_sub_device` 实际要求 `v31` 提供工作项标识、`s8:s9` 提供隐式参数指针。不能仅按原文参数列表顺序手算最终物理寄存器编号。

### 3.4 `byref`、`byval`、`sret` 的原文描述尚未统一

第 2 节保留了原文对结构体传参的全部说明，包括其间不一致的描述和 TODO。特别是原文前面的 `byref` 说明、后面的 by-value struct 说明，以及 `sret` 参数位置说明，不应直接当作所有源语言和编译器版本都通用的确定规则。

实际接入时，应使用当前编译器生成所需函数声明的调用代码，核对 LLVM IR、参数 lowering 结果和最终物理寄存器/栈布局。我们的 `Mailbox` 是 16 字节结构体；具体传参位置见 [stages/sub_kernel.s](stages/sub_kernel.s) 的开头注释。

### 3.5 编译器通过什么机制知道要保存哪些寄存器

这部分是对实现的说明，不是第 2 节原文内容。

| 实现位置 | 作用 |
| --- | --- |
| `AMDGPUCallingConv.td` 的 `CSR_AMDGPU_*` | 定义被调用方保存的寄存器集合 |
| 同一文件的 `CC_AMDGPU_Func`、`RetCC_AMDGPU_Func` | 定义参数和返回值的分配规则 |
| `SIRegisterInfo.cpp::getCalleeSavedRegs()` | 根据 calling convention 选择保存集合 |
| `SIRegisterInfo.cpp::getCallPreservedMask()` | 返回调用后保持寄存器的掩码 |
| `AMDGPUCallLowering.cpp` 中的 `MIB.addRegMask(Mask)` | 把寄存器掩码附加到机器级调用指令上 |

本机源码便捷入口：

- [AMDGPUCallingConv.td](/home/feifei/repo/llvm-project/llvm/lib/Target/AMDGPU/AMDGPUCallingConv.td:71)。
- [SIRegisterInfo.cpp](/home/feifei/repo/llvm-project/llvm/lib/Target/AMDGPU/SIRegisterInfo.cpp:405)。
- [AMDGPUCallLowering.cpp](/home/feifei/repo/llvm-project/llvm/lib/Target/AMDGPU/AMDGPUCallLowering.cpp:1578)。

本机源码树与已安装编译器并非同一提交；要复核特定编译器行为，应使用对应提交源码和实际生成结果。

调用方编译器根据 ABI 掩码保护跨调用活跃值，并不会反汇编供应方 `.co` 来推导其破坏集合。如果供应方 ASM 覆盖了 ABI 承诺保持的寄存器，仍需供应方函数或独立 ABI 适配层恢复它们。

## 4. 与本目录示例一起阅读

- [README.md](README.md)：构建流程、ABI 保存责任、当前机器上的验证结果。
- [stages/sub_api.h](stages/sub_api.h)：只有设备函数声明的调用接口。
- [stages/sub_kernel.s](stages/sub_kernel.s)：已符合当前示例设备函数 ABI 的独立 ASM。
- [mono_kernel.cpp](mono_kernel.cpp)：主 Mono 中的普通设备函数调用。
- [AMDGPU_DEVICE_FUNCTION_ABI.en.rst](AMDGPU_DEVICE_FUNCTION_ABI.en.rst)：逐段核对用英文原文快照。
