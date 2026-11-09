// Compile a device call to let LLVM prepare the argument registers. The default
// build fuses the binary stage into the final assembly and uses direct branches.
#include "stages/sub_api.h"
#include "stages/scale.h"
#include "stages/relu.h"

// The only launchable kernel in the default linked module.
// fuse_sub.py removes the subtraction call/return; scale/relu are C++ inlines.
extern "C" __global__ void mono_kernel(const float* input, float* output,
                                       Mailbox first, Mailbox second, int n,
                                       unsigned epoch) {
  if (blockIdx.x == 0) {
    stage_sub_device(input, first, n, epoch);
  } else if (blockIdx.x == 1) {
    stage_scale(first, second, n, epoch);
  } else if (blockIdx.x == 2) {
    stage_relu(second, output, n, epoch);
  }
}
