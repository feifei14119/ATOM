# SPDX-License-Identifier: MIT
"""GPR budget of the mono step kernel's stage insertion points, from the compiled code and a GPU run.

  analyze   the native kernel (every stage wrapped by markers): registers live just before / after each insertion
            point and through each stage, from post-RA MIR (the register allocator's own liveness)
  contract  every stage of --replace becomes one asm with its real inputs (v0 = t read-only, SGPRs tied: the asm
            may overwrite them) that clobbers every register outside its kept window. SGPR spill (to VGPR lanes or
            to scratch) is forbidden: none in the build with no clobber (else an error with the spill sites), none
            in the final one. Kept window per insertion point: VGPRs = those live across it (+ --vslack; the top of
            v0..v{limit-1}; what does not fit goes to scratch, a warning), SGPRs = those live across it plus the
            smallest slack with no SGPR spill (the top of the usable ones). Report: live before / after / across,
            input bindings, the asm's registers
  verify    GPU run of the analyze build whose markers overwrite every register the analysis reports dead, each
            declared clobbered (the post-RA scheduler moves ALU code across an asm with no register dependency on
            it), vs a golden run; the allocation must stay the native one (checked); a negative control also
            overwrites the live ones at one executed point
  limit     GPU launch with one asm declaring v{n-1} clobbered (the kernel's VGPR count becomes n): the largest
            VGPR an asm may touch in this kernel (its 256-thread workgroup must fit a SIMD's VGPR file)
(report.py: the markdown tables of the budget doc from the json results.)

Every build: FlyDSL hands its LLVM bitcode to the fixed LLVM (/app/llvm-upstream/build: gfx1250 inline asm clobbers
v256..v1023 honored), the post-RA MIR is `llc -O2 -stop-before=prolog-epilog` of that bitcode (the kernel's own code).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mir  # noqa: E402
from regs import LLVM, ranges, split  # noqa: E402

TIER1 = ["stage_A", "stage_C", "stage_D", "stage_E", "stage_F_cluster", "stage_iq", "stage_iw", "stage_cgemm",
         "stage_crow", "stage_score_any", "stage_engkv", "front_B", "front_D", "ug_shared_early", "moe_ug", "moe_dn",
         "moe_dn_shared"]
XCLOB = ["vcc_lo", "vcc_hi", "scc"]  # wave32: vcc_hi is an allocatable SGPR (the compiler keeps values in it)


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def env(llvm):
    e = dict(os.environ)
    e.update(PYTHONPATH=f"/app/flydsl_overlay:/app/ATOM", FLYDSL_COMPILE_LLVM_DIR=str(llvm),
             FLYDSL_COMPILE_LLVM_HANDOFF="llvm", FLYDSL_RUNTIME_ENABLE_CACHE="0", FLYDSL_DUMP_IR="1")
    return e


def notes(hsaco, llvm):
    out = subprocess.run([str(llvm / "bin/llvm-readobj"), "--notes", str(hsaco)], capture_output=True, text=True).stdout
    r = {}
    for k in ("vgpr_count", "sgpr_count", "vgpr_spill_count", "sgpr_spill_count", "private_segment_fixed_size"):
        m = re.search(rf"\.{k}:\s+(\d+)", out)
        r[k] = int(m.group(1)) if m else None
    return r


def build(plan, out, args, run=False, extra=()):
    """FlyDSL build (+ GPU run) of probe.py with `plan` -> out/: bitcode, hsaco, post-RA MIR, bindings, result."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "plan.json").write_text(json.dumps(plan))
    e = env(args.llvm)
    e.update(GPRTOOL_PLAN=str(out / "plan.json"), GPRTOOL_BIND=str(out / "bind.json"), FLYDSL_DUMP_DIR=str(out / "dump"))
    if args.patch:
        e["GPRTOOL_PATCH"] = str(Path(args.patch).resolve())
    if not run:
        e["COMPILE_ONLY"] = "1"
    cmd = [sys.executable, str(HERE / "probe.py"), "--rows", str(args.rows), "--layers", str(args.layers),
           "--repeat", str(args.repeat if run else 1), "--out", str(out / "result.json"), *extra]
    t0 = time.time()
    with open(out / "log.txt", "w") as f:
        rc = subprocess.run(cmd, env=e, stdout=f, stderr=subprocess.STDOUT, timeout=args.timeout).returncode
    d = out / "dump" / "body_0"
    bc, hs = d / "20_external_binary.bc", d / "20_external_binary.hsaco"
    info = dict(rc=rc, seconds=round(time.time() - t0, 1), built=hs.exists())
    if hs.exists():
        mir.post_ra_mir(bc, out / "post.mir", args.llvm)
        info["notes"] = notes(hs, args.llvm)
    if run and (out / "result.json").exists():
        info["result"] = json.loads((out / "result.json").read_text())
    (out / "info.json").write_text(json.dumps(info, indent=1))
    log(f"build {out.name}: rc {rc}, {info['seconds']} s, notes {info.get('notes')}")
    return info


