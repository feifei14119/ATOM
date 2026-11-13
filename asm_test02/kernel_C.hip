// HIP device function, independently compiled into an AMDGPU ELF object.
// A invokes it through the compiler's ordinary device-function ABI.
// Runtime parameters prevent this from being just a constant expression.
extern "C" __device__ __attribute__((noinline, used, visibility("protected")))
unsigned int kernel_C(unsigned int value, unsigned int multiplier) {
    return value * multiplier + 7u;
}
