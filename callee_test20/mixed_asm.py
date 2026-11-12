#!/usr/bin/env python3
"""Bounded gfx1100 HIP-in-ASM demo: two f32 inputs, one f32 output per block.

Clang compiles ordinary pure HIP helpers. Their complete native bodies are
audited before copying the supported scalar VALU instructions into an isolated
VGPR pool. This is not an unrestricted AMDGPU register-remapping backend.
"""
import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
SYMBOL = "asm_hip_demo"
HELPER = "hip_fragment"
TARGET = "gfx1100"
REG = re.compile(r"v([0-9]+)$")
NUMBER = r"(?:0x[0-9a-fA-F]+|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
SOURCE_NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?[fF]?")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(argv):
    result = subprocess.run([str(a) for a in argv], capture_output=True, text=True)
    require(result.returncode == 0, f"Command failed: {argv}\n{result.stdout}{result.stderr}")
    return result.stdout


@dataclass(frozen=True)
class Binding:
    kind: str
    name: str
    reg: int


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    id: str
    bindings: tuple[Binding, ...]
    pool: tuple[int, ...]
    clobbers: tuple[str, ...]
    code: str
    code_line: int


def mask_comments(lines):
    """Mask // and /* */ while retaining source line numbers.

    Strings/raw strings are outside the accepted HIP expression grammar.
    In particular, .hip.end inside a block comment cannot end a code block.
    """
    result, inside = [], False
    for line in lines:
        out, i = "", 0
        while i < len(line):
            if inside:
                end = line.find("*/", i)
                if end < 0:
                    break
                i, inside = end + 2, False
            elif line.startswith("/*", i):
                inside, i = True, i + 2
                out += " "
            elif line.startswith("//", i):
                break
            else:
                out += line[i]
                i += 1
        result.append(out.strip())
    require(not inside, "Unclosed comment")
    return result


def validate_code(code, bindings):
    """Accept one assignment of a scalar arithmetic expression; Clang types it."""
    output = bindings[-1].name
    match = re.fullmatch(r"\s*" + re.escape(output) + r"\s*=\s*(.*?)\s*;\s*", code, re.S)
    require(match is not None, "HIP demo requires one assignment to its output")
    expression = match[1]
    tokens, position = [], 0
    while position < len(expression):
        if expression[position].isspace():
            position += 1
            continue
        token = re.match(r"[A-Za-z_][A-Za-z0-9_]*|" + SOURCE_NUMBER.pattern + r"|[()+*/-]", expression[position:])
        require(token is not None, "Only f32 identifiers/literals and + - * / () are supported")
        value = token[0]
        if SOURCE_NUMBER.fullmatch(value):
            require(not re.search(r"[.eE]", value) or value[-1] in "fF", "Float literals require an f suffix")
        tokens.append(value)
        position += len(value)
    inputs = {b.name for b in bindings[:2]}
    cursor = 0

    def atom():
        nonlocal cursor
        require(cursor < len(tokens), "Incomplete HIP expression")
        token = tokens[cursor]
        cursor += 1
        if token in ("+", "-"):
            atom()
        elif token == "(":
            expression_rule()
            require(cursor < len(tokens) and tokens[cursor] == ")", "Unmatched parenthesis")
            cursor += 1
        else:
            require(token in inputs or SOURCE_NUMBER.fullmatch(token), "Unknown/uninitialized identifier: " + token)

    def product():
        nonlocal cursor
        atom()
        while cursor < len(tokens) and tokens[cursor] in ("*", "/"):
            cursor += 1
            atom()

    def expression_rule():
        nonlocal cursor
        product()
        while cursor < len(tokens) and tokens[cursor] in ("+", "-"):
            cursor += 1
            product()

    expression_rule()
    require(cursor == len(tokens), "Calls, casts and other C++ constructs are outside this demo")