def tag_of(prefix):
    def f(text):
        m = re.match(r"; gpr: (\S+)", text)
        return m.group(1) if m else None
    return f


def liveness(out):
    blocks, order, reserved = mir.parse(Path(out) / "post.mir")
    at = mir.marker_liveness(blocks, order, tag_of("gpr"))
    return blocks, order, reserved, at


def S(us, reserved=()):
    us = set(us) - set(reserved)
    v, s, o = split(us)
    return dict(v=len(v), s=len(s), v_regs=ranges(v, "v"), s_regs=ranges(s, "s"), other=o)


# ------------------------------------------------------------------ analyze (native kernel, wrapped stages)
def cmd_analyze(args):
    out = Path(args.work) / "analyze"
    info = build({"mode": "wrap"}, out, args)
    blocks, order, reserved, at = liveness(out)
    res = {"info": info, "reserved": sorted(reserved), "spills": mir.spill_counts(blocks), "points": {}}
    tags = sorted({t.rsplit(":", 1)[0] for t in at}, key=lambda t: min(e["block"] for e in at[t + ":in"]))
    for st in tags:
        ein, eout = at.get(st + ":in", []), at.get(st + ":out", [])
        if len(ein) != 1 or len(eout) != 1:
            res["points"][st] = {"error": f"{len(ein)} in / {len(eout)} out markers"}
            continue
        i, o = ein[0], eout[0]
        rdefs = mir.region_defs(blocks, (i["block"], i["index"]), (o["block"], o["index"]))
        through = (i["after"] & o["before"]) - rdefs
        res["points"][st] = {
            "in_before": S(i["before"], reserved), "in_after": S(i["after"], reserved),
            "out_before": S(o["before"], reserved), "out_after": S(o["after"], reserved),
            "through": S(through, reserved), "through_remat": S(mir.remat_units(blocks, (i["block"], i["index"]), through)),
        }
    sp = spills(out)
    res["vgpr_scratch_by_region"] = by_region(sp["sites"], "vgpr")
    res["sgpr_spill_sites"] = [s for s in sp["sites"] if s["kind"].startswith("sgpr")]
    (Path(args.work) / "analyze.json").write_text(json.dumps(res, indent=1))
    log(f"analyze: {len(res['points'])} insertion points, reserved {sorted(reserved)}, spills {res['spills']}")
    if sp["vgpr"]:
        log(f"WARNING: VGPR scratch {sp['vgpr']} instructions, by region: {res['vgpr_scratch_by_region']}")
    if sp["sgpr"] or sp["wwm"]:
        sgpr_spill_error(sp, "native kernel")
        sys.exit(2)


# ------------------------------------------------------------------ contract (replaced stages)
def windows(K, reserved, limit, usable_s, layout="top"):
    """Per tag: the kept VGPR window and SGPR window (top of the usable SGPRs). VGPRs: "top": the top K of
    v0..limit-1 plus the WWM registers (SGPR spill lanes) where R0 put them; "top-packed": the top K + number of WWM
    registers, which move into it; "low": v1..v{K + number of WWM registers}. With the last two the asm's VGPRs
    are one contiguous range."""
    rv = split(reserved)[0]
    w = {}
    for tag, (kv, ks) in K.items():
        if layout == "low":
            vw = list(range(1, 1 + kv + len(rv)))
        elif layout == "top-packed":
            vw = list(range(limit - kv - len(rv), limit))
        else:
            top = [n for n in range(limit - 1, -1, -1) if n not in rv][:kv]
            vw = sorted(set(top) | set(rv))
        sw = usable_s[len(usable_s) - ks:] if ks else []
        w[tag] = (vw, sw)
    return w


