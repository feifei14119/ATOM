// Host-only HIP module launcher. The GPU entry and memory traffic are ASM.
#include <hip/hip_runtime_api.h>
#include <array>
#include <cmath>
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

using Record = std::array<std::uint32_t, 14>;
static_assert(sizeof(Record) == 56);

static float value(std::uint32_t raw) {
    float result;
    std::memcpy(&result, &raw, sizeof(result));
    return result;
}

static std::uint32_t bits(float number) {
    std::uint32_t result;
    std::memcpy(&result, &number, sizeof(result));
    return result;
}

static float reference_c(float a, float b) {
    volatile float product = b * a;
    return a + product;
}

static float reference_d(float a, float b) {
    volatile float quotient = b / a;
    return a - quotient;
}

static std::uint32_t ordered_bits(std::uint32_t raw) {
    return raw & 0x80000000u ? ~raw : raw | 0x80000000u;
}

static bool equal_float(std::uint32_t actual, std::uint32_t expected, unsigned max_ulp) {
    const float a = value(actual), e = value(expected);
    if (std::isnan(e)) return std::isnan(a);
    if (std::isinf(e) || e == 0.0f) return actual == expected;
    if (!std::isfinite(a)) return false;
    const auto x = static_cast<std::uint64_t>(ordered_bits(actual));
    const auto y = static_cast<std::uint64_t>(ordered_bits(expected));
    return (x > y ? x - y : y - x) <= max_ulp;
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
        const long parsed = std::strtol(argv[2], &end, 10);
        if (end == argv[2] || *end || parsed < 0 || parsed >= count) {
            std::fprintf(stderr, "Invalid HIP device\n"); return EXIT_FAILURE;
        }
        device = static_cast<int>(parsed);
    } else {
        for (int id = 0; id < count; ++id) {
            hipDeviceProp_t prop{};
            HIP_CHECK(hipGetDeviceProperties(&prop, id));
            if (std::strcmp(prop.gcnArchName, "gfx1100") == 0) { device = id; break; }
        }
    }
    if (device < 0) { std::fprintf(stderr, "No gfx1100 GPU found\n"); return EXIT_FAILURE; }
    hipDeviceProp_t prop{};
    HIP_CHECK(hipGetDeviceProperties(&prop, device));
    if (std::strcmp(prop.gcnArchName, "gfx1100") != 0) {
        std::fprintf(stderr, "Expected gfx1100, got %s\n", prop.gcnArchName); return EXIT_FAILURE;
    }
    HIP_CHECK(hipSetDevice(device));
    std::printf("GPU %d: %s (%s)\n", device, prop.name, prop.gcnArchName);
    hipModule_t module{};
    hipFunction_t kernel{};
    HIP_CHECK(hipModuleLoad(&module, argv[1]));
    HIP_CHECK(hipModuleGetFunction(&kernel, module, "asm_hip_demo"));
    constexpr unsigned pad = 16;
    constexpr std::uint32_t sentinel = 0xcdcdcdcdu;
    unsigned launches = 0, records = 0;
    const char* fields[] = {"a", "b", "c", "d", "VGPR guard", "SGPR guard", "SCC", "mul_add VCC",
                            "EXEC", "MODE before", "MODE after", "lane", "final guard", "second VGPR guard"};
    const std::array<std::array<std::uint32_t, 2>, 14> edges = {{
        {0x00000000u, 0x3f800000u}, {0x80000000u, 0x3f800000u},
        {0x00000000u, 0xbf800000u}, {0x3f800000u, 0x00000000u},
        {0x00000001u, 0x3f800000u}, {0x00800000u, 0x00800000u},
        {0x7f7fffffu, 0x7f7fffffu}, {0x7f800000u, 0x3f800000u},
        {0x3f800000u, 0x7f800000u}, {0x7fc00001u, 0x3f800000u},
        {0x7f800001u, 0x00000000u}, {0x3f800001u, 0xbf800002u},
        {0xbf800001u, 0xbf800002u}, {0x80000001u, 0x00000001u},
    }};
    for (unsigned threads : {1u, 13u, 32u}) for (unsigned kind = 0; kind < 4; ++kind)
    for (unsigned repeat = 0; repeat < 3; ++repeat) {
        std::vector<std::uint32_t> input_a(threads + 2 * pad, sentinel), input_b(input_a);
        for (unsigned lane = 0; lane < threads; ++lane) {
            std::uint32_t a = 0, b = 0;
            if (kind == 1) {
                a = bits((static_cast<int>(lane % 17) - 8) * 0.125f);
                b = bits((static_cast<int>(lane % 11) - 5) * 0.25f);
                if (lane == 0) a = 0x80000000u;
            } else if (kind == 2) {
                const unsigned x = (lane + 17 * repeat + 1) * 1664525u + 1013904223u;
                const unsigned y = x * 1664525u + 1013904223u;
                a = (x & 0x807fffffu) | ((117u + ((x >> 23) % 20)) << 23);
                b = (y & 0x807fffffu) | ((117u + ((y >> 23) % 20)) << 23);
            } else if (kind == 3) {
                const auto edge = edges[(lane + repeat * 5) % edges.size()];
                a = edge[0]; b = edge[1];
            }
            input_a[pad + lane] = a;
            input_b[pad + lane] = b;
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
        HIP_CHECK(hipFree(a_all)); HIP_CHECK(hipFree(b_all)); HIP_CHECK(hipFree(out_all));
        if (read_a != input_a || read_b != input_b) {
            std::fprintf(stderr, "Input memory/guards modified\n"); return EXIT_FAILURE;
        }
        for (unsigned row = 0; row < actual.size(); ++row) {
            Record expected;
            expected.fill(sentinel);
            const bool live = row > 0 && row <= threads;
            if (live) {
                const unsigned lane = row - 1;
                const auto av = input_a[pad + lane], bv = input_b[pad + lane];
                const auto exec = threads == 32 ? 0xffffffffu : (1u << threads) - 1;
                expected = {av, bv, bits(reference_c(value(av), value(bv))), bits(reference_d(value(av), value(bv))),
                            0x12345678u, 0x2468ace0u, 1u, 0x5a5a5a5au, exec,
                            actual[row][9], actual[row][9], lane, 0x76543210u, 0xabcdef01u};
            }
            for (unsigned field = 0; field < expected.size(); ++field) {
                const bool equal = live && (field == 2 || field == 3)
                    ? equal_float(actual[row][field], expected[field], field == 3 ? 2 : 0)
                    : actual[row][field] == expected[field];
                if (!equal) {
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
           << ",\n  \"fields_per_record\": 14,\n  \"thread_counts\": [1, 13, 32],\n"
           << "  \"c_max_ulp\": 0,\n  \"d_max_ulp\": 2,\n  \"zero_sign_and_inf_exact\": true,\n"
           << "  \"nan_payload_ignored\": true,\n  \"input_memory_unchanged\": true,\n"
           << "  \"output_guards_unchanged\": true,\n  \"scc_exec_mode_preserved\": true,\n"
           << "  \"mul_add_vcc_preserved\": true,\n  \"division_vcc_clobber_authorized\": true\n}\n";
    result.close();
    if (!result) { std::fprintf(stderr, "Cannot write GPU result\n"); return EXIT_FAILURE; }
    std::printf("GPU PASS: %u launches, %u records; all 14 fields and memory guards checked\n", launches, records);
    return EXIT_SUCCESS;
}
