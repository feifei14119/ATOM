"""Local packaging for the known C1 stage; never executes or loads a GPU object.

The original v1 demo auditor only accepts zero-LDS linear code. This isolated
extension checks our fixed full-stage source, imported LDS ranges, local branch
targets and decoded register use. It is not an arbitrary-ASM proof system.
"""
from pathlib import Path
import json
import re
import struct
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "llvm_asm_contract"))
from demo.contract import Elf, digest, expand, register_operands, run, verify_identity
from demo.build import begin_build, metadata, require_backend
from static_checks import check_c1_layout


def llvm_attributes(m):
    r = m["resources"]
    return {
        "amdgpu-asm-contract": "1",
        "amdgpu-asm-arg-regs": ",".join(a["register"] for a in m["arguments"]),
        "amdgpu-asm-clobbers": ",".join(m["clobbers"]),
        "amdgpu-asm-vgpr-count": str(r["vgpr_count"]),
        "amdgpu-asm-sgpr-count": str(r["sgpr_count"]),
        "amdgpu-asm-private-bytes": "0",
    }


def audit_object(path, m, llvm):
    obj = Elf(path)
    if obj.type != 1 or m["resources"]["private_bytes"] != 0:
        raise ValueError("expected a zero-private ET_REL device function")
    if m["symbol"] != "mono_wqkv_asm" or m["specialization"] != {
        "hidden": 5120, "qkv_rows": 1792, "t0": 0, "n": 1, "task_range": [0, 111]
    }:
        raise ValueError("this auditor only covers the fixed C1 function")
    if m["borrowed_lds"]["xl_offset"]["bytes"] != 5120 or m["borrowed_lds"]["red_offset"]["bytes"] != 512:
        raise ValueError("unexpected imported LDS layout")
    if any(s[1] in (4, 9) and s[5] for s in obj.sections):
        raise ValueError("unexpected relocation in the self-contained stage")
    headers, _ = run([Path(llvm)/"llvm-readobj", "--file-headers", path])
    if "GFX1250" not in headers or "AMDGPU_HSA" not in headers:
        raise ValueError("wrong device target")
    dis, _ = run([Path(llvm)/"llvm-objdump", "--mcpu=gfx1250",
                  "--disassemble-symbols="+m["symbol"], path])
    code = obj.symbol_bytes(m["symbol"])
    start = obj.symbols[m["symbol"]][1]
    rows = []
    for line in dis.splitlines():
        match = re.match(r"\s*(.*?)\s*//\s*([0-9a-fA-F]+):\s*((?:[0-9a-fA-F]{8}(?:\s+|$))+)", line)
        if match and start <= int(match[2], 16) < start+len(code):
            rows.append((int(match[2], 16)-start, match[1].strip(), match[3].split()))
    if b"".join(struct.pack("<I", int(w,16)) for _,_,ws in rows for w in ws) != code:
        raise ValueError("not all stage bytes were decoded")
    writes, uses, exec_ops, targets = set(), set(), [], []
    allowed = {
        "s_wait_loadcnt", "s_wait_storecnt", "s_wait_dscnt", "s_wait_alu",
        "s_mov_b32", "s_mul_i32", "s_lshr_b32", "s_lshl_b32", "s_add_u32", "s_sub_u32",
        "s_cmp_eq_u32", "s_cmp_lt_u32", "s_cmp_lg_u32", "s_and_saveexec_b32", "s_sleep",
        "s_branch", "s_cbranch_scc0", "s_cbranch_scc1", "s_cbranch_vccz", "s_cbranch_vccnz",
        "s_barrier_signal", "s_barrier_wait", "s_setpc_b64", "s_set_pc_i64",
        "v_mov_b32", "v_lshrrev_b32", "v_lshlrev_b32", "v_and_b32", "v_or_b32",
        "v_add_nc_u32", "v_mul_lo_u32", "v_cmp_eq_u32", "v_cmp_ne_u32", "v_cmp_gt_u32",
        "v_add_f32", "v_cvt_pk_bf16_f32", "v_wmma_scale_f32_16x16x128_f8f6f4",
        "global_load_b32", "global_load_b64", "global_load_b128", "global_store_b64",
        "global_atomic_or_b32", "ds_load_b32", "ds_load_b128", "ds_store_b32", "ds_store_b128",
    }
    pcs = {pc for pc,_,_ in rows}
    for pc, inst, ws in rows:
        op, _, operands = inst.partition(" ")
        op = re.sub(r"_e(?:32|64)$", "", op)
        op = {"s_sub_co_u32":"s_sub_u32", "s_add_co_u32":"s_add_u32"}.get(op,op)
        if op not in allowed:
            raise ValueError("instruction outside the reviewed vocabulary: "+inst)
        uses |= register_operands(operands)
        if op.startswith("v_cmp"):
            writes.add("vcc")
        elif op.startswith("v_") or op.startswith("global_load") or op.startswith("ds_load"):
            writes |= register_operands(operands.split(",",1)[0])
        elif op.startswith("s_") and op in {
            "s_mov_b32", "s_mul_i32", "s_lshr_b32", "s_lshl_b32", "s_add_u32", "s_sub_u32", "s_and_saveexec_b32"
        }:
            writes |= register_operands(operands.split(",",1)[0])
        if op in {"s_lshr_b32", "s_lshl_b32", "s_add_u32", "s_sub_u32", "s_cmp_eq_u32", "s_cmp_lt_u32", "s_cmp_lg_u32", "s_and_saveexec_b32"}:
            writes.add("scc")
        if op == "s_and_saveexec_b32" or operands.startswith("exec_lo,"):
            exec_ops.append(re.sub(r"\s+", " ", op+" "+operands))
        if op == "s_branch" or op.startswith("s_cbranch"):
            imm = int(ws[0],16) & 0xffff
            if imm & 0x8000:
                imm -= 0x10000
            target = pc+4+imm*4
            if target not in pcs:
                raise ValueError("branch target outside the decoded function")
            targets.append([pc,target])
    if exec_ops != ["s_and_saveexec_b32 s20, vcc_lo", "s_mov_b32 exec_lo, s20"] * 2:
        raise ValueError("unexpected EXEC save/restore structure")
    returns = [inst for _,inst,_ in rows if re.match(r"s_(?:setpc_b64|set_pc_i64)\b",inst)]
    if len(returns) != 1 or not rows[-1][1].endswith("s[30:31]"):
        raise ValueError("expected exactly one final leaf return")
    if writes - expand(m["clobbers"]) or uses - expand(m["uses"]):
        raise ValueError(f"undeclared registers: writes={writes-expand(m['clobbers'])}, uses={uses-expand(m['uses'])}")
    for bank, count in (("v",m["resources"]["vgpr_count"]),("s",m["resources"]["sgpr_count"])):
        if any(int(r[1:]) >= count for r in uses if re.fullmatch(bank+r"\d+",r)):
            raise ValueError("register extent does not cover the object")
    for key, value in {"num_vgpr":96, "numbered_sgpr":64, "private_seg_size":0,
                       "num_agpr":0,"num_named_barrier":0,"uses_vcc":1,
                       "uses_flat_scratch":0,"has_dyn_sized_stack":0,
                       "has_recursion":0,"has_indirect_call":0}.items():
        sym = obj.symbols.get(m["symbol"]+"."+key)
        if not sym or sym[0] != 0xfff1 or sym[1] != value:
            raise ValueError("bad absolute resource symbol: "+key)
    return {"object_sha256":digest(obj.data), "symbol_sha256":digest(code),
            "symbol_size":len(code), "instruction_count":len(rows),
            "registers_used":sorted(uses), "registers_written":sorted(writes),
            "local_branch_targets":targets, "exec_restore_pairs":2,
            "resources":m["resources"], "borrowed_lds":m["borrowed_lds"],
            "audit_scope":m["audit_scope"], "gpu_execution":"NOT_RUN", "disassembly":dis}


