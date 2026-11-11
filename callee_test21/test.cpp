// Host-only launcher: load the ASM code object and compare every output field.
#include <hip/hip_runtime_api.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <vector>

#define HIP_CHECK(call) do { \
    const hipError_t error = (call); \
    if (error != hipSuccess) { \
        std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(error)); \
        std::exit(EXIT_FAILURE); \
    } \
} while (false)

using Record = std::array<std::uint32_t, 12>;
static_assert(sizeof(Record) == 48);

static std::uint32_t bits(float value) {
    std::uint32_t result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

static float reference(float a, float b) {
    // Independent CPU FP32 reference with separate multiply/add rounding.
    volatile float product = b * a;
    return a + product;
}

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3) {
        std::fprintf(stderr, "Usage: %s demo.co [HIP-device-id]\n", argv[0]);
        return EXIT_FAILURE;
    }
    const auto result_path = std::filesystem::path(argv[1]).parent_path() / "gpu_result.json";
    std::filesystem::remove(result_path);
    int count = 0, device = -1;
    HIP_CHECK(hipGetDeviceCount(&count));
    if (argc == 3) {
        char* end = nullptr;
        const long value = std::strtol(argv[2], &end, 10);
        if (end == argv[2] || *end || value < 0 || value >= count) {
            std::fprintf(stderr, "Invalid HIP device: %s\n", argv[2]);
            return EXIT_FAILURE;
        }
        device = static_cast<int>(value);
    } else {
        for (int d = 0; d < count; ++d) {
            hipDeviceProp_t prop{};
            HIP_CHECK(hipGetDeviceProperties(&prop, d));
            if (std::strcmp(prop.gcnArchName, "gfx1100") == 0) { device = d; break; }
        }
    }
    if (device < 0) { std::fprintf(stderr, "No gfx1100 GPU found\n"); return EXIT_FAILURE; }
    hipDeviceProp_t prop{};
    HIP_CHECK(hipGetDeviceProperties(&prop, device));
    if (std::strcmp(prop.gcnArchName, "gfx1100") != 0) {
        std::fprintf(stderr, "Expected gfx1100, got %s\n", prop.gcnArchName);
        return EXIT_FAILURE;
    }
    HIP_CHECK(hipSetDevice(device));
    std::printf("GPU %d: %s (%s)\n", device, prop.name, prop.gcnArchName);
    hipModule_t module{};
    hipFunction_t kernel{};
    HIP_CHECK(hipModuleLoad(&module, argv[1]));
    HIP_CHECK(hipModuleGetFunction(&kernel, module, "asm_flydsl_demo"));
    constexpr std::uint32_t sentinel = 0xcdcdcdcdu;
    constexpr unsigned pad = 16;
    unsigned launches = 0, records = 0;
    const char* fields[] = {"a", "b", "c", "VGPR guard", "SGPR guard", "SCC", "VCC", "EXEC",
                            "MODE before", "MODE after", "lane", "final guard"};
    for (unsigned threads : {1u, 13u, 32u}) for (unsigned kind = 0; kind < 3; ++kind)
    for (unsigned repeat = 0; repeat < 3; ++repeat) {
        std::vector<std::uint32_t> input_a(threads + 2 * pad, sentinel), input_b(input_a);
        for (unsigned i = 0; i < threads; ++i) {
            float a = 0, b = 0;
            if (kind == 1) {
                a = (static_cast<int>(i % 17) - 8) * 0.125f;
                b = (static_cast<int>(i % 11) - 5) * 0.25f;
                if (i == 0) a = -0.0f;
            } else if (kind == 2) {
                const unsigned x = (i + 17 * repeat + 1) * 1664525u + 1013904223u;
                const unsigned y = x * 1664525u + 1013904223u;
                a = (static_cast<int>((x >> 8) % 8193) - 4096) / 128.0f;
                b = (static_cast<int>((y >> 8) % 4097) - 2048) / 256.0f;
            }
            input_a[pad + i] = bits(a);
            input_b[pad + i] = bits(b);
        }
        std::vector<Record> actual(threads + 2);
        for (auto& row : actual) row.fill(sentinel);
        std::uint32_t *a_all = nullptr, *b_all = nullptr;
        Record* out_all = nullptr;
        HIP_CHECK(hipMalloc(&a_all, input_a.size() * 4));
        HIP_CHECK(hipMalloc(&b_all, input_b.size() * 4));
        HIP_CHECK(hipMalloc(&out_all, actual.size() * sizeof(Record)));
        HIP_CHECK(hipMemcpy(a_all, input_a.data(), input_a.size() * 4, hipMemcpyHostToDevice));
        HIP_CHECK(hipMemcpy(b_all, input_b.data(), input_b.size() * 4, hipMemcpyHostToDevice));
        HIP_CHECK(hipMemcpy(out_all, actual.data(), actual.size() * sizeof(Record), hipMemcpyHostToDevice));
        auto* a = a_all + pad;
        auto* b = b_all + pad;
        auto* out = out_all + 1;
        void* args[] = {&a, &b, &out};
        HIP_CHECK(hipModuleLaunchKernel(kernel, 1, 1, 1, threads, 1, 1, 0, nullptr, args, nullptr));
        HIP_CHECK(hipDeviceSynchronize());
        HIP_CHECK(hipMemcpy(actual.data(), out_all, actual.size() * sizeof(Record), hipMemcpyDeviceToHost));
        std::vector<std::uint32_t> read_a(input_a.size()), read_b(input_b.size());
        HIP_CHECK(hipMemcpy(read_a.data(), a_all, read_a.size() * 4, hipMemcpyDeviceToHost));
        HIP_CHECK(hipMemcpy(read_b.data(), b_all, read_b.size() * 4, hipMemcpyDeviceToHost));
        HIP_CHECK(hipFree(a_all));
        HIP_CHECK(hipFree(b_all));
        HIP_CHECK(hipFree(out_all));
        if (read_a != input_a || read_b != input_b) {
            std::fprintf(stderr, "Input memory/guard modified\n"); return EXIT_FAILURE;
        }
        for (unsigned row = 0; row < actual.size(); ++row) {
            Record expected;
            expected.fill(sentinel);
            if (row > 0 && row <= threads) {
                const unsigned lane = row - 1;
                float av, bv;
                std::memcpy(&av, &input_a[pad + lane], 4);
                std::memcpy(&bv, &input_b[pad + lane], 4);
                const auto exec = threads == 32 ? 0xffffffffu : (1u << threads) - 1;
                expected = {bits(av), bits(bv), bits(reference(av, bv)), 0x12345678u, 0x2468ace0u,
                            1u, 0x5a5a5a5au, exec, actual[row][8], actual[row][8], lane, 0x76543210u};
            }
            for (unsigned field = 0; field < expected.size(); ++field) {
                if (actual[row][field] != expected[field]) {
                    std::fprintf(stderr, "FAIL threads=%u case=%u repeat=%u row=%u %s: got %08x expected %08x\n",
                                 threads, kind, repeat, row, fields[field], actual[row][field], expected[field]);
                    return EXIT_FAILURE;
                }
            }
        }
        ++launches;
        records += threads;
    }
    HIP_CHECK(hipModuleUnload(module));
    std::ofstream result(result_path);
    result << "{\n  \"status\": \"PASS\",\n  \"target\": \"gfx1100\",\n  \"device\": " << device
           << ",\n  \"launches\": " << launches << ",\n  \"records\": " << records
           << ",\n  \"fields_per_record\": 12,\n  \"thread_counts\": [1, 13, 32],\n"
           << "  \"input_memory_unchanged\": true,\n  \"output_guards_unchanged\": true,\n"
           << "  \"scc_vcc_exec_mode_preserved\": true\n}\n";
    result.close();
    if (!result) { std::fprintf(stderr, "Cannot write result JSON\n"); return EXIT_FAILURE; }
    std::printf("GPU PASS: %u launches, %u records, all 12 fields and memory guards checked\n", launches, records);
    return EXIT_SUCCESS;
}
