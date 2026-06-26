# SPDX-License-Identifier: MIT
# Copyright (C) 2024-2026, Advanced Micro Devices, Inc. All rights reserved.

"""Dump the inputs / output / params of ATOM's V4 sparse MLA decode kernel.

Enabled by the ``ATOM_DUMP_MLA_DIR`` env var. Wired into
``DeepseekV4Attention.forward`` decode branch, right after
``sparse_attn_v4_paged_decode(...)`` (atom/models/deepseek_v4.py) -- the exact
kernel ATOM runs on the V4 decode path (``ATOM_USE_TRITON_ATTN=1`` -> the triton
``_sparse_attn_v4_paged_decode_triton``). The dumped ``o`` is therefore ATOM's
real triton output, i.e. the golden the aiter unit test compares against.

The aiter counterpart op is
``aiter.ops.triton.attention.pa_decode_sparse.pa_decode_sparse`` (identical
signature). The unit test ``aiter/op_tests/test_mla_atom_dump.py`` consumes:

1. A JSONL manifest line (always, cheap) to ``<dir>/mla_calls.rank<r>.jsonl``
   carrying just the shape/params of the call (T, H, D, per-token kv spans,
   ratio, softmax_scale, ...). The test's "params" mode regenerates random cases
   of the same shape and uses the torch reference as golden -- no tensors.

2. Up to ``ATOM_DUMP_MLA_MAX`` full tensor files to
   ``<dir>/mla_decode.rank<r>.<idx>.pt`` with the EXACT kernel inputs in a
   compact, replayable form (only the referenced KV pages are kept and the
   indices remapped) plus the kernel output:
     - ``q``          : [T, H, D]            (bf16)
     - ``unified_kv`` : [num_used_pages, D]  (compact; bf16 or fp8)
     - ``kv_indices`` : [total_indices] int32 (remapped into the compact pool)
     - ``kv_indptr``  : [T+1] int32
     - ``attn_sink``  : [H] fp32
     - ``kv_scales``  : [num_used_pages, D//64] fp32  (only if fp8 KV)
     - ``o``          : [T, H, D]            (ATOM triton output == golden)
     - plus all the manifest params (softmax_scale, ratio, ...).
"""

import json
import logging
import os
import threading
from typing import Optional

import torch

from atom.utils import envs

logger = logging.getLogger("atom")

_LOCK = threading.Lock()
_TENSOR_DUMPS = 0
_CALL_IDX = 0
_LAYERS_CACHE: Optional[set] = None
_MANIFEST_PATH: Optional[str] = None


def mla_dump_enabled() -> bool:
    return bool(envs.ATOM_DUMP_MLA_DIR)


def _dump_layers() -> Optional[set]:
    global _LAYERS_CACHE
    if _LAYERS_CACHE is None:
        raw = envs.ATOM_DUMP_MLA_LAYERS.strip()
        if raw:
            _LAYERS_CACHE = {int(x) for x in raw.replace(",", " ").split()}
        else:
            _LAYERS_CACHE = set()  # empty == all layers
    return _LAYERS_CACHE


def _rank() -> int:
    for key in ("ATOM_DP_RANK", "RANK", "LOCAL_RANK"):
        val = os.getenv(key)
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
    return 0


def _manifest_path(dump_dir: str) -> str:
    global _MANIFEST_PATH
    if _MANIFEST_PATH is None:
        os.makedirs(dump_dir, exist_ok=True)
        _MANIFEST_PATH = os.path.join(dump_dir, f"mla_calls.rank{_rank()}.jsonl")
    return _MANIFEST_PATH


def _compact_unified_kv(unified_kv, kv_indices, kv_scales):
    """Keep only the KV pages this call references and remap the indices into the
    compact pool, so dumps stay small and self-contained. Preserves ``-1``
    sentinels.

    Returns (kv_compact, indices_remapped, scales_compact_or_None).
    """
    total_pages = unified_kv.shape[0]
    valid = kv_indices >= 0
    if valid.any():
        used = torch.unique(kv_indices[valid].to(torch.int64))
    else:
        used = torch.zeros(0, dtype=torch.int64, device=kv_indices.device)
    remap = torch.full((total_pages,), -1, dtype=torch.int64, device=kv_indices.device)
    remap[used] = torch.arange(used.numel(), device=kv_indices.device)
    idx64 = kv_indices.to(torch.int64).clamp(min=0)
    remapped = torch.where(valid, remap[idx64], torch.full_like(idx64, -1))
    kv_compact = unified_kv.index_select(0, used).contiguous()
    scales_compact = (
        kv_scales.index_select(0, used).contiguous() if kv_scales is not None else None
    )
    return kv_compact, remapped.to(torch.int32), scales_compact


