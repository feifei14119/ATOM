# SPDX-License-Identifier: MIT
"""Per-stage asm budget + register binding tables (markdown) from stage_inputs.json and live48.json.

Binding rules (the stage_C fragment's convention): v0 = t (the asm derives l = t & 31 and w = readfirstlane(t) >> 5);
SGPR inputs from s0: i64 pointers as aligned pairs, then b, w, the i32 scalars, one flags word (bit k = the k-th bool);
past s29 they continue at s40 (s30..s39: LLVM's stack / return registers). Trace-time constants are baked into the text.
Usage: python3 bind_design.py build/budget/stage_inputs.json build/budget/live48.json > out.md"""
import json
import sys

CONST = set("MT SMEM TR QV RPC o NP topk ne nexp_max rms_eps hc_eps norm_eps hdev stx rank xcpol sm rk dn8_bi dn8_nct".split())
VREG = {"t", "l"}
I32 = set("b w kring_off ccap wcap cmain crpp cprow bstride irpp ilw imain scale".split())
BOOL = set("isffn first last merge eng xs32 iprod".split())
# positional parameters that are runtime values (others: trace-time)
PARAM_RT = {"stage_cgemm": {"r1": "bool"}, "stage_crow": {"r1": "bool"}, "stage_cring": {"r1": "bool"},
            "stage_score_any": {"isrx": "bool"}, "stage_select_any": {"lev": "i32", "mode": "i32"},
            "tp_allreduce": {"region": "i32", "tag": "i32"}, "ug_shared_early": {"bi": "i32"},
            "stage_tap1": {"j": "i32", "src": "ptr"}}
