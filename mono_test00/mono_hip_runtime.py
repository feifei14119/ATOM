"""HIP memory and occupancy checks for a single device; no compilation here."""
from __future__ import annotations

import ctypes as C
from pathlib import Path

import torch


class Hip:
    def __init__(self):
        # Use the runtime already loaded by PyTorch, avoiding mixed ROCm installs.
        paths = sorted({line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
                        if "libamdhip64.so" in line and line.split()[-1].startswith("/")})
        if len(paths) != 1:
            raise RuntimeError(f"Expected one loaded HIP runtime after torch.cuda.init(): {paths}")
        self.path = paths[0]
        self.lib = C.CDLL(self.path)
        signatures = {
            "hipMalloc": [C.POINTER(C.c_void_p), C.c_size_t],
            "hipExtMallocWithFlags": [C.POINTER(C.c_void_p), C.c_size_t, C.c_uint],
            "hipFree": [C.c_void_p],
            "hipMemcpy": [C.c_void_p, C.c_void_p, C.c_size_t, C.c_int],
            "hipModuleLoadData": [C.POINTER(C.c_void_p), C.c_void_p],
            "hipModuleGetFunction": [C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p],
            "hipModuleOccupancyMaxActiveBlocksPerMultiprocessor": [C.POINTER(C.c_int), C.c_void_p, C.c_int, C.c_size_t],
            "hipModuleUnload": [C.c_void_p],
        }
        for name, args in signatures.items():
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, C.c_int
        self.lib.hipGetErrorString.argtypes = [C.c_int]
        self.lib.hipGetErrorString.restype = C.c_char_p

    def call(self, name, *args):
        result = getattr(self.lib, name)(*args)
        if result:
            text = self.lib.hipGetErrorString(result)
            raise RuntimeError(f"{name}: {result}: {text.decode() if text else 'unknown HIP error'}")

    def occupancy(self, binary: bytes, symbol: str, threads: int, cus: int, grid: int):
        blob = C.create_string_buffer(binary)
        module, function, blocks = C.c_void_p(), C.c_void_p(), C.c_int()
        self.call("hipModuleLoadData", C.byref(module), C.cast(blob, C.c_void_p))
        try:
            self.call("hipModuleGetFunction", C.byref(function), module, symbol.encode())
            self.call("hipModuleOccupancyMaxActiveBlocksPerMultiprocessor", C.byref(blocks), function, threads, 0)
            capacity = blocks.value * cus
            if capacity < grid:
                raise RuntimeError(f"Insufficient residency: {blocks.value} CTAs/CU x {cus} CUs = {capacity}, need {grid}")
            return {"blocks_per_cu": blocks.value, "cus": cus, "capacity": capacity, "required": grid}
        finally:
            self.call("hipModuleUnload", module)


class Buffer:
    GUARD = 256
    SENTINEL = 0xA7

    def __init__(self, hip: Hip, name: str, nbytes: int, *, uncached=False):
        self.hip, self.name, self.nbytes = hip, name, nbytes
        self.base = C.c_void_p()
        self.total = nbytes + 2 * self.GUARD
        if uncached:
            # Same flag as ATOM's allocate_uncached: no cached fallback.
            hip.call("hipExtMallocWithFlags", C.byref(self.base), self.total, 3)
        else:
            hip.call("hipMalloc", C.byref(self.base), self.total)
        self.ptr = self.base.value + self.GUARD
        self.expected = None

    def upload(self, tensor):
        raw = tensor.contiguous().view(torch.uint8).flatten()
        if raw.device.type != "cpu" or raw.numel() != self.nbytes:
            raise ValueError(f"{self.name}: invalid CPU payload")
        full = torch.full((self.total,), self.SENTINEL, dtype=torch.uint8)
        full[self.GUARD:-self.GUARD] = raw
        self.hip.call("hipMemcpy", self.base, C.c_void_p(full.data_ptr()), self.total, 1)
        self.expected = raw.clone()

    def download(self, *, immutable=False):
        full = torch.empty(self.total, dtype=torch.uint8)
        self.hip.call("hipMemcpy", C.c_void_p(full.data_ptr()), self.base, self.total, 2)
        if not bool((full[:self.GUARD] == self.SENTINEL).all() and (full[-self.GUARD:] == self.SENTINEL).all()):
            raise AssertionError(f"{self.name}: memory guard overwritten")
        payload = full[self.GUARD:-self.GUARD].clone()
        if immutable and not torch.equal(payload, self.expected):
            raise AssertionError(f"{self.name}: read-only/unused payload was modified")
        return payload

    def close(self):
        if self.base.value:
            self.hip.call("hipFree", self.base)
            self.base = C.c_void_p()
