"""Source-derived FlyDSL computation fragments; the outer scheduler is ASM.

The exact reviewed step.py source is pinned before slicing. This preserves the
large context/callback expressions without maintaining a second algorithm copy.
All layer/front/selection loops and their outer predicates live in step.s.
"""
import hashlib
import importlib
from pathlib import Path
import sys
import textwrap
import types

from contract import KERNELS, REPO

STEP_SHA256 = "1ef733d1ed0664a3a0618e53e05d9779b44825686bcf6225373d0a64dbd9d7d1"
PACKAGE = "atom.models.deepseek_v41.mono.gfx1250.kernels"

# Inclusive source line spans in the pinned step.py. A span may contain a
# stage's internal work/conditionals, but never the outer layer/hf/pi loops.
SPANS = {
    "target_state": [(229, 234)],
    "target_front": [(237, 237)],
    "draft_meta": [(257, 259)],
    "draft_state": [(260, 262)],
    "draft_front": [(265, 265)],
    "layer_stamp_start": [(300, 303)],
    "engq": [(306, 306)],
    "attention_A": [(307, 309)],
    "engkv": [(313, 314)],
    "kv_C": [(315, 316)],
    "index_prepare": [(320, 328)],
    "index_quant": [(332, 344)],
    "index_score": [(348, 359)],
    "index_select": [(363, 365)],
    "attention_D": [(367, 368)],
    "attention_E": [(370, 371)],
    "attention_F": [(373, 374)],
    "tp1": [(375, 377)],
    "front_wait": [(385, 385)],
    "front": [(387, 422)],
    "shared_early": [(423, 434)],
    "moe": [(438, 445)],
    "moe_combine_tp2": [(448, 450)],
    "tap": [(454, 456)],
    "layer_stamp_end": [(457, 457)],
    "target_tail": [(459, 465)],
    "draft_tail": [(467, 472)],
}

LAYER_HANDOFFS = {
    "handoff_A": "ATTN_A", "handoff_KV_C": "KV_C", "handoff_quant": "INDEX_QUANT",
    "handoff_score": "SCORE", "handoff_D": "ATTN_D", "handoff_E": "ATTN_E",
    "handoff_front": "FRONT", "handoff_moe_done": "MOE_DONE", "handoff_layer_end": "LAYER_END",
}
TAIL_HANDOFFS = {"handoff_target_state": "TARGET_STATE", "handoff_target_front": "TARGET_FRONT",
                 "handoff_draft_state": "DRAFT_STATE", "handoff_draft_front": "DRAFT_FRONT"}
STAGES = tuple(SPANS) + tuple(LAYER_HANDOFFS) + tuple(TAIL_HANDOFFS) + (
    "epoch_begin", "epoch_end", "handoff_select")

TARGET_ONLY = {
    "target_state", "target_front", "engq", "engkv", "index_prepare", "index_quant",
    "index_score", "index_select", "tap", "target_tail", "handoff_target_state",
    "handoff_target_front", "handoff_quant", "handoff_score", "handoff_select", "epoch_begin", "epoch_end",
}
DRAFT_ONLY = {"draft_meta", "draft_state", "draft_front", "draft_tail",
              "handoff_draft_state", "handoff_draft_front"}
SEGMENTS = {name: "target" if name in TARGET_ONLY else "draft" if name in DRAFT_ONLY else "both"
            for name in STAGES}


def reviewed_source():
    text = (KERNELS / "step.py").read_text()
    if hashlib.sha256(text.encode()).hexdigest() != STEP_SHA256:
        raise RuntimeError("step.py changed: re-review the source partitions before building mono_test31")
    return text


def piece(spans):
    lines = reviewed_source().splitlines()
    return "\n".join(textwrap.dedent("\n".join(lines[lo - 1:hi])) for lo, hi in spans)


def body_source(name):
    if name in SPANS:
        body = piece(SPANS[name])
        if name in ("index_score", "index_select"):
            setup = piece([(348, 358)])
            body = setup + "\n" + piece([(359, 359)]) if name == "index_score" else setup + "\n" + body
        if name == "moe_combine_tp2":
            body = "par = Ly % 2\n" + body
        return body
    if name in LAYER_HANDOFFS:
        return f"handoff(lc + i64(LY.{LAYER_HANDOFFS[name]}), t, True)"
    if name in TAIL_HANDOFFS:
        return f"handoff(TCNT + i64(LY.{TAIL_HANDOFFS[name]}), t, False)"
    if name == "handoff_select":
        return "handoff(lc + i64(LY.SELECT0) + i64(pi) * 4, t, True)"
    if name == "epoch_begin":
        return ("recv, tep = tp_epoch_begin([recv0, recv1, recv2, recv3], fp, rank)\n"
                "if t == 0:\n    hx.lstore(fx.Int32(SCHED_LDS), tep)\ngpu.barrier()")
    if name == "epoch_end":
        return "tp_epoch_end(fp, tep)"
    raise ValueError(name)