SKIP_IN_C = {"recv"}          # tp_allreduce: 4 pointers
CALL = {   # step.py call sites, function, tier (1: WMMA / GEMM compute, 2: elementwise / control / communication)
    "stage_A": ("307", 1, "x·wqkv_aᵀ（MXFP8 WMMA，N=1792 K=5120，K 两半）+ 收尾：bf16 qkv、平方和 ss、q·qnw → MXFP8 qr8/qrs"),
    "stage_kv": ("315", 2, "kv_norm(rstd·kvnw) + RoPE + QAT(e4m3 往返) → 写 KV ring（CTA 0..11）"),
    "stage_C": ("316", 1, "qr8·wq_bᵀ（MXFP8 WMMA，K=1280 N=8192）× rstd + RoPE → q（P2 已替换）"),
    "stage_D": ("367", 1, "稀疏注意力：K/q 异步拷 LDS，S=q·Kᵀ（bf16 WMMA）、softmax、P·V，cluster 合并 + sink + 反 RoPE → o8/os"),
    "stage_E": ("370", 1, "wo_a 分组低秩投影（MXFP8 WMMA，K=4096/4 切片）+ cluster 相加 → y8/ys"),
    "stage_F_cluster": ("373", 1, "wo_b 2048→5120（MXFP8 WMMA，K/4 切片）+ cluster 相加 → out + LDS[r][20]"),
    "tp_allreduce": ("376 / 449", 2, "TP all-reduce：bf16 打包推给 3 个对端 + 轮询求和 → y1/y2（通信）"),
    "stage_iq": ("322", 1, "indexer wq_b（FP8 WMMA，K=1280 N=4096）× rstd + RoPE → iq"),
    "stage_iw": ("323", 1, "weights_proj（bf16 WMMA，K 切片）× axn → iwp 部分和"),
    "stage_iquant": ("332", 2, "iw 切片求和；iq 按 amax 量化 e4m3 → iq_out/iqs_out/iw_out"),
    "stage_cgemm": ("327-328", 1, "compressor wkv_gate × axn（WMMA）→ cpart 部分和"),
    "stage_crow": ("343", 1, "压缩计划行：部分和归约、softmax 门控、norm/RoPE、投影（WMMA）→ main KV 行 + index 行"),
    "stage_cring": ("344", 2, "本步原始投影写 7 槽 ring（kv fp32、score+ape）"),
    "stage_score_any": ("359", 1, "indexer 打分：iq_out·index 行（FP8 WMMA）× iw，ReLU 加权 → ilog（FULL/REINDEX）"),
    "stage_select_any": ("365", 2, "两级选择树上的精确 top-k（基数/计数选择，非 GEMM）"),
    "stage_engq": ("304-306", 2, "Engram embedding → MXFP8 eng8/engs"),
    "stage_engkv": ("311-314", 1, "engkv = eng8·engwᵀ（MXFP8 WMMA，N=25600 K=6144）"),
    "front_any": ("422（hf 两遍）/ 144", 1, "整个 mHC front（A,B,|C,D,|E1,|E2，中间 3 个 cluster 屏障）"),
    "front_A": ("front.py:520 内", 2, "mHC post+pre（+Engram 门控）"),
    "front_B": ("front.py 内", 1, "R'·fn hi/lo → mHC mixes 部分和（bf16 WMMA）"),
    "front_C": ("front.py 内", 2, "RMSNorm×nw → MXFP8 x8/xs（+bf16 axn）"),
    "front_D": ("front.py 内（hf=0）", 1, "路由 logits 部分和（gate 320 列，WMMA）"),
    "front_E1": ("front.py 内（hf=0）", 2, "logits 归约 + sqrtsoftplus + 本地 top-6"),
    "front_E2": ("front.py 内", 2, "候选合并 → ids/wts；下一子层 mHC 系数（Sinkhorn）"),
    "ug_shared_early": ("434", 1, "front 闲置 CTA 先算共享专家 UG 的 K 切片（FP8 WMMA）"),
    "moe_union": ("443 → moe.py:817", 2, "专家并集 + pick 列表（排序网络，LDS）"),
    "moe_ug": ("443 → moe.py:819", 1, "UG：FP4×MXFP8 WMMA（路由）/ FP8×MXFP8（共享），SwiGLU → MID（MXFP8）"),
    "moe_dn_stage": ("443 → moe.py:823", 2, "MID 读入 LDS"),
    "moe_dn": ("443 → moe.py:825", 1, "down 投影（FP4×MXFP8 WMMA）× 路由权重 → out 部分和"),
    "moe_dn_shared": ("443 → moe.py:827", 1, "共享专家 down（FP8 WMMA）"),
    "moe_combine": ("447", 2, "6 个 pick + 共享相加 → LDS[r][20]"),
    "stage_tap1": ("455", 2, "aRout 4 路均值 → MXFP8 aux8/auxs"),
    "stage_block_state": ("232 / 260", 2, "embedding → 4 路初始状态"),
}
PROBE = {"front_any": "front_any#1", "front_A": "front_A#1", "front_B": "front_B#1", "front_C": "front_C#1",
         "front_E2": "front_E2#1", "front_D": "front_D#0", "front_E1": "front_E1#0", "tp_allreduce": "tp_allreduce#0"}
SG_LIMIT = 96


def sgprs():
    for i in list(range(30)) + list(range(40, 106)):
        yield i


def bind(name, info):
    keys = [k for k in info["keys"] if k not in CONST and k not in VREG]
    ptrs = [k for k in keys if k not in I32 and k not in BOOL and k not in SKIP_IN_C]
    if name == "tp_allreduce":
        ptrs += ["recv0", "recv1", "recv2", "recv3"]
    scal = [k for k in ("b", "w") if k in keys or k in info["keys"]] + \
           [k for k in keys if k in I32 and k not in ("b", "w")]
    bools = [k for k in keys if k in BOOL]
    for p, ty in PARAM_RT.get(name, {}).items():
        {"bool": bools, "i32": scal, "ptr": ptrs}[ty].append(p)
    if "w" not in scal:
        scal.insert(1 if "b" in scal else 0, "w")
    regs = sgprs()
    out = []
    nxt = next(regs)
    for p in ptrs:
        if nxt % 2:
            nxt = next(regs)
        a = nxt
        bb = next(regs)
        out.append((f"s[{a}:{bb}]", p, "i64"))
        nxt = next(regs)
    for s in scal:
        out.append((f"s{nxt}", s, "f32" if s == "scale" else "i32"))
        nxt = next(regs)
    if bools:
        out.append((f"s{nxt}", "flags", "bit " + ",".join(f"{i}:{b}" for i, b in enumerate(bools))))
        nxt = next(regs)
    if name == "stage_C":   # the implemented fragment (sp3/stage_c_full.sp3): s20 = the wave mask (MT baked as a mask)
        out = [("s[0:1]", "qr8", "i64"), ("s[2:3]", "wqb", "i64"), ("s[4:5]", "qrs", "i64"), ("s[6:7]", "wqb_s", "i64"),
               ("s[8:9]", "ss", "i64"), ("s[10:11]", "q", "i64"), ("s[12:13]", "rpos", "i64"), ("s[14:15]", "rcos", "i64"),
               ("s[16:17]", "rsin", "i64"), ("s18", "b", "i32"), ("s19", "w", "i32"), ("s20", "wave mask（MT 决定）", "i32")]
    nsg = sum(2 if t == "i64" else 1 for _, _, t in out)
    return out, nsg, ptrs, scal, bools


