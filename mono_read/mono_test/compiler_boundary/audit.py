"""Checks deliberately limited to this straight-line, full-wave LLVM caller.

This is not a general AMDGPU CFG/lane liveness analyzer. LLVM's MIR provides
explicit register defs and uses, including implicit operands and tuple aliases.
"""
import re


class BudgetError(ValueError):
    pass


def resources(assembly):
    keys = ["private_segment_fixed_size", "group_segment_fixed_size",
            "sgpr_spill_count", "vgpr_spill_count", "sgpr_count", "vgpr_count"]
    return {key: int(re.search(r"\." + key + r":\s*(\d+)", assembly)[1]) for key in keys}


def require_no_spills(assembly):
    r = resources(assembly)
    if any(r[k] for k in ("private_segment_fixed_size", "sgpr_spill_count", "vgpr_spill_count")):
        raise BudgetError(f"boundary budget exceeded: {r}")
    if re.search(r"\b(?:scratch_|flat_|v_(?:readlane|writelane))", assembly):
        raise BudgetError("unexpected scratch/lane-spill instructions")
    return r


def registers(text):
    result = set()
    for operand in re.findall(r"\$([\w]+)", text):
        if re.fullmatch(r"(?:[sv]gpr\d+)(?:_[sv]gpr\d+)*", operand):
            result.update(re.findall(r"[sv]gpr\d+", operand))
        else:
            if operand not in {"exec", "exec_lo", "vcc", "vcc_lo", "scc", "mode", "m0", "sgpr_null", "pc_reg"}:
                raise ValueError(f"unreviewed register operand: {operand}")
            if operand not in {"sgpr_null", "pc_reg"}:
                result.add(operand)
    return result


def boundary_liveness(mir, bank):
    body = mir.split("body:", 1)[1]
    if len(re.findall(r"^  bb\.", body, re.M)) != 1:
        raise ValueError("this audit requires exactly one basic block")
    if re.search(r"%\d|\b(?:S_CBRANCH|SI_SPILL|V_WRITELANE|V_READLANE)", body):
        raise ValueError("unreviewed virtual registers, control flow or lane spills")
    allowed = {f"sgpr{i}" for i in bank.scalars} | {f"vgpr{i}" for i in range(bank.vgprs)}
    live, reports = set(), []
    for line in reversed(body.splitlines()):
        if not line.startswith("    ") or not line.strip() or "CFI_INSTRUCTION" in line:
            continue
        line = line.split(" :: ")[0]
        if "INLINEASM" in line:
            index = int(re.search(r"MONO_BOUNDARY_(\d)", line)[1])
            # EXEC is reconstructed to full; supplier/adapter do not write MODE
            # or M0 (M0 is an implicit operand of the backend's dealloc sendmsg).
            if not live <= allowed | {"exec", "exec_lo", "mode", "m0"}:
                raise ValueError(f"boundary {index}: unprotected live-out {sorted(live-allowed)}")
            reports.append({"boundary": index, "live_out": sorted(live)})
        lhs, rhs = line.split(" = ", 1) if " = " in line else ("", line)
        defs, uses = registers(lhs), set()
        for part in rhs.split(","):
            if "implicit-def" in part:
                defs |= registers(part)
            else:
                uses |= registers(part)
        live = (live - defs) | uses
    if len(reports) != 2:
        raise ValueError("expected exactly two boundaries")
    return list(reversed(reports))
