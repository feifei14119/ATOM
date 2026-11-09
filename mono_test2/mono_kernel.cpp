// Compile a real device call. LLVM handles argument placement and the call ABI.
// The implementation of stage_sub_device is supplied only as stage_sub.co.
#include "stages/sub_api.h"
#include "stages/scale.h"
#include "stages/relu.h"

// callsite_regmask.py narrows only the stage_sub_device call's preserved VGPR
// mask before register allocation. There is no function-wide VGPR limit, so
// inlined scale/relu and other local computations retain their register budget.
// make check rejects spills; the call mask alone does not prohibit them.
extern "C" __global__
void mono_kernel(const float* input, float* output, Mailbox first,
                 Mailbox second, int n, unsigned epoch, unsigned* sub_done) {
  if (blockIdx.x == 0) {
    const unsigned tid = threadIdx.x;
    // A real value that must survive the opaque ASM call. Volatile requires
    // this read to occur before the call, rather than loading it afterwards.
    const float lane_bias = tid < static_cast<unsigned>(n)
                                ? static_cast<const volatile float*>(input)[tid]
                                : 0.0f;

    // The supplied ASM publishes its output before returning. Give it an
    // internal tag so CTA 1 cannot consume data before our post-call work.
    stage_sub_device(input, Mailbox{first.data, sub_done}, n, epoch);

    for (int i = tid; i < n; i += blockDim.x) {
      first.data[i] += lane_bias;
    }
    publish(first, epoch);
  } else if (blockIdx.x == 1) {
    stage_scale(first, second, n, epoch);
  } else if (blockIdx.x == 2) {
    stage_relu(second, output, n, epoch);
  }
}
