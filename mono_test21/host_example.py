"""参考 aiter.ops.asm.asm_utils 的 host 主流程。

这里只展示已准备数据到 module-load / cluster-launch 的接缝，
不重新实现模型加载、权重打包、KV 分配或分布式初始化。
直接运行本文件只打印 kernarg 布局，不初始化 GPU。
"""
from __future__ import annotations

import ctypes
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contract import StepArgs


@dataclass
class PreparedStep:
    """host 已准备好的一个 rank 的输入，与 SingleStepRunner._launch_args 对应。

    device 是进程内 HIP device ordinal；rank 是 TP group 内 rank，两者不可等同。
    recv 是映射到本进程/本 GPU 地址空间的四个 peer VA。
    keepalive 应包含 StepTables、scratch、cache 和 peer allocation owner 等：
    裸整数地址本身不会让 PyTorch allocator 延长 tensor 的生命周期。
    """
    device: int
    rank: int
    rows: int
    recv: tuple[int, int, int, int]
    cnt: Any             # torch.uint8/int32 contiguous GPU tensor
    st: Any              # 时间戳 GPU tensor
    fp: Any              # StepTables.fptab，int64 device table
    tp: Any              # StepTables.tp，int64 device table
    scale: float
    keepalive: tuple[Any, ...]


def pack_args(step: PreparedStep) -> StepArgs:
    """仅拷贝地址与一个 float；没有把各层实际权重拷进 kernarg。"""
    if len(step.recv) != 4:
        raise ValueError("原始 step 是 TP4，需要四个可访问的 receive 地址")
    return StepArgs(
        recv0=step.recv[0], recv1=step.recv[1],
        recv2=step.recv[2], recv3=step.recv[3],
        cnt=step.cnt.data_ptr(), st=step.st.data_ptr(),
        scale=step.scale, _padding=0,
        fp=step.fp.data_ptr(), tp=step.tp.data_ptr(),
    )


def load_ready_kernel(manifest_path: str | Path, step: PreparedStep):
    """准备阶段加载一次，之后复用；不要把首次 hipModuleLoad 放进 graph capture。

    当前示例只有语法检查 .co，明确拒绝加载/执行。
    将来真正集成 stage 后，manifest 应由资源/ABI/链接验证流程生成，
    而不是手工把 compute_stages_implemented 改成 true。
    """
    manifest = Path(manifest_path)
    cfg = json.loads(manifest.read_text())
    if not cfg.get("compute_stages_implemented"):
        raise NotImplementedError(
            "这个 .co 只包含 ASM 调度和 trap 占位，不能作为网络执行。"
        )
    if cfg["rank"] != step.rank or cfg["target_rows"] != step.rows:
        raise ValueError("每个 rank/row count 必须选正确构建；不能混用权重分片")
    # 这些是真实的 AITER API，不是手写的同名伪 API。
    from aiter.ops.asm.asm_utils import (
        device_guard, get_function, get_gfx_from_device,
    )
    with device_guard(step.device):
        if get_gfx_from_device(step.device) != "gfx1250":
            raise RuntimeError("需要 gfx1250")
        # 内部 hipModuleLoad -> hipModuleGetFunction；按 device/path/symbol 缓存。
        function = get_function(cfg["code_object"], cfg["symbol"], device=step.device)
    return function, cfg


