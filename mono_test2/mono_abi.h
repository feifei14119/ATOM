#pragma once

// Shared host/device argument layout and launch configuration.
// Mailbox is passed by value, with identical layout in both compilations.
struct Mailbox {
  float* data;
  unsigned* tag;
};
static_assert(sizeof(void*) == 8, "This demo requires 64-bit pointers");
static_assert(sizeof(unsigned) == 4, "The epoch tag must be 32-bit");
static_assert(sizeof(Mailbox) == 16, "Unexpected Mailbox argument layout");

inline constexpr int kBlocks = 3;
inline constexpr int kThreads = 128;
inline constexpr int kElements = 4096;
inline constexpr unsigned kSteps = 32;
inline constexpr int kTags = 3;  // first, second, internal ASM completion
inline constexpr char kKernelSymbol[] = "mono_kernel";
