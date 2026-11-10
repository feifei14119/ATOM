#include "stage_api.h"

// Test blocks use at most 256 threads; this permits all 256 VGPRs on gfx1100.
extern "C" __global__ __launch_bounds__(256) void caller_kernel(
    std::uint32_t* input, Record* records, const std::uint32_t* uniform_seed) {
  // Resource declaration: the stage uses v255 and s105, even where the
  // boundary preserves s105. This empty asm emits no instruction and sets no
  // register limit; LLVM includes the highest registers in the descriptor.
  asm volatile("" ::: "v255", "s105");
  const unsigned tx = threadIdx.x, ty = threadIdx.y;
  const unsigned bx = blockIdx.x, by = blockIdx.y;
  const unsigned local = ty * blockDim.x + tx;
  const unsigned block = by * gridDim.x + bx;
  const unsigned i = block * (blockDim.x * blockDim.y) + local;
  Record* a = records + 2 * i;
  Record* b = a + 1;

  // Volatile snapshots are taken BEFORE the first call. The ASM mutates
  // input[i]; r0 and both snapshots remain live across the second call.
  auto live_lane = static_cast<volatile std::uint32_t*>(input)[i]
                         ^ 0x2468ace0u;
  auto live_uniform = *static_cast<const volatile std::uint32_t*>(uniform_seed)
                            ^ 0xa5a5a5a5u;
  // Test anchors: place real live values in overwritten callee-saved VGPRs.
  // These empty asm statements impose no function-wide register count limit.
  asm volatile("" : "+{v72}"(live_lane), "+{v255}"(live_uniform));
  const auto r0 = stage_probe(37u, input + i, a, tx, ty, bx, by);
  const auto r1 = stage_probe(0xa13579bdu, input + i, b, tx, ty, bx, by);

  asm volatile("" : "+{v72}"(live_lane), "+{v255}"(live_uniform));
  a->returned = r0;
  b->returned = r1;
  a->live_lane = b->live_lane = live_lane;
  a->live_uniform = b->live_uniform = live_uniform;
  a->first_return = b->first_return = r0;
}
