# SPDX-License-Identifier: MIT
"""Markdown tables (zh-CN) of the gprtool results: build/gpr/{contract,analyze,verify,limit}.json -> stdout."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(work, name):
    p = Path(work) / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def stage(tag):
    return tag.split("#")[0] + ("" if tag.endswith("#0") else f"（第 {int(tag.split('#')[1]) + 1} 次调用）")


def contract_tables(c):
    f = lambda d: f"{d['v']} / {d['s']}"
    out = ["| stage | 调用前活跃 V / S | 调用后活跃 V / S | 跨调用须保留 V / S（R0 → 最终） | 入参绑定 V / S | 保留窗口 V / S "
           "| 调用后 VGPR scratch | asm 可用 VGPR | asm 可用 SGPR（含可改写的入参） | 可 clobber 的特殊寄存器 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for tag, p in c["points"].items():
        w, a = p["window"], p["asm"]
        out.append(f"| `{stage(tag)}` | {f(p['before_final'])} | {f(p['after_final'])} | "
                   f"{f(p['keep_r0'])} → {f(p['through_final'])} | {p['inputs_v']} / {p['inputs_s']} | "
                   f"{w['v']} / {w['s']}：`{w['v_regs']}` `{w['s_regs']}` | {p['vgpr_scratch_after'] or ''} | "
                   f"**{a['v']}**：`{a['v_regs']}` | **{a['s']}**：`{a['s_regs']}` | "
                   f"{' '.join(f'`{x}`' for x in a['x']) or '无'} |")
    out += ["", "| stage | 入参绑定（VGPR 只读 / SGPR 可改写） |", "|---|---|"]
    for tag, p in c["points"].items():
        ins = " ".join(f"`{b['name']}={b['reg']}`" for b in p["inputs"])
        out.append(f"| `{stage(tag)}` | {ins} |")
    return out


def analyze_table(a):
    f = lambda d: f"{d['v']} / {d['s']}"
    out = ["| 插入点 | 入口活跃 V / S | 出口活跃 V / S | 贯穿 stage V / S | 其中立即数常量 V / S |",
           "|---|---|---|---|---|"]
    for tag, p in a["points"].items():
        if "error" in p:
            out.append(f"| `{stage(tag)}` | {p['error']} | | | |")
            continue
        out.append(f"| `{stage(tag)}` | {f(p['in_before'])} | {f(p['out_after'])} | {f(p['through'])} | "
                   f"{f(p['through_remat'])} |")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", default=str(HERE / "build" / "gpr"))
    args = ap.parse_args()
    c, a, v, lim = (load(args.work, n) for n in ("contract", "analyze", "verify", "limit"))
    out = []
    if c:
        out += ["## 契约（替换后的 kernel）", "",
                f"SGPR spill：R0（替换、无 clobber）{c['spills_r0']['sgpr']}，最终 {c['spills_final']['sgpr']}（硬性要求为 0）；"
                f"VGPR scratch 指令：R0 {c['spills_r0']['vgpr']}，最终 {c['spills_final']['vgpr']}"
                f"（按所在区域 {c['vgpr_scratch_final_by_region']}）；SGPR 窗口全局余量 {c['sgpr_slack']}；"
                f"最终 notes {c['notes_final']}", ""]
        out += contract_tables(c) + [""]
    if a:
        out += ["## 原生 kernel 的活跃寄存器", "", f"预留 {a['reserved']}，溢出 {a['spills']}", ""]
        out += analyze_table(a) + [""]
    if v:
        g = v["poison"].get("golden", {}).get("rel_l2")
        out += ["## 运行时验证", "",
                f"- 毒化 {v['poisoned_points']} 个插入点：{v['poisoned_vgpr_writes']} 次 VGPR 写、"
                f"{v['poisoned_sgpr_writes']} 次 SGPR 写；结果 pass={v['poison']['pass']}，相对 golden 的 rel L2 {g}"
                f"（容差 {v['noise_rtol']}：{'在噪声内' if v['poison_within_noise'] else '超出'}）",
                f"- 负对照 `{v['negative']['tag']}` 同时毒化 {v['negative']['live_vgprs']} 个活跃 VGPR：rc "
                f"{v['negative']['rc']}", ""]
    if lim:
        out += ["## VGPR 上限", ""]
        out += [f"- v{int(n) - 1}：{r.get('note') or ('rc %s pass %s %s vgpr_count %s' % (r['rc'], r['pass'], r['errors'], r['notes']['vgpr_count']))}"
                for n, r in lim.items()]
    print("\n".join(out))


if __name__ == "__main__":
    main()