def _compact_token_cache(kv_cache, block_table, context_lens):
    """V3 dense decode helper. The triton MLA decode reads a token-major cache
    ``kv_cache[num_slots, 1, D]`` (``page_size=1``) addressed by a dense
    ``block_table[bs, max_blocks]`` of token-slot ids, only up to each row's
    ``context_lens`` columns. Keep just the referenced slots and remap the
    block_table into the compact pool so the dump stays tiny regardless of the
    full KV pool size.

    Returns (kv_compact, block_table_remapped).
    """
    num_slots = kv_cache.shape[0]
    bs, max_blocks = block_table.shape
    cols = torch.arange(max_blocks, device=block_table.device).unsqueeze(0)
    valid = cols < context_lens.to(torch.int64).unsqueeze(1)
    valid &= (block_table >= 0) & (block_table < num_slots)
    if valid.any():
        used = torch.unique(block_table[valid].to(torch.int64))
    else:
        used = torch.zeros(0, dtype=torch.int64, device=block_table.device)
    remap = torch.full((num_slots,), 0, dtype=torch.int64, device=block_table.device)
    remap[used] = torch.arange(used.numel(), device=block_table.device)
    bt64 = block_table.to(torch.int64).clamp(min=0, max=max(num_slots - 1, 0))
    # Out-of-context entries are never read by the kernel; map them to 0.
    bt_remapped = torch.where(valid, remap[bt64], torch.zeros_like(bt64))
    kv_compact = kv_cache.index_select(0, used).contiguous()
    return kv_compact, bt_remapped.to(torch.int32)


def dump_v3_dense_decode(
    *,
    layer_id: int,
    q: torch.Tensor,
    kv_cache: torch.Tensor,
    block_table: torch.Tensor,
    context_lens: torch.Tensor,
    sm_scale: float,
    page_size: int,
    num_kv_splits: int,
    kv_lora_rank: int,
    qk_rope_head_dim: int,
    o: torch.Tensor,
    k_scale: Optional[torch.Tensor] = None,
    v_scale: Optional[torch.Tensor] = None,
) -> None:
    """Record one DeepSeek-V3 dense MLA decode call exactly as ATOM runs it on
    the ``ATOM_USE_TRITON_MLA=1`` path -- right after
    ``aiter.ops.triton.attention.mla_decode.decode_attention_fwd`` writes ``o``
    (attention_mla.py ``_forward_decode``, the ``triton_block_table`` branch).
    The dumped ``o`` is therefore ATOM's real triton output == the golden the
    aiter ``mla_decode_fwd`` unit test compares against.

    Layout (``page_size`` is 1 on the triton path -> token-major cache):
      - ``q``            : [total_q, H, kv_lora_rank + qk_rope_head_dim]  (bf16)
      - ``kv_cache``     : [num_slots, 1, kv_lora_rank + qk_rope_head_dim] (compact; bf16 or fp8)
      - ``block_table``  : [bs, max_blocks] int32 (remapped into the compact pool)
      - ``context_lens`` : [bs] int32
      - ``o``            : [total_q, H, kv_lora_rank]                     (golden)
      - ``k_scale`` / ``v_scale`` : scalar fp32 (only meaningful if fp8 KV).

    Safe no-op on any failure (a dump must never break inference)."""
    if not mla_dump_enabled():
        return
    layers = _dump_layers()
    if layers and layer_id not in layers:
        return

    global _TENSOR_DUMPS, _CALL_IDX
    try:
        dump_dir = envs.ATOM_DUMP_MLA_DIR
        total_q, H, D = int(q.shape[0]), int(q.shape[1]), int(q.shape[2])
        bs = int(block_table.shape[0])
        ctx_cpu = context_lens.to(torch.int64).cpu().tolist()

        def _scalar(t):
            if t is None:
                return 1.0
            try:
                return float(t.item()) if torch.is_tensor(t) else float(t)
            except Exception:
                return None

        params = {
            "phase": "decode",
            "op": "decode_attention_fwd",  # ATOM_USE_TRITON_MLA triton path
            "model": "deepseek_v3",
            "layer_id": int(layer_id),
            "rank": _rank(),
            "total_q": total_q,
            "bs": bs,
            "H": H,
            "D": D,
            "kv_lora_rank": int(kv_lora_rank),
            "qk_rope_head_dim": int(qk_rope_head_dim),
            "page_size": int(page_size),
            "num_kv_splits": int(num_kv_splits),
            "total_slots": int(kv_cache.shape[0]),
            "context_lens": ctx_cpu,
            "max_ctx": int(max(ctx_cpu)) if ctx_cpu else 0,
            "softmax_scale": float(sm_scale),
            "q_dtype": str(q.dtype),
            "kv_dtype": str(kv_cache.dtype),
            "k_scale": _scalar(k_scale),
            "v_scale": _scalar(v_scale),
        }

        with _LOCK:
            call_idx = _CALL_IDX
            _CALL_IDX += 1
            do_tensor = _TENSOR_DUMPS < int(envs.ATOM_DUMP_MLA_MAX)
            if do_tensor:
                _TENSOR_DUMPS += 1
            manifest_path = _manifest_path(dump_dir)
        params["call_idx"] = call_idx

        tensor_file = None
        if do_tensor:
            kv_compact, bt_remapped = _compact_token_cache(
                kv_cache, block_table, context_lens
            )
            tensor_file = os.path.join(
                dump_dir, f"mla_v3_decode.rank{_rank()}.{call_idx}.pt"
            )
            payload = {
                "params": params,
                "q": q.detach().cpu().contiguous(),
                "kv_cache": kv_compact.detach().cpu(),
                "block_table": bt_remapped.detach().cpu(),
                "context_lens": context_lens.detach().to(torch.int32).cpu().contiguous(),
                "k_scale": (
                    k_scale.detach().float().cpu() if torch.is_tensor(k_scale) else None
                ),
                "v_scale": (
                    v_scale.detach().float().cpu() if torch.is_tensor(v_scale) else None
                ),
                "o": o.detach().cpu().contiguous(),
            }
            torch.save(payload, tensor_file)
            logger.info(
                "mla_dump(v3): wrote tensors %s (total_q=%d bs=%d H=%d D=%d max_ctx=%d)",
                tensor_file,
                total_q,
                bs,
                H,
                D,
                params["max_ctx"],
            )

        params["tensor_file"] = (
            os.path.basename(tensor_file) if tensor_file else None
        )
        with _LOCK:
            with open(manifest_path, "a") as fh:
                fh.write(json.dumps(params) + "\n")
    except Exception as exc:  # never break inference because of a dump
        logger.warning("mla_dump(v3): skipped a call due to %r", exc)