def parse(source):
    lines = source.splitlines(keepends=True)
    clean = mask_comments(lines)
    require(not any(re.match(r"\.(?:macro|if\w*|rept|irp|irpc)\b", x) for x in clean),
            "This demo requires top-level blocks without ASM macro/conditional expansion")
    require('.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"' in clean, "Demo target must be gfx1100")
    budgets = re.findall(r"^\s*\.amdhsa_next_free_vgpr\s+(\d+)\s*$", source, re.M)
    require(len(budgets) == 1, "One literal VGPR descriptor budget is required")
    budget = int(budgets[0])
    expected_mode = {"wavefront_size32": 1, "float_round_mode_32": 0, "float_round_mode_16_64": 0,
                     "float_denorm_mode_32": 3, "float_denorm_mode_16_64": 3,
                     "dx10_clamp": 0, "ieee_mode": 1}
    for field, value in expected_mode.items():
        require(re.findall(r"^\s*\.amdhsa_" + field + r"\s+(\d+)\s*$", source, re.M) == [str(value)],
                "ASM FP MODE/wave contract mismatch: " + field)
    blocks, ids, i = [], set(), 0
    while i < len(lines):
        begin = re.fullmatch(r"\.hip.begin ([A-Za-z_][A-Za-z0-9_]*)", clean[i])
        if not begin:
            require(not clean[i].startswith(".hip."), f"Unexpected directive at line {i + 1}")
            i += 1
            continue
        start, name = i, begin[1]
        require(name not in ids, "Duplicate block ID")
        ids.add(name)
        bindings, pool, clobbers, seen = [], None, (), set()
        i += 1
        while i < len(lines) and clean[i] != ".hip.code":
            text = clean[i]
            i += 1
            if not text:
                continue
            match = re.fullmatch(r"\.hip\.(in|out) f32 ([A-Za-z_][A-Za-z0-9_]*)\s*=\s*v(\d+)", text)
            if match:
                bindings.append(Binding(match[1], match[2], int(match[3])))
                continue
            match = re.fullmatch(r"\.hip.temp vgpr\s*=\s*v\[(\d+):(\d+)\]", text)
            if match:
                require(pool is None, "Duplicate VGPR pool")
                first, last = int(match[1]), int(match[2])
                require(0 <= first <= last < 256 and first % 8 == 0, "Pool must be gfx1100 VGPRs with an 8-aligned base")
                pool = tuple(range(first, last + 1))
                continue
            match = re.fullmatch(r"\.hip\.(allow_clobber|fp_contract|fast_math) (.+)", text)
            require(match is not None, f"Unsupported declaration at line {i}: {text}")
            require(match[1] not in seen, "Duplicate declaration")
            seen.add(match[1])
            if match[1] == "allow_clobber":
                require(match[2] == "vcc", "Only VCC clobber is supported; SCC/EXEC/MODE remain preserved")
                clobbers = ("vcc",)
            else:
                require(match[2] == "off", "Demo requires fp_contract=off and fast_math=off")
        require(i < len(lines), "Missing .hip.code")
        i += 1
        code_start = i
        while i < len(lines) and clean[i] != ".hip.end":
            require(not clean[i].startswith(".hip."), "Nested or invalid HIP directive")
            i += 1
        require(i < len(lines), "Missing .hip.end")
        require([b.kind for b in bindings] == ["in", "in", "out"] and pool is not None,
                "Each block needs two ordered f32 inputs, one f32 output and a VGPR pool")
        require(len({b.name for b in bindings}) == 3 and len({b.reg for b in bindings}) == 3,
                "Bindings must have distinct names and registers")
        require(all(0 <= b.reg < 256 for b in bindings), "Invalid gfx1100 VGPR binding")
        require(not {b.reg for b in bindings} & set(pool), "Bindings overlap the temporary pool")
        require(max([b.reg for b in bindings] + list(pool)) < budget <= 256, "VGPR descriptor does not cover the contract")
        code = "\n".join(clean[code_start:i])
        validate_code(code, bindings)
        blocks.append(Block(start, i, name, tuple(bindings), pool, clobbers,
                            "".join(lines[code_start:i]), code_start + 1))
        i += 1
    require(blocks, "No HIP blocks")
    return lines, blocks


def hip_source(block, source_path):
    a, b, out = block.bindings
    # Literal paths in #line are escaped as C++ strings, never shell commands.
    filename = json.dumps(str(source_path))
    return (f'extern "C" __attribute__((device, noinline, used)) float {HELPER}(float input_a, float input_b) {{\n'
            f'  const float {a.name} = input_a;\n  const float {b.name} = input_b;\n  float {out.name};\n'
            f'#line {block.code_line} {filename}\n{block.code}\n'
            f'  return {out.name};\n}}\n')


def normalize_ir(text):
    """Remove only Clang's unused HIP compilation-unit identity global."""
    uid = re.findall(r"^@(__hip_cuid_[0-9a-f]+) = addrspace\(1\) global i8 0$", text, re.M)
    require(len(uid) == 1, "Unexpected HIP compilation-unit identity layout")
    require(text.count("@" + uid[0]) == 2, "HIP identity has unexpected uses")
    text = re.sub(r"^@" + uid[0] + r" = [^\n]+\n", "", text, flags=re.M)
    used = re.findall(r"^@llvm.compiler.used = [^\n]+$", text, re.M)
    require(len(used) == 1 and "@" + HELPER in used[0], "Unexpected retained HIP symbols")
    text = text.replace(used[0], '@llvm.compiler.used = appending addrspace(1) global [1 x ptr] [ptr @hip_fragment], section "llvm.metadata"')
    require(re.findall(r"^define\b[^\n]*@([\w.]+)\(", text, re.M) == [HELPER], "Only one helper definition is supported")
    function = re.search(r"^define [^\n]*float @hip_fragment\(([^\n]*)\)[^\n]*\{\n(.*?)^\}", text, re.M | re.S)
    require(function is not None and re.fullmatch(r"float noundef %\d+, float noundef %\d+", function[1]),
            "Unexpected HIP helper ABI; expected float(float,float)")
    require(not re.search(r"\b(?:call|invoke|load|store|alloca|br|switch|amdgpu_kernel)\b", function[2]),
            "Helper IR contains calls, memory or source control flow")
    globals_ = re.findall(r"^@([^ ]+) =", text, re.M)
    require(globals_ == ["llvm.compiler.used"], "Unexpected external data")
    return text


