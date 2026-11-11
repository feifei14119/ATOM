// 所有 PSEUDO_FLYDSL 都是“在当前 CTA/waves 中执行设备代码”的伪操作。
// 不是 host launch，不是另启动一个 __global__ kernel。
//
// 这一步只展示 ASM 调度，不选择 FFI、device ABI、inline 或链接方案。
// 未来 adapter 必须满足：
//   1. 调用前后 s32:s59、v63 的调度状态不变，除明确写出的返回值。
//   2. 返回时 EXEC 恢复到调用时状态；不能把 SCC/VCC 当成跨调用状态。
//   3. s0:s31、v0:v62 等临时值按每个调用点说明读取/返回。
//   4. LDS、cluster、global/peer memory 的语义必须保留。
// 这是一份待实现的自定义约定，不是现成 AMDGPU 标准 device ABI。
// 特别是 s32 在标准 ABI 中常是 stack offset，不能直接拿本约定去调用它。
//
// 默认为未实现时报错。build_example.py 只在语法检查模式下展开为
// trap + endpgm；绝不把缺失算子展开成 no-op 后声称得到了网络结果。
.macro PSEUDO_FLYDSL name
    .if ASM_SYNTAX_ONLY
        s_trap 2
        s_endpgm
    .else
        .error "PSEUDO_FLYDSL 尚未实现：需要真正的设备阶段适配器"
    .endif
.endm

// LazyC 的 ASM 对应物：只在用到时才从 fp / 当前 layer row 读指针。
// 这些表在一次 launch 内应保持稳定；并非对动态 counter 用 scalar cache 轮询。
.macro LOAD_FP pair, name
    s_load_b64 \pair, s[34:35], FP_\name
    s_wait_kmcnt 0
.endm
.macro LOAD_AT pair, name
    s_load_b64 \pair, s[34:35], AT_\name
    s_wait_kmcnt 0
.endm
.macro LOAD_LAYER pair, name
    s_load_b64 \pair, s[48:49], LK_\name
    s_wait_kmcnt 0
.endm

// 当前 layer 的计数器 -> s0:s1；64-bit 加法不能漏掉低位进位。
.macro LAYER_COUNTER offset
    s_add_u32 s0, s50, \offset
    s_addc_u32 s1, s51, 0
.endm
.macro TAIL_COUNTER offset
    s_add_u32 s0, s52, \offset
    s_addc_u32 s1, s53, 0
.endm

// 直接复用原 hx.handoff 的逻辑，暂时写成设备伪调用：
// s0:s1 = counter, s8 = hdev，固定 n=256；v63 = threadIdx.x。
// hdev=1：各 wave wait_storecnt0 → CTA barrier → t==0 atomic/poll → CTA barrier。
// hdev=0：保留原 release/acquire fences。poll 保留 timeout/cyc 报告。
// 注意 s_barrier 只覆盖一个 CTA，绝不能拿它替代此处 device-wide handoff。
.macro HANDOFF offset, hdev=1
    LAYER_COUNTER \offset
    s_mov_b32 s8, \hdev
    PSEUDO_FLYDSL device_handoff_256
.endm
.macro TAIL_HANDOFF offset
    TAIL_COUNTER \offset
    s_mov_b32 s8, 0
    PSEUDO_FLYDSL device_handoff_256
.endm
