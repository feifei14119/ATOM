"""CPU-only address checks for the fixed C1 stage; no GPU/WMMA emulation."""


def check_c1_layout():
    # The independent layout definition is reference.py::pack_weight's
    # [N/16, K/32, 2, 16, 16] permutation. Check every 16-byte load endpoint.
    hidden, rows = 5120, 1792
    checked = 0
    for task in range(rows // 16):
        for st in range(hidden // 128):
            for lane in range(32):
                for j in range(4):
                    start = task * 81920 + st * 2048 + (lane // 16) * 256 + (lane % 16) * 16 + j * 512
                    n = task * 16 + lane % 16
                    for byte in (0, 15):
                        k = st * 128 + j * 32 + (lane // 16) * 16 + byte
                        ref = (((n // 16) * (hidden // 32) + k // 32) * 2 + k % 32 // 16) * 256 + n % 16 * 16 + k % 16
                        if start + byte != ref or not 0 <= ref < rows * hidden:
                            raise ValueError("ASM weight load disagrees with packed logical W[n,k]")
                        checked += 1
    words = [tid + i * 256 for tid in range(256) for i in range(5)]
    if sorted(words) != list(range(1280)):
        raise ValueError("X copy must cover each packed word exactly once")
    steps = [wave + 8 * i for wave in range(8) for i in range(5)]
    if sorted(steps) != list(range(40)):
        raise ValueError("eight waves do not partition K128 steps")
    input_bytes = [st * 128 + half * 16 + j * 32 + byte
                   for st in steps for half in range(2) for j in range(4) for byte in range(16)]
    if sorted(input_bytes) != list(range(hidden)):
        raise ValueError("LDS X fragments omit or duplicate a K byte")
    for task in range(112):
        for st in steps:
            for j in range(4):
                if (task // 2) * 160 + st * 4 + j != ((task * 16) // 32) * (hidden // 32) + st * 4 + j:
                    raise ValueError("weight scale layout mismatch")
    red = [wave * 64 + half * 32 + row * 4
           for wave in range(8) for half in range(2) for row in range(8)]
    if sorted(red) != list(range(0, 512, 4)):
        raise ValueError("reduction stores must cover red[8][16] exactly")
    # Confirm actual copied plan's task ownership, including modulo wraparound.
    from mono1250.kernels.reference_plan import C1ReferencePlan
    plan = C1ReferencePlan(feeds_index=True)
    owners = {}
    for name, count in (("k1.slice", 160), ("k1.norm", 1), ("k1.wqkv_a", 112)):
        pairs = [(bid, task) for bid in range(256) for task in plan.stages[name].tasks(bid)]
        if sorted(task for _, task in pairs) != list(range(count)):
            raise ValueError("plan must assign every task exactly once")
        owners[name] = {"tasks": count, "ctas": [bid for bid, _ in pairs]}
    return {"status": "PASS", "weight_load_endpoints_checked": checked,
            "x_words": 1280, "k128_steps": 40, "reduction_bytes": 512,
            "plan": owners, "scope": "integer address formulas and task placement only",
            "wmma_numerical_validation": "NOT_RUN"}
