#pragma once

#include <cstdint>
#include "../mailbox.h"

// Fixed ABI of the supplied gfx1100 machine code. Every thread of CTA 0 must
// participate: the embedded stage contains a barrier and publishes its mailbox.
__device__ __forceinline__ __attribute__((convergent))
void stage_sub_inline(const float* input, Mailbox output, int n, unsigned epoch) {
  // Clang's C++ register names are single 32-bit registers. Split every pointer
  // explicitly: binding an i64 to "v0" would not also populate its high word!
  const auto in = reinterpret_cast<std::uintptr_t>(input);
  const auto out = reinterpret_cast<std::uintptr_t>(output.data);
  const auto flag = reinterpret_cast<std::uintptr_t>(output.tag);
  const auto implicit = reinterpret_cast<std::uintptr_t>(__builtin_amdgcn_implicitarg_ptr());
  register unsigned in_lo asm("v0") = static_cast<unsigned>(in);
  register unsigned in_hi asm("v1") = static_cast<unsigned>(in >> 32);
  register unsigned out_lo asm("v2") = static_cast<unsigned>(out);
  register unsigned out_hi asm("v3") = static_cast<unsigned>(out >> 32);
  register unsigned tag_lo asm("v4") = static_cast<unsigned>(flag);
  register unsigned tag_hi asm("v5") = static_cast<unsigned>(flag >> 32);
  register int count asm("v6") = n;
  register unsigned tag asm("v7") = epoch;
  register unsigned tid asm("v31") = threadIdx.x;
  register unsigned implicit_lo asm("s8") = static_cast<unsigned>(implicit);
  register unsigned implicit_hi asm("s9") = static_cast<unsigned>(implicit >> 32);
  register unsigned block_id asm("s12") = blockIdx.x;

  asm volatile(
      "s_branch 1f\n"
      ".p2align 6\n"
      "1:\n"
      // C++ string literals containing .long values, generated from the .co.
#include "sub_words.inc"
      // The original device return is omitted. Finish stores and fall through
      // to compiler-generated Mono code with the original EXEC restored.
      "s_waitcnt vmcnt(0) lgkmcnt(0)\n"
      "s_waitcnt_vscnt null, 0\n"
      "s_waitcnt_depctr 0\n"
      :
      : "v"(in_lo), "v"(in_hi), "v"(out_lo), "v"(out_hi),
        "v"(tag_lo), "v"(tag_hi), "v"(count), "v"(tag),
        "v"(tid), "s"(implicit_lo), "s"(implicit_hi), "s"(block_id)
      : "s0", "s1", "s2", "s3",
        "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15",
        "vcc", "scc", "memory");
}