def contract_plan(base, W, binds, limit, usable_s, xclob):
    con = {}
    for tag, (vw, sw) in W.items():
        taken = {r for b in binds.get(tag, []) for r in expand(b["reg"])}
        con[tag] = {"clobber_v": [n for n in range(limit) if n not in vw and f"v{n}" not in taken],
                    "clobber_s": [n for n in usable_s if n not in sw and f"s{n}" not in taken],
                    "clobber_x": xclob.get(tag, XCLOB)}
    return dict(base, contracts=con)


def expand(reg):
    m = re.fullmatch(r"([vs])\[(\d+):(\d+)\]", reg)
    if m:
        return [f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(3)) + 1)]
    return [reg]


def read_only(binds):
    return {u for b in binds if not b.get("writable", True) for u in expand(b["reg"])}


def spills(out):
    """Spill instructions of a build: counts per kind (+ "sgpr", "vgpr" totals), the WWM VGPRs (SGPR spill lanes),
    the sites (region = the last marker before the instruction)."""
    blocks, order, res = mir.parse(Path(out) / "post.mir")
    c = mir.spill_counts(blocks)
    return dict(sgpr=c["sgpr"], vgpr=c["vgpr"], counts=c, wwm=split(res)[0],
                sites=mir.spill_sites(blocks, order, tag_of("gpr")))


def by_region(sites, prefix):
    r = {}
    for s in sites:
        if s["kind"].startswith(prefix):
            r[s["region"] or "(entry)"] = r.get(s["region"] or "(entry)", 0) + 1
    return r


def sgpr_spill_error(sp, where):
    log(f"ERROR {where}: {sp['sgpr']} SGPR spill instructions {sp['counts']} (SGPR spill is forbidden; with "
        f"--patch patches/zero_sgpr_spill.py the native kernel has none). Sites (region: defining instruction):")
    for s in sp["sites"]:
        if s["kind"] in ("sgpr_to_vgpr_lane", "sgpr_scratch_save"):
            log(f"  {s['region']}: {s['defn']}")


