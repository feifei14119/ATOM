#pragma once

#include <hip/hip_runtime.h>

#include "../mono_abi.h"

// Declaration only. The implementation is supplied as an AMDGPU ELF REL object.
// ABI: ROCm 7.2, gfx1100, wave32, default HIP device-function calling convention.
// All threads of the producer CTA must call this function. It writes input-1
// to output.data, then publishes epoch to output.tag with agent release ordering.
extern "C" __device__ void stage_sub_device(
    const float* input, Mailbox output, int n, unsigned epoch);
