import unittest

from build import parse, preprocess
from contract import ROOT, source_layout
from native import aggregate, expand, extract


def assembly(symbol="leaf", body=None, **override):
    body = body or """s_wait_loadcnt_dscnt 0
scratch_store_b32 off, v40, s32
v_writelane_b32 v41, s48, 0
s_branch 1f
.LBB0_1:
v_add_f32 v0, v0, v1
1:
s_cbranch_scc0 .LBB0_1
v_readlane_b32 s48, v41, 0
scratch_load_b32 v40, off, s32
s_wait_loadcnt 0
s_set_pc_i64 s[30:31]
"""
    resources = dict(num_vgpr=64, num_agpr=0, numbered_sgpr=56, num_named_barrier=0,
                     private_seg_size=16, uses_vcc=1, uses_flat_scratch=1,
                     has_dyn_sized_stack=0, has_recursion=0, has_indirect_call=0)
    resources.update(override)
    return (f'.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"\n.type {symbol},@function\n'
            + symbol + ":\n" + body + "\n.Lfunc_end0:\n"
            + "".join(f".set .L{symbol}.{k}, {v}\n" for k, v in resources.items()))


class NativeTests(unittest.TestCase):
    def test_saves_restores_and_scratch_survive_expansion(self):
        fragment = extract(assembly(), "leaf")
        output = expand(fragment, "one")
        for instruction in ("scratch_store_b32 off, v40, s32", "v_writelane_b32 v41, s48, 0",
                            "v_readlane_b32 s48, v41, 0", "scratch_load_b32 v40, off, s32"):
            self.assertIn(instruction, output)
        self.assertNotIn("s_set_pc_i64 s[30:31]", output)
        self.assertIn("STEP_JMP .Lone_end", output)
        self.assertIn("PREP_STAGE", output)
        self.assertIn("s_set_vgpr_msb 0", output)

    def test_multiple_insertions_do_not_share_local_labels(self):
        fragment = extract(assembly(), "leaf")
        first, second = expand(fragment, "first"), expand(fragment, "second")
        self.assertNotIn(".LBB0_1", first)
        self.assertNotIn("1f", first)
        first_labels = {x[:-1] for x in first.splitlines() if x.endswith(":")}
        second_labels = {x[:-1] for x in second.splitlines() if x.endswith(":")}
        self.assertFalse(first_labels & second_labels)

    def test_realtime_counter_is_retained(self):
        body = "s_sendmsg_rtn_b64 s[8:9], sendmsg(MSG_RTN_GET_REALTIME)\ns_setpc_b64 s[30:31]"
        self.assertIn("MSG_RTN_GET_REALTIME", expand(extract(assembly(body=body), "leaf"), "clock"))

    def test_rejects_unbridged_native_code(self):
        for body in ("s_swappc_b64 s[30:31], s[0:1]", "s_getpc_b64 s[0:1]",
                     "s_endpgm", "s_trap 2", "s_mov_b32 s0, ttmp9", "s_branch unknown",
                     "s_branch 9f", "s_setpc_b64 s[0:1]", ".long 0x1234"):
            with self.subTest(body=body), self.assertRaises(RuntimeError):
                extract(assembly(body=body + "\ns_setpc_b64 s[30:31]"), "leaf")
        with self.assertRaises(RuntimeError):
            extract(assembly() + '\n.section .rodata,"a",@progbits\n', "leaf")

    def test_resources_come_from_native_report_and_include_scheduler(self):
        small = extract(assembly(), "leaf")
        big = extract(assembly("large", num_vgpr=320, private_seg_size=100, num_named_barrier=2), "large")
        result = aggregate([small, big])
        self.assertEqual(result["vgpr"], 320)
        self.assertEqual(result["private"], 112)
        self.assertEqual(result["scratch"], 1)
        self.assertEqual(result["named_barriers"], 2)
        self.assertGreaterEqual(result["numbered_sgpr"], 56)
        for key in ("num_agpr", "has_dyn_sized_stack", "has_recursion", "has_indirect_call"):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                extract(assembly(**{key: 1}), "leaf")

    def test_missing_reachable_fragment_is_an_error(self):
        lines, blocks = parse((ROOT / "step.s").read_text())
        cfg = source_layout(target_layers=1, draft_layers=0)
        with self.assertRaisesRegex(RuntimeError, "Missing reachable fragment"):
            preprocess(lines, blocks, cfg, {})


if __name__ == "__main__":
    unittest.main()
