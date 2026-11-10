// Host-only HIP module loader; no HIP device source or linked GPU fat binary.
#include <hip/hip_runtime_api.h>
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define CHECK(call) do { \
  hipError_t e = (call); \
  if (e != hipSuccess) { \
    std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(e)); \
    std::exit(1); \
  } \
} while (false)

int main(int argc, char** argv) {
  if (argc != 4) {
    std::fprintf(stderr, "Usage: %s device build_directory supplier.co\n", argv[0]);
    return 2;
  }
  CHECK(hipSetDevice(std::atoi(argv[1])));
  hipDeviceProp_t prop{};
  CHECK(hipGetDeviceProperties(&prop, std::atoi(argv[1])));
  std::printf("GPU: %s (%s), wave=%d\n", prop.name, prop.gcnArchName, prop.warpSize);
  if (prop.warpSize != 32 || std::strncmp(prop.gcnArchName, "gfx1100", 7) != 0) return 2;
  constexpr int guard = 16, max_n = 257 * 128, cap = max_n + 2 * guard;
  constexpr size_t bytes = cap * sizeof(float);
  constexpr float sentinel = 123456.0f;
  std::array<float*, 4> allocation{}, device{};
  for (int k = 0; k < 4; ++k) {
    CHECK(hipMalloc(&allocation[k], bytes));
    device[k] = allocation[k] + guard;
  }
  std::vector<float> x(cap, sentinel), buffer(cap, sentinel), blank(cap, sentinel);
  for (int i = 0; i < max_n; ++i) x[guard+i] = float(i % 257 - 128);
  CHECK(hipMemcpy(allocation[0], x.data(), bytes, hipMemcpyHostToDevice));
  CHECK(hipMemcpy(allocation[1], blank.data(), bytes, hipMemcpyHostToDevice));
  hipModule_t supplier{};
  CHECK(hipModuleLoad(&supplier, argv[3]));
  hipFunction_t stage{};
  CHECK(hipModuleGetFunction(&stage, supplier, "clobber_stage"));
  void* stage_args[] = {&device[0], &device[1]};
  CHECK(hipModuleLaunchKernel(stage, 257, 1, 1, 128, 1, 1, 0, nullptr, stage_args, nullptr));
  CHECK(hipDeviceSynchronize());
  CHECK(hipMemcpy(buffer.data(), allocation[1], bytes, hipMemcpyDeviceToHost));
  for (int j = 0; j < cap; ++j) {
    const float expected = j < guard || j >= guard+max_n ? sentinel : x[j] - 1;
    if (buffer[j] != expected) {
      std::fprintf(stderr, "standalone mismatch: %d got=%g expected=%g\n", j, buffer[j], expected);
      return 1;
    }
  }
  CHECK(hipModuleUnload(supplier));
  std::puts("PASS: standalone supplier binary and guards, 257 CTAs");

  for (const char* config : {"s16_v8", "s8_v8"}) {
    const std::string path = std::string(argv[2]) + "/" + config + "/mono.co";
    hipModule_t module{};
    CHECK(hipModuleLoad(&module, path.c_str()));
    hipFunction_t kernel{};
    CHECK(hipModuleGetFunction(&kernel, module, "mono_boundary"));
    int occupancy = 0;
    CHECK(hipModuleOccupancyMaxActiveBlocksPerMultiprocessor(&occupancy, kernel, 128, 0));
    std::printf("Testing %s; HIP occupancy=%d blocks/multiprocessor\n", config, occupancy);
    std::fflush(stdout);
    unsigned launches = 0;
    for (int blocks : {1, 3, 17, 257}) {
      const int n = blocks * 128;
      for (unsigned epoch = 0; epoch < 10; ++epoch) {
        unsigned seed = 17 + 31 * epoch;
        for (int i = 0; i < max_n; ++i)
          x[guard+i] = float((i*13 + epoch*7) % 257) - 128.0f + float(epoch) * 0.25f;
        CHECK(hipMemcpy(allocation[0], x.data(), bytes, hipMemcpyHostToDevice));
        for (int k = 1; k < 4; ++k)
          CHECK(hipMemcpy(allocation[k], blank.data(), bytes, hipMemcpyHostToDevice));
        void* args[] = {&device[0], &device[1], &device[2], &device[3], &seed};
        CHECK(hipModuleLaunchKernel(kernel, blocks, 1, 1, 128, 1, 1, 0, nullptr, args, nullptr));
        CHECK(hipDeviceSynchronize());
        ++launches;
        for (int k = 0; k < 4; ++k) {
          CHECK(hipMemcpy(buffer.data(), allocation[k], bytes, hipMemcpyDeviceToHost));
          for (int j = 0; j < cap; ++j) {
            const int i = j - guard;
            const float expected = k == 0 ? x[j]
                : i < 0 || i >= n ? sentinel
                : k == 1 ? x[j] - 1.0f
                : k == 2 ? x[j] - 2.0f
                : 4.0f*x[j] + float(seed + i/128 + 1);
            if (buffer[j] != expected) {
              std::fprintf(stderr, "%s blocks=%d epoch=%u buffer=%d i=%d got=%g expected=%g\n",
                           config, blocks, epoch, k, i, buffer[j], expected);
              return 1;
            }
          }
        }
      }
    }
    std::printf("PASS %s: %u launches; two non-tail binary stages; input, tmp1, tmp2, output, both guards verified\n",
                config, launches);
    CHECK(hipModuleUnload(module));
  }
  for (auto ptr : allocation) CHECK(hipFree(ptr));
}
