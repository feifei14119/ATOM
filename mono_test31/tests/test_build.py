"""Optional complete offline compile/link check. No GPU launch."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from contract import ROOT
from elf import audit_binary


@unittest.skipUnless(os.environ.get("MONO31_BUILD_TEST") == "1", "Offline compilation is opt-in")
class OfflineBuildTests(unittest.TestCase):
    def test_full_kernel_has_one_descriptor_and_all_reachable_stages(self):
        with tempfile.TemporaryDirectory(prefix="mono31-build-") as directory:
            subprocess.run([sys.executable, str(ROOT / "build.py"), "--build-dir", directory], check=True)
            path = Path(directory)
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "BUILT_NOT_TESTED")
            report = json.loads((path / "build_report.json").read_text())
            self.assertIn("target/index_select", report["exports"])
            self.assertIn("draft/moe", report["exports"])
            self.assertIn("target/target_tail", report["exports"])
            self.assertIn("draft/draft_tail", report["exports"])
            audit_binary((path / "kernel.co").read_bytes(), manifest, manifest["resources"])
            source = (path / "step.generated.s").read_text()
            self.assertNotRegex(source, r"(?m)^\s*\.flydsl\.")
            self.assertNotIn("s_trap", source)
            self.assertNotRegex(source, r"\bs_(?:swappc_b64|swap_pc_i64)\b")
