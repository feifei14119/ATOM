#pragma once
#include <cstdint>
#include <hip/hip_runtime.h>

// Numeric address matches FlyDSL ffi's uint64 type. Inside the wrapper it is
// cast to DqConvertArgs*. The record address must be uniform across the wave.
// Standard device C ABI, full EXEC, gfx1250 wave32; all 256 CTA threads call.
extern "C" __device__ __attribute__((noinline, convergent))
void mono_dq_convert_wrapper(std::uint64_t args_address, std::uint32_t linear_tid);
