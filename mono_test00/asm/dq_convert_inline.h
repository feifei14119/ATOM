#pragma once

#include <hip/hip_runtime.h>
#include "dq_convert_args.h"

#if defined(__HIP_DEVICE_COMPILE__) && !defined(__gfx1250__)
#error "dq_convert inline instruction words require gfx1250 wave32"
#endif

// Whole 128/256-thread 1D CTA, full EXEC; uniform GPU-global args pointer.
// args describes one packed FP32 64x64 tile and one BF16 64x64 output tile.
// Caller provides global-memory fences and whole-CTA barriers before/after.
// This helper is force-inlined into the STANDARD-ABI noinline wrapper.
// LLVM sees the clobbers below and preserves the wrapper's callee-saved GPRs.
// No register-count attributes or custom regmask are used.
__device__ __forceinline__ __attribute__((convergent))
void stage_dq_convert_inline(const DqConvertArgs* args, unsigned linear_tid) {
  const auto raw_address = reinterpret_cast<std::uintptr_t>(args);
  // The argument record is uniform within the wave. Make that fact visible
  // before satisfying the fixed scalar-register input constraint.
  const std::uint32_t lo = __builtin_amdgcn_readfirstlane(static_cast<unsigned>(raw_address));
  const std::uint32_t hi = __builtin_amdgcn_readfirstlane(static_cast<unsigned>(raw_address >> 32));
  const std::uint64_t address = std::uint64_t(lo) | (std::uint64_t(hi) << 32);
  const unsigned lane = linear_tid & 31u;
  const unsigned wave = static_cast<unsigned>(__builtin_amdgcn_readfirstlane(linear_tid)) >> 5;
  asm volatile(
      // Preserve the fragment's alignment. Numeric labels allow repeated uses.
      "s_branch 1f\n"
      ".p2align 6\n"
      "1:\n"
#include "dq_convert.inline.words.inc"
      :
      : [args] "{s[0:1]}"(address), [lane] "{v0}"(lane), [wave] "{s24}"(wave)
      : // All and only written GPRs, including s5 for the MODE backup.
        // Read-only fixed inputs s0:s1, s24 and v0 are NOT clobbers.
        "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9",
        "s10", "s11", "s12", "s13", "s14", "s15", "s16", "s17",
        "s18", "s19", "s20", "s21", "s22", "s23",
        "s25", "s26", "s27", "s28", "s29",
        "s40", "s41", "s42", "s43", "s44", "s45", "s46", "s47", "s48",
        "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11",
        "v12", "v13", "v14", "v15", "v16", "v17", "v18", "v19",
        "v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27",
        "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v35",
        "v36", "v37", "v38", "v39", "v40", "v41", "v42", "v43",
        "v44", "v45", "scc", "memory");
  // EXEC and floating-point MODE are restored by the fragment. It never
  // changes VCC, M0, TTMP, s30:s39, stack state or gfx1250 VGPR bank bits.
}
