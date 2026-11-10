// Host-only module launcher. Build with a normal C++ compiler and ROCm HIP.
#include <hip/hip_runtime_api.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#define HIP_CHECK(expr) do { const auto err = (expr); if (err != hipSuccess) { \
  std::fprintf(stderr, "%s: %s\n", #expr, hipGetErrorString(err)); std::exit(1); \
} } while (false)

using Record = std::array<std::uint32_t, 16>;
constexpr std::uint32_t Guard = 0xcdcdcdcdu;

std::uint32_t expected(std::uint32_t x, std::uint32_t bias, unsigned tx,
                       unsigned ty, unsigned bx, unsigned by) {
  return ((x ^ 0x13579bdfu) + bias + tx + (ty << 8) + (bx << 16)
          + (by << 24)) ^ (bx ^ by);
}

int main(int argc, char **argv) {
  if (argc < 2 || argc > 3) {
    std::fprintf(stderr, "Usage: %s kernel.co [symbol]\n", argv[0]);
    return 1;
  }
  int count = 0, device = -1;
  HIP_CHECK(hipGetDeviceCount(&count));
  for (int i = 0; i < count; ++i) {
    hipDeviceProp_t p{};
    HIP_CHECK(hipGetDeviceProperties(&p, i));
    if (!std::strncmp(p.gcnArchName, "gfx1250", 7)) { device = i; break; }
  }
  if (device < 0) {
    std::fprintf(stderr, "No gfx1250 GPU: offline build does not establish runtime correctness.\n");
    return 2;
  }
  HIP_CHECK(hipSetDevice(device));
  hipModule_t module{};
  hipFunction_t kernel{};
  HIP_CHECK(hipModuleLoad(&module, argv[1]));
  HIP_CHECK(hipModuleGetFunction(&kernel, module, argc == 3 ? argv[2] : "contract_caller"));
  unsigned cases = 0;
  for (const auto &shape : {std::array<unsigned, 2>{1, 1}, {3, 2}, {2, 3}}) {
    for (std::uint32_t seed : {0u, 0x76543210u, 0xffffffffu}) {
      unsigned gx = shape[0], gy = shape[1], n = gx * gy * 256;
      std::vector<Record> input(n + 2), output(n + 2);
      for (auto &record : input) record.fill(Guard);
      for (unsigned i = 0; i < n; ++i)
        input[i + 1][0] = (i * 0x10203041u) ^ seed;
      Record *all = nullptr;
      std::uint32_t *seed_gpu = nullptr;
      HIP_CHECK(hipMalloc(&all, input.size() * sizeof(Record)));
      HIP_CHECK(hipMalloc(&seed_gpu, sizeof(seed)));
      HIP_CHECK(hipMemcpy(all, input.data(), input.size() * sizeof(Record), hipMemcpyHostToDevice));
      HIP_CHECK(hipMemcpy(seed_gpu, &seed, sizeof(seed), hipMemcpyHostToDevice));
      Record *records = all + 1;
      void *parameters[] = {&records, &seed_gpu, &gx};
      HIP_CHECK(hipModuleLaunchKernel(kernel, gx, gy, 1, 32, 8, 1, 0, nullptr, parameters, nullptr));
      HIP_CHECK(hipDeviceSynchronize());
      HIP_CHECK(hipMemcpy(output.data(), all, output.size() * sizeof(Record), hipMemcpyDeviceToHost));
      unsigned failures = 0;
      for (unsigned row = 0; row < n + 2; ++row) {
        Record want;
        want.fill(Guard);
        if (row > 0 && row <= n) {
          const unsigned i = row - 1, local = i % 256, block = i / 256;
          const unsigned tx = local % 32, ty = local / 32, bx = block % gx, by = block / gx;
          const auto x = input[row][0];
          const auto after0 = (x ^ 0x9e3779b9u) + 37u;
          const auto after1 = (after0 ^ 0x9e3779b9u) + 0xa13579bdu;
          const auto r0 = expected(x, 37, tx, ty, bx, by);
          const auto r1 = expected(after0, 0xa13579bdu, tx, ty, bx, by);
          const auto address = reinterpret_cast<std::uint64_t>(records + i);
          want = {after1, r0, r1, x ^ 0x2468ace0u, seed ^ 0xa5a5a5a5u, r0 ^ r1,
                  0xa13579bdu, bx, by, tx, ty, after0,
                  std::uint32_t(address), std::uint32_t(address >> 32), r1, Guard};
        }
        for (unsigned field = 0; field < 16; ++field) {
          if (output[row][field] != want[field]) {
            if (failures < 8)
              std::fprintf(stderr, "record %u field %u: got %08x expected %08x\n",
                           row, field, output[row][field], want[field]);
            ++failures;
          }
        }
      }
      HIP_CHECK(hipFree(seed_gpu));
      HIP_CHECK(hipFree(all));
      if (failures) return 1;
      ++cases;
      std::printf("PASS grid=(%u,%u) block=(32,8) seed=%08x: %u device calls\n",
                  gx, gy, seed, 2*n);
    }
  }
  HIP_CHECK(hipModuleUnload(module));
  std::printf("GPU PASS: %u cases, fixed parameters, middle-call live values, input mutations and guards.\n", cases);
}
