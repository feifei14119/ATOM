#include "../../stages/sub_api.h"

// A separate one-CTA test of a value that must survive an opaque device call.
// Limit allocation below v40, where the ordinary ABI's first preserved VGPR
// bank begins. This deliberately makes LLVM demonstrate a scratch save/reload.
// This constraint belongs to the test, not to the main Mono kernel.
extern "C" __global__ __attribute__((amdgpu_num_vgpr(40)))
void live_state_kernel(float* data, unsigned* tag, float* before_result,
                       int n, unsigned epoch) {
  const unsigned tid = threadIdx.x;
  const float before = tid < static_cast<unsigned>(n)
                           ? static_cast<volatile float*>(data)[tid]
                           : 0.0f;

  // All threads participate: stage_sub_device contains a CTA barrier.
  // The same allocation is input and output, so the old value cannot be
  // recovered by simply reloading data after the call.
  stage_sub_device(data, Mailbox{data, tag}, n, epoch);

  if (tid < static_cast<unsigned>(n)) {
    before_result[tid] = before;
  }
}
