#pragma once

#include <hip/hip_runtime.h>

#include "mono_abi.h"

// Shared inline device helpers. Each device compilation includes these
// definitions; there is no separate mailbox object or module.
__device__ __forceinline__ void wait_for(const Mailbox mailbox, unsigned epoch) {
  // Every reader thread acquires the publication before reading its elements.
  while (__hip_atomic_load(mailbox.tag, __ATOMIC_ACQUIRE,
                           __HIP_MEMORY_SCOPE_AGENT) != epoch) {
    __builtin_amdgcn_s_sleep(1);
  }
}

__device__ __forceinline__ void publish(const Mailbox mailbox, unsigned epoch) {
  // All threads finish writing the global payload before thread 0 publishes.
  __syncthreads();
  if (threadIdx.x == 0) {
    __hip_atomic_store(mailbox.tag, epoch, __ATOMIC_RELEASE,
                       __HIP_MEMORY_SCOPE_AGENT);
  }
}
