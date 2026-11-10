#pragma once

#include <cstddef>
#include <cstdint>

// Exact 240-byte supplier layout. All strides are in bytes, pointers are GPU
// global addresses, and reserved fields must be zero. Initialize with {}.
struct alignas(16) DqConvertArgs {
  const float* ptr_dq_acc;           std::uint64_t reserved_00;
  std::uint16_t* ptr_dq;             std::uint64_t reserved_10;
  std::uint64_t Hs_dq_acc;           std::uint64_t reserved_20;
  std::uint64_t BAs_dq_acc;          std::uint64_t reserved_30;
  std::uint32_t Seqs_dq_acc;         std::uint32_t reserved_40[3];
  std::uint64_t Hs_dq;               std::uint64_t reserved_50;
  std::uint64_t BAs_dq;              std::uint64_t reserved_60;
  std::uint32_t Seqs_dq;             std::uint32_t reserved_70[3];
  std::uint32_t seqlen_q;            std::uint32_t reserved_80[3];
  std::uint32_t head_dim;            std::uint32_t reserved_90[3];
  const std::int32_t* ptr_qseq;      std::uint64_t reserved_a0;
  const std::int32_t* ptr_qseq_padded; std::uint64_t reserved_b0;
  std::uint32_t max_seqlen_dq;       std::uint32_t reserved_c0[3];
  std::uint32_t nsplit;              std::uint32_t reserved_d0[3];
  std::uint32_t split_stride;        std::uint32_t reserved_e0[3];
};
static_assert(sizeof(void*) == 8);
static_assert(sizeof(DqConvertArgs) == 240 && alignof(DqConvertArgs) == 16);
#define DQ_OFFSET(field, offset) static_assert(offsetof(DqConvertArgs, field) == offset)
DQ_OFFSET(ptr_dq_acc, 0x00);
DQ_OFFSET(ptr_dq, 0x10);
DQ_OFFSET(Hs_dq_acc, 0x20);
DQ_OFFSET(BAs_dq_acc, 0x30);
DQ_OFFSET(Seqs_dq_acc, 0x40);
DQ_OFFSET(Hs_dq, 0x50);
DQ_OFFSET(BAs_dq, 0x60);
DQ_OFFSET(Seqs_dq, 0x70);
DQ_OFFSET(seqlen_q, 0x80);
DQ_OFFSET(head_dim, 0x90);
DQ_OFFSET(ptr_qseq, 0xa0);
DQ_OFFSET(ptr_qseq_padded, 0xb0);
DQ_OFFSET(max_seqlen_dq, 0xc0);
DQ_OFFSET(nsplit, 0xd0);
DQ_OFFSET(split_stride, 0xe0);
#undef DQ_OFFSET

