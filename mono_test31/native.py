"""Strict native leaf extraction and inline expansion, with no register remap."""
from dataclasses import dataclass
import re


RESOURCE_KEYS = (
    "num_vgpr", "num_agpr", "numbered_sgpr", "num_named_barrier",
    "private_seg_size", "uses_vcc", "uses_flat_scratch", "has_dyn_sized_stack",
    "has_recursion", "has_indirect_call",
)
RETURN = re.compile(r"s_(?:setpc_b64|set_pc_i64)\s+s\[30:31\]\s*$")
LABEL = re.compile(r"^\s*([A-Za-z_.$][\w.$]*|[0-9]+):\s*(.*)$")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


@dataclass(frozen=True)
class NativeFragment:
    symbol: str
    lines: tuple[str, ...]
    resources: dict


def resources(text, symbol):
    result = {}
    for key in RESOURCE_KEYS:
        values = re.findall(r"^\s*\.set\s+(?:\.L)?" + re.escape(symbol)
                            + r"\." + key + r",\s*(\d+)\s*$", text, re.M)
        require(len(values) == 1, f"{symbol}: absent/non-literal resource {key}")
        result[key] = int(values[0])
    require(not any(result[k] for k in ("num_agpr", "has_dyn_sized_stack",
                                       "has_recursion", "has_indirect_call")),
            "Only leaf, fixed-stack, VGPR-only fragments are supported")
    require(result["uses_vcc"] in (0, 1) and result["uses_flat_scratch"] in (0, 1),
            "Unexpected special-register resource flags")
    require(result["private_seg_size"] > 0 or not result["uses_flat_scratch"],
            "Flat scratch use without a private allocation needs review")
    return result


def strip_comments(line):
    return re.sub(r"/\*.*?\*/", "", line).split("//", 1)[0].split(";", 1)[0].strip()


def extract(text, symbol):
    require("gfx1250" in text, "Native fragment must target gfx1250")
    require(not re.search(r"^\s*\.amdhsa_kernel\b", text, re.M), "Callee still has a kernel descriptor")
    require(not re.search(r"^\s*\.(?:section\s+[^\n]*(?:rodata|data|bss)|data\b|bss\b)", text, re.M),
            "External constant/global data requires relocatable fragment support")
    definitions = re.findall(r"^\s*\.type\s+([\w.$]+),\s*@function", text, re.M)
    require(definitions == [symbol], f"Unexpected function definitions: {definitions}")
    match = re.search(r"^" + re.escape(symbol) + r":[^\n]*\n(.*?)"
                      r"^\.Lfunc_end[0-9]+:", text, re.M | re.S)
    require(match is not None, f"Cannot locate sized native body {symbol}")
    lines = []
    for raw in match[1].splitlines():
        line = strip_comments(raw)
        if not line or line.startswith("#"):
            continue
        label = LABEL.fullmatch(line)
        if label:
            lines.append(label[1] + ":")
            line = label[2]
            if not line:
                continue
        if line.startswith("."):
            require(re.fullmatch(r"\.(?:p2align|p2alignl)\s+[\d,\s]+", line),
                    f"Unsupported body directive (data/debug/relocation): {line}")
        require(not re.search(r"\bs_(?:swappc_b64|swap_pc_i64|getpc_b64|get_pc_i64|call_b64|call)\b", line),
                f"Non-leaf/PC-relative operation: {line}")
        require(not re.search(r"\b(?:ttmp\d+|s_endpgm|s_trap)\b|@", line),
                f"Implicit dispatch/termination/relocation operation: {line}")
        if line.startswith("s_sendmsg_rtn"):
            require(re.fullmatch(r"s_sendmsg_rtn_b64\s+s\[\d+:\d+\],\s*sendmsg\(MSG_RTN_GET_REALTIME\)", line),
                    f"Unbridged message-return state: {line}")
        if re.search(r"\bs_(?:setpc_b64|set_pc_i64)\b", line):
            require(RETURN.fullmatch(line), f"Unsupported indirect return: {line}")
        lines.append(line)
    require(any(RETURN.fullmatch(line) for line in lines), "No native CCC return")
    fragment = NativeFragment(symbol, tuple(lines), resources(text, symbol))
    # Validate every branch reference while all local definitions are available.
    expand(fragment, "validate")
    return fragment


def expand(fragment, prefix):
    require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", prefix), "Invalid inline namespace")
    lines = fragment.lines
    named, numeric, replacements = {}, {}, {}
    for i, line in enumerate(lines):
        label = LABEL.fullmatch(line)
        if not label:
            continue
        name = label[1]
        if name.isdecimal():
            numeric.setdefault(name, []).append(i)
            replacements[i] = f".L{prefix}_n{name}_{i}"
        else:
            require(name not in named, f"Duplicate local label: {name}")
            require(name.startswith(".L"), f"Non-local label: {name}")
            named[name] = f".L{prefix}_{len(named)}"
            replacements[i] = named[name]
    end = f".L{prefix}_end"
    output = [f"// Inline {fragment.symbol}; native prologue/epilogue retained.", "    PREP_STAGE"]
    for i, line in enumerate(lines):
        if i in replacements:
            output.append(replacements[i] + ":")
            continue
        if RETURN.fullmatch(line):
            output.append(f"    STEP_JMP {end}")
            continue
        # LLVM and source inline ASM can both define local branch labels.
        def replace_named(match):
            require(match[0] in named, f"Unresolved local label: {match[0]}")
            return named[match[0]]
        line = re.sub(r"(?<![\w.$])\.L[\w.$]+", replace_named, line)

        def replace_numeric(match):
            number, direction = match[1], match[2]
            positions = [p for p in numeric.get(number, [])
                         if (p > i if direction == "f" else p < i)]
            require(positions, f"Unresolved numeric label: {match[0]}")
            return replacements[min(positions) if direction == "f" else max(positions)]
        line = re.sub(r"(?<![\w.])([0-9]+)([fb])(?![\w.])", replace_numeric, line)
        branch = re.match(r"s_(?:branch|cbranch_\w+)\s+(.+)$", line)
        if branch:
            require(branch[1] in set(named.values()) | set(replacements.values()),
                    f"External/unresolved branch: {line}")
        output.append("    " + line)
    output += [end + ":", "    s_set_vgpr_msb 0", "    s_waitcnt_depctr 0", "    s_nop 7"]
    return "\n".join(output) + "\n"


def aggregate(fragments):
    values = [fragment.resources for fragment in fragments]
    require(values, "No native fragments")
    result = {
        "vgpr": max(41, *(r["num_vgpr"] for r in values)),
        "numbered_sgpr": max(56, *(r["numbered_sgpr"] for r in values)),
        "private": max(r["private_seg_size"] for r in values),
        "vcc": max(r["uses_vcc"] for r in values),
        "named_barriers": max(r["num_named_barrier"] for r in values),
    }
    result["private"] = (result["private"] + 15) // 16 * 16
    result["scratch"] = int(result["private"] > 0)
    result["sgpr"] = result["numbered_sgpr"] + 2 * result["vcc"]
    return result
