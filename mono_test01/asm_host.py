"""Per-task argument tables and complete supplier-tile checks, CPU/HIP only."""
from __future__ import annotations

import struct

import torch

from hip_runtime import Buffer
from reference import exact

TASKS, ELEMENTS, ARGS_BYTES = 112, 4096, 240
TILE_GUARD = 256
INPUT_BYTES, OUTPUT_BYTES = ELEMENTS * 4, ELEMENTS * 2
INPUT_SLOT = INPUT_BYTES + 2 * TILE_GUARD
OUTPUT_SLOT = OUTPUT_BYTES + 2 * TILE_GUARD


def packed_indices():
    i = torch.arange(ELEMENTS)
    r, c = i // 64, i % 64
    sr = 16 * (r // 16) + 8 * ((c // 16) % 2) + r % 8
    sc = 32 * (c // 32) + 16 * ((r // 8) % 2) + c % 16
    return sr * 64 + sc


class DqWorkspace:
    def __init__(self, hip):
        self.input = Buffer(hip, 'dq_input_slots', TASKS * INPUT_SLOT, uncached=True)
        self.output = Buffer(hip, 'dq_output_slots', TASKS * OUTPUT_SLOT, uncached=True)
        self.args = Buffer(hip, 'dq_args', TASKS * ARGS_BYTES, uncached=True)
        self.permutation = packed_indices()
        exact('supplier layout is bijective', self.permutation.sort().values, torch.arange(ELEMENTS))
        exact('sixteen live positions', self.permutation[:16], torch.arange(16))
        table = bytearray(TASKS * ARGS_BYTES)
        for task in range(TASKS):
            src = self.input.ptr + task * INPUT_SLOT + TILE_GUARD
            dst = self.output.ptr + task * OUTPUT_SLOT + TILE_GUARD
            # This supplier's buffer descriptor retains 53 address bits.
            if src >= 1 << 53 or dst >= 1 << 53:
                raise RuntimeError('Supplier buffer descriptor does not support this VA range')
            for offset, fmt, value in (
                (0x00, 'Q', src), (0x10, 'Q', dst),
                (0x20, 'Q', INPUT_BYTES), (0x30, 'Q', INPUT_BYTES), (0x40, 'I', 256),
                (0x50, 'Q', OUTPUT_BYTES), (0x60, 'Q', OUTPUT_BYTES), (0x70, 'I', 128),
                (0x80, 'I', 64), (0x90, 'I', 64), (0xC0, 'I', 64),
            ):
                struct.pack_into('<'+fmt, table, task * ARGS_BYTES + offset, value)
        self.table = torch.frombuffer(table, dtype=torch.uint8).clone()

    def reset(self, seed):
        source = torch.full((TASKS, INPUT_SLOT), Buffer.SENTINEL, dtype=torch.uint8)
        output = torch.full((TASKS, OUTPUT_SLOT), Buffer.SENTINEL, dtype=torch.uint8)
        task = torch.arange(TASKS)[:, None]
        elem = torch.arange(ELEMENTS)[None, :]
        # Nonzero task-dependent padding detects tile mixups and checks the
        # whole supplier kernel, while only the first 16 values feed Mono.
        logical = (((task * 17 + elem * 13 + seed) % 1021) - 510).float() / 256
        logical[:, :16] = float('nan')  # producer must overwrite all live slots
        packed = torch.empty_like(logical)
        packed[:, self.permutation] = logical
        source[:, TILE_GUARD:TILE_GUARD+INPUT_BYTES] = packed.view(torch.uint8)
        output[:, TILE_GUARD:TILE_GUARD+OUTPUT_BYTES] = 0xCC
        self.source_before = source.clone()
        self.input.upload(source)
        self.output.upload(output)
        self.args.upload(self.table)

    def verify(self, qkv):
        src = self.input.download().reshape(TASKS, INPUT_SLOT)
        dst = self.output.download().reshape(TASKS, OUTPUT_SLOT)
        self.args.download(immutable=True)
        for name, data, size in (('input', src, INPUT_BYTES), ('output', dst, OUTPUT_BYTES)):
            for tail in (data[:, :TILE_GUARD], data[:, TILE_GUARD+size:]):
                exact('per-tile '+name+' guard', tail, torch.full_like(tail, Buffer.SENTINEL))
        # All input bytes except the first sixteen FP32 sums must be unchanged.
        exact('packed input padding', src[:, TILE_GUARD+64:], self.source_before[:, TILE_GUARD+64:])
        packed = src[:, TILE_GUARD:TILE_GUARD+INPUT_BYTES].contiguous().view(torch.float32)
        logical = packed[:, self.permutation]
        if not bool(torch.isfinite(logical).all()):
            raise AssertionError('Missing producer store or nonfinite WQKV sum')
        expected = logical.bfloat16()
        got = dst[:, TILE_GUARD:TILE_GUARD+OUTPUT_BYTES].contiguous().view(torch.bfloat16)
        exact('all ASM tile results', got.view(torch.int16), expected.view(torch.int16))
        exact('ASM result consumed by QKV mailbox', qkv, got[:, :16].contiguous().flatten().float())
        return {'tasks': TASKS, 'converted_elements': TASKS * ELEMENTS,
                'live_mono_elements': TASKS * 16, 'tile_guards': 'PASS',
                'all_bf16_bits': 'PASS', 'post_asm_mailbox': 'PASS'}

    def close(self):
        self.args.close()
        self.output.close()
        self.input.close()
