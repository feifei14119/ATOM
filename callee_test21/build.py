#!/usr/bin/env python3
"""Minimal, fail-closed FlyDSL-in-ASM preprocessor, pinned to gfx1100.

Only one f32(f32,f32) straight-line fragment and a small instruction subset.
The LLVM helper ABI is checked before bounded VGPR remapping. No LLVM patch,
HIP wrapper, device call, machine-code injection, or unrestricted ASM rewriting.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
SYMBOL = "flydsl_fragment"
REG = re.compile(r"v([0-9]+)\Z")
OPS = {"v_mul_f32_e32", "v_add_f32_e32", "v_sub_f32_e32"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(argv):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    require(result.returncode == 0, f"Command failed: {argv}\n{result.stdout}{result.stderr}")
    return result.stdout


def parse(source):
    lines = source.splitlines(keepends=True)
    starts = [i for i, x in enumerate(lines) if x.strip().startswith(".flydsl.begin ")]
    ends = [i for i, x in enumerate(lines) if x.strip() == ".flydsl.end"]
    require(len(starts) == len(ends) == 1 and starts[0] < ends[0],
            "Demo requires exactly one top-level .flydsl.begin/.flydsl.end block")
    start, end = starts[0], ends[0]
    block_id = lines[start].strip().split()[1]
    require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", block_id), "Invalid block ID")
    bindings, function, pool = [], None, None
    for line in lines[start + 1:end]:
        text = line.strip()
        if not text or text.startswith("//"):
            continue
        m = re.fullmatch(r"\.flydsl\.(in|out) f32 ([A-Za-z_][A-Za-z0-9_]*)\s*=\s*v([0-9]+)", text)
        if m:
            bindings.append({"kind": m[1], "name": m[2], "reg": int(m[3])})
            continue
        m = re.fullmatch(r"\.flydsl\.function ([^\s:]+):([A-Za-z_][A-Za-z0-9_]*)", text)
        if m:
            require(function is None, "Duplicate function declaration")
            function = [m[1], m[2]]
            continue
        m = re.fullmatch(r"\.flydsl\.temp vgpr\s*=\s*v\[([0-9]+):([0-9]+)\]", text)
        if m:
            require(pool is None, "Duplicate temporary pool")
            first, last = int(m[1]), int(m[2])
            require(0 <= first <= last <= 255, "Invalid gfx1100 temporary VGPR range")
            pool = list(range(first, last + 1))
            continue
        raise RuntimeError(f"Unsupported fragment directive: {text}")
    require(function is not None and pool is not None, "Missing function or pool")
    require([x["kind"] for x in bindings] == ["in", "in", "out"],
            "Demo signature must be two ordered f32 inputs and one f32 output")
    registers = [x["reg"] for x in bindings]
    require(all(0 <= r <= 255 for r in registers), "Invalid gfx1100 binding")
    require(len(set(registers)) == 3 and not set(registers) & set(pool),
            "Bindings must be distinct and disjoint from the temporary pool")
    require(len({x["name"] for x in bindings}) == 3, "Duplicate variable name")
    require('.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"' in source, "Requires gfx1100 ASM")
    require(not any(".flydsl." in x for x in lines[:start] + lines[end + 1:]),
            "Unexpected FlyDSL directive outside the block")
    # Top-level blocks only: this deliberately does not implement ASM macro expansion.
    require(not re.search(r"^\s*\.(?:macro|if\w*|rept|irp|irpc)\b", source, re.M),
            "Demo does not accept ASM macros or conditional/repeated assembly")
    declared = re.findall(r"^\s*\.amdhsa_next_free_vgpr\s+([0-9]+)\s*$", source, re.M)
    require(len(declared) == 1, "Demo requires one literal VGPR descriptor budget")
    require(max(registers + pool) < int(declared[0]) <= 256,
            "ASM descriptor does not cover the bindings and authorized temporary pool")
    return lines, start, end, {"id": block_id, "function": function,
                              "bindings": bindings, "temporary_vgprs": pool}


def trace(function_path, function_name, names, output):
    import flydsl.expr as fx
    from flydsl._mlir import ir
    from flydsl._mlir.dialects import func
    from flydsl._mlir.passmanager import PassManager
    from flydsl._mlir._mlir_libs._mlirDialectsLLVM import translate_module_to_llvmir
    from flydsl.compiler.jit_function import _create_mlir_context

    spec = importlib.util.spec_from_file_location("demo_expressions", function_path)
    require(spec is not None and spec.loader is not None, "Cannot import expression file")
    python_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(python_module)
    function = getattr(python_module, function_name)
    import inspect
    require(list(inspect.signature(function).parameters) == names,
            "Ordered input names must match the FlyDSL function parameters")
    with _create_mlir_context(), ir.Location.unknown():
        module = ir.Module.create()
        with ir.InsertionPoint(module.body):
            f32 = ir.F32Type.get()
            fn = func.FuncOp(SYMBOL, ([f32, f32], [f32]))
            block = fn.add_entry_block()
            with ir.InsertionPoint(block):
                value = function(*[fx.Float32(arg) for arg in block.arguments])
                require(isinstance(value, fx.Float32), "Function must return one FlyDSL Float32")
                func.ReturnOp([value.ir_value()])
        module.operation.verify()
        (output / "fragment.mlir").write_text(str(module) + "\n")
        def walk(op):
            yield op
            for region in op.regions:
                for b in region.blocks:
                    for child in b.operations:
                        yield from walk(child.operation)
        allowed = {"builtin.module", "func.func", "func.return", "arith.mulf", "arith.addf", "arith.subf"}
        require(all(op.name in allowed for op in walk(module.operation)),
                "Demo accepts only f32 add/sub/mul: unsupported MLIR operation")
        pm = PassManager.parse("builtin.module(convert-arith-to-llvm,convert-func-to-llvm,reconcile-unrealized-casts)")
        pm.enable_verifier(True)
        pm.run(module.operation)
        (output / "fragment.lowered.mlir").write_text(str(module) + "\n")
        (output / "fragment.ll").write_text(translate_module_to_llvmir(module.operation))


def extract(assembly):
    # Check the complete native helper body, including its ABI shell.
    match = re.search(r"^" + SYMBOL + r":[^\n]*\n(.*?)^\.Lfunc_end[0-9]+:", assembly, re.M | re.S)
    require(match is not None, "Cannot locate sized helper function")
    instructions = []
    for raw in match[1].splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            require(not line.startswith(".") and not line.endswith(":"),
                    "Unexpected label/directive or multiple basic blocks")
            instructions.append(line)
    require(instructions and instructions[0] == "s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)",
            "Unexpected helper prologue; review this LLVM version")
    require(instructions[-1] == "s_setpc_b64 s[30:31]", "Unexpected helper return ABI")
    body = instructions[1:-1]
    written, available = set(), {0, 1}
    used, parsed = {0, 1}, []
    for line in body:
        if re.fullmatch(r"s_delay_alu instid0\(VALU_DEP_[1-4]\)", line):
            parsed.append((None, line))
            continue
        opcode, _, operands = line.partition(" ")
        require(opcode in OPS, f"Unsupported helper instruction: {line}")
        args = [x.strip() for x in operands.split(",")]
        require(len(args) == 3 and all(REG.fullmatch(x) for x in args),
                f"Only three single-VGPR operands are supported: {line}")
        regs = [int(REG.fullmatch(x)[1]) for x in args]
        require(set(regs[1:]) <= available, "Read of an undefined helper register")
        available.add(regs[0])
        written.add(regs[0])
        used.update(regs)
        parsed.append((opcode, regs))
    require(0 in written, "Helper result v0 was not defined")
    return parsed, sorted(used)


def remap(parsed, used, contract):
    pool = contract["temporary_vgprs"]
    require(len(used) <= len(pool), f"Temporary pool has {len(pool)} registers; helper uses {len(used)}")
    mapping = dict(zip(used, pool))
    inputs = contract["bindings"][:2]
    result = contract["bindings"][2]["reg"]
    lines = [f"// FlyDSL fragment {contract['id']}: inputs copied into isolated VGPR pool."]
    for native, item in enumerate(inputs):
        lines += [f"v_mov_b32_e32 v{mapping[native]}, v{item['reg']}", "s_nop 7"]
    for opcode, regs in parsed:
        if opcode is None:
            lines.append(regs)
        else:
            lines.append(opcode + " " + ", ".join(f"v{mapping[r]}" for r in regs))
            # Conservative spacing for this small demo, including new bridge edges.
            lines.append("s_nop 7")
    lines += [f"v_mov_b32_e32 v{result}, v{mapping[0]}", "s_nop 7"]
    return "\n".join("    " + line for line in lines) + "\n", mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "kernel.s")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--llvm-bin", type=Path, default=Path("/opt/rocm/lib/llvm/bin"))
    args = parser.parse_args()
    source, output, llvm = args.source.resolve(), args.build_dir.resolve(), args.llvm_bin.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A failed rebuild must not leave an older code object masquerading as success.
    for name in ("demo.co", "kernel.generated.s", "build_report.json", "gpu_result.json", "static_report.json"):
        (output / name).unlink(missing_ok=True)
    text = source.read_text()
    lines, start, end, contract = parse(text)
    os.environ["ARCH"] = "gfx1100"
    os.environ["FLYDSL_GPU_ARCH"] = "gfx1100"
    os.environ["COMPILE_ONLY"] = "1"
    expression_file = (source.parent / contract["function"][0]).resolve()
    try:
        trace(expression_file, contract["function"][1],
              [x["name"] for x in contract["bindings"][:2]], output)
    except ModuleNotFoundError as error:
        raise RuntimeError("Select a Python environment with FlyDSL installed: make PYTHON=/path/to/python") from error
    run([llvm / "llc", "-mtriple=amdgcn-amd-amdhsa", "-mcpu=gfx1100", "-O2", "-fp-contract=off",
         output / "fragment.ll", "-o", output / "fragment.native.s"])
    parsed, used = extract((output / "fragment.native.s").read_text())
    fragment, mapping = remap(parsed, used, contract)
    (output / "fragment.inc").write_text(fragment)
    generated = ("".join(lines[:start]) + "asm_flydsl_demo.fragment_begin:\n" + fragment
                 + "asm_flydsl_demo.fragment_end:\n" + "".join(lines[end + 1:]))
    (output / "kernel.generated.s").write_text(generated)
    run([llvm / "llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1100", "-filetype=obj",
         output / "kernel.generated.s", "-o", output / "kernel.o"])
    run([llvm / "ld.lld", "-shared", "--no-undefined", output / "kernel.o", "-o", output / "demo.co"])
    (output / "kernel.disasm.txt").write_text(run([
        llvm / "llvm-objdump", "--mcpu=gfx1100", "--disassemble-symbols=asm_flydsl_demo", output / "demo.co"]))
    (output / "kernel.elf.txt").write_text(run([llvm / "llvm-readelf", "-h", "-s", "-r", "-n", output / "demo.co"]))
    import importlib.metadata
    report = {"status": "BUILT_NOT_GPU_TESTED", "target": "gfx1100", "wave_size": 32,
              "contract": contract, "native_to_pool": mapping, "native_live_in": [0, 1],
              "native_result": 0, "fragment_written_vgprs": sorted(set(mapping.values()) | {contract['bindings'][2]['reg']}),
              "special_clobbers": [], "calls": 0, "private_bytes": 0,
              "llvm_version": run([llvm / "llc", "--version"]).splitlines()[0],
              "flydsl_version": importlib.metadata.version("flydsl"),
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "expression_sha256": hashlib.sha256(expression_file.read_bytes()).hexdigest(),
              "binary_sha256": hashlib.sha256((output / "demo.co").read_bytes()).hexdigest()}
    (output / "build_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Built {output / 'demo.co'}; FlyDSL v0/v1 -> pool {mapping} -> output v{contract['bindings'][2]['reg']}")


if __name__ == "__main__":
    main()
