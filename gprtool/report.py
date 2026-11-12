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
    out = ["| stage | 跨 asm 保留 V / S（R0） | 保留窗口 V / S | 最终构建跨 asm 活跃 V / S | asm 可用 VGPR | asm 可用 SGPR "
           "| 可 clobber 的特殊寄存器 |",
           "|---|---|---|---|---|---|---|"]
    for tag, p in c["points"].items():
        w, a, f = p["window"], p["asm"], p["through_final"]
        out.append(f"| `{stage(tag)}` | {p['keep_r0']['v']} / {p['keep_r0']['s']} | {w['v']} / {w['s']} | "
                   f"{f['v']} / {f['s']} | "
                   f"**{a['v']}**：`{a['v_regs']}` | **{a['s']}**：`{a['s_regs']}` | "
                   f"{' '.join(f'`{x}`' for x in a['x']) or '无'} |")
    out += ["", "| stage | 输入（只读 VGPR / 可改写 SGPR） | 输入 SGPR 数 |", "|---|---|---|"]
    for tag, p in c["points"].items():
        ins = " ".join(f"`{b['name']}={b['reg']}`" for b in p["inputs"])
        out.append(f"| `{stage(tag)}` | {ins} | {p['inputs_s']} |")
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
                f"R0（替换、无 clobber）溢出 {c['spills_r0']}，最终 {c['spills_final']}"
                f"（VGPR scratch 指令数、SGPR↔VGPR lane 指令数、承载 SGPR 溢出的 WWM VGPR），"
                f"容差 VGPR {c.get('vtol')} / SGPR {c.get('stol')}；最终 notes {c['notes_final']}", ""]
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