def pack_stage(llvm, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    m = json.loads((ROOT/"asm/wqkv.contract.json").read_text())
    obj = output/"wqkv.co"
    run([Path(llvm)/"llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
         "-mattr=+wavefrontsize32", "-filetype=obj", ROOT/"asm/wqkv.s", "-o",obj])
    audit = audit_object(obj,m,llvm)
    audit["address_layout_checks"] = check_c1_layout()
    m.update(object_path=str(obj.resolve()),object_sha256=audit["object_sha256"],
             source_sha256=digest((ROOT/"asm/wqkv.s").read_bytes()))
    (output/"wqkv.dis.s").write_text(audit.pop("disassembly"))
    (output/"wqkv.contract.json").write_text(json.dumps(m,indent=2)+"\n")
    (output/"wqkv.audit.json").write_text(json.dumps(audit,indent=2)+"\n")
    return m, audit


def check_borrowed_lds(output, m, meta):
    """Fail closed on changes to this known caller's two imported LDS bases.

    This is a fixed integration check, not general assembly data-flow analysis.
    LLVM owns allocation; the manifest imports pointers to those allocations.
    """
    ir = (output/"caller.ll").read_text()
    for name, size in (("__shared_alloc_1", 12800), ("__shared_alloc_0", 2048)):
        if not re.search(r"@"+name+r" = external dso_local addrspace\(3\) global \["
                         +str(size)+r" x i8\], align 16", ir):
            raise ValueError("caller LDS allocation changed: "+name)
    call = [line for line in ir.splitlines() if "call void @mono_wqkv_asm(" in line]
    imported = ("i32 ptrtoint (ptr addrspace(3) @__shared_alloc_1 to i32), "
                "i32 ptrtoint (ptr addrspace(3) @__shared_alloc_0 to i32)")
    if len(call) != 1 or imported not in call[0]:
        raise ValueError("call does not pass the expected AS3 allocations")
    asm = (output/"caller.s").read_text()
    calls = list(re.finditer(r"\bs_(?:swappc_b64|swap_pc_i64)\b", asm))
    if len(calls) != 1:
        raise ValueError("cannot identify the single LDS import call")
    before = asm[:calls[0].start()]
    # A fresh block/comment or control-flow instruction starts this local scan.
    block = re.split(r"(?m)^\.LBB[^\n]*|^; %bb[^\n]*|^\s*s_(?:cbranch\w*|branch) [^\n]*", before)[-1]
    ranges = {}
    for name, reg, expected in (("xl_offset", "s1", 0), ("red_offset", "s4", 12800)):
        defs = []
        for line in block.splitlines():
            match = re.match(r"\s*(s_\w+)\s+([^,]+),\s*(.*)", line)
            if match and reg in register_operands(match[2]):
                defs.append(match)
        if not defs or defs[-1][1] not in {"s_mov_b32", "s_movk_i32"}:
            raise ValueError("cannot prove constant imported LDS base: "+reg)
        try:
            base = int(defs[-1][3].strip(), 0)
        except ValueError as error:
            raise ValueError("nonconstant imported LDS base: "+reg) from error
        desc = m["borrowed_lds"][name]
        end = base + desc["bytes"]
        if base != expected or base % desc["alignment"] or end > meta["group_segment_fixed_size"]:
            raise ValueError("imported LDS interval is misaligned or out of bounds")
        ranges[name] = {"register": reg, "start": base, "end_exclusive": end}
    if ranges["xl_offset"]["end_exclusive"] > ranges["red_offset"]["start"]:
        raise ValueError("WQKV input and reduction LDS overlap")
    return {"scope": "fixed C1 IR allocations and constant bases at machine call",
            "ranges": ranges, "descriptor_bytes": meta["group_segment_fixed_size"],
            "distinct_and_in_bounds": True}


def compile_and_link(ir, m, llvm, output, symbol):
    llvm, output = Path(llvm), Path(output)
    verify_identity(m)
    flags = [llvm/"llc", "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
             "-mattr=+wavefrontsize32", "-global-isel=0", "-O2", "-verify-machineinstrs"]
    report_path = output/"backend.resources.json"
    _, err = run([*flags,"-amdgpu-asm-contract-report="+str(report_path),
                  "-filetype=obj",ir,"-o",output/"caller.o"])
    (output/"codegen.stderr").write_text(err)
    run([*flags,"-filetype=asm",ir,"-o",output/"caller.s"])
    verify_identity(m)
    final = output/"kernel.pending.co"
    run([llvm/"ld.lld","-shared","--no-undefined",output/"caller.o",m["object_path"],"-o",final])
    if Elf(final).symbol_bytes(m["symbol"]) != Elf(m["object_path"]).symbol_bytes(m["symbol"]):
        raise ValueError("callee changed during link")
    meta, notes = metadata(llvm,final)
    (output/"kernel.notes.txt").write_text(notes)
    if meta["private_segment_fixed_size"] != 0:
        raise ValueError("nonzero scratch")
    # The exact original Smem + StageLds union owns both imported regions.
    if meta["group_segment_fixed_size"] < 14848:
        raise ValueError("caller descriptor does not cover its original LDS allocation")
    if meta["vgpr_count"] < 96 or meta["sgpr_count"] < 64:
        raise ValueError("callee registers omitted from final descriptor")
    lds = check_borrowed_lds(output, m, meta)
    dis,_=run([llvm/"llvm-objdump","--mcpu=gfx1250","-d",final])
    (output/"kernel.dis.s").write_text(dis)
    report=json.loads(report_path.read_text())
    if report.get("strict_policy_status") != "checked":
        raise ValueError("strict policy did not pass")
    fn=next(f for f in report["functions"] if f["function"]==symbol)
    calls=[c for c in fn["calls"] if c["callee"]==m["symbol"]]
    if len(calls)!=1 or not calls[0]["call_instruction_live_through"]:
        raise ValueError("expected one real stage call with live caller context")
    if calls[0]["amdgpu-asm-arg-regs"] != llvm_attributes(m)["amdgpu-asm-arg-regs"]:
        raise ValueError("backend did not retain argument register bindings")
    live = set(calls[0]["call_instruction_live_through"])
    if live & expand(m["clobbers"]) or live - set(calls[0]["preserved_allocatable_gprs"]):
        raise ValueError("caller context overlaps a clobbered register")
    zero_fields = ("lowered_sgpr_spill_dwords", "lowered_vgpr_spill_dwords",
                   "sgpr_abi_lane_saves", "abi_memory_saves", "wwm_spill_registers",
                   "private_frame_bytes", "private_access_instructions", "incoming_stack_argument_bytes")
    if any(fn.get(field) != 0 for field in zero_fields):
        raise ValueError("backend reports a spill or private-memory resource")
    if len(re.findall(r"\bs_(?:swappc_b64|swap_pc_i64)\b",dis)) != 1:
        raise ValueError("unexpected device call count")
    if re.search(r"\bscratch_(?:load|store)",dis):
        raise ValueError("scratch instruction in final code")
    final.rename(output/"kernel.co")
    return {"status":"OFFLINE_COMPILED", "kernel":str(output/"kernel.co"),
            "symbol":symbol, "metadata":meta, "device_calls":1,
            "calls":calls, "strict_policy_status":"checked",
            "backend_scope":report["scope"], "backend_resource_report":str(report_path),
            "callee_bytes_preserved":True, "object_hash_verified":True,
            "borrowed_lds_validation":lds,
            "zero_spill_counters":{field:fn[field] for field in zero_fields},
            "gpu_execution":"NOT_RUN", "numerical_validation":"NOT_RUN"}
