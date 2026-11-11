"""Opt-in TP4 gfx1250 comparison against the original FlyDSL Mono kernel.

Run with torchrun. A factory supplies two independent prepared model states;
see fixture_contract.md. Import/CPU discovery never initializes torch/HIP.
"""
from datetime import timedelta
import importlib
import json
import os
from pathlib import Path
import unittest


ENABLED = os.environ.get("MONO31_GPU_TEST") == "1"


@unittest.skipUnless(ENABLED, "Set MONO31_GPU_TEST=1 and provide TP4 gfx1250 fixtures")
class MonoGpuComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import torch.distributed as dist
        cls.torch, cls.dist = torch, dist
        if not torch.cuda.is_available():
            raise RuntimeError("GPU tests require ROCm torch and four gfx1250 GPUs")
        if int(os.environ.get("WORLD_SIZE", "0")) != 4:
            raise RuntimeError("Run with torchrun --nproc_per_node=4")
        cls.rank, cls.device = int(os.environ["RANK"]), int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(cls.device)
        # CPU control collectives avoid concurrent communication kernels
        # competing with the persistent ASM kernel for GPU residency.
        if not dist.is_initialized():
            dist.init_process_group("gloo", timeout=timedelta(seconds=300))
        if dist.get_world_size() != 4 or dist.get_backend() != "gloo":
            raise RuntimeError("Comparison control group must be TP4 Gloo")
        spec = os.environ.get("MONO31_FIXTURE", "")
        if ":" not in spec:
            raise RuntimeError("MONO31_FIXTURE must be module:factory (see fixture_contract.md)")
        module, factory = spec.split(":", 1)
        cls.factory = staticmethod(getattr(importlib.import_module(module), factory))

    def collective(self, callback):
        """Make local assertion/preparation failures visible to every TP rank."""
        result, error = None, None
        try:
            result = callback()
        except Exception as exc:
            error = f"rank {self.rank}: {type(exc).__name__}: {exc}"
        errors = [None] * 4
        self.dist.all_gather_object(errors, error)
        self.assertFalse(any(errors), "\n".join(e for e in errors if e))
        return result

    def compare(self, mode):
        from aiter.ops.asm.asm_utils import current_raw_stream, get_gfx_from_device
        from host import launch_prepared, load_kernel
        import flydsl.expr as fx
        from atom.models.deepseek_v41.mono.gfx1250.kernels import step as original

        def setup():
            self.assertEqual(get_gfx_from_device(self.device), "gfx1250")
            root = Path(os.environ["MONO31_MANIFEST_ROOT"]) / f"rank{self.rank}"
            parts = ("all",) if mode == "all" else ("target", "draft")
            manifests = [root / part / "manifest.json" for part in parts]
            configs = [json.loads(path.read_text()) for path in manifests]
            cfg = configs[0]
            for other in configs:
                for key in ("target_rows", "draft_rows", "target_layers", "draft_layers", "rank", "sources_sha256"):
                    self.assertEqual(cfg[key], other[key])
            fixture = self.factory(config=cfg, mode=mode, rank=self.rank, device=self.device)
            for name in ("cnt", "st", "fp", "tp"):
                self.assertNotEqual(getattr(fixture.baseline, name).data_ptr(), getattr(fixture.asm, name).data_ptr())
            self.assertFalse(set(fixture.baseline.recv) & set(fixture.asm.recv))
            ranges = {path: fixture.mutable_ranges(path) for path in ("baseline", "asm")}
            self.assertTrue(ranges["baseline"] and ranges["asm"])
            for a, na in ranges["baseline"].values():
                for b, nb in ranges["asm"].values():
                    self.assertTrue(a + na <= b or b + nb <= a, "Baseline/ASM mutable allocations overlap")
            required = {"entry", "attention", "front", "moe", "index", "compressor", "engram",
                        "tap", "tail", "epoch", "ratio1", "candidate_producer", "reindex", "shared_early"}
            self.assertTrue(required <= set(fixture.covered_features), "Fixture must exercise the full Mono path")
            handles = [load_kernel(path, fixture.asm) for path in manifests]
            baselines = [original.build(cfg["target_rows"], self.rank, NL=cfg["target_layers"],
                                        ndr=cfg["draft_layers"], trd=cfg["draft_rows"], part=part,
                                        sources=json.dumps(cfg["sources_sha256"], sort_keys=True))[0]
                         for part in parts]
            return fixture, handles, baselines, cfg

        fixture, handles, baselines, cfg = self.collective(setup)
        self.addCleanup(lambda: self.collective(fixture.close))
        # Two decode steps verify that epochs and draft state persist; split
        # advances by two epochs per step and all advances by one.
        for iteration in range(2):
            for path in ("baseline", "asm"):
                self.collective(lambda: fixture.prepare_step(path, iteration))
                self.dist.barrier()
                prepared = getattr(fixture, path)
                stream = current_raw_stream(self.device)
                if path == "baseline":
                    for launcher in baselines:
                        launcher(*prepared.recv, prepared.cnt.data_ptr(), prepared.st.data_ptr(),
                                 prepared.scale, prepared.fp.data_ptr(), prepared.tp.data_ptr(), stream=fx.Stream(stream))
                else:
                    for function, config in handles:
                        launch_prepared(function, config, prepared, stream=stream)
                # Every rank has already enqueued its peer-dependent kernel.
                self.torch.cuda.synchronize(self.device)
                self.dist.barrier()

            def assert_observables():
                reference, actual = fixture.observables("baseline"), fixture.observables("asm")
                self.assertEqual(set(reference), set(actual))
                groups = {name.split("/", 1)[0] for name in reference}
                self.assertTrue({"attention", "kv", "index", "compressor", "moe", "tail", "epoch"} <= groups)
                self.assertTrue(reference)
                for name in reference:
                    ref, value = reference[name], actual[name]
                    self.assertEqual(ref.shape, value.shape, name)
                    self.assertEqual(ref.dtype, value.dtype, name)
                    rtol, atol = (0, 0)
                    if ref.is_floating_point():
                        self.assertTrue(self.torch.isfinite(ref).all().item(), name)
                        self.assertTrue(self.torch.isfinite(value).all().item(), name)
                        rtol, atol = ((1e-2, 1e-2) if ref.dtype in (self.torch.float16, self.torch.bfloat16)
                                      else (1e-4, 1e-4))
                    self.torch.testing.assert_close(value, ref, rtol=rtol, atol=atol, msg=name)
                epochs = [name for name in reference if name.startswith("epoch/")]
                self.assertTrue(epochs)
                increment = len(handles) * (iteration + 1)
                for name in epochs:
                    expected = fixture.initial_epochs[name] + increment
                    self.assertTrue((actual[name] == expected).all().item(), f"Persistent epoch: {name}")
                self.assertEqual(fixture.timeout_count("baseline"), 0)
                self.assertEqual(fixture.timeout_count("asm"), 0)

            self.collective(assert_observables)

    def test_all(self):
        if os.environ.get("MONO31_TEST_MODE", "all") not in ("all", "both"):
            self.skipTest("MONO31_TEST_MODE does not select all")
        self.compare("all")

    def test_split(self):
        if os.environ.get("MONO31_TEST_MODE", "all") not in ("split", "both"):
            self.skipTest("MONO31_TEST_MODE does not select split")
        self.compare("split")


if __name__ == "__main__":
    unittest.main()
