import ast
import ctypes
from pathlib import Path
import unittest
from unittest.mock import patch

from build import Block, metadata, parse, variants
from contract import ROOT, StepArgs, source_layout
from fragments import STAGES, generated_source, reviewed_source


class ContractTests(unittest.TestCase):
    def test_nine_argument_abi(self):
        self.assertEqual(ctypes.sizeof(StepArgs), 72)
        self.assertEqual([getattr(StepArgs, n).offset for n, _ in StepArgs._fields_],
                         [0, 8, 16, 24, 32, 40, 48, 52, 56, 64])
        args = StepArgs(1, 2, 3, 4, 5, 6, 0.5, 0, 7, 8)
        self.assertEqual(ctypes.c_uint64.from_buffer_copy(bytes(args)[56:64]).value, 7)

    def test_layout_covers_both_shapes_and_appended_epoch_slot(self):
        for rows in range(6, 49, 6):
            cfg = source_layout(rows)
            self.assertEqual(cfg["draft_rows"], rows // 6 * 5)
            self.assertEqual(cfg["cluster"], [16, 1, 1])
            self.assertEqual(cfg["grid"], [256, 1, 1])
            self.assertEqual(cfg["block"], [256, 1, 1])
            self.assertEqual(cfg["scheduler_lds_offset"] % 256, 0)
            self.assertGreaterEqual(cfg["scheduler_lds_offset"], cfg["original_dynamic_lds_bytes"])
            self.assertEqual(cfg["dynamic_lds_bytes"], cfg["scheduler_lds_offset"] + 256)
        self.assertEqual(source_layout(target_layers=2, draft_layers=1)["counter_bytes_min"], 3 * 256 + 512)

    def test_invalid_build_config_rejected(self):
        for kwargs in ({"rank": 4}, {"target_rows": 5}, {"part": "other"},
                       {"target_layers": 41}, {"draft_layers": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                source_layout(**kwargs)

    def test_source_drift_fails_before_slicing(self):
        original = reviewed_source()
        with patch.object(Path, "read_text", return_value=original + "\n# changed\n"):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                reviewed_source()

    def test_all_adapters_have_explicit_signature(self):
        for name in STAGES:
            with self.subTest(stage=name):
                fn = ast.parse(generated_source(name)).body[0]
                self.assertEqual([a.arg for a in fn.args.args],
                                 ["record", "explicit_bid", "explicit_tid", "layer", "front_pass", "select_pass", "epoch"])
                self.assertEqual([a.annotation.id for a in fn.args.args], ["Int64"] + ["Int32"] * 6)
        for name in ("epoch_begin", "epoch_end", "target_state", "target_front", "draft_state", "draft_front", "target_tail", "draft_tail"):
            self.assertNotIn('ltab(fp, Ly, "kring")', generated_source(name))

    def test_parser_rejects_incomplete_or_unreviewed_blocks(self):
        text = (ROOT / "step.s").read_text()
        _, blocks = parse(text)
        self.assertEqual({b.name for b in blocks}, set(STAGES))
        for replacement in (text.replace(".flydsl.end", "", 1),
                            text.replace("leaf-ccc-inline", "unchecked", 1),
                            text.replace(".flydsl.segment target", ".flydsl.segment draft", 1),
                            text.replace("fragments.py:epoch_begin", "other.py:epoch_begin", 1),
                            text.replace(".flydsl.begin epoch_begin", ".flydsl.begin missing", 1),
                            text + "\n.flydsl.out f32 c = v0\n"):
            with self.assertRaises(RuntimeError):
                parse(replacement)

    def test_epoch_variants_remain_in_empty_split_draft(self):
        cfg = source_layout(part="draft", target_layers=0, draft_layers=0)
        self.assertEqual(variants(Block(0, 1, "epoch_begin", "target", "leaf-ccc-inline"), cfg), (False,))
        self.assertEqual(variants(Block(0, 1, "epoch_end", "target", "leaf-ccc-inline"), cfg), (False,))
        self.assertEqual(variants(Block(0, 1, "attention_A", "both", "leaf-ccc-inline"), cfg), ())

    def test_metadata_has_no_hidden_args_or_fixed_lds(self):
        cfg = source_layout()
        resource = dict(vgpr=64, sgpr=58, private=32)
        text = metadata(cfg, resource)
        self.assertIn(".group_segment_fixed_size: 0", text)
        self.assertIn(".private_segment_fixed_size: 32", text)
        self.assertIn(".kernarg_segment_size: 72", text)
        self.assertNotIn("hidden", text)
        self.assertEqual(text.count(".value_kind: by_value"), 9)


if __name__ == "__main__":
    unittest.main()
