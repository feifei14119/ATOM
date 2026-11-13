// Host-only HIP launcher. A/B are ASM, C is HIP, D is FlyDSL; one linked ELF.
#include <hip/hip_runtime_api.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#define HIP_CHECK(call) do { \
    const hipError_t error = (call); \
    if (error != hipSuccess) { \
        std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(error)); \
        std::exit(EXIT_FAILURE); \
    } \
} while (false)

static bool is_target(const hipDeviceProp_t& prop) {
    return std::strncmp(prop.gcnArchName, "gfx1250", 7) == 0 &&
           (prop.gcnArchName[7] == '\0' || prop.gcnArchName[7] == ':');
}

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3) {
        std::fprintf(stderr, "Usage: %s demo.co [HIP-device-id]\n", argv[0]);
        return EXIT_FAILURE;
    }
    int count = 0, device = -1;
    HIP_CHECK(hipGetDeviceCount(&count));
    if (argc == 3) {
        char* end = nullptr;
        const long number = std::strtol(argv[2], &end, 10);
        if (end == argv[2] || *end || number < 0 || number >= count) {
            std::fprintf(stderr, "Invalid device: %s\n", argv[2]);
            return EXIT_FAILURE;
        }
        device = static_cast<int>(number);
    } else {
        for (int i = 0; i < count; ++i) {
            hipDeviceProp_t prop{};
            HIP_CHECK(hipGetDeviceProperties(&prop, i));
            if (is_target(prop)) { device = i; break; }
        }
    }
    if (device < 0) {
        std::fprintf(stderr, "No gfx1250 GPU found\n");
        return EXIT_FAILURE;
    }
    hipDeviceProp_t prop{};
    HIP_CHECK(hipGetDeviceProperties(&prop, device));
    if (!is_target(prop)) {
        std::fprintf(stderr, "Expected gfx1250, got %s\n", prop.gcnArchName);
        return EXIT_FAILURE;
    }
    HIP_CHECK(hipSetDevice(device));
    std::printf("GPU %d: %s (%s)\n", device, prop.name, prop.gcnArchName);

    hipModule_t module{};
    hipFunction_t kernel{};
    HIP_CHECK(hipModuleLoad(&module, argv[1]));
    HIP_CHECK(hipModuleGetFunction(&kernel, module, "kernel_A"));
    unsigned launches = 0, values = 0;
    constexpr std::uint32_t sentinel = 0xcdcdcdcdu;
    for (unsigned threads : {1u, 13u, 32u, 64u, 256u}) {
        for (unsigned kind = 0; kind < 3; ++kind) {
            std::vector<std::uint32_t> a(threads), b(threads);
            for (unsigned i = 0; i < threads; ++i) {
                if (kind == 0) { a[i] = i; b[i] = 2u * i; }
                if (kind == 1) { a[i] = 0xffffffffu - i; b[i] = i + 2u; }
                if (kind == 2) {
                    a[i] = (i + 1u) * 1664525u + 1013904223u;
                    b[i] = a[i] * 1664525u + 1013904223u;
                }
            }
            // Guards before/after out catch accidental writes by inactive lanes.
            std::vector<std::uint32_t> out(threads + 2u, sentinel);
            std::uint32_t *da = nullptr, *db = nullptr, *dout_all = nullptr;
            HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&da), a.size() * 4));
            HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&db), b.size() * 4));
            HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&dout_all), out.size() * 4));
            HIP_CHECK(hipMemcpy(da, a.data(), a.size() * 4, hipMemcpyHostToDevice));
            HIP_CHECK(hipMemcpy(db, b.data(), b.size() * 4, hipMemcpyHostToDevice));
            HIP_CHECK(hipMemcpy(dout_all, out.data(), out.size() * 4, hipMemcpyHostToDevice));
            auto* dout = dout_all + 1;
            void* args[] = {&da, &db, &dout};
            // One dispatch only. A calls B, then C, then D, and adds one.
            HIP_CHECK(hipModuleLaunchKernel(kernel, 1, 1, 1, threads, 1, 1,
                                           0, nullptr, args, nullptr));
            HIP_CHECK(hipDeviceSynchronize());
            HIP_CHECK(hipMemcpy(out.data(), dout_all, out.size() * 4, hipMemcpyDeviceToHost));
            std::vector<std::uint32_t> read_a(threads), read_b(threads);
            HIP_CHECK(hipMemcpy(read_a.data(), da, a.size() * 4, hipMemcpyDeviceToHost));
            HIP_CHECK(hipMemcpy(read_b.data(), db, b.size() * 4, hipMemcpyDeviceToHost));
            HIP_CHECK(hipFree(da));
            HIP_CHECK(hipFree(db));
            HIP_CHECK(hipFree(dout_all));
            if (read_a != a || read_b != b || out.front() != sentinel || out.back() != sentinel) {
                std::fprintf(stderr, "FAIL threads=%u case=%u: input/guard modified\n", threads, kind);
                return EXIT_FAILURE;
            }
            for (unsigned i = 0; i < threads; ++i) {
                // Independent integer reference; reduce to uint32_t at the end.
                const std::uint32_t expected = static_cast<std::uint32_t>(
                    15ull * (static_cast<std::uint64_t>(a[i]) + b[i]) + 47ull);
                if (out[i + 1] != expected) {
                    std::fprintf(stderr, "FAIL threads=%u case=%u tid=%u: got %08x expected %08x\n",
                                 threads, kind, i, out[i + 1], expected);
                    return EXIT_FAILURE;
                }
            }
            ++launches;
            values += threads;
        }
    }
    HIP_CHECK(hipModuleUnload(module));
    std::printf("GPU PASS: %u launches, %u values, out=15*(a+b)+47, input/guards unchanged\n",
                launches, values);
    return EXIT_SUCCESS;
}