def generated_source(name):
    # All source stages see the same typed table context. Input IDs inside
    # imported helpers are rebound to explicit parameters in lowered MLIR.
    prefix = '''
record = fx.Int64(fx.rocdl.readfirstlane(T.i64, record.ir_value()))
Ly = fx.Int32(fx.rocdl.readfirstlane(T.i32, layer.ir_value()))
hf = fx.Int32(fx.rocdl.readfirstlane(T.i32, front_pass.ir_value()))
pi = fx.Int32(fx.rocdl.readfirstlane(T.i32, select_pass.ir_value()))
tep = fx.Int32(fx.rocdl.readfirstlane(T.i32, epoch.ir_value()))
recv0, recv1, recv2, recv3 = [hx.sload64(record + i64(k * 8)) for k in range(4)]
cnt, st = hx.sload64(record + i64(32)), hx.sload64(record + i64(40))
scale = hx.gload(record + i64(48), fx.Float32)
fp, tp = hx.sload64(record + i64(56)), hx.sload64(record + i64(64))
recv = [r + i64(tep & 1) * RECV_HALF for r in (recv0, recv1, recv2, recv3)]
hx.TOFLAG[0] = fptr(fp, "cyc")
seg_kind = 4 if DRS else 1
kind = seg_kind
FIRST_LY = -1
TRx = TRD if DRS else TR
Lx = smem_layout(TRx)
DSUF = "_d" if DRS else ""
RNE, RTOPK = (DRAFT_NE, DRAFT_TOPK) if DRS else (FS.NE, FS.TOPK)
stx = hx.stx_dev
TCNT = cnt + i64((NL + NDR) * LCB)
t = hx.opaque_v(fx.thread_idx.x)
b = hx.opaque_s(fx.block_idx.x)
sm = hx.lds_base()
lc = cnt + i64(Ly) * LCB
'''
    if name not in STAGES:
        raise ValueError(name)
    # Entry/epoch/tail/handoff adapters must not access a layer row: zero-layer
    # builds still execute these, and the draft entry row is not a body row.
    layer_stages = set(SPANS) - {
        "target_state", "target_front", "draft_meta", "draft_state",
        "draft_front", "target_tail", "draft_tail",
    }
    context = piece([(269, 298)]) if name in layer_stages else ""
    body = textwrap.dedent(prefix).strip() + "\n" + context + "\n" + body_source(name)
    body += "\nhx.TOFLAG[0] = None"
    return ("def adapted(record: Int64, explicit_bid: Int32, explicit_tid: Int32, layer: Int32, "
            "front_pass: Int32, select_pass: Int32, epoch: Int32):\n" + textwrap.indent(body, "    ") + "\n")


def import_step():
    # Build-process-only namespace loading avoids importing ATOM's serving
    # runtime/AITER just to compile these self-contained kernel sources.
    for depth in range(1, len(PACKAGE.split('.')) + 1):
        name = '.'.join(PACKAGE.split('.')[:depth])
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = [str(REPO.joinpath(*name.split('.')))]
            sys.modules[name] = module
    return importlib.import_module(PACKAGE + '.step')


def create_launcher(name, cfg, draft, output):
    import flydsl.compiler as flyc
    import flydsl.expr as fx
    from flydsl.compiler.ast_rewriter import ASTRewriter
    from flydsl.expr.typing import Int32, Int64, T
    step = import_step()
    namespace = dict(vars(step), Int32=Int32, Int64=Int64, T=T,
                     TR=cfg['target_rows'], TRD=cfg['draft_rows'], NL=cfg['target_layers'],
                     NDR=cfg['draft_layers'], rank=cfg['rank'], part=cfg['part'],
                     DRS=draft, SCHED_LDS=cfg['scheduler_lds_offset'])
    path = Path(output) / 'adapted.py'
    path.write_text(generated_source(name))
    # Explicit typed arguments and a real file support AST source inspection.
    exec(compile(path.read_text(), str(path), 'exec', dont_inherit=True), namespace)
    symbol = f"step31_{'draft' if draft else 'target'}_{name}"
    stage = flyc.kernel(name=symbol, known_block_size=[256, 1, 1])(
        ASTRewriter.transform(namespace['adapted']))

    @flyc.jit
    def launcher(record: Int64, bid: Int32, tid: Int32, layer: Int32, hf: Int32,
                 pi: Int32, epoch: Int32, stream: fx.Stream):
        stage(record, bid, tid, layer, hf, pi, epoch).launch(
            grid=(256,), block=(256,), smem=cfg['dynamic_lds_bytes'], cluster=(16, 1, 1), stream=stream)
    return launcher, symbol, step.hx
