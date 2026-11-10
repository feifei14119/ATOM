// Host-only test runner. Load the final code object, launch, compare with CPU.
#include <hip/hip_runtime_api.h>
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "test_types.h"

#define HIP_CHECK(call) do { \
  const hipError_t e = (call); \
  if (e != hipSuccess) { \
    std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(e)); \
    std::exit(EXIT_FAILURE); \
  } \
} while (false)

static std::uint32_t reference(std::uint32_t x, std::uint32_t bias,
                               unsigned tx, unsigned ty, unsigned bx, unsigned by) {
  return ((x ^ 0x13579bdfu) + bias + tx + (ty << 8) + (bx << 16)
          + (by << 24)) ^ (bx ^ by);
}

int main(int argc, char** argv) {
  if (argc < 2 || argc > 3) {
    std::fprintf(stderr, "Usage: %s caller.co [HIP-device-id]\n", argv[0]);
    return EXIT_FAILURE;
  }
  int count = 0, device = -1;
  HIP_CHECK(hipGetDeviceCount(&count));
  if (argc == 3) {
    char* end = nullptr;
    errno = 0;
    const long parsed = std::strtol(argv[2], &end, 10);
    if (errno || end == argv[2] || *end || parsed < 0 || parsed >= count) {
      std::fprintf(stderr, "Invalid HIP device id: %s\n", argv[2]);
      return EXIT_FAILURE;
    }
    device = static_cast<int>(parsed);
  } else {
    for (int d = 0; d < count; ++d) {
      hipDeviceProp_t p{};
      HIP_CHECK(hipGetDeviceProperties(&p, d));
      if (std::strncmp(p.gcnArchName, "gfx1100", 7) == 0) { device = d; break; }
    }
  }
  if (device < 0) {
    std::fprintf(stderr, "No gfx1100 GPU: this assembly test requires gfx1100.\n");
    return EXIT_FAILURE;
  }
  hipDeviceProp_t p{};
  HIP_CHECK(hipGetDeviceProperties(&p, device));
  if (std::strncmp(p.gcnArchName, "gfx1100", 7) != 0) {
    std::fprintf(stderr, "Selected GPU is %s; expected gfx1100.\n", p.gcnArchName);
    return EXIT_FAILURE;
  }
  HIP_CHECK(hipSetDevice(device));
  std::printf("GPU %d: %s (%s)\n", device, p.name, p.gcnArchName);
  hipModule_t module{};
  hipFunction_t kernel{};
  HIP_CHECK(hipModuleLoad(&module, argv[1]));
  HIP_CHECK(hipModuleGetFunction(&kernel, module, "caller_kernel"));

  struct Shape { unsigned gx, gy, tx, ty; };
  const Shape shapes[] = {{1, 1, 1, 1}, {3, 2, 8, 4}, {2, 3, 16, 4},
                          {3, 4, 7, 5}, {4, 3, 32, 8}};
  constexpr std::uint32_t sentinel = 0xcdcdcdcdu;
  const std::uint32_t seeds[] = {0u, 0x76543210u, 0xffffffffu};
  const char* names[] = {"bias", "loaded", "tx", "ty", "bx", "by",
      "implicit_tx", "implicit_ty", "implicit_bx", "implicit_by", "computed",
      "returned", "live_lane", "live_uniform", "first_return", "guard"};
  unsigned cases = 0;
  std::size_t total_records = 0;
  std::uint64_t digest = 14695981039346656037ull;
  for (auto shape : shapes) for (auto seed : seeds) {
    const unsigned n = shape.gx * shape.gy * shape.tx * shape.ty;
    constexpr unsigned pad = 16;
    std::vector<std::uint32_t> original(n + 2 * pad, sentinel);
    for (unsigned i = 0; i < n; ++i)
      original[pad + i] = i % 17 == 0 ? 0u : i % 17 == 1 ? 0xffffffffu
                                              : (i * 0x10203041u) ^ seed;
    std::vector<std::uint32_t> actual_input(original.size());
    // One whole guarded record before and after the valid output range.
    std::vector<Record> actual(2 * n + 2);
    std::memset(actual.data(), 0xcd, actual.size() * sizeof(Record));
    std::uint32_t *input_all = nullptr, *seed_gpu = nullptr;
    Record* records_all = nullptr;
    HIP_CHECK(hipMalloc(&input_all, original.size() * sizeof(std::uint32_t)));
    HIP_CHECK(hipMalloc(&records_all, actual.size() * sizeof(Record)));
    HIP_CHECK(hipMalloc(&seed_gpu, sizeof(seed)));
    HIP_CHECK(hipMemcpy(input_all, original.data(), original.size() * sizeof(std::uint32_t),
                        hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(records_all, actual.data(), actual.size() * sizeof(Record),
                        hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(seed_gpu, &seed, sizeof(seed), hipMemcpyHostToDevice));
    auto* input = input_all + pad;
    auto* records = records_all + 1;
    void* args[] = {&input, &records, &seed_gpu};
    HIP_CHECK(hipModuleLaunchKernel(kernel, shape.gx, shape.gy, 1,
              shape.tx, shape.ty, 1, 0, nullptr, args, nullptr));
    HIP_CHECK(hipDeviceSynchronize());
    HIP_CHECK(hipMemcpy(actual.data(), records_all, actual.size() * sizeof(Record),
                        hipMemcpyDeviceToHost));
    HIP_CHECK(hipMemcpy(actual_input.data(), input_all,
                        original.size() * sizeof(std::uint32_t), hipMemcpyDeviceToHost));
    HIP_CHECK(hipFree(seed_gpu));
    HIP_CHECK(hipFree(records_all));
    HIP_CHECK(hipFree(input_all));

    unsigned failures = 0;
    for (unsigned row = 0; row < actual.size(); ++row) {
      std::array<std::uint32_t, 16> expected, got;
      expected.fill(sentinel);
      std::memcpy(got.data(), &actual[row], sizeof(Record));
      if (row > 0 && row <= 2 * n) {
        const unsigned i = (row - 1) / 2, call = (row - 1) % 2;
        const unsigned local = i % (shape.tx * shape.ty);
        const unsigned block = i / (shape.tx * shape.ty);
        const unsigned tx = local % shape.tx, ty = local / shape.tx;
        const unsigned bx = block % shape.gx, by = block / shape.gx;
        const auto x = original[pad + i];
        const auto loaded = call ? x ^ 0x9e3779b9u : x;
        const auto bias = call ? 0xa13579bdu : 37u;
        const auto result = reference(loaded, bias, tx, ty, bx, by);
        expected = {bias, loaded, tx, ty, bx, by, tx, ty, bx, by, result, result,
                    x ^ 0x2468ace0u, seed ^ 0xa5a5a5a5u,
                    reference(x, 37u, tx, ty, bx, by), sentinel};
      }
      for (unsigned field = 0; field < expected.size(); ++field) {
        if (got[field] != expected[field]) {
          if (failures < 8)
            std::fprintf(stderr, "record %u field %s: got %08x expected %08x\n",
                         row, names[field], got[field], expected[field]);
          ++failures;
        }
        digest = (digest ^ got[field]) * 1099511628211ull;
      }
    }
    if (actual_input != original) {
      std::fprintf(stderr, "Input not restored after two XORs, or input guard modified.\n");
      ++failures;
    }
    if (failures) {
      std::fprintf(stderr, "FAIL grid=(%u,%u) block=(%u,%u) seed=%08x: %u mismatches\n",
                   shape.gx, shape.gy, shape.tx, shape.ty, seed, failures);
      return EXIT_FAILURE;
    }
    ++cases;
    total_records += 2 * n;
    std::printf("PASS grid=(%u,%u) block=(%u,%u) seed=%08x: %u calls\n",
                 shape.gx, shape.gy, shape.tx, shape.ty, seed, 2 * n);
  }
  HIP_CHECK(hipModuleUnload(module));
  std::printf("PASS: %u cases, %zu ASM invocations; arguments, implicit IDs, returns, "
              "live values and guards verified.\n", cases, total_records);
  std::printf("Result digest: %016llx\n", static_cast<unsigned long long>(digest));
}
