// Host-only program: load the separately compiled GPU ELF and launch its kernel.
// Build with a regular C++ compiler linked to libamdhip64.
#include <hip/hip_runtime_api.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "mono_abi.h"

#define HIP_CHECK(call)                                                        \
  do {                                                                         \
    const hipError_t error = (call);                                            \
    if (error != hipSuccess) {                                                  \
      std::fprintf(stderr, "%s:%d: %s: %s\n", __FILE__, __LINE__, #call,          \
                   hipGetErrorString(error));                                   \
      std::exit(EXIT_FAILURE);                                                 \
    }                                                                          \
  } while (false)

int main(int argc, char** argv) {
  int device = 0;
  if (argc > 3) {
    std::fprintf(stderr, "Usage: %s [HIP-device-id] [kernel.hsaco]\n", argv[0]);
    return EXIT_FAILURE;
  }
  if (argc >= 2) {
    char* end = nullptr;
    errno = 0;
    const long parsed = std::strtol(argv[1], &end, 10);
    if (errno || end == argv[1] || *end || parsed < 0 || parsed > 1024) {
      std::fprintf(stderr, "Invalid HIP device id: %s\n", argv[1]);
      return EXIT_FAILURE;
    }
    device = static_cast<int>(parsed);
  }
  const std::string kernel_path =
      argc == 3 ? argv[2]
                : (std::filesystem::path(argv[0]).parent_path() /
                   "mono_kernel.hsaco").string();
  std::ifstream code_file(kernel_path, std::ios::binary);
  if (!code_file) {
    std::fprintf(stderr, "Cannot open code object: %s\n", kernel_path.c_str());
    return EXIT_FAILURE;
  }
  // This vector holds the raw ELF bytes, like FlyDSL's extracted gpu.binary.
  const std::vector<char> binary((std::istreambuf_iterator<char>(code_file)),
                                 std::istreambuf_iterator<char>());
  if (binary.empty() || code_file.bad()) {
    std::fprintf(stderr, "Cannot read code object: %s\n", kernel_path.c_str());
    return EXIT_FAILURE;
  }
  HIP_CHECK(hipSetDevice(device));
  hipDeviceProp_t properties{};
  HIP_CHECK(hipGetDeviceProperties(&properties, device));
  std::printf("GPU %d: %s (%s), wave size %d\n", device, properties.name,
              properties.gcnArchName, properties.warpSize);
  if (!properties.cooperativeLaunch) {
    std::fprintf(stderr, "This demo requires HIP cooperative launch support.\n");
    return EXIT_FAILURE;
  }

  // Load from memory, then resolve the kernel by its unmangled C symbol.
  // Neither the kernel source nor its binary is linked into this host program.
  hipModule_t module = nullptr;
  hipFunction_t kernel = nullptr;
  HIP_CHECK(hipModuleLoadData(&module, binary.data()));
  HIP_CHECK(hipModuleGetFunction(&kernel, module, kKernelSymbol));
  std::printf("Loaded code object: %s (%zu bytes), symbol: %s\n",
              kernel_path.c_str(), binary.size(), kKernelSymbol);

  // Cooperative launch enforces the resident-grid limit. Occupancy alone is
  // a capacity estimate and is not a scheduling guarantee for a normal launch.
  int blocks_per_multiprocessor = 0;
  HIP_CHECK(hipModuleOccupancyMaxActiveBlocksPerMultiprocessor(
      &blocks_per_multiprocessor, kernel, kThreads, 0));
  const int capacity =
      blocks_per_multiprocessor * properties.multiProcessorCount;
  std::printf("Resident grid capacity: %d CTAs (%d per HIP multiprocessor)\n",
              capacity, blocks_per_multiprocessor);
  if (capacity < kBlocks) {
    std::fprintf(stderr, "The grid needs %d resident CTAs.\n", kBlocks);
    return EXIT_FAILURE;
  }

  float *input = nullptr, *output = nullptr, *scratch = nullptr;
  unsigned* tags = nullptr;
  const size_t bytes = kElements * sizeof(float);
  HIP_CHECK(hipMalloc(&input, bytes));
  HIP_CHECK(hipMalloc(&output, bytes));
  HIP_CHECK(hipMalloc(&scratch, 2 * bytes));
  HIP_CHECK(hipMalloc(&tags, 2 * sizeof(unsigned)));
  // Initialize tags only once. A new epoch distinguishes later publications.
  // The following steps are serialized on one stream, so scratch is reusable.
  HIP_CHECK(hipMemset(tags, 0, 2 * sizeof(unsigned)));
  Mailbox first{scratch, tags};
  Mailbox second{scratch + kElements, tags + 1};
  int n = kElements;
  std::vector<float> host_input(n), host_output(n);
  unsigned host_tags[2]{};

  for (unsigned epoch = 1; epoch <= kSteps; ++epoch) {
    for (int i = 0; i < n; ++i) {
      host_input[i] = static_cast<float>(i % 257 - 128) + (epoch % 11);
    }
    HIP_CHECK(hipMemcpy(input, host_input.data(), bytes, hipMemcpyHostToDevice));
    // Each entry points to storage containing one argument's value. The
    // cooperative API expects this argument array; Mailbox is passed by value.
    void* args[] = {&input, &output, &first, &second, &n, &epoch};
    HIP_CHECK(hipModuleLaunchCooperativeKernel(
        kernel, kBlocks, 1, 1, kThreads, 1, 1, 0, nullptr, args));
    HIP_CHECK(hipDeviceSynchronize());
    HIP_CHECK(hipMemcpy(host_output.data(), output, bytes, hipMemcpyDeviceToHost));
    HIP_CHECK(hipMemcpy(host_tags, tags, sizeof(host_tags), hipMemcpyDeviceToHost));
    if (host_tags[0] != epoch || host_tags[1] != epoch) {
      std::fprintf(stderr, "Wrong mailbox tags at epoch %u: %u, %u\n", epoch,
                   host_tags[0], host_tags[1]);
      return EXIT_FAILURE;
    }
    for (int i = 0; i < n; ++i) {
      // An independent CPU expression checks both positive and zero outputs.
      const float expected = std::max(2.0f * host_input[i] - 5.0f, 0.0f);
      if (host_output[i] != expected) {
        std::fprintf(stderr, "Mismatch: epoch=%u i=%d input=%g got=%g expected=%g\n",
                     epoch, i, host_input[i], host_output[i], expected);
        return EXIT_FAILURE;
      }
    }
  }

  std::printf("PASS: %u epochs x %d elements; 1 kernel launch per epoch, "
              "%d CTAs x %d threads\n", kSteps, n, kBlocks, kThreads);
  std::printf("Formula: y = max(2*x - 5, 0)\n");
  for (int i : {0, 128, 256}) {
    std::printf("  x[%d]=%g -> y[%d]=%g\n", i, host_input[i], i, host_output[i]);
  }
  HIP_CHECK(hipFree(tags));
  HIP_CHECK(hipFree(scratch));
  HIP_CHECK(hipFree(output));
  HIP_CHECK(hipFree(input));
  HIP_CHECK(hipModuleUnload(module));
  return EXIT_SUCCESS;
}
