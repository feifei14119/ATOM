#include "dq_wrapper.h"
#include "dq_convert_inline.h"

// This definition, including its opaque inline-asm body and clobbers, is
// compiled into bitcode. FlyDSL links the bitcode BEFORE register allocation.
// Keep one real device function boundary when the linked module is optimized.
extern "C" __device__ __attribute__((noinline, convergent))
void mono_dq_convert_wrapper(std::uint64_t args_address, std::uint32_t linear_tid) {
  stage_dq_convert_inline(reinterpret_cast<const DqConvertArgs*>(args_address), linear_tid);
}
