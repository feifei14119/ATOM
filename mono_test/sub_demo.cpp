// Host-only validator for the kernel assembled from build/sub.s.
#include <hip/hip_runtime_api.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>

#include "mono_abi.h"

#define HIP_CHECK(call)                                                       \
  do {                                                                        \
    const hipError_t error = (call);                                           \
    if (error != hipSuccess) {                                                 \
      std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(error));         \
      std::exit(EXIT_FAILURE);                                                \
    }                                                                         \
  } while (false)

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "Usage: %s HIP-device-id sub.hsaco\n", argv[0]);
    return EXIT_FAILURE;
  }
  char* end = nullptr;
  errno = 0;
  const long device = std::strtol(argv[1], &end, 10);
  if (errno || end == argv[1] || *end || device < 0 || device > 1024) {
    std::fprintf(stderr, "Invalid HIP device id: %s\n", argv[1]);
    return EXIT_FAILURE;
  }
  std::ifstream file(argv[2], std::ios::binary);
  const std::vector<char> binary((std::istreambuf_iterator<char>(file)), {});
  if (!file || binary.empty()) {
    std::fprintf(stderr, "Cannot read code object: %s\n", argv[2]);
    return EXIT_FAILURE;
  }
  HIP_CHECK(hipSetDevice(static_cast<int>(device)));
  hipDeviceProp_t properties{};
  HIP_CHECK(hipGetDeviceProperties(&properties, static_cast<int>(device)));
  std::printf("GPU %ld: %s (%s)\n", device, properties.name, properties.gcnArchName);

  hipModule_t module = nullptr;
  hipFunction_t kernel = nullptr;
  HIP_CHECK(hipModuleLoadData(&module, binary.data()));
  HIP_CHECK(hipModuleGetFunction(&kernel, module, "sub_kernel"));
  std::printf("Loaded %s (%zu bytes), symbol: sub_kernel\n", argv[2], binary.size());

  constexpr int capacity = 4097;  // Includes one guard element for n=4096.
  constexpr float sentinel = 123456.0f;
  constexpr size_t bytes = capacity * sizeof(float);
  float *input = nullptr, *output = nullptr;
  unsigned* tag = nullptr;
  HIP_CHECK(hipMalloc(&input, bytes));
  HIP_CHECK(hipMalloc(&output, bytes));
  HIP_CHECK(hipMalloc(&tag, sizeof(unsigned)));
  HIP_CHECK(hipMemset(tag, 0, sizeof(unsigned)));
  Mailbox mailbox{output, tag};
  std::vector<float> host_input(capacity), host_output(capacity);
  unsigned epoch = 0;
  // Vary block size to check the hidden launch arguments used by blockDim.x.
  for (int threads : {32, 64, 128, 256}) {
    for (int n : {0, 1, 31, 32, 33, 127, 128, 129, 4096}) {
      ++epoch;
      for (int i = 0; i < capacity; ++i) {
        host_input[i] = (i % 257 - 128) * 0.25f + static_cast<float>(epoch);
      }
      std::fill(host_output.begin(), host_output.end(), sentinel);
      HIP_CHECK(hipMemcpy(input, host_input.data(), bytes, hipMemcpyHostToDevice));
      HIP_CHECK(hipMemcpy(output, host_output.data(), bytes, hipMemcpyHostToDevice));
      void* args[] = {&input, &mailbox, &n, &epoch};
      // Exactly one CTA: stage_sub uses only threadIdx.x and blockDim.x.
      HIP_CHECK(hipModuleLaunchKernel(
          kernel, 1, 1, 1, threads, 1, 1, 0, nullptr, args, nullptr));
      HIP_CHECK(hipDeviceSynchronize());
      HIP_CHECK(hipMemcpy(host_output.data(), output, bytes, hipMemcpyDeviceToHost));
      unsigned host_tag = 0;
      HIP_CHECK(hipMemcpy(&host_tag, tag, sizeof(host_tag), hipMemcpyDeviceToHost));
      if (host_tag != epoch) {
        std::fprintf(stderr, "Wrong tag: got=%u expected=%u\n", host_tag, epoch);
        return EXIT_FAILURE;
      }
      for (int i = 0; i < capacity; ++i) {
        const float expected = i < n ? host_input[i] - 1.0f : sentinel;
        if (host_output[i] != expected) {
          std::fprintf(stderr, "Mismatch: threads=%d n=%d i=%d got=%g expected=%g\n",
                       threads, n, i, host_output[i], expected);
          return EXIT_FAILURE;
        }
      }
    }
  }
  std::printf("PASS: %u launches; block sizes 32/64/128/256; "
              "n=0/1/31/32/33/127/128/129/4096\n", epoch);
  std::puts("Verified: y=x-1, mailbox epoch, untouched elements at i>=n");
  HIP_CHECK(hipFree(tag));
  HIP_CHECK(hipFree(output));
  HIP_CHECK(hipFree(input));
  HIP_CHECK(hipModuleUnload(module));
  return EXIT_SUCCESS;
}
