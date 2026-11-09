// Host-only executable: load the linked GPU module and launch mono_kernel.
#include <hip/hip_runtime_api.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "mono_abi.h"

#define HIP_CHECK(call)                                                      \
  do {                                                                       \
    hipError_t error = (call);                                                \
    if (error != hipSuccess) {                                                \
      std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(error));        \
      std::exit(EXIT_FAILURE);                                               \
    }                                                                        \
  } while (false)

int main(int argc, char** argv) {
  if (argc > 3) {
    std::fprintf(stderr, "Usage: %s [HIP-device-id] [kernel.co]\n", argv[0]);
    return EXIT_FAILURE;
  }
  int device = 0;
  if (argc >= 2) {
    char* end = nullptr;
    errno = 0;
    long value = std::strtol(argv[1], &end, 10);
    if (errno || end == argv[1] || *end || value < 0 || value > 1024) {
      std::fprintf(stderr, "Invalid HIP device id: %s\n", argv[1]);
      return EXIT_FAILURE;
    }
    device = static_cast<int>(value);
  }
  const char* path = argc == 3 ? argv[2] : "build/mono_kernel.co";
  HIP_CHECK(hipSetDevice(device));
  hipDeviceProp_t properties{};
  HIP_CHECK(hipGetDeviceProperties(&properties, device));
  std::printf("GPU %d: %s (%s)\n", device, properties.name, properties.gcnArchName);
  if (std::strncmp(properties.gcnArchName, "gfx1100", 7) != 0 ||
      !properties.cooperativeLaunch) {
    std::fprintf(stderr, "Requires gfx1100 with cooperative launch support.\n");
    return EXIT_FAILURE;
  }

  hipModule_t module = nullptr;
  hipFunction_t kernel = nullptr;
  HIP_CHECK(hipModuleLoad(&module, path));
  HIP_CHECK(hipModuleGetFunction(&kernel, module, kKernelSymbol));

  // The CTAs wait on each other. A cooperative launch keeps the entire grid
  // within the residency limit, avoiding a blocked producer outside the GPU.
  int blocks_per_mp = 0;
  HIP_CHECK(hipModuleOccupancyMaxActiveBlocksPerMultiprocessor(
      &blocks_per_mp, kernel, kThreads, 0));
  if (blocks_per_mp * properties.multiProcessorCount < kBlocks) {
    std::fprintf(stderr, "Insufficient capacity for %d resident CTAs.\n", kBlocks);
    return EXIT_FAILURE;
  }

  int n = kElements;
  unsigned epoch = 1;
  const size_t bytes = n * sizeof(float);
  float *input = nullptr, *output = nullptr, *storage = nullptr;
  unsigned* tags = nullptr;
  HIP_CHECK(hipMalloc(&input, bytes));
  HIP_CHECK(hipMalloc(&output, bytes));
  HIP_CHECK(hipMalloc(&storage, 2 * bytes));
  HIP_CHECK(hipMalloc(&tags, kTags * sizeof(unsigned)));
  HIP_CHECK(hipMemset(tags, 0, kTags * sizeof(unsigned)));
  Mailbox first{storage, tags};
  Mailbox second{storage + n, tags + 1};

  std::vector<float> x(n), y(n), intermediate(2 * n);
  for (int i = 0; i < n; ++i) x[i] = (i % 257 - 128) * 0.25f;
  HIP_CHECK(hipMemcpy(input, x.data(), bytes, hipMemcpyHostToDevice));
  void* args[] = {&input, &output, &first, &second, &n, &epoch};
  HIP_CHECK(hipModuleLaunchCooperativeKernel(
      kernel, kBlocks, 1, 1, kThreads, 1, 1, 0, nullptr, args));
  HIP_CHECK(hipDeviceSynchronize());
  HIP_CHECK(hipMemcpy(y.data(), output, bytes, hipMemcpyDeviceToHost));
  HIP_CHECK(hipMemcpy(intermediate.data(), storage, 2 * bytes, hipMemcpyDeviceToHost));
  unsigned done[kTags]{};
  HIP_CHECK(hipMemcpy(done, tags, sizeof(done), hipMemcpyDeviceToHost));
  if (done[0] != epoch || done[1] != epoch) {
    std::fprintf(stderr, "Mailbox publication failed.\n");
    return EXIT_FAILURE;
  }
  // Check both intermediates too, so ReLU cannot hide an incorrect stage.
  for (int i = 0; i < n; ++i) {
    const float sub = x[i] - 1.0f;
    const float scale = sub * 2.0f;
    if (intermediate[i] != sub || intermediate[n + i] != scale ||
        y[i] != std::max(scale - 3.0f, 0.0f)) {
      std::fprintf(stderr, "Mismatch at element %d\n", i);
      return EXIT_FAILURE;
    }
  }
  std::printf("PASS: %d elements, %d CTAs x %d threads; sub -> scale -> relu\n",
              n, kBlocks, kThreads);
  std::printf("y[i] = max(2*x[i] - 5, 0); both mailboxes and output verified\n");
  HIP_CHECK(hipFree(tags));
  HIP_CHECK(hipFree(storage));
  HIP_CHECK(hipFree(output));
  HIP_CHECK(hipFree(input));
  HIP_CHECK(hipModuleUnload(module));
}
