"""Execute the scheduler's uniform control flow on CPU, recording stage visits.

This interpreter tests scheduling only. It does not emulate FlyDSL arithmetic,
memory ordering, scratch, cluster barriers or GPU instruction timing.
"""
from pathlib import Path
import re

from build import constants, parse


def trace(cfg, bid=0, flags=None, scorer=None):
    flags, scorer = flags or {}, scorer or {}
    source = (Path(__file__).resolve().parents[1] / "step.s").read_text()
    lines, blocks = parse(source)
    stage_at = {b.start: b for b in blocks}
    values = {name: int(value) for name, value in
              re.findall(r"\.set (\w+), (\d+)", constants(cfg))}
    program, include, macro = [], [True], False
    i = 0
    while i < len(lines):
        line = lines[i].split("//", 1)[0].strip()
        if i in stage_at:
            block = stage_at[i]
            if all(include):
                program.append("EVENT " + block.name)
            i = block.end + 1
            continue
        i += 1
        if line.startswith(".macro "):
            macro = True
        if macro:
            if line == ".endm":
                macro = False
            continue
        if line.startswith(".if "):
            expression = line[4:].replace("&&", " and ").replace("||", " or ")
            include.append(bool(eval(expression, {"__builtins__": {}}, values)))
            continue
        if line == ".else":
            include[-1] = not include[-1]
            continue
        if line == ".endif":
            include.pop()
            continue
        if all(include) and line and (not line.startswith(".") or re.fullmatch(r"\.L\w+:", line)):
            program.append(line)
    labels = {line[:-1]: n for n, line in enumerate(program) if line.endswith(":")}
    # Supply physical CTA ID instead of interpreting the hardware dispatch
    # decoder; begin at the scalar scheduler-state initialization.
    pc = program.index("s_mov_b32 s39, 0")
    regs, scc, events = {"s38": bid}, False, []

    def operand(text):
        if text in regs:
            return regs[text]
        if text in values:
            return values[text]
        return eval(text, {"__builtins__": {}}, dict(values, **regs))

    for _ in range(20000):
        line = program[pc]
        pc += 1
        if line.startswith("EVENT "):
            name = line[6:]
            events.append((name, regs.get("s52", 0), regs.get("s39", 0),
                           regs.get("s49", 0), regs.get("s50", 0)))
            continue
        if line == "s_endpgm":
            return events
        if line.startswith("STEP_JMP "):
            pc = labels[line.split()[1]]
            continue
        if line.startswith("STEP_CJMP "):
            cond, label = line[len("STEP_CJMP "):].split(", ")
            if scc == (cond == "scc1"):
                pc = labels[label]
            continue
        if line.startswith("LOAD_LAYER "):
            destination, key = line[11:].split(", ")
            value = flags.get(regs["s39"], 0) if key == "LK_lflags" else scorer.get(regs["s39"], 0)
            first = 0 if destination == "s[0:1]" else 2
            regs[f"s{first}"], regs[f"s{first + 1}"] = value & 0xffffffff, value >> 32
            continue
        match = re.fullmatch(r"s_mov_b32 (s\d+), (.+)", line)
        if match:
            regs[match[1]] = operand(match[2])
            continue
        match = re.fullmatch(r"s_(add_u32|or_b32) (s\d+), (.+), (.+)", line)
        if match:
            a, b = operand(match[3]), operand(match[4])
            regs[match[2]] = (a + b if match[1] == "add_u32" else a | b) & 0xffffffff
            continue
        match = re.fullmatch(r"s_cmp_(eq|lg|lt|ge)_u32 (.+), (.+)", line)
        if match:
            a, b = operand(match[2]), operand(match[3])
            scc = {"eq": a == b, "lg": a != b, "lt": a < b, "ge": a >= b}[match[1]]
            continue
        match = re.fullmatch(r"s_bitcmp1_b32 (s\d+), (\d+)", line)
        if match:
            scc = bool(regs[match[1]] & (1 << int(match[2])))
            continue
        if line.endswith(":") or re.match(r"(?:v_|ds_|s_wait|s_prefetch_|s_nop\b)", line):
            continue
        raise AssertionError("Unsupported scheduler instruction: " + line)
    raise AssertionError("Scheduler did not terminate")