def native_resources(assembly):
    result = {}
    for name in ("num_vgpr", "num_agpr", "numbered_sgpr", "private_seg_size", "num_named_barrier",
                 "uses_vcc", "uses_flat_scratch", "has_dyn_sized_stack", "has_recursion", "has_indirect_call"):
        values = re.findall(r"^\s*\.set \.Lhip_fragment\." + name + r",\s*(\d+)\s*$", assembly, re.M)
        require(len(values) == 1, "Missing/non-literal native resource: " + name)
        result[name] = int(values[0])
    require(not any(result[k] for k in ("num_agpr", "private_seg_size", "num_named_barrier", "uses_flat_scratch",
                                       "has_dyn_sized_stack", "has_recursion", "has_indirect_call")),
            "Only leaf, zero-scratch scalar-VGPR helpers are supported")
    require(result["uses_vcc"] in (0, 1), "Unexpected native VCC resource flag")
    return result


def extract(assembly):
    require(re.findall(r"^\s*\.type\s+([\w.]+),\s*@function", assembly, re.M) == [HELPER],
            "Unexpected native function definitions")
    match = re.search(r"^hip_fragment:[^\n]*\n(.*?)^\.Lfunc_end\d+:", assembly, re.M | re.S)
    require(match is not None, "Cannot locate sized HIP helper body")
    lines = [x.split(";", 1)[0].strip() for x in match[1].splitlines()]
    lines = [x for x in lines if x]
    require(lines and lines[0] == "s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)", "Unexpected native prologue")
    require(lines[-1] == "s_setpc_b64 s[30:31]", "Unexpected native return ABI")
    arities = {"v_add_f32_e32": 3, "v_sub_f32_e32": 3, "v_mul_f32_e32": 3,
               "v_fma_f32": 4, "v_fmac_f32_e32": 3, "v_rcp_f32_e32": 2,
               "v_div_scale_f32": 5, "v_div_fmas_f32": 4, "v_div_fixup_f32": 4,
               "v_mov_b32_e32": 2, "v_xor_b32_e32": 3}
    available, used, actual_used, writes, clobbers, vcc_defined = {0, 1}, {0, 1}, {0}, set(), set(), False
    body = lines[1:-1]
    for line in body:
        if re.fullmatch(r"s_delay_alu instid0\(VALU_DEP_[1-4]\)(?: \| instskip\((?:NEXT|SKIP_[1-5])\) \| instid1\(VALU_DEP_[1-4]\))?", line):
            continue
        if line == "s_waitcnt_depctr 0xfff":
            continue
        opcode, _, operands = line.partition(" ")
        require(opcode in arities, "Unsupported native operation: " + line)
        args = [a.strip() for a in operands.split(",")]
        require(len(args) == arities[opcode] and REG.fullmatch(args[0]), "Unexpected native operand shape: " + line)
        dest = int(REG.fullmatch(args[0])[1])
        sources = args[1:]
        if opcode == "v_div_scale_f32":
            require(sources[0] in ("null", "vcc_lo"), "Unexpected division flag destination")
            if sources[0] == "vcc_lo":
                clobbers.add("vcc")
                vcc_defined = True
            sources = sources[1:]
        if opcode == "v_div_fmas_f32":
            require(vcc_defined, "Division consumes an undefined native VCC flag")
            clobbers.add("vcc")
        if opcode == "v_fmac_f32_e32":
            require(dest in available, "FMAC accumulator is undefined")
        for source in sources:
            operand = source[1:] if source.startswith("-") else source
            reg = REG.fullmatch(operand)
            if reg:
                index = int(reg[1])
                require(index in available, "Native read of undefined VGPR")
                used.add(index)
                actual_used.add(index)
            else:
                require(re.fullmatch(NUMBER, operand), "Unsupported scalar/symbolic/native operand: " + source)
        available.add(dest)
        used.add(dest)
        actual_used.add(dest)
        writes.add(dest)
    require(0 in available, "Native return v0 is undefined")
    resource = native_resources(assembly)
    require(max(actual_used) < resource["num_vgpr"], "Native resource report misses a VGPR")
    require(bool(resource["uses_vcc"]) == bool(clobbers), "Native VCC resource/audit mismatch")
    return {"body": body, "used": sorted(used), "writes": sorted(writes),
            "clobbers": sorted(clobbers), "resources": resource}


