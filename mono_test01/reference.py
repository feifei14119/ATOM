"""CPU inputs and numerical oracles. This module never imports ATOM/FlyDSL.

All reference arithmetic stays on CPU. The GPU under test executes only the
one fused projection kernel, once per test iteration.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

HIDDEN, HC, ROWS = 5120, 4, 1792
SLICES, MIX, GROUP = 160, 24, 32
CASES = ("zero", "pattern", "random")


@dataclass
class Inputs:
    residual: torch.Tensor
    pre: torch.Tensor
    hc_fn: torch.Tensor
    norm_weight: torch.Tensor
    weight_fp8: torch.Tensor
    weight_scale: torch.Tensor
    packed_weight: torch.Tensor
    weight_real: torch.Tensor


def pack_weight(q):
    """AITER 16x16 FP8 shuffle: [N/16,K/32,2,16,16] bytes.

    Logical W[n,k] lives at
    (((n//16)*(K//32) + k//32)*2 + (k%32)//16)*256
      + (n%16)*16 + k%16.
    Scales are NOT shuffled: one E8M0 byte per 32 output x 32 input tile.
    """
    return (q.view(torch.uint8).reshape(ROWS // 16, 16, HIDDEN // 32, 2, 16)
            .permute(0, 2, 3, 1, 4).contiguous().flatten())


def make_inputs(case: str, seed: int) -> Inputs:
    g = torch.Generator(device="cpu").manual_seed(seed)
    pre = torch.tensor([0.125, 0.25, -0.125, 0.5], dtype=torch.float32)
    if case == "zero":
        residual = torch.zeros(HC, HIDDEN, dtype=torch.bfloat16)
    elif case == "pattern":
        i = torch.arange(HC * HIDDEN).reshape(HC, HIDDEN)
        residual = (((i * 13 + seed * 7) % 127 - 63).float() / 32).bfloat16()
    elif case == "random":
        residual = torch.randn(HC, HIDDEN, generator=g).bfloat16()
    else:
        raise ValueError(case)
    # Dyadic normalization weights avoid arbitrary input conversion differences.
    norm_weight = (torch.randint(8, 25, (HIDDEN,), generator=g).float() / 16).bfloat16()
    hc_fn = torch.randn(MIX, HC * HIDDEN, generator=g) / 128
    if case == "pattern":
        n = torch.arange(ROWS)[:, None]
        k = torch.arange(HIDDEN)[None, :]
        weight = (((n * 11 + k * 7 + seed) % 61) - 30).float() / 8
    else:
        weight = torch.randn(ROWS, HIDDEN, generator=g) * 2
    q = weight.to(torch.float8_e4m3fn)
    scale = torch.randint(118, 124, (ROWS // GROUP, HIDDEN // GROUP), generator=g).to(torch.uint8)
    real = q.double() * torch.exp2(scale.double() - 127).repeat_interleave(GROUP, 0).repeat_interleave(GROUP, 1)
    packed = pack_weight(q)
    # Check the host layout against independent scalar addressing at boundaries
    # and pseudorandom coordinates before uploading it.
    n = torch.cat((torch.tensor([0, 15, 16, 31, 32, ROWS - 1]), torch.randint(ROWS, (1000,), generator=g)))
    k = torch.cat((torch.tensor([0, 15, 16, 31, 128, HIDDEN - 1]), torch.randint(HIDDEN, (1000,), generator=g)))
    at = (((n // 16) * (HIDDEN // 32) + k // 32) * 2 + k % 32 // 16) * 256 + n % 16 * 16 + k % 16
    if not torch.equal(packed[at], q.view(torch.uint8)[n, k]):
        raise AssertionError("Host weight packing failed its address check")
    return Inputs(residual, pre, hc_fn, norm_weight, q, scale, packed, real)


def quantize_norm(normed):
    """CPU OCP E4M3FN + E8M0 per 32 elements, matching the mathematical format."""
    rows = normed.float().reshape(-1, GROUP)
    amax = rows.abs().amax(1).clamp_min(1e-4)
    # Preserve the FP32 reciprocal multiplication used by code_ceil, then use
    # float64 log2/ceil as an independent exponent implementation.
    ratio = amax * (1.0 / 448.0)
    code = (torch.ceil(torch.log2(ratio.double())) + 127).clamp(1, 254).to(torch.uint8)
    scale = torch.exp2(code.float() - 127)
    quant = (rows / scale[:, None]).clamp(-448, 448).to(torch.float8_e4m3fn)
    return quant.flatten(), code


def dequantize(q, code):
    return q.double() * torch.exp2(code.double() - 127).repeat_interleave(GROUP)


def _finite(name, value):
    if not bool(torch.isfinite(value).all()):
        raise AssertionError(f"{name}: NaN/Inf")


def exact(name, got, expected):
    if got.shape != expected.shape or not torch.equal(got, expected):
        count = int((got != expected).sum()) if got.shape == expected.shape else -1
        raise AssertionError(f"{name}: {count} mismatches; {tuple(got.shape)} vs {tuple(expected.shape)}")


def bounded(name, got, expected, tolerance):
    got, expected = got.double(), expected.double()
    _finite(name, got)
    _finite(name + " reference", expected)
    error = (got - expected).abs()
    limit = torch.broadcast_to(torch.as_tensor(tolerance, dtype=torch.float64), error.shape)
    bad = error > limit
    if bool(bad.any()):
        index = int((error / limit.clamp_min(1e-30)).flatten().argmax())
        raise AssertionError(
            f"{name}: {int(bad.sum())} failures, worst flat index {index}: "
            f"got={got.flatten()[index].item():.9g}, expected={expected.flatten()[index].item():.9g}, "
            f"error={error.flatten()[index].item():.9g}, tolerance={limit.flatten()[index].item():.9g}"
        )
    return {"max_abs": float(error.max()), "rms": float(error.square().mean().sqrt()),
            "max_error_over_bound": float((error / limit.clamp_min(1e-30)).max())}


def verify(inp: Inputs, outputs: dict) -> dict:
    """Validate every produced region, with roundoff allowances made explicit."""
    metrics = {}
    r = inp.residual.float()
    lin = torch.zeros(HIDDEN, dtype=torch.float32)
    for h in range(HC):
        lin = lin + inp.pre[h] * r[h]
    lin = lin.bfloat16()
    exact("LIN BF16", outputs["lin"].view(torch.int16), lin.view(torch.int16))

    # Full residual streams, before collapse, enter the 24 mix projections.
    x = r.double().reshape(HC, SLICES, 32).permute(1, 0, 2).reshape(SLICES, 128)
    hi = inp.hc_fn.bfloat16().float()
    fn = hi + (inp.hc_fn - hi).bfloat16().float()
    w = fn.double().reshape(MIX, HC, SLICES, 32).permute(2, 0, 1, 3).reshape(SLICES, MIX, 128)
    dot = (w * x[:, None]).sum(-1)
    magnitude = (w.abs() * x[:, None].abs()).sum(-1)
    metrics["pmix"] = bounded("PMIX", outputs["pmix"][:, :MIX], dot, magnitude * 4e-6 + 1e-8)
    sq = x.square().sum(-1)
    metrics["residual_square"] = bounded("PMIX square", outputs["pmix"][:, MIX], sq, sq * 2e-6 + 1e-8)

    # A high precision mathematical RMSNorm, not a copy of the GPU reduction.
    norm = lin.double() * torch.rsqrt(lin.double().square().mean() + 1e-20) * inp.norm_weight.double()
    # Half BF16 ULP <= |x| / 256; the additional 5e-6 covers FP32 reduction
    # and the approximate rsq. Zero remains exact in the all-zero case.
    metrics["rmsnorm"] = bounded("normed", outputs["normed"], norm, norm.abs() * (1 / 256 + 5e-6) + 1e-8)
    exact("NB vs normed", outputs["nb"].view(torch.int16), outputs["normed"].view(torch.int16))

    # Check the quantizer exactly against its actual, independently-validated
    # BF16 input, so a norm rounding boundary cannot excuse a layout error.
    q, codes = quantize_norm(outputs["normed"])
    exact("X8 bytes", outputs["x8"], q.view(torch.uint8))
    exact("X8S codes", outputs["x8s"], codes.int())
    actual_x = dequantize(outputs["x8"].view(torch.float8_e4m3fn), codes)
    ideal_q, ideal_codes = quantize_norm(norm.bfloat16())
    ideal_x = dequantize(ideal_q, ideal_codes)

    expected = inp.weight_real @ actual_x
    sum_abs = inp.weight_real.abs() @ actual_x.abs()
    # Eight K-split groups, each summing 640 products, then eight FP32 partials.
    # gamma_648 is conservative even if the matrix instruction sums serially.
    u = 2.0 ** -24
    gamma = 648 * u / (1 - 648 * u)
    fp_error = gamma * sum_abs
    limit = expected.abs() / 256 + fp_error * (1 + 1 / 256) + 1e-8
    metrics["qkv"] = bounded("QKV", outputs["qkv"], expected, limit)
    # Full input-to-output check: bound propagation of the separately checked
    # RMSNorm rounding differences through the independent logical weight.
    end_to_end = inp.weight_real @ ideal_x
    propagated = inp.weight_real.abs() @ (actual_x - ideal_x).abs()
    metrics["end_to_end"] = bounded("end-to-end QKV", outputs["qkv"], end_to_end, limit + propagated)
    metrics["fp8_bytes_different_from_ideal_norm"] = int((q.view(torch.uint8) != ideal_q.view(torch.uint8)).sum())
    metrics["qkv_nonzero"] = int(torch.count_nonzero(outputs["qkv"]))
    return metrics
