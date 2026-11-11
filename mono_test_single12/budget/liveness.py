# SPDX-License-Identifier: MIT
"""Pre-RA liveness at the `; probe: <stage>#<k>:in|out` marks of a MIR file (llc -stop-before=greedy).

Per stage call: L_in / L_out = the 32-bit (virtual register, lane) units live at its two marks, split into SGPR / VGPR.
  keep = L_in & L_out    live across the stage: the asm replacing it must leave these intact
  in   = L_in - L_out    dead after the stage: its inputs (and values only it reads)
  out  = L_out - L_in    born in the stage: its outputs (or values hoisted into it)
Units whose every def is an immediate move / IMPLICIT_DEF are counted apart (+imm): the allocator rematerializes them.
Adapted from /tmp/k2probe/liveness.py (the K2 analysis). Usage: python3 liveness.py pre.mir [--json out.json]
"""
import json
import re
import sys
from collections import defaultdict

BB = re.compile(r'^\s*bb\.(\d+)')
SUCC = re.compile(r'%bb\.(\d+)')
REGDECL = re.compile(r'-\s*\{\s*id:\s*(\d+),\s*class:\s*([\w]+)')
OPND = re.compile(r'((?:implicit-def|early-clobber|def|implicit|undef|killed|dead|renamable|internal)\s+)*%(\d+)(\.[\w]+)?(?::([\w]+))?')
MARK = re.compile(r'INLINEASM &"; probe: ([^"]*)"')
REMAT = re.compile(r'^(S_MOV_B32|S_MOV_B64|S_MOV_B64_IMM_PSEUDO|V_MOV_B32_e32|V_MOV_B32_e64|V_MOV_B64_PSEUDO|V_MOV_B64_e32|IMPLICIT_DEF)\b')