def launch_prepared(function, cfg, step: PreparedStep):
    """核心 launch：此函数不做数据准备/计数器清零，也不在内部 synchronize。

    前置步骤都已在当前 stream 排好；特别是 split draft 不可在这里清 cnt。
    两种调度：
      all:    prepare_step -> launch(all)
      split:  prepare_step -> launch(target) -> event -> launch(draft)
    原 runner 当前使用 split；step.build 本身也支持 all。
    """
    if not cfg.get("compute_stages_implemented"):
        raise NotImplementedError("拒绝执行含占位阶段的 .co")
    if (cfg["rank"], cfg["target_rows"]) != (step.rank, step.rows):
        raise ValueError("rank/rows 与 code object 不匹配")
    from aiter.ops.asm.asm_utils import (
        current_raw_stream, device_guard, launch_co_cluster,
    )
    with device_guard(step.device):
        args = pack_args(step)
        stream = current_raw_stream(step.device)
        # launch_co_cluster 内部使用 ctypes 组装 HIP_LAUNCH_CONFIG，
        # 设置 hipLaunchAttributeClusterDimension，
        # 经 hipDrvLaunchKernelEx 传入 BUFFER_POINTER / BUFFER_SIZE 参数块。
        #
        # 256 workgroups × 256 threads，16 workgroups 一个硬件 cluster。
        # grid 是 CTA 数，不是线程数；不能把 (256,1,1) 换成 (65536,1,1)。
        # .co 固定 LDS=0，因此这里传整个动态 LDS，而不是再重复加固定 LDS。
        launch_co_cluster(
            function,
            grid=tuple(cfg["grid"]),
            block=tuple(cfg["block"]),
            kernarg=args,
            cluster_dim=tuple(cfg["cluster"]),
            shared_mem=cfg["dynamic_lds_bytes"],
            stream=stream,
        )
        # HIP 调用期间 args 保持有效；异步 GPU 使用的 tensor/peer owners
        # 则要保留到执行完成。生产集成可复用 runner 的长期驻留状态。
        # 不要在每一层之间同步：40+3 层循环由 ASM kernel 内部完成。


def outline_existing_atom_integration(runner, rows: int) -> PreparedStep:
    """给已有 SingleStepRunner 的接入示意：只打包已有资源。

    原流程中先完成：
      1. TP4 / peer mappings；StepTables 绑定各 rank 的权重/cache。
      2. Engram host staging 与 side-stream join，避免常驻 grid 相互等待。
      3. StepInputs 的本步更新：tids、positions、index/compressor plans、
         sampling parameters、dgeom、cache pointers；cnt.zero_() 一次。
      4. 所需 H2D 和 memset 与当前 stream 建立顺序。

    上面四步沿用 runner 的 prepare/_host_inputs/_device_inputs 语义；
    本函数不代替这些步骤，也不调用私有方法拼凑一个不完整网络。
    """
    return PreparedStep(
        device=runner.device.index, rank=runner.rank, rows=rows,
        recv=tuple(int(p) for p in runner.recv),
        cnt=runner.scratch["cnt"], st=runner.scratch["st"],
        fp=runner.tables.fptab, tp=runner.tables.tp,
        scale=float(runner.base.layers[0].attn.softmax_scale),
        keepalive=(runner,),
    )


# 未来 stage 接好后的主要调用方式（示意）：
#
#   prepared = outline_existing_atom_integration(runner, rows=6)
#   # 在所有 TP ranks 上各自 load 自己的 rank 构建。
#   kernel, cfg = load_ready_kernel(".../manifest.json", prepared)
#   # ...原 host 本步准备（包含 cnt 清零，不能清 qlog/qids/tpep 持久状态）...
#   launch_prepared(kernel, cfg, prepared)
#   # ...同 stream 后继消费者，或 event 后读取 outtok/verdict/mids...
#
# split 时先加载 target、draft 两个句柄，host 一次本步准备后依序 launch。
# 两次 launch 之间不重置 cnt，也不重新清 peer receive buffers；
# kernel 的 tp_epoch_begin/end 负责各自 receive parity。
#
# 跨 GPU：每个 TP rank 都要 enqueue，不可先等待 rank0 完成再启动 rank1；
# TP kernel 会等待 peers。沿用原 ATOM 分布式/graph 的组织方式。


if __name__ == "__main__":
    print(f"StepArgs: {ctypes.sizeof(StepArgs)} bytes（不启动 GPU）")
    for name, ty in StepArgs._fields_:
        print(f"  {name:10s} offset={getattr(StepArgs, name).offset:2d}"
              f" size={ctypes.sizeof(ty)}")
