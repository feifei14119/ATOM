# 早期独立验证的源代码

`separate_probe/` 保存早期 `live_state_kernel` 验证的源代码，供核对历史实验使用。这些文件不参与当前 Makefile 的构建或运行，原来的 `make run-live` 入口已移除。

当前示例只需在上级目录执行 `make run`：主机加载 `mono_kernel.co`，启动 `mono_kernel.cpp` 中的 `mono_kernel`，由同一个 kernel 验证跨 ASM 调用的活跃状态及完整三 CTA 流水线。

旧 `build/live_state.*` 和 `build/callee_saved_probe.*` 如果仍存在，属于历史产物，不是当前 `make run` 的输入；当前检查报告是 `build/link_check.json`，运行日志是 `build/main.log`。
