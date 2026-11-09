// Compile/link check only. No GPU execution or ATOM scheduling is performed.
#include "dq_convert_inline.h"

extern "C" __global__ __launch_bounds__(256)
void mono_inline_check(const DqConvertArgs* args, float* state) {
  const unsigned tid = threadIdx.x;
  // Independent live value must survive both opaque inline fragments.
  const float live = static_cast<volatile float*>(state)[tid];
  __threadfence_block();
  __syncthreads();
  stage_dq_convert_inline(args, tid);
  __threadfence_block();
  __syncthreads();
  state[tid] = live + 1.0f;
  // Exercise repeated inline expansion and a nonterminal stage. In a real
  // pipeline args/output are per CTA and stage tags obey the Mono protocol.
  stage_dq_convert_inline(args, tid);
  __threadfence_block();
  __syncthreads();
  state[tid] = live + 2.0f;
}
