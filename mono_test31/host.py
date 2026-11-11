"""Load/launch seam for already prepared ATOM TP4 resources; no work at import."""
from dataclasses import dataclass
import ctypes
import hashlib
import json
from pathlib import Path
from typing import Any

from contract import StepArgs
from elf import audit_binary


@dataclass
class PreparedStep:
    device: int
    rank: int
    rows: int
    recv: tuple[int, int, int, int]
    cnt: Any
    st: Any
    fp: Any
    tp: Any
    scale: float
    keepalive: tuple[Any, ...]


def pack_args(step):
    if len(step.recv) != 4 or any(p <= 0 or p % 16 for p in step.recv):
        raise ValueError("TP4 requires four mapped, 16-byte-aligned receive addresses")
    return StepArgs(*step.recv, step.cnt.data_ptr(), step.st.data_ptr(),
                    step.scale, 0, step.fp.data_ptr(), step.tp.data_ptr())


def validate_prepared(cfg, step):
    if (cfg["rank"], cfg["target_rows"]) != (step.rank, step.rows):
        raise ValueError("Code object rank/rows differs from prepared tensors")
    if not step.keepalive:
        raise ValueError("Keep table/cache/peer-allocation owners alive through GPU completion")
    for name in ("cnt", "st", "fp", "tp"):
        tensor = getattr(step, name)
        if not tensor.is_cuda or not tensor.is_contiguous() or tensor.device.index != step.device:
            raise ValueError(f"{name} must be a contiguous tensor on device {step.device}")
    if step.cnt.numel() * step.cnt.element_size() < cfg["counter_bytes_min"]:
        raise ValueError("Counter allocation is smaller than the source-derived layout")
    if step.st.numel() * step.st.element_size() < 256 * 32 * 8:
        raise ValueError("Timestamp allocation must cover all 256 CTAs")
    # Source table reserves rows 0..44, including target entry at row 44.
    table_bytes = (len(cfg["fp_names"]) + len(cfg["attention_names"])
                   + 45 * len(cfg["layer_names"])) * 8
    if step.fp.numel() * step.fp.element_size() < table_bytes:
        raise ValueError("fp must include the original complete layer/entry table")
    if step.tp.numel() * step.tp.element_size() < len(cfg["tail_names"]) * 8:
        raise ValueError("tp is smaller than tail.TPTRS")


def residency_bound(function, cfg, device):
    """Reject a persistent grid that exceeds HIP's resident-block upper bound.

    This is a capacity check, not a proof of clustered placement. Cluster
    placement and cross-rank progress still need the opt-in hardware test.
    """
    import torch
    from aiter.ops.asm.asm_utils import _get_hip, hip_check
    hip = _get_hip()
    query = hip.hipModuleOccupancyMaxActiveBlocksPerMultiprocessor
    query.restype = ctypes.c_int
    query.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
    blocks = ctypes.c_int()
    hip_check(query(ctypes.byref(blocks), function, 256, cfg["dynamic_lds_bytes"]),
              "hipModuleOccupancyMaxActiveBlocksPerMultiprocessor")
    multiprocessors = torch.cuda.get_device_properties(device).multi_processor_count
    capacity = blocks.value * multiprocessors
    if capacity < cfg["grid"][0]:
        raise RuntimeError(f"Persistent grid needs 256 resident CTAs; HIP capacity upper bound is {capacity}")
    return {"blocks_per_multiprocessor": blocks.value, "multiprocessors": multiprocessors,
            "resident_ctas_upper_bound": capacity}


def load_kernel(manifest_path, step):
    cfg = json.loads(Path(manifest_path).read_text())
    if cfg.get("status") != "BUILT_NOT_TESTED" or not cfg.get("compute_stages_implemented"):
        raise RuntimeError("Manifest must come from a completed build with every reachable fragment")
    data = Path(cfg["code_object"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != cfg["binary_sha256"]:
        raise RuntimeError("Code object differs from its build manifest")
    audit_binary(data, cfg, cfg["resources"])
    validate_prepared(cfg, step)
    from aiter.ops.asm.asm_utils import device_guard, get_function, get_gfx_from_device
    with device_guard(step.device):
        if get_gfx_from_device(step.device) != "gfx1250":
            raise RuntimeError("This kernel requires gfx1250")
        function = get_function(cfg["code_object"], cfg["symbol"], device=step.device)
        cfg["host_residency_bound"] = residency_bound(function, cfg, step.device)
    return function, cfg


def launch_prepared(function, cfg, step, stream=None):
    """Enqueue only; host prepares plans and clears cnt once per decode step.

    Split target/draft share counters without clearing between launches. Each
    launch advances the epoch, exactly as the original step.build does.
    Every TP rank must enqueue; never wait for rank 0 before enqueuing peers.
    """
    validate_prepared(cfg, step)
    if "host_residency_bound" not in cfg:
        raise RuntimeError("Load the kernel and check its resources before launching")
    from aiter.ops.asm.asm_utils import current_raw_stream, device_guard, launch_co_cluster
    with device_guard(step.device):
        args = pack_args(step)
        launch_co_cluster(function, grid=tuple(cfg["grid"]), block=tuple(cfg["block"]),
                          kernarg=args, cluster_dim=tuple(cfg["cluster"]),
                          shared_mem=cfg["dynamic_lds_bytes"],
                          stream=current_raw_stream(step.device) if stream is None else stream)


def prepared_from_runner(runner, rows):
    """Call after the existing runner's host/device input and Engram preparation."""
    return PreparedStep(device=runner.device.index, rank=runner.rank, rows=rows,
                        recv=tuple(int(p) for p in runner.recv), cnt=runner.scratch["cnt"],
                        st=runner.scratch["st"], fp=runner.tables.fptab, tp=runner.tables.tp,
                        scale=float(runner.base.layers[0].attn.softmax_scale), keepalive=(runner,))
