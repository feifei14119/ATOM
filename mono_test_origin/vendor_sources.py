#!/usr/bin/env python3
"""Regenerate the isolated source subset; never compile or launch a kernel.

Only maintainers need Git. run.sh uses the committed mono1250/ files directly.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import tarfile
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMIT = "7c925f72b22ee6a815fd6d63734bbcff5fa72a08"
BASE = "atom/models/deepseek_v41/mono/"
FILES = {
    **{f"atom/mono/{p}.py": f"mono1250/{p}.py" for p in (
        "device/ops", "device/mx", "device/sync", "plan/execution",
        "plan/layout", "plan/trace", "plan/shard", "plan/arith", "plan/check",
        "runtime/compile",
    )},
    **{f"{BASE}gfx1250/kernels/{p}.py": f"mono1250/kernels/{p}.py" for p in (
        "reference_k1", "reference_norm", "reference_projection",
        "reference_plan", "reference_sync",
    )},
    f"{BASE}kernels/dims.py": "mono1250/kernels/dims.py",
    f"{BASE}index_plan.py": "mono1250/index_plan.py",
    f"{BASE}kernels/attn_pre.py": "mono1250/kernels/attn_helpers.py",
}
ROOT_SYMBOLS = set("""MIX KT PART HIDDEN SLICES EPS X8_WORDS QKV_ROWS COLS K_MIX
ld_f32 ld_bf fma lds_row poll_copy batched_rounds bf16_round first_rounds
slice_issued slice_loads slice_row slice_input""".split())


def extract_helpers(source):
    """Select whole, verbatim definitions and their dependencies using AST names.

    attn_pre also imports model deployment/attention/MoE modules. None is needed
    for these slice/load helpers. No function body is rewritten by this step.
    """
    tree = ast.parse(source)
    definitions, imports = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            definitions[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        definitions[name.id] = node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = node
    needed = set(ROOT_SYMBOLS)
    while True:
        expanded = set(needed)
        for name in needed:
            if name in definitions:
                expanded.update(n.id for n in ast.walk(definitions[name])
                                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                                and n.id in definitions.keys() | imports.keys())
        if expanded == needed:
            break
        needed = expanded
    selected = {id(definitions[n]) for n in needed if n in definitions}
    lines = source.splitlines(keepends=True)
    pieces = ["# SPDX-License-Identifier: MIT\n",
              "# Copyright (C) 2026, Advanced Micro Devices, Inc. All rights reserved.\n",
              '# Selected verbatim definitions from pinned attn_pre.py; see SOURCE_MANIFEST.json.\n']
    ranges = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a for a in node.names if (a.asname or a.name.split(".")[0]) in needed]
            if names:
                if isinstance(node, ast.Import):
                    reduced = ast.Import(names=names)
                else:
                    reduced = ast.ImportFrom(module=node.module, names=names, level=node.level)
                pieces.append(ast.unparse(reduced) + "\n")
        elif id(node) in selected:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            pieces.append("\n\n" + "".join(lines[start - 1:node.end_lineno]))
            ranges.append([start, node.end_lineno])
    return "".join(pieces) + "\n", ranges


def remap(source):
    for old, new in (
        ("atom.models.deepseek_v41.mono.kernels.attn_pre", "mono1250.kernels.attn_helpers"),
        ("atom.models.deepseek_v41.mono.gfx1250.kernels", "mono1250.kernels"),
        ("atom.models.deepseek_v41.mono.kernels", "mono1250.kernels"),
        ("atom.models.deepseek_v41.mono", "mono1250"),
        ("atom.mono", "mono1250"),
    ):
        source = source.replace(old, new)
    return source


def main():
    manifest = {"repository": "https://github.com/ROCm/ATOM", "commit": COMMIT,
                "files": [], "generated_packages": []}
    originals = []
    for origin, destination in FILES.items():
        raw = subprocess.check_output(["git", "show", f"{COMMIT}:{origin}"], cwd=ROOT.parent)
        originals.append((origin, raw))
        source = raw.decode()
        record = {"upstream": origin, "local": destination,
                  "upstream_sha256": hashlib.sha256(raw).hexdigest()}
        if destination.endswith("attn_helpers.py"):
            source, record["selected_line_ranges"] = extract_helpers(source)
        source = remap(source)
        if destination.endswith("reference_projection.py"):
            old = '{"lin": 1, "pmix": 2, "x8": 3, "x8s": 4, "nb": 5, "qkv": 6}, failure)'
            if source.count(old) != 1:
                raise RuntimeError("Upstream mailbox call changed")
            source = source.replace(old, old[:-1] + ", diagnostic=True)")
            record["adaptation"] = "Enable existing bounded diagnostic mailbox; compute stages unchanged."
        target = ROOT / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
        record["local_sha256"] = hashlib.sha256(source.encode()).hexdigest()
        manifest["files"].append(record)
    for directory in sorted({p.parent for p in (ROOT / "mono1250").rglob("*.py")}):
        init = directory / "__init__.py"
        init.write_text('"""Isolated ATOM PR #2908 source subset; no model engine imports."""\n')
        manifest["generated_packages"].append(str(init.relative_to(ROOT)))
    license_bytes = subprocess.check_output(["git", "show", f"{COMMIT}:LICENSE"], cwd=ROOT.parent)
    (ROOT / "UPSTREAM_LICENSE").write_bytes(license_bytes)
    # Retain pristine inputs for offline review/regeneration of diffs on another machine.
    with tarfile.open(ROOT / "upstream_sources.tar.gz", "w:gz") as archive:
        for name, raw in originals:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(raw), 0o644, 0
            archive.addfile(info, io.BytesIO(raw))
    (ROOT / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(FILES)} isolated modules. No imports, compilation or GPU execution.")


if __name__ == "__main__":
    main()
