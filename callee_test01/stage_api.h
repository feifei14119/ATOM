#pragma once
#include <hip/hip_runtime.h>
#include "test_types.h"

// CUSTOM ABI: same parameter/return locations as the default device ABI, but
// only its v<64 and s<40 preservation bits survive (plus special registers).
// This declaration alone does NOT communicate that contract to Clang.
// Use the Makefile's pre-RA regmask pass; do not link it to a normal HIP caller.
// A distinct symbol prevents accidental substitution for the standard ABI.
extern "C" __device__ std::uint32_t stage_probe_lowctx(
    std::uint32_t bias, std::uint32_t* input, Record* record,
    std::uint32_t tx, std::uint32_t ty, std::uint32_t bx, std::uint32_t by);
