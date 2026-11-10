#pragma once
#include <hip/hip_runtime.h>
#include "test_types.h"

// Only a declaration: stage_probe.s supplies the implementation in a separate
// relocatable AMDGPU ELF object. This is NOT a __global__ kernel entry.
// stage_probe.s really overwrites v64-v255/s40-s105, and explicitly restores
// the callee-saved subset. Its private frame occupies 528 bytes at incoming s32.
extern "C" __device__ std::uint32_t stage_probe(
    std::uint32_t bias, std::uint32_t* input, Record* record,
    std::uint32_t tx, std::uint32_t ty, std::uint32_t bx, std::uint32_t by);
