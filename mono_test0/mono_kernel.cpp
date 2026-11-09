#include "stages/sub_api.h"
#include "stages/scale.h"
#include "stages/relu.h"

// A single launchable kernel. The compiler generates a normal device call to
// stage_sub_device; the linker resolves it from the separately assembled .co.
extern "C" __global__
void mono_kernel(const float* input, float* output, Mailbox first,
                 Mailbox second, int n, unsigned epoch) {
  if (blockIdx.x == 0) {
    stage_sub_device(input, first, n, epoch);
  } else if (blockIdx.x == 1) {
    stage_scale(first, second, n, epoch);
  } else if (blockIdx.x == 2) {
    stage_relu(second, output, n, epoch);
  }
}
