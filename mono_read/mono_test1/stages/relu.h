#pragma once

#include "../mailbox.h"

// CTA 2: consume the second mailbox and write the final output.
__device__ __forceinline__ void stage_relu(const Mailbox input, float* output,
                                          int n, unsigned epoch) {
  wait_for(input, epoch);
  for (int i = threadIdx.x; i < n; i += blockDim.x) {
    output[i] = fmaxf(input.data[i] - 3.0f, 0.0f);
  }
}
