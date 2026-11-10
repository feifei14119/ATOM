#!/usr/bin/env python3
"""Compile all three actual gfx1250 variants and run CPU/static checks only."""
import argparse
from pathlib import Path


def build_all(llvm):
    from build_asm_mono import configure,build,BUILD
    configure()
    build(llvm)
    import flydsl.expr as fx
    from mono1250.kernels.reference_projection import build_projection_c1
    from mono1250.kernels.projection_asm import build_projection_asm
    from mono1250.runtime.compile import _code_object
    variants=[('native',build_projection_c1(front=True,fold=False,feeds_index=True,threads=256),14),
              ('inline',build_projection_asm(),15)]
    for variant,launch,argc in variants:
        launch(*([0]*argc),stream=fx.Stream(0))
        artifacts=list(launch._mem_cache.values())
        assert len(artifacts)==1
        text=artifacts[0]._ir_text
        out=BUILD/variant;out.mkdir(parents=True,exist_ok=True)
        (out/'kernel.mlir').write_text(text)
        (out/'kernel.co').write_bytes(_code_object(text))
        print('[offline/build] '+variant,flush=True)
    from verify_offline import verify
    verify()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-bin',type=Path,default=Path('/opt/rocm/llvm/bin'))
    build_all(parser.parse_args().llvm_bin)
