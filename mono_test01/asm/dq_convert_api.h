#pragma once
#include "dq_convert_args.h"
#if defined(__HIPCC__) || defined(__HIP__)
#include <hip/hip_runtime.h>
// CUSTOM ABI: parameter layout matches ordinary device C calling convention,
// but caller MUST run callsite_regmask.py before register allocation.
// The declaration alone does not narrow the call-preserved mask.
// args -> v0:v1; linear_tid -> v2; return PC -> s30:s31.
// Whole CTA / full EXEC / wave32 / 256 threads in the Mono unit test.
extern "C" __device__ __attribute__((noinline, convergent))
void mono_dq_convert_lowctx(const DqConvertArgs* args, unsigned linear_tid);
#endif