def remap(native, block):
    require(set(native["clobbers"]) <= set(block.clobbers), "Native special clobber was not authorized")
    require(max(native["used"]) < len(block.pool), "Temporary VGPR pool is too small")
    mapping = {r: block.pool[r] for r in native["used"]}
    result = [f"// HIP block {block.id}: bounded scalar VALU lowering, no device call."]
    for arg, binding in enumerate(block.bindings[:2]):
        result.extend([f"v_mov_b32_e32 v{mapping[arg]}, v{binding.reg}", "s_nop 7"])
    # Keep LLVM's internal hazard sequence intact. Bridge spacing is outside it.
    for instruction in native["body"]:
        result.append(re.sub(r"\bv(\d+)\b", lambda m: "v" + str(mapping[int(m[1])]), instruction))
    result.extend(["s_nop 7", f"v_mov_b32_e32 v{block.bindings[-1].reg}, v{mapping[0]}", "s_nop 7"])
    written = {mapping[r] for r in native["writes"]} | {mapping[0], mapping[1], block.bindings[-1].reg}
    return "\n".join("    " + x for x in result) + "\n", mapping, sorted(written)


def build(source_path, output, llvm):
    source_path, output, llvm = Path(source_path).resolve(), Path(output).resolve(), Path(llvm).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for file in ("demo.co", "kernel.generated.s", "build_report.json", "static_report.json", "gpu_result.json", "test.log"):
        (output / file).unlink(missing_ok=True)
    report = {"status": "BUILDING", "target": TARGET, "gpu_execution": False, "tests_executed": False, "blocks": []}
    try:
        lines, blocks = parse(source_path.read_text())
        generated, cursor = [], 0
        for block in blocks:
            folder = output / block.id
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "fragment.hip.cpp").write_text(hip_source(block, source_path))
            run([llvm / "clang++", "-x", "hip", "--cuda-device-only", "--offload-arch=gfx1100",
                 "-nogpuinc", "-nogpulib", "-O2", "-ffp-contract=off", "-fno-fast-math",
                 "-fdenormal-fp-math=ieee", "-Werror=uninitialized", "-S", "-emit-llvm",
                 folder / "fragment.hip.cpp", "-o", folder / "fragment.raw.ll"])
            (folder / "fragment.ll").write_text(normalize_ir((folder / "fragment.raw.ll").read_text()))
            run([llvm / "llc", "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1100",
                 "-mattr=+wavefrontsize32", "-O2", folder / "fragment.ll", "-o", folder / "fragment.native.s"])
            native = extract((folder / "fragment.native.s").read_text())
            fragment, mapping, writes = remap(native, block)
            (folder / "fragment.inc").write_text(fragment)
            generated.extend(lines[cursor:block.start])
            prefix = SYMBOL + "." + block.id
            generated.extend([prefix + ".begin:\n", fragment, prefix + ".end:\n"])
            cursor = block.end + 1
            report["blocks"].append(dict(contract=asdict(block), native=native, native_to_pool=mapping,
                                          written_vgprs=writes, special_clobbers=native["clobbers"]))
        generated.extend(lines[cursor:])
        text = "".join(generated)
        require(not re.search(r"^\s*\.hip\.", text, re.M), "Unprocessed HIP directive")
        (output / "kernel.generated.s").write_text(text)
        run([llvm / "llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1100", "-filetype=obj",
             output / "kernel.generated.s", "-o", output / "kernel.o"])
        run([llvm / "ld.lld", "-shared", "--no-undefined", output / "kernel.o", "-o", output / "demo.co"])
        (output / "kernel.disasm.txt").write_text(run([llvm / "llvm-objdump", "--mcpu=gfx1100", "-d", output / "demo.co"]))
        (output / "kernel.elf.txt").write_text(run([llvm / "llvm-readelf", "-h", "-s", "-r", "-n", output / "demo.co"]))
        report.update(status="BUILT_NOT_TESTED", llvm_version=run([llvm / "clang++", "--version"]).splitlines()[0],
                      source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                      preprocessor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      binary_sha256=hashlib.sha256((output / "demo.co").read_bytes()).hexdigest(),
                      fp_contract="off", fast_math=False, calls=0, private_bytes=0)
        print(f"Built {output / 'demo.co'}: {len(blocks)} HIP blocks, no tests/GPU launch")
        return report
    except Exception as error:
        (output / "demo.co").unlink(missing_ok=True)
        report.update(status="BUILD_FAILED", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        (output / "build_report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=ROOT / "kernel.s")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--llvm-bin", type=Path, default=Path("/opt/rocm/lib/llvm/bin"))
    args = parser.parse_args()
    build(args.source, args.build_dir, args.llvm_bin)
