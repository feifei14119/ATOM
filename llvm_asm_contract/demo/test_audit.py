#!/usr/bin/env python3
"""Negative tests for the real-object packaging boundary; no GPU required."""
import argparse
import copy
from pathlib import Path
import tempfile

from contract import audit_object, pack_stage, run, verify_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-bin", type=Path, default=Path("/opt/rocm/llvm/bin"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="asm-contract-audit-") as directory:
        manifest, audit = pack_stage(Path(__file__).resolve().parent, directory, args.llvm_bin)
        cases = []
        bad = copy.deepcopy(manifest)
        bad["clobbers"].remove("v95")
        cases.append(("undeclared high VGPR write", bad, "undeclared register write"))
        bad = copy.deepcopy(manifest)
        bad["resources"]["vgpr_count"] = 64
        cases.append(("resource extent below actual register", bad, "resource extent"))
        bad = copy.deepcopy(manifest)
        bad["resources"]["private_bytes"] = 16
        cases.append(("callee private memory declaration", bad, "private/LDS"))
        for name, candidate, diagnostic in cases:
            try:
                audit_object(candidate["object_path"], candidate, args.llvm_bin)
            except ValueError as error:
                assert diagnostic in str(error), error
                print("PASS:", name)
            else:
                raise AssertionError(name+" was incorrectly accepted")
        shared = Path(directory)/"stage.shared.co"
        run([args.llvm_bin/"ld.lld", "-shared", manifest["object_path"], "-o", shared])
        try:
            audit_object(shared, manifest, args.llvm_bin)
        except ValueError as error:
            assert "ELF ET_REL" in str(error), error
            print("PASS: non-relocatable device object")
        else:
            raise AssertionError("ET_DYN object was incorrectly accepted")
        unsupported_source = Path(directory)/"unsupported.s"
        source = (Path(__file__).resolve().parent/"stage.s").read_text()
        unsupported_source.write_text(source.replace("contract_stage:\n", "contract_stage:\n    s_nop 0\n", 1))
        unsupported_object = Path(directory)/"unsupported.co"
        run([args.llvm_bin/"llvm-mc", "-triple=amdgcn-amd-amdhsa", "-mcpu=gfx1250",
             "-filetype=obj", unsupported_source, "-o", unsupported_object])
        try:
            audit_object(unsupported_object, manifest, args.llvm_bin)
        except ValueError as error:
            assert "unsupported callee instruction" in str(error), error
            print("PASS: instruction outside the restricted audit vocabulary")
        else:
            raise AssertionError("unrecognized instruction was incorrectly accepted")
        # A correctly packaged contract must reject a subsequent same-path replacement.
        path = Path(manifest["object_path"])
        path.write_bytes(path.read_bytes()+b"replacement")
        try:
            verify_identity(manifest)
        except ValueError as error:
            assert "object hash differs" in str(error), error
            print("PASS: changed object identity")
        else:
            raise AssertionError("modified object was incorrectly accepted")
        print(f"AUDIT PASS: {audit['instruction_count']} real decoded instructions; 6 rejected violations")


if __name__ == "__main__":
    main()
