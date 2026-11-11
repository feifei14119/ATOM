import unittest

from contract import source_layout
from asm_trace import trace


class SchedulerTests(unittest.TestCase):
    def test_complete_layer_order_and_two_fronts(self):
        cfg = source_layout(target_layers=1, draft_layers=0)
        names = [e[0] for e in trace(cfg)]
        self.assertEqual(names, [
            "epoch_begin", "target_state", "handoff_target_state", "target_front", "handoff_target_front",
            "layer_stamp_start", "attention_A", "handoff_A", "kv_C", "handoff_KV_C",
            "attention_D", "handoff_D", "attention_E", "handoff_E", "attention_F", "tp1",
            "front_wait", "front", "shared_early", "handoff_front", "moe", "handoff_moe_done",
            "moe_combine_tp2", "front_wait", "front", "handoff_layer_end", "layer_stamp_end", "epoch_end",
        ])

    def test_index_flags_and_reindex_precedence(self):
        cfg = source_layout(target_layers=1, draft_layers=0)
        for bits, passes in ((8, 2), (8 | 32, 4), (8 | 64, 2), (8 | 32 | 64, 2)):
            with self.subTest(bits=bits):
                visits = trace(cfg, flags={0: bits}, scorer={0: 1 << 40})
                self.assertEqual([e[4] for e in visits if e[0] == "index_select"], list(range(passes)))
                self.assertEqual([e[4] for e in visits if e[0] == "handoff_select"], list(range(passes)))
                names = [e[0] for e in visits]
                self.assertLess(names.index("index_prepare"), names.index("handoff_KV_C"))
                self.assertLess(names.index("handoff_quant"), names.index("index_score"))
                self.assertLess(names.index("handoff_score"), names.index("index_select"))

    def test_null_scorer_skips_selection_but_retains_quant_handoff(self):
        cfg = source_layout(target_layers=1, draft_layers=0)
        names = [e[0] for e in trace(cfg, flags={0: 8}, scorer={0: 0})]
        self.assertIn("handoff_quant", names)
        self.assertNotIn("index_score", names)
        self.assertNotIn("index_select", names)

    def test_idle_ctas_skip_front_waits(self):
        cfg = source_layout(target_layers=1, draft_layers=0)
        visits = trace(cfg, bid=cfg["front_ctas"])
        names = [e[0] for e in visits]
        self.assertNotIn("target_front", names)
        self.assertNotIn("front", names)
        self.assertNotIn("front_wait", names)
        self.assertIn("shared_early", names)
        self.assertIn("handoff_front", names)
        self.assertIn("moe", names)

    def test_draft_omits_target_only_work(self):
        cfg = source_layout(target_layers=1, draft_layers=1)
        events = trace(cfg, flags={0: 0xff, 1: 0xff}, scorer={0: 1, 1: 1})
        draft = [e[0] for e in events if e[1] == 1]
        for stage in ("engq", "engkv", "index_prepare", "index_score", "index_select", "tap"):
            self.assertNotIn(stage, draft)
        self.assertIn("attention_A", draft)
        self.assertEqual(sum(e[0] == "target_tail" for e in events), 1)
        self.assertEqual(sum(e[0] == "draft_tail" for e in events), 1)
        self.assertEqual([e[2] for e in events if e[0] == "layer_stamp_start"], [0, 1])

    def test_split_and_empty_launch_epoch_semantics(self):
        for part in ("all", "target", "draft"):
            cfg = source_layout(part=part, target_layers=0, draft_layers=0)
            names = [e[0] for e in trace(cfg)]
            self.assertEqual(names.count("epoch_begin"), 1)
            self.assertEqual(names.count("epoch_end"), 1)
            self.assertNotIn("attention_A", names)
            self.assertEqual("target_tail" in names, part == "target")
            self.assertEqual("target_state" in names, part != "draft")
        for part in ("target", "draft"):
            cfg = source_layout(part=part, target_layers=2, draft_layers=1)
            names = [e[0] for e in trace(cfg)]
            self.assertEqual("target_state" in names, part == "target")
            self.assertEqual("draft_state" in names, part == "draft")

    def test_engram_and_tap_order(self):
        cfg = source_layout(target_layers=1, draft_layers=0)
        names = [e[0] for e in trace(cfg, flags={0: 128 | 16})]
        self.assertLess(names.index("engq"), names.index("attention_A"))
        self.assertLess(names.index("handoff_A"), names.index("engkv"))
        self.assertLess(names.index("engkv"), names.index("kv_C"))
        self.assertLess(names.index("handoff_layer_end"), names.index("tap"))
        self.assertLess(names.index("tap"), names.index("layer_stamp_end"))


if __name__ == "__main__":
    unittest.main()
