#pragma once
#include <cstdint>

// Each record is 64 bytes. Assembly writes words 0..10, caller writes 11..14,
// and word 15 stays untouched as a local overrun guard.
struct Record {
  std::uint32_t bias, loaded, tx, ty, bx, by;
  std::uint32_t implicit_tx, implicit_ty, implicit_bx, implicit_by;
  std::uint32_t computed, returned, live_lane, live_uniform, first_return, guard;
};
static_assert(sizeof(Record) == 64);
