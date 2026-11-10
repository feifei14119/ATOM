#pragma once

#include "../mailbox.h"

// CTA 1: consume the first mailbox, then produce and publish the second one.
__device__ __forceinline__ void stage_scale(const Mailbox input,
                                           const Mailbox output, int n,
                                           unsigned epoch) {
  wait_for(input, epoch);
  for (int i = threadIdx.x; i < n; i += blockDim.x) {
    output.data[i] = input.data[i] * 2.0f;
  }
  publish(output, epoch);
}