def main():
    S = json.load(open(sys.argv[1]))
    L = json.load(open(sys.argv[2]))
    rows = []
    for name, info in S.items():
        if name not in CALL:
            continue
        call, tier, what = CALL[name]
        pk = PROBE.get(name, name + "#0")
        lv = L.get(pk)
        out, nsg, ptrs, scal, bools = bind(name, info)
        rows.append((name, info, call, tier, what, lv, out, nsg, ptrs, scal, bools))
    print("## 1. stage 清单（tier 1 = WMMA/GEMM 计算密集，建议替换；tier 2 = 逐元素/控制/通信，可选）\n")
    print("| tier | stage | 定义 | step.py 调用 | 功能 |\n|---|---|---|---|---|")
    for name, info, call, tier, what, *_ in sorted(rows, key=lambda r: r[3]):
        print(f"| {tier} | `{name}` | `{info['module']}.py:{info['line']}` | {call} | {what} |")
    print("\n## 2. 寄存器预算（pre-RA liveness，48 行；keep = 跨 stage 必须保留，+N = 可重物化立即数）\n")
    print("| stage | keep S | keep V | in S/V | out S/V | SGPR 无溢出余量 96−keepS | 推荐 asm SGPR 预算 | 输入 SGPR（直接模式） | asm 临时 SGPR | asm 可用 VGPR（修复版 LLVM） |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, info, call, tier, what, lv, out, nsg, *_ in sorted(rows, key=lambda r: r[3]):
        k, i, o = lv["keep"], lv["inp"], lv["outp"]
        free = SG_LIMIT - k["s"]
        recn = min(max(free, 30), 60)
        rec = f"{recn}" if free >= 30 else "30（超出部分溢出到 VGPR lane）"
        tmp = recn - nsg
        tmps = str(tmp) if tmp >= 8 else f"{tmp} → 表模式 {recn - 6}"
        print(f"| `{name}` | {k['s']}+{k['s_imm']} | {k['v']}+{k['v_imm']} | {i['s']}/{i['v']} | {o['s']}/{o['v']} | "
              f"{free if free > 0 else '≤0'} | {rec} | {nsg} | {tmps} | v1–v{511 - k['v'] - k['v_imm']}（{511 - k['v'] - k['v_imm']}） |")
    print("\n## 3. 输入参数与寄存器绑定（直接指针模式；v0 = t）\n")
    for name, info, call, tier, what, lv, out, nsg, ptrs, scal, bools in sorted(rows, key=lambda r: r[3]):
        consts = [k for k in info["keys"] if k in CONST]
        rt_params = PARAM_RT.get(name, {})
        tconst = [p for p in info["params"][1:] if p not in rt_params]
        over = " **（超出 s0–s29，建议表模式）**" if nsg > 30 else ""
        print(f"### `{name}`（tier {tier}，{nsg} 个 SGPR 输入{over}）\n")
        print(f"- trace 期常量（写入 asm 文本）：{' '.join(consts + tconst) or '—'}")
        print("- 绑定：`v0`=t；" + "；".join(f"`{r}`={n}" + ("" if t in ("i64", "i32") else f"（{t}）") for r, n, t in out))
        print()


if __name__ == "__main__":
    main()
