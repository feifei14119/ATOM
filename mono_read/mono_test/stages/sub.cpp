// Separate device compilation of sub.h. Keep the original inline helper intact
// and expose a callable device symbol for later linking into a GPU program.
#include "sub.h"

extern "C" __device__ __attribute__((noinline)) void stage_sub_device(
    const float* input, Mailbox output, int n, unsigned epoch) {
  stage_sub(input, output, n, epoch);
}