def dump_v4_sparse_decode(
    *,
    layer_id: int,
    ratio: int,
    q: torch.Tensor,
    unified_kv: torch.Tensor,
    kv_indices: torch.Tensor,
    kv_indptr: torch.Tensor,
    attn_sink: torch.Tensor,
    softmax_scale: float,
    o: torch.Tensor,
    kv_scales: Optional[torch.Tensor] = None,
) -> None:
    """Record one V4 sparse MLA decode call. Safe no-op on any failure (a dump
    must never break inference)."""
    if not mla_dump_enabled():
        return
    layers = _dump_layers()
    if layers and layer_id not in layers:
        return

    global _TENSOR_DUMPS, _CALL_IDX
    try:
        dump_dir = envs.ATOM_DUMP_MLA_DIR
        T, H, D = int(q.shape[0]), int(q.shape[1]), int(q.shape[2])
        kv_lens = (kv_indptr[1 : T + 1] - kv_indptr[:T]).to(torch.int64)
        kv_lens_cpu = kv_lens.cpu().tolist()
        total_indices = int(kv_indptr[T].item()) if T > 0 else 0

        params = {
            "phase": "decode",
            "op": "sparse_attn_v4_paged_decode",
            "layer_id": int(layer_id),
            "ratio": int(ratio),
            "rank": _rank(),
            "T": T,
            "H": H,
            "D": D,
            "total_pages": int(unified_kv.shape[0]),
            "total_indices": total_indices,
            "kv_lens": kv_lens_cpu,
            "max_kv_len": int(max(kv_lens_cpu)) if kv_lens_cpu else 0,
            "softmax_scale": float(softmax_scale),
            "q_dtype": str(q.dtype),
            "kv_dtype": str(unified_kv.dtype),
            "has_kv_scales": kv_scales is not None,
            "has_invalid": bool((kv_indices < 0).any().item()),
        }

        with _LOCK:
            call_idx = _CALL_IDX
            _CALL_IDX += 1
            do_tensor = _TENSOR_DUMPS < int(envs.ATOM_DUMP_MLA_MAX)
            if do_tensor:
                _TENSOR_DUMPS += 1
            manifest_path = _manifest_path(dump_dir)
        params["call_idx"] = call_idx

        tensor_file = None
        if do_tensor:
            kv_compact, idx_remapped, scales_compact = _compact_unified_kv(
                unified_kv, kv_indices, kv_scales
            )
            tensor_file = os.path.join(
                dump_dir, f"mla_decode.rank{_rank()}.{call_idx}.pt"
            )
            payload = {
                "params": params,
                "q": q.detach().cpu().contiguous(),
                "unified_kv": kv_compact.detach().cpu(),
                "kv_indices": idx_remapped.detach().cpu(),
                "kv_indptr": kv_indptr.detach().cpu().contiguous(),
                "attn_sink": attn_sink.detach().cpu().contiguous(),
                "kv_scales": (
                    scales_compact.detach().cpu() if scales_compact is not None
                    else None
                ),
                "o": o.detach().cpu().contiguous(),
            }
            torch.save(payload, tensor_file)
            logger.info(
                "mla_dump: wrote tensors %s (T=%d H=%d D=%d ratio=%d max_kv=%d)",
                tensor_file,
                T,
                H,
                D,
                ratio,
                params["max_kv_len"],
            )

        params["tensor_file"] = (
            os.path.basename(tensor_file) if tensor_file else None
        )
        with _LOCK:
            with open(manifest_path, "a") as fh:
                fh.write(json.dumps(params) + "\n")
    except Exception as exc:  # never break inference because of a dump
        logger.warning("mla_dump: skipped a call due to %r", exc)