def cmd_contract(args):
    work = Path(args.work)
    base = {"mode": "replace", "replace": args.replace}
    r0 = build(base, work / "c_r0", args)
    blocks, order, reserved, at = liveness(work / "c_r0")
    binds = json.loads((work / "c_r0" / "bind.json").read_text())["bindings"]
    reserved = set(reserved) | {"s102", "s103"}
    usable_s = [n for n in range(106) if f"s{n}" not in reserved]
    sp0 = spills(work / "c_r0")
    log(f"r0: reserved {sorted(reserved)}, spills {sp0['counts']}")
    if sp0["sgpr"] or sp0["wwm"]:
        # every asm clobbers what is not kept: no window can make room for SGPRs the kernel spills with no clobber
        sgpr_spill_error(sp0, "r0 (stages replaced, no clobber)")
        (work / "contract.json").write_text(json.dumps(
            {"error": "sgpr spill in r0", "spills_r0": sp0["counts"], "sites_r0": sp0["sites"]}, indent=1))
        sys.exit(2)
    K, R, X = {}, {}, {}
    for tag, es in at.items():
        if ":" in tag:
            continue
        e = es[0]
        through = e["after"] - e["defs"]
        th = set(through) - reserved - read_only(binds.get(tag, []))
        rm = mir.remat_units(blocks, (e["block"], e["index"]), th)
        v, s, o = split(th)
        rv, rs, _ = split(rm)
        K[tag] = (len(v), len(s))
        R[tag] = (len(v) - len(rv), len(s) - len(rs))
        X[tag] = [x for x in XCLOB if x not in o]
    # VGPR windows: exactly the kept VGPRs (what does not fit goes to scratch: a warning). SGPR windows: the kept
    # SGPRs, plus the smallest global slack with no SGPR spill, then per point back to no slack where that keeps none
    hist, n = [], [0]
    nin = {t: len({u for b in binds.get(t, []) for u in expand(b["reg"]) if u[0] == "s"}) for t in K}

    def trial(cur):
        name = f"c_try{n[0]}"
        n[0] += 1
        W = windows(cur, reserved, args.limit, usable_s, args.vlayout)
        info = build(contract_plan(base, W, binds, args.limit, usable_s, X), work / name, args)
        sp = spills(work / name) if info["built"] else None
        good = sp is not None and sp["sgpr"] == 0 and not sp["wwm"]
        hist.append(dict(name=name, windows={t: list(v) for t, v in cur.items()}, notes=info.get("notes"),
                         spills=sp and sp["counts"], wwm=sp and sp["wwm"], ok=good))
        log(f"{name}: {'ok' if good else 'REJECTED'} spills {sp and sp['counts']}")
        return good, name

    def slack(ds):
        return {t: (min(K[t][0] + args.vslack, args.limit - 1), min(K[t][1] + ds, len(usable_s) - nin[t])) for t in K}

    final = None
    for ds in (0, 2, 4, 6, 8, 12, 16, 24, 32):
        good, final = trial(slack(ds))
        if good:
            break
    else:
        sgpr_spill_error(spills(work / final), f"{final} (SGPR slack {ds})")
        sys.exit(2)
    cur = slack(ds)
    for t in K:
        for s in sorted({K[t][1], (K[t][1] + cur[t][1]) // 2}):
            if s >= cur[t][1]:
                continue
            good, nm = trial({**cur, t: (cur[t][0], s)})
            if good:
                cur, final = {**cur, t: (cur[t][0], s)}, nm
                break
    log(f"sgpr slack {ds}; final windows {cur}")
    shutil.copytree(work / final, work / "c_final", dirs_exist_ok=True)
    b2, o2, res2, at2 = liveness(work / "c_final")
    spf = spills(work / "c_final")
    assert spf["sgpr"] == 0 and not spf["wwm"], spf["counts"]
    W = windows(cur, reserved, args.limit, usable_s, args.vlayout)
    res = {"limit": args.limit, "vlayout": args.vlayout, "reserved_r0": sorted(reserved),
           "reserved_final": sorted(res2), "spills_r0": sp0["counts"], "spills_final": spf["counts"],
           "vgpr_scratch_r0_by_region": by_region(sp0["sites"], "vgpr"),
           "vgpr_scratch_final_by_region": by_region(spf["sites"], "vgpr"),
           "sgpr_slack": ds, "vslack": args.vslack, "notes_r0": r0.get("notes"),
           "notes_final": json.loads((work / "c_final" / "info.json").read_text()).get("notes"), "history": hist,
           "points": {}}
    for tag in K:
        vw, sw = W[tag]
        e = at2[tag][0]
        b = binds.get(tag, [])
        ro = read_only(b)
        ins = {u for x in b for u in expand(x["reg"])}
        th2 = e["after"] - e["defs"]
        tv, ts, _ = split(set(th2) - set(res2) - reserved - ro)
        outside = [f"v{n}" for n in tv if n not in vw] + [f"s{n}" for n in ts if n not in sw]
        asm_v = [n for n in range(args.limit) if n not in vw and f"v{n}" not in ro]
        asm_s = [n for n in usable_s if n not in sw]
        res["points"][tag] = {
            "inputs": b, "inputs_s": len({u for u in ins if u[0] == "s"}), "inputs_v": len({u for u in ins if u[0] == "v"}),
            "keep_r0": dict(v=K[tag][0], s=K[tag][1]), "keep_r0_noremat": dict(v=R[tag][0], s=R[tag][1]),
            # final build, just before / after the asm (before: kept + inputs; after: kept + read-only inputs)
            "before_final": S(e["before"], res2), "after_final": S(e["after"], res2),
            "window": dict(v=len(vw), s=len(sw), v_regs=ranges(vw, "v"), s_regs=ranges(sw, "s")),
            "asm": dict(v=len(asm_v), s=len(asm_s), v_regs=ranges(asm_v, "v"), s_regs=ranges(asm_s, "s"),
                        x=X[tag]),
            "through_final": S(th2, res2), "outside_window": outside,
            "vgpr_scratch_after": by_region(spf["sites"], "vgpr").get(tag, 0),
        }
        if outside:
            log(f"ERROR {tag}: live across the asm outside its window {outside}")
    (work / "contract.json").write_text(json.dumps(res, indent=1))
    dv = spf["vgpr"] - sp0["vgpr"]
    log(f"contract: final {final}, SGPR spills 0, VGPR scratch {spf['vgpr']} instructions (r0 {sp0['vgpr']})")
    if spf["vgpr"]:
        log(f"WARNING: VGPR scratch {spf['vgpr']} instructions ({dv:+d} vs r0), by region (after which marker): "
            f"{res['vgpr_scratch_final_by_region']}")


# ------------------------------------------------------------------ verify (GPU run, overwrite dead registers)
def mir_body_sans_asm(path):
    t = Path(path).read_text()
    t = t[t.index("\n---\nname:"):]
    t = t[re.search(r"^body:", t, re.M).start():]
    return [ln for ln in t.splitlines() if "INLINEASM" not in ln]


def cmd_verify(args):
    work = Path(args.work)
    a = work / "analyze"
    blocks, order, reserved, at = liveness(a)
    vcount = json.loads((a / "info.json").read_text())["notes"]["vgpr_count"]
    gold = work / "golden.pt"
    if gold.exists() and (work / "v_golden" / "info.json").exists():
        g = json.loads((work / "v_golden" / "info.json").read_text())
    else:
        g = build({"mode": "wrap"}, work / "v_golden", args, run=True, extra=["--golden", str(gold)])
    con, npv, nps = {}, 0, 0
    lo, hi = args.vrange
    for tag, es in at.items():
        if args.only and not any(re.fullmatch(p, tag) for p in args.only):
            continue
        e = es[0]
        keep = e["before"] | e["after"] | reserved
        pv = [n for n in range(max(lo, 0), min(hi, vcount)) if f"v{n}" not in keep]
        ps = [n for n in range(106) if f"s{n}" not in keep] if not args.no_sgpr else []
        if pv and not ps:
            ps = [min(n for n in range(106) if f"s{n}" not in keep)]
        con[tag] = {"poison_v": pv, "poison_s": ps, "clobber_v": pv, "clobber_s": ps}
        npv += len(pv)
        nps += len(ps)
    pdir = work / f"v_poison{args.tag}"
    p = build({"mode": "wrap", "contracts": con}, pdir, args, run=True, extra=["--golden", str(gold)])
    same = mir_body_sans_asm(a / "post.mir") == mir_body_sans_asm(pdir / "post.mir")
    log(f"poison: rc {p['rc']}, allocation identical {same}, {p.get('result', {}).get('pass')}")
    if args.no_negative:
        return
    # negative control: one executed point also overwrites its live VGPRs
    neg_tag = args.negative
    e = at[neg_tag][0]
    con2 = json.loads(json.dumps(con))
    live_v = sorted(n for n in split(e["before"] | e["after"])[0] if n < vcount)
    con2[neg_tag]["poison_v"] = sorted(set(con2[neg_tag]["poison_v"]) | set(live_v))
    nctl = build({"mode": "wrap", "contracts": con2}, work / f"v_negative{args.tag}", args, run=True,
                 extra=["--golden", str(gold)])
    res = {"vgpr_count": vcount, "poisoned_points": len(con), "poisoned_vgpr_writes": npv,
           "poisoned_sgpr_writes": nps, "allocation_identical": same,
           "spills_native": mir.spill_counts(blocks), "notes_native": json.loads((a / "info.json").read_text())["notes"],
           "spills_poison": mir.spill_counts(mir.parse(pdir / "post.mir")[0]), "notes_poison": p.get("notes"),
           "golden": {k: g.get("result", {}).get(k) for k in ("pass", "failures", "run_to_run")},
           "poison": {k: p.get("result", {}).get(k) for k in ("pass", "failures", "golden", "run_to_run", "stats")},
           "poison_rc": p["rc"],
           "negative": {"tag": neg_tag, "live_vgprs": len(live_v), "rc": nctl["rc"],
                        "result": {k: nctl.get("result", {}).get(k) for k in ("pass", "failures", "golden")}},
           "noise_rtol": args.rtol}
    gl = (res["poison"].get("golden") or {}).get("rel_l2", {})
    res["poison_within_noise"] = bool(gl) and all(v <= args.rtol for v in gl.values()) and p["rc"] in (0, 1)
    (work / "verify.json").write_text(json.dumps(res, indent=1))
    log(f"verify: allocation identical {same}, poison {res['poison'].get('pass')} rel_l2 {gl}, "
        f"negative rc {nctl['rc']} {res['negative']['result']}")


# ------------------------------------------------------------------ limit (largest declarable VGPR)
def cmd_limit(args):
    work = Path(args.work)
    res = {}
    for n in args.n:
        con = {args.at: {"clobber_v": [n - 1]}}
        info = build({"mode": "wrap", "contracts": con}, work / f"limit_{n}", args, run=True)
        log_t = (work / f"limit_{n}" / "log.txt").read_text()
        err = re.findall(r"(hipError\w+|HIP error[^\n]*|RuntimeError[^\n]*|out of resources[^\n]*)", log_t)
        res[n] = {"rc": info["rc"], "notes": info.get("notes"), "pass": info.get("result", {}).get("pass"),
                  "errors": sorted(set(err))[:4]}
        log(f"limit v{n - 1}: rc {info['rc']} notes {info.get('notes')} pass {res[n]['pass']} {res[n]['errors']}")
    (work / "limit.json").write_text(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("analyze", "contract", "verify", "limit"))
    ap.add_argument("--work", default=str(HERE / "build" / "gpr"))
    ap.add_argument("--llvm", type=Path, default=LLVM)
    ap.add_argument("--rows", type=int, default=48)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--limit", type=int, default=512, help="VGPRs of the asm contracts: v0..v{limit-1}")
    ap.add_argument("--replace", nargs="+", default=TIER1)
    ap.add_argument("--patch", help="python file run in the build before tracing (kernel monkeypatches, see patches/)")
    ap.add_argument("--vlayout", choices=("top", "top-packed", "low"), default="top", help="contract: where the kept VGPR window goes (see windows())")
    ap.add_argument("--vslack", type=int, default=0, help="contract: VGPRs kept beyond those live across each "
                    "insertion point (fewer VGPR scratch instructions, fewer VGPRs for the asm)")
    ap.add_argument("--negative", default="stage_E#0:in")
    ap.add_argument("--only", nargs="*", help="verify: poison only at the tags matching these regexes")
    ap.add_argument("--vrange", type=int, nargs=2, default=[0, 1024], help="verify: poison VGPRs in [lo, hi) only")
    ap.add_argument("--no-sgpr", action="store_true", help="verify: no SGPR poison (but the MSB-save one)")
    ap.add_argument("--no-negative", action="store_true")
    ap.add_argument("--tag", default="", help="verify: suffix of the build dirs")
    ap.add_argument("--rtol", type=float, default=0.25, help="poison run vs golden rel L2 bound (unpoisoned runs vs "
                    "the golden: xh / aRout 0.02..0.06, kv_rows 0.10..0.20)")
    ap.add_argument("--at", default="stage_E#0:in", help="limit: the insertion point of the clobbering asm")
    ap.add_argument("--n", type=int, nargs="+", default=[512, 768, 1024])
    args = ap.parse_args()
    Path(args.work).mkdir(parents=True, exist_ok=True)
    {"analyze": cmd_analyze, "contract": cmd_contract, "verify": cmd_verify, "limit": cmd_limit}[args.cmd](args)


if __name__ == "__main__":
    main()
