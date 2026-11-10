#include "stages/sub.h"
#include "stages/scale.h"
#include "stages/relu.h"

// Same three-CTA pipeline as mono_test0. The subtraction is actual inline asm
// containing .long instruction words, visible to LLVM before allocation.
extern "C" __global__
void mono_kernel(const float* input, float* output, Mailbox first,
                 Mailbox second, int n, unsigned epoch) {
  if (blockIdx.x == 0) {
    stage_sub_inline(input, first, n, epoch);
  } else if (blockIdx.x == 1) {
    stage_scale(first, second, n, epoch);
  } else if (blockIdx.x == 2) {
    stage_relu(second, output, n, epoch);
  }
}
