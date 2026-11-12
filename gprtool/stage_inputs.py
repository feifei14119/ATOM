# SPDX-License-Identifier: MIT
"""The stage dict keys (c["k"] / c.get("k")) each candidate stage reads, following same-module helpers that receive c,
plus its positional parameters. Usage: python3 stage_inputs.py [--json out.json]"""
import ast
import json
import sys
from pathlib import Path

KDIR = Path("/app/ATOM/atom/models/deepseek_v41/mono/gfx1250/kernels")
STAGES = [
    ("attention", "stage_A"), ("attention", "stage_kv"), ("attention", "stage_C"), ("attention", "stage_D"),
    ("attention", "stage_E"), ("attention", "stage_F_cluster"), ("attention", "tp_allreduce"),
    ("index_query", "stage_iq"), ("index_query", "stage_iw"), ("index_query", "stage_iquant"),
    ("compressor", "stage_cgemm"), ("compressor", "stage_crow"), ("compressor", "stage_cring"),
    ("index_score", "stage_score_any"), ("topk", "stage_select_any"), ("engram", "stage_engq"), ("engram", "stage_engkv"),
    ("front", "front_any"), ("front", "front_A"), ("front", "front_B"), ("front", "front_C"), ("front", "front_D"),
    ("front", "front_E1"), ("front", "front_E2"),
    ("moe", "ug_shared_early"), ("moe", "moe_union"), ("moe", "moe_ug"), ("moe", "moe_dn_stage"), ("moe", "moe_dn"),
    ("moe", "moe_dn_shared"), ("moe", "moe_combine"), ("draft_ctx", "stage_tap1"), ("draft_ctx", "stage_block_state"),
]


def funcs(mod):
    """mod's functions, then (not shadowing) every other kernel module's: helpers imported across modules (rope_cs, ...)."""
    tab = {}
    for p in [KDIR / f"{mod}.py"] + sorted(KDIR.glob("*.py")):
        tree = ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef):
                tab.setdefault(n.name, n)
    return tab


def keys_of(fn, table, seen):
    if fn.name in seen:
        return set(), []
    seen.add(fn.name)
    cname = fn.args.args[0].arg if fn.args.args else None
    keys, calls = set(), []
    for n in ast.walk(fn):
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str) and n.value.id in (cname, "c", "cu", "cd", "ce", "cc", "ci"):
            if not isinstance(n.ctx, ast.Store):
                keys.add(n.slice.value)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == cname and n.args \
                and isinstance(n.args[0], ast.Constant):
            keys.add(n.args[0].value)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in table and n.func.id != fn.name:
            if any(isinstance(a, ast.Name) and a.id == cname for a in n.args) or \
                    any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in ("dict", "cwith")
                        for a in n.args):
                calls.append(n.func.id)
    for cn in calls:
        k2, _ = keys_of(table[cn], table, seen)
        keys |= k2
    return keys, calls


def main():
    out = {}
    for mod, name in STAGES:
        table = funcs(mod)
        fn = table[name]
        keys, calls = keys_of(fn, table, set())
        out[name] = dict(module=mod, line=fn.lineno, params=[a.arg for a in fn.args.args], helpers=calls,
                         keys=sorted(keys))
        print(f"{mod}.py:{fn.lineno} {name}({', '.join(a.arg for a in fn.args.args)})  helpers={calls}\n    keys: {' '.join(sorted(keys))}")
    if "--json" in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
