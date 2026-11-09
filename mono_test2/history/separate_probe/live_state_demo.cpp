#include <hip/hip_runtime_api.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "../../mono_abi.h"

#define HIP_CHECK(call)                                                        \
  do {                                                                         \
    const hipError_t error = (call);                                            \
    if (error != hipSuccess) {                                                  \
      std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(error));         \
      std::exit(EXIT_FAILURE);                                                 \
    }                                                                          \
  } while (false)

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "Usage: %s HIP-device-id live_state.co\n", argv[0]);
    return EXIT_FAILURE;
  }
  char* end = nullptr;
  errno = 0;
  const long device = std::strtol(argv[1], &end, 10);
  if (errno || end == argv[1] || *end || device < 0 || device > 1024) {
    std::fprintf(stderr, "Invalid HIP device id: %s\n", argv[1]);
    return EXIT_FAILURE;
  }
  HIP_CHECK(hipSetDevice(static_cast<int>(device)));
  hipDeviceProp_t properties{};
  HIP_CHECK(hipGetDeviceProperties(&properties, static_cast<int>(device)));
  std::printf("GPU %ld: %s (%s)\n", device, properties.name, properties.gcnArchName);
  if (std::string(properties.gcnArchName).substr(0, 7) != "gfx1100") {
    std::fprintf(stderr, "This assembly example requires gfx1100.\n");
    return EXIT_FAILURE;
  }
  hipModule_t module = nullptr;
  hipFunction_t kernel = nullptr;
  HIP_CHECK(hipModuleLoad(&module, argv[2]));
  HIP_CHECK(hipModuleGetFunction(&kernel, module, "live_state_kernel"));

  float *data = nullptr, *before_result = nullptr;
  unsigned* tag = nullptr;
  HIP_CHECK(hipMalloc(&data, kElements * sizeof(float)));
  HIP_CHECK(hipMalloc(&before_result, kThreads * sizeof(float)));
  HIP_CHECK(hipMalloc(&tag, sizeof(unsigned)));
  HIP_CHECK(hipMemset(tag, 0, sizeof(unsigned)));
  std::vector<float> input(kElements), after(kElements), before(kThreads);
  unsigned launches = 0;
  for (int n : {1, 31, 128, 257, kElements}) {
    for (unsigned epoch = 1; epoch <= 8; ++epoch) {
      for (int i = 0; i < n; ++i) {
        input[i] = static_cast<float>(i % 251 - 125) + 0.25f * epoch;
      }
      // Nonparticipating lanes must leave their slots unchanged.
      std::fill(before.begin(), before.end(), -9999.0f);
      HIP_CHECK(hipMemcpy(data, input.data(), n * sizeof(float), hipMemcpyHostToDevice));
      HIP_CHECK(hipMemcpy(before_result, before.data(), kThreads * sizeof(float),
                          hipMemcpyHostToDevice));
      void* args[] = {&data, &tag, &before_result, &n, &epoch};
      HIP_CHECK(hipModuleLaunchKernel(kernel, 1, 1, 1, kThreads, 1, 1,
                                      0, nullptr, args, nullptr));
      HIP_CHECK(hipDeviceSynchronize());
      HIP_CHECK(hipMemcpy(after.data(), data, n * sizeof(float), hipMemcpyDeviceToHost));
      HIP_CHECK(hipMemcpy(before.data(), before_result, kThreads * sizeof(float),
                          hipMemcpyDeviceToHost));
      unsigned observed_tag = 0;
      HIP_CHECK(hipMemcpy(&observed_tag, tag, sizeof(unsigned), hipMemcpyDeviceToHost));
      if (observed_tag != epoch) {
        std::fprintf(stderr, "Wrong publication tag: %u != %u\n", observed_tag, epoch);
        return EXIT_FAILURE;
      }
      for (int i = 0; i < n; ++i) {
        if (after[i] != input[i] - 1.0f) {
          std::fprintf(stderr, "Stage mismatch: n=%d epoch=%u i=%d got=%g\n",
                       n, epoch, i, after[i]);
          return EXIT_FAILURE;
        }
      }
      for (int i = 0; i < kThreads; ++i) {
        const float expected = i < n ? input[i] : -9999.0f;
        if (before[i] != expected) {
          std::fprintf(stderr, "Live-state mismatch: n=%d epoch=%u lane=%d got=%g expected=%g\n",
                       n, epoch, i, before[i], expected);
          return EXIT_FAILURE;
        }
      }
      ++launches;
    }
  }
  std::printf("PASS: %u nonterminal-call launches; n=1,31,128,257,4096; "
              "pre-call values, in-place subtraction, tags and inactive lanes verified\n",
              launches);
  HIP_CHECK(hipFree(tag));
  HIP_CHECK(hipFree(before_result));
  HIP_CHECK(hipFree(data));
  HIP_CHECK(hipModuleUnload(module));
}