def width(cls):
    m = re.search(r'_(\d+)', cls)
    return max(1, (int(m.group(1)) if m else 32) // 32)


def kind(cls):
    if 'sgpr' in cls or 'sreg' in cls:
        return 's'
    if 'vgpr' in cls or 'vreg' in cls or cls.startswith('av_') or 'agpr' in cls:
        return 'v'
    return None


def lanes(sub, w):
    if not sub:
        return range(w)
    idx = sorted({int(x) for x in re.findall(r'sub(\d+)', sub)})   # AMDGPU names every lane: sub0_sub1_sub2_sub3
    return idx or [0]


def parse(path):
    classes, blocks, order, cur, seq, in_body = {}, {}, [], None, [], False
    for line in open(path):
        if not in_body:
            m = REGDECL.search(line)
            if m:
                classes[int(m.group(1))] = m.group(2)
            if line.startswith('body:'):
                in_body = True
            continue
        m = BB.match(line)
        if m and line.rstrip().endswith(':'):
            cur = int(m.group(1))
            blocks[cur] = dict(succ=[], ins=[])
            order.append(cur)
            continue
        if cur is None:
            continue
        s = line.strip()
        if s.startswith('successors:'):
            blocks[cur]['succ'] = [int(x) for x in SUCC.findall(s)]
            continue
        if not s or s.startswith(('liveins:', ';', '#', '...', '---')):
            continue
        mk = MARK.search(s)
        seq.append((cur, ('mark', mk.group(1)) if mk else ('raw', s)))
    remat_ok = defaultdict(lambda: True)
    staged = []
    for cur, (tag, s) in seq:
        if tag == 'mark':
            staged.append((cur, ('mark', s)))
            continue
        lhs, _, rhs = s.partition(' = ') if ' = ' in s else ('', '', s)
        defs, uses = [], []
        for m in OPND.finditer(lhs):
            reg, sub, cls = int(m.group(2)), m.group(3), m.group(4)
            if cls:
                classes.setdefault(reg, cls)
            defs.append((reg, sub))
        for m in OPND.finditer(rhs):
            flags, reg, sub, cls = m.group(0), int(m.group(2)), m.group(3), m.group(4)
            if cls:
                classes.setdefault(reg, cls)
            if re.search(r'\b(implicit-def|def)\s', flags):
                defs.append((reg, sub))
            elif 'undef' not in flags:
                uses.append((reg, sub))
        imm = bool(REMAT.match(rhs)) and not uses
        for reg, _ in defs:
            remat_ok[reg] = remat_ok[reg] and imm
        staged.append((cur, ('op', defs, uses)))

    def expand(items):
        out = set()
        for reg, sub in items:
            c = classes.get(reg)
            if c and kind(c):
                out.update((reg, l) for l in lanes(sub, width(c)))
        return out
    defined = set()
    for cur, ins in staged:
        if ins[0] == 'op':
            defined |= expand(ins[1])
    for cur, ins in staged:
        blocks[cur]['ins'].append(ins if ins[0] == 'mark' else ('op', expand(ins[1]), expand(ins[2]) & defined))
    return classes, blocks, order, remat_ok


def live_at_marks(classes, blocks, order):
    gen, kill = {}, {}
    for b, blk in blocks.items():
        g, k = set(), set()
        for ins in reversed(blk['ins']):
            if ins[0] == 'op':
                _, d, u = ins
                g -= d
                k |= d
                g |= u
        gen[b], kill[b] = g, k
    live_in = defaultdict(set)
    changed = True
    while changed:
        changed = False
        for b in reversed(order):
            succ = blocks[b]['succ']
            out = set().union(*(live_in[s] for s in succ)) if succ else set()
            new = gen[b] | (out - kill[b])
            if new != live_in[b]:
                live_in[b] = new
                changed = True
    # path-wise may-defined (forward), as LiveIntervals: no live range along a path no def of the unit reaches
    preds = defaultdict(list)
    for b in order:
        for s in blocks[b]['succ']:
            preds[s].append(b)
    def_out = defaultdict(set)
    changed = True
    while changed:
        changed = False
        for b in order:
            din = set().union(*(def_out[p] for p in preds[b])) if preds[b] else set()
            new = din | kill[b]
            if new != def_out[b]:
                def_out[b] = new
                changed = True
    def_at = {}
    for b in order:
        dset = set().union(*(def_out[p] for p in preds[b])) if preds[b] else set()
        for ins in blocks[b]['ins']:
            if ins[0] == 'mark':
                def_at[ins[1]] = frozenset(dset)
            else:
                dset |= ins[1]
    at = {}
    for b in order:
        succ = blocks[b]['succ']
        live = set().union(*(live_in[s] for s in succ)) if succ else set()
        for ins in reversed(blocks[b]['ins']):
            if ins[0] == 'mark':
                at[ins[1]] = (frozenset(live) & def_at[ins[1]], b)
            else:
                _, d, u = ins
                live -= d
                live |= u
    return at


def count(units, classes, remat_ok):
    c = defaultdict(int)
    for reg, _ in units:
        c[kind(classes[reg]) + ('i' if remat_ok[reg] else '')] += 1
    return dict(s=c['s'], s_imm=c['si'], v=c['v'], v_imm=c['vi'])


def main(path, out_json=None):
    classes, blocks, order, remat_ok = parse(path)
    at = live_at_marks(classes, blocks, order)
    stages = sorted({m.rsplit(':', 1)[0] for m in at}, key=lambda s: min(order.index(at[f"{s}:{p}"][1]) for p in ("in", "out")
                                                                       if f"{s}:{p}" in at))
    rows = {}
    for s in stages:
        if f"{s}:in" not in at or f"{s}:out" not in at:
            print(f"{s}: missing a mark", file=sys.stderr)
            continue
        li, lo = at[f"{s}:in"][0], at[f"{s}:out"][0]
        rows[s] = dict(L_in=count(li, classes, remat_ok), L_out=count(lo, classes, remat_ok),
                       keep=count(li & lo, classes, remat_ok), inp=count(li - lo, classes, remat_ok),
                       outp=count(lo - li, classes, remat_ok))
    hdr = f'{"stage":22s} | {"keep S":>9s} {"keep V":>9s} | {"in S":>8s} {"in V":>8s} | {"out S":>8s} {"out V":>8s} | {"Lin S":>6s} {"Lin V":>6s}'
    print(hdr)
    fmt = lambda d, k: f"{d[k]}" + (f"+{d[k + '_imm']}" if d[k + '_imm'] else "")
    for s, r in rows.items():
        print(f'{s:22s} | {fmt(r["keep"], "s"):>9s} {fmt(r["keep"], "v"):>9s} | {fmt(r["inp"], "s"):>8s} {fmt(r["inp"], "v"):>8s} | '
              f'{fmt(r["outp"], "s"):>8s} {fmt(r["outp"], "v"):>8s} | {r["L_in"]["s"]:6d} {r["L_in"]["v"]:6d}')
    if out_json:
        json.dump(rows, open(out_json, "w"), indent=1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
