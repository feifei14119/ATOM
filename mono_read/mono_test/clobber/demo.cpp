// Host-only correctness harness. The same .co is embedded twice in each Mono.
#include <hip/hip_runtime_api.h>

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#define CHECK(call) do {                                                       \
  hipError_t e = (call);                                                       \
  if (e != hipSuccess) {                                                       \
    std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(e));              \
    std::exit(1);                                                             \
  }                                                                           \
} while (false)

int main(int argc, char** argv) {
  if (argc != 4) {
    std::fprintf(stderr, "Usage: %s device mono.co stage.co\n", argv[0]);
    return 2;
  }
  CHECK(hipSetDevice(std::atoi(argv[1])));
  hipDeviceProp_t prop{};
  CHECK(hipGetDeviceProperties(&prop, std::atoi(argv[1])));
  std::printf("GPU: %s (%s), wave=%d\n", prop.name, prop.gcnArchName, prop.warpSize);
  if (prop.warpSize != 32 || std::strcmp(prop.gcnArchName, "gfx1100") != 0) {
    std::fprintf(stderr, "This experiment requires gfx1100 wave32.\n");
    return 2;
  }
  hipModule_t module{}, stage_module{};
  CHECK(hipModuleLoad(&module, argv[2]));
  CHECK(hipModuleLoad(&stage_module, argv[3]));
  hipFunction_t stage{};
  CHECK(hipModuleGetFunction(&stage, stage_module, "clobber_stage"));
  constexpr float sentinel = 123456.0f;
  constexpr unsigned flag_sentinel = 0xdeadbeef;
  constexpr int guard = 16, max_n = 17 * 128, cap = max_n + guard;
  constexpr size_t bytes = cap * sizeof(float);
  std::array<float*, 5> device{};  // x, tmp1, tmp2, out, semantic state
  for (auto& ptr : device) CHECK(hipMalloc(&ptr, bytes));
  unsigned* flags{};
  CHECK(hipMalloc(&flags, (max_n * 8 + guard) * sizeof(unsigned)));
  std::vector<float> x(cap), buffer(cap);
  std::vector<unsigned> host_flags(max_n * 8 + guard);
  void* args[] = {&device[0], &device[1], &device[2], &device[3], &device[4], &flags};
  void* stage_args[] = {&device[0], &device[1]};

  // Check that the supplied binary is also an ordinary, independently launchable kernel.
  for (int i = 0; i < cap; ++i) x[i] = float(i % 257 - 128);
  CHECK(hipMemcpy(device[0], x.data(), bytes, hipMemcpyHostToDevice));
  CHECK(hipModuleLaunchKernel(stage, 17, 1, 1, 128, 1, 1, 0, nullptr, stage_args, nullptr));
  CHECK(hipDeviceSynchronize());
  CHECK(hipMemcpy(buffer.data(), device[1], bytes, hipMemcpyDeviceToHost));
  for (int i = 0; i < max_n; ++i) {
    if (buffer[i] != x[i] - 1.0f) {
      std::fprintf(stderr, "Standalone stage mismatch: i=%d got=%g\n", i, buffer[i]);
      return 1;
    }
  }
  std::puts("PASS: standalone supplier .co, 17 CTAs x 128 threads");

  for (const char* name : {"mono_unsafe", "mono_preserve", "mono_phase"}) {
    hipFunction_t f{};
    CHECK(hipModuleGetFunction(&f, module, name));
    int occupancy = 0;
    CHECK(hipModuleOccupancyMaxActiveBlocksPerMultiprocessor(&occupancy, f, 128, 0));
    std::printf("Testing %s; occupancy=%d blocks per HIP multiprocessor\n", name, occupancy);
    std::fflush(stdout);
    const bool negative = std::strcmp(name, "mono_unsafe") == 0;
    unsigned launches = 0, value_mismatches = 0, flag_mismatches = 0;
    for (int blocks : {1, 3, 17}) {
      const int n = blocks * 128;
      for (int epoch = 0; epoch < 5; ++epoch) {
        ++launches;
        for (int i = 0; i < cap; ++i) x[i] = float(i % 257 - 128) + epoch * 0.25f;
        CHECK(hipMemcpy(device[0], x.data(), bytes, hipMemcpyHostToDevice));
        std::fill(buffer.begin(), buffer.end(), sentinel);
        for (int k = 1; k < 5; ++k)
          CHECK(hipMemcpy(device[k], buffer.data(), bytes, hipMemcpyHostToDevice));
        std::fill(host_flags.begin(), host_flags.end(), flag_sentinel);
        CHECK(hipMemcpy(flags, host_flags.data(), host_flags.size()*sizeof(unsigned), hipMemcpyHostToDevice));
        CHECK(hipModuleLaunchKernel(f, blocks, 1, 1, 128, 1, 1, 0, nullptr, args, nullptr));
        CHECK(hipDeviceSynchronize());
        for (int k = 1; k < 5; ++k) {
          CHECK(hipMemcpy(buffer.data(), device[k], bytes, hipMemcpyDeviceToHost));
          for (int i = 0; i < cap; ++i) {
            const float expected = i >= n ? sentinel
                : k == 1 ? x[i] - 1.0f
                : k == 2 ? x[i] - 2.0f
                : k == 3 ? 4.0f*x[i] + float(i/128 + 18)
                         : 3.0f*x[i] + 2.0f;
            if (buffer[i] != expected) {
              if (negative && i < n && k >= 3) { ++value_mismatches; continue; }
              std::fprintf(stderr, "%s: blocks=%d epoch=%d buffer=%d i=%d got=%g expected=%g\n",
                           name, blocks, epoch, k, i, buffer[i], expected);
              return 1;
            }
          }
        }
        CHECK(hipMemcpy(host_flags.data(), flags, host_flags.size()*sizeof(unsigned), hipMemcpyDeviceToHost));
        for (size_t i = 0; i < host_flags.size(); ++i) {
          unsigned expected = flag_sentinel;
          if (i < size_t(n*8)) {
            const int field = i % 4, stage_index = (i % 8) / 4;
            expected = field == 0 ? 0x5a5aa5a5u : field == 1 ? 0xffffffffu
                     : field == 2 ? 1u : unsigned(i/8/128 + 17 + stage_index);
          }
          if (host_flags[i] != expected) {
            if (negative && i < size_t(n*8)) { ++flag_mismatches; continue; }
            std::fprintf(stderr, "%s: flag i=%zu got=%08x expected=%08x\n",
                         name, i, host_flags[i], expected);
            return 1;
          }
        }
      }
    }
    if (negative) {
      if (!value_mismatches || !flag_mismatches) return 1;
      std::printf("EXPECTED FAILURE reproduced: %u value mismatches, %u state mismatches\n",
                  value_mismatches, flag_mismatches);
    } else {
      std::printf("PASS: %s, %u launches, two non-tail binary stages per launch; "
                  "intermediates/output/state/guards verified\n", name, launches);
    }
  }
  for (auto ptr : device) CHECK(hipFree(ptr));
  CHECK(hipFree(flags));
  CHECK(hipModuleUnload(stage_module));
  CHECK(hipModuleUnload(module));
  return 0;
}
