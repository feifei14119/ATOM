#pragma once

#include <cstdint>
#include "../mailbox.h"

// All threads of CTA 0 must participate: the payload contains a CTA barrier.
// Fixed input constraints make LLVM place each argument in the register read
// by the payload. No explicit argument moves or C++ register variables needed.
__device__ __forceinline__ __attribute__((convergent))
void stage_sub_inline(const float* input, Mailbox output, int n, unsigned epoch) {
  const auto in = reinterpret_cast<std::uintptr_t>(input);
  const auto out = reinterpret_cast<std::uintptr_t>(output.data);
  const auto flag = reinterpret_cast<std::uintptr_t>(output.tag);
  const auto implicit = reinterpret_cast<std::uintptr_t>(__builtin_amdgcn_implicitarg_ptr());

  asm volatile(
      "s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)\n"
      "s_waitcnt_vscnt null, 0\n"
      "s_waitcnt_depctr 0\n"
      "s_branch 1f\n"
      ".p2align 6\n"
      "1:\n"
#include "sub_words.inc"
      // Original return removed; complete writes, then continue Mono normally.
      "s_waitcnt vmcnt(0) lgkmcnt(0)\n"
      "s_waitcnt_vscnt null, 0\n"
      "s_waitcnt_depctr 0\n"
      : // Results go to memory; there are no C++ register outputs.
      : [in_lo] "{v0}"(static_cast<unsigned>(in)),
        [in_hi] "{v1}"(static_cast<unsigned>(in >> 32)),
        [out_lo] "{v2}"(static_cast<unsigned>(out)),
        [out_hi] "{v3}"(static_cast<unsigned>(out >> 32)),
        [tag_lo] "{v4}"(static_cast<unsigned>(flag)),
        [tag_hi] "{v5}"(static_cast<unsigned>(flag >> 32)),
        [count] "{v6}"(n), [epoch] "{v7}"(epoch), [tid] "{v31}"(threadIdx.x),
        [implicit_lo] "{s8}"(static_cast<unsigned>(implicit)),
        [implicit_hi] "{s9}"(static_cast<unsigned>(implicit >> 32)),
        [block_id] "{s12}"(blockIdx.x)
      : // Only actual payload writes. Read-only fixed inputs must not also
        // appear as clobbers. No function-wide register-count limit is set.
        "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15",
        "s0", "s1", "s2", "s3",
        "vcc", "scc", "memory");
  // The payload restores EXEC itself. It does not modify MODE or the stack.
}
