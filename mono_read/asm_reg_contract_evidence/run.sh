#!/usr/bin/env bash
# Reproduce the evidence in ../ASM_REG_CONTRACT_REQUIREMENT.zh-CN.md (compile only, no GPU).
# Usage: LLVM_BIN=/path/to/llvm/bin ./run.sh
set -u
here=$(cd "$(dirname "$0")" && pwd)
L=${LLVM_BIN:-/app/ATOM/mono_test01/build/llvm-bin}
llc() { "$L/llc" -mtriple=amdgcn-amd-amdhsa -mcpu=gfx1250 "$@"; }
out=$(mktemp -d)
"$L/llc" --version | grep -m1 -i 'llvm version'

meta() { grep -E "^\s+\.(name|private_segment_fixed_size|sgpr_count|sgpr_spill_count|vgpr_count|vgpr_spill_count):" "$1" |
  grep -vE '^\s{8}\.name' ; }

echo "== E1: high VGPR as an output constraint"
llc "$here/e1_high_vgpr_output.ll" -o "$out/e1.s" 2>&1 | head -1

echo "== E2: clobber names (hi=~{v300}, rng=~{v[4:200]}, tup=~{v[4:7]}, lo=~{v200})"
llc "$here/e2_clobber_names.ll" -o "$out/e2.s" 2>&1
meta "$out/e2.s" | grep -E 'name|vgpr_count'

echo "== E3: v0-v255 / s0-s105 clobbered while values are live across the asm"
llc "$here/e3_live_across.ll" -o "$out/e3.s" 2>&1 | grep -v '^note'
meta "$out/e3.s"
echo "-- instructions around the asm (VGPR MSB state at asm entry):"
grep -B2 -A2 'big clobber' "$out/e3.s"

echo "== E4: same, with amdgpu-waves-per-eu=4 (256 VGPR cap)"
llc "$here/e4_spill_to_scratch.ll" -o "$out/e4.s" 2>&1 | grep -v -e '^note' -e s105
meta "$out/e4.s" | head -6
grep -cE 'scratch_(store|load)' "$out/e4.s" | sed 's/^/scratch spill instructions: /'

for ipra in "" "-enable-ipra"; do
  echo "== E5: noinline asm wrapper called from a kernel ${ipra:-(default)}"
  llc $ipra "$here/e5_function_call.ll" -o "$out/e5.s" 2>&1
  sed -n '/^frag:/,/s_set_pc/p' "$out/e5.s" | grep -E 'FRAG|scratch_|s_set_pc'
  grep -E 's_swap_pc|private_segment_fixed_size' "$out/e5.s"
done
echo "outputs: $out"
