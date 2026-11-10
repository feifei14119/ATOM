#pragma once

#include "../mailbox.h"

// CTA 0: produce the first mailbox's payload and publish its current epoch.
__device__ __forceinline__ void stage_add(const float* input,
                                         const Mailbox output, int n,
                                         unsigned epoch) {
  for (int i = threadIdx.x; i < n; i += blockDim.x) {
    output.data[i] = input[i] + 1.0f;
  }
  publish(output, epoch);
}
