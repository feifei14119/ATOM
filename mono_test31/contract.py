"""mono_test31 explicit kernarg ABI and source-derived resource/layout contract."""
from __future__ import annotations

import ast
import ctypes
import hashlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
KERNELS = REPO / "atom/models/deepseek_v41/mono/gfx1250/kernels"
SYMBOL = "mono_step31"


class StepArgs(ctypes.Structure):
    """ASM entry 的显式 kernarg ABI，与 step.body 的九个参数顺序一致。

    没有照搬某个 MLA kernel 的 120-byte / 16-byte-slot ABI。
    ASM descriptor、metadata 和本结构共同定义布局。
    不声称某一版 FlyDSL 自动生成的 hidden-args/preload ABI 也只有 72 字节。
    """

    _fields_ = [
        ("recv0", ctypes.c_uint64),  # 0x00: 当前 rank 可访问的 rank0 receive VA
        ("recv1", ctypes.c_uint64),  # 0x08
        ("recv2", ctypes.c_uint64),  # 0x10
        ("recv3", ctypes.c_uint64),  # 0x18
        ("cnt", ctypes.c_uint64),    # 0x20: 本 step 的 handoff counters
        ("st", ctypes.c_uint64),     # 0x28: 时间戳缓冲区
        ("scale", ctypes.c_float),   # 0x30: attention softmax scale
        ("_padding", ctypes.c_uint32),  # 0x34: 让 fp 保持 8-byte 对齐
        ("fp", ctypes.c_uint64),     # 0x38: FPTRS + ATAB + LKEYS[45] 表
        ("tp", ctypes.c_uint64),     # 0x40: tail.TPTRS 表
    ]


assert ctypes.sizeof(StepArgs) == 72
assert StepArgs.scale.offset == 48
assert StepArgs.fp.offset == 56 and StepArgs.tp.offset == 64


def _tree(name):
    return ast.parse((KERNELS / name).read_text())


def _constant_environment(name, **initial):
    """只求值模块顶层的常量赋值；不执行 import、装饰器或 GPU 函数。

    输入是当前仓库中已审阅的源码。作用是按原始公式求 LDS 等常量，
    避免为了展示 host launch 就初始化 FlyDSL / torch / 分布式环境。
    """
    env = dict(initial)
    for node in _tree(name).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = eval(
                compile(ast.Expression(node.value), str(KERNELS / name), "eval"),
                {"__builtins__": {}}, env,
            )
        except (NameError, AttributeError, TypeError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                env[target.id] = value
            elif isinstance(target, (ast.Tuple, ast.List)):
                names = [t.id for t in target.elts if isinstance(t, ast.Name)]
                if len(names) == len(target.elts):
                    env.update(zip(names, value))
    return env


def _pure_function(name, function, env):
    """仅提取两个已审阅的纯数值函数：attention.smem_layout、head.geom。"""
    node = next(n for n in _tree(name).body
                if isinstance(n, ast.FunctionDef) and n.name == function)
    assert not node.decorator_list
    scope = dict(env, __builtins__={"dict": dict})
    exec(compile(ast.Module(body=[node], type_ignores=[]),
                 str(KERNELS / name), "exec"), scope)
    return scope[function]


def source_layout(target_rows=6, rank=0, part="all", target_layers=40, draft_layers=3):
    """生成一个明确的构建配置；target 每请求 6 行，draft 每请求 5 行。"""
    if target_rows not in range(6, 49, 6):
        raise ValueError("只接受 6,12,...,48 个 target rows")
    if rank not in range(4) or part not in ("all", "target", "draft"):
        raise ValueError("需要 rank=0..3，part=all/target/draft")
    if not 0 <= target_layers <= 40 or not 0 <= draft_layers <= 3:
        raise ValueError("需要 NL=0..40、ndr=0..3")
    dim = _constant_environment("dims.py")
    d = SimpleNamespace(**dim)
    layout = _constant_environment("layout.py")
    # 这里抽取的都是 step.py 的原始 list/string 常量，不复制表索引。
    st = _constant_environment("step.py", D=d, LY=SimpleNamespace(**layout))
    tail = _constant_environment("tail.py", D=d)
    front = _constant_environment("front.py", D=d)
    moe = _constant_environment(
        "moe.py", D=d, MP=SimpleNamespace(WIDE_NCH=3)
    )
    attn = _constant_environment("attention.py", D=d)
    head = _constant_environment("head.py", D=d)
    smem = _pure_function("attention.py", "smem_layout", attn)
    geom = _pure_function("head.py", "geom", head)
    draft_rows = target_rows // 6 * 5
    dynamic_lds = max(
        smem(target_rows)["LDS"], smem(draft_rows)["LDS"],
        2 * geom(2, 4)[3],
        layout["FRONT_LDS"] + max(front["FRONT_LDS"], moe["MOE_LDS"]),
        layout["RKEEP"] + front["RK_BYTES"],
    )
    sources = tuple(p.name for p in sorted(KERNELS.glob("*.py")))
    return {
        "symbol": SYMBOL, "target_rows": target_rows, "draft_rows": draft_rows,
        "rank": rank, "part": part, "part_number": ("all", "target", "draft").index(part),
        "target_layers": target_layers, "draft_layers": draft_layers,
        "grid": [dim["CTAS"], 1, 1], "block": [dim["THREADS"], 1, 1],
        "cluster": [dim["CL"], 1, 1], "wave_size": 32,
        "original_dynamic_lds_bytes": dynamic_lds,
        "scheduler_lds_offset": (dynamic_lds + 255) // 256 * 256,
        "dynamic_lds_bytes": (dynamic_lds + 255) // 256 * 256 + 256,
        "front_ctas": front["FRONT_CTAS"],
        "recv_half_bytes": st["RECV_HALF"],
        "counter_bytes_min": (target_layers + draft_layers) * layout["LAYER_BYTES"] + 512,
        "fp_names": st["FPTRS"], "attention_names": st["ATAB"],
        "layer_names": st["LKEYS"], "tail_names": tail["TPTRS"],
        "layout": {k: v for k, v in layout.items() if isinstance(v, int)},
        "sources_sha256": {
            name: hashlib.sha256((KERNELS / name).read_bytes()).hexdigest()
            for name in sources
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(source_layout(), indent=2, ensure_ascii=False))
