"""CPU contract/native rejection tests. No compiler or GPU is needed."""
from dataclasses import replace
from pathlib import Path
import unittest

from mixed_asm import extract, mask_comments, parse, remap, validate_code


ROOT = Path(__file__).resolve().parent


def native(body="v_mul_f32_e32 v0, v0, v1", vgpr=2, vcc=0, **extra):
    fields = dict(num_vgpr=vgpr, num_agpr=0, numbered_sgpr=32, private_seg_size=0,
                  num_named_barrier=0, uses_vcc=vcc, uses_flat_scratch=0,
                  has_dyn_sized_stack=0, has_recursion=0, has_indirect_call=0)
    fields.update(extra)
    return ('\t.type hip_fragment,@function\nhip_fragment:\n'
            's_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)\n' + body
            + '\ns_setpc_b64 s[30:31]\n.Lfunc_end0:\n'
            + ''.join(f'.set .Lhip_fragment.{key}, {value}\n' for key, value in fields.items()))


class HipInAsmTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "kernel.s").read_text()
        _, self.blocks = parse(self.source)

    def test_two_physical_output_bindings(self):
        self.assertEqual([b.id for b in self.blocks], ["mul_add", "sub_div"])
        self.assertEqual([b.bindings[-1].reg for b in self.blocks], [2, 7])
        self.assertEqual(self.blocks[0].clobbers, ())
        self.assertEqual(self.blocks[1].clobbers, ("vcc",))

    def test_cpp_comments_do_not_end_blocks(self):
        commented = self.source.replace('c = a + b * a;', '/*\n.hip.end\n*/\nc = a + b * a;')
        _, blocks = parse(commented)
        self.assertEqual(len(blocks), 2)
        self.assertIn('/*', blocks[0].code)
        self.assertEqual(mask_comments(['/* start\n', '.hip.end\n', '*/ a + b\n']), ['', '', 'a + b'])

    def test_pool_overlap_and_descriptor_underallocation_rejected(self):
        for modified in (self.source.replace('v[32:35]', 'v[0:3]'),
                         self.source.replace('v[32:35]', 'v[33:35]'),
                         self.source.replace('.amdhsa_next_free_vgpr 64', '.amdhsa_next_free_vgpr 63'),
                         self.source.replace('f32 c = v2', 'f32 c = v0')):
            with self.assertRaises(RuntimeError):
                parse(modified)

    def test_unknown_missing_nested_duplicate_directives_rejected(self):
        for modified in (self.source.replace('.hip.code', '.hip.unsupported', 1),
                         self.source.replace('.hip.end', '', 1),
                         self.source.replace('.hip.begin sub_div', '.hip.begin mul_add'),
                         self.source.replace('c = a + b * a;', '.hip.begin nested\nc = a+b;'),
                         self.source.replace('.hip.fast_math off', '.hip.fast_math on', 1)):
            with self.assertRaises(RuntimeError):
                parse(modified)

    def test_source_calls_memory_control_flow_and_undefined_values_rejected(self):
        for code in ('c = sqrt(a);', 'c = a[0];', 'if (a) c = b;', 'c = c + a;',
                     'a = b; c = a;', 'c = a + 1.0;', 'c = a++;', 'c = "text";'):
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                validate_code(code, self.blocks[0].bindings)
        validate_code('c = -(a + b) * 1.0f / b;', self.blocks[0].bindings)

    def test_mode_mismatch_is_rejected(self):
        with self.assertRaises(RuntimeError):
            parse(self.source.replace('.amdhsa_float_denorm_mode_32 3', '.amdhsa_float_denorm_mode_32 0'))

    def test_remap_preserves_inputs_and_uses_selected_output(self):
        parsed = extract(native())
        block = replace(self.blocks[0], bindings=self.blocks[0].bindings[:2] + (replace(self.blocks[0].bindings[-1], reg=6),))
        code, mapping, writes = remap(parsed, block)
        self.assertEqual(mapping, {0: 32, 1: 33})
        self.assertIn('v_mov_b32_e32 v6, v32', code)
        self.assertEqual(set(writes), {6, 32, 33})
        self.assertFalse({0, 1} & set(writes))

    def test_native_memory_calls_control_flow_and_special_writes_rejected(self):
        for body in ('s_mov_b32 s0, 0', 's_mov_b32 exec_lo, -1', 'scratch_load_b32 v0, off, s32',
                     's_swappc_b64 s[30:31], s[0:1]', 's_branch .Lother',
                     'v_add_f32_e32 v0, v8, v1', 'v_add_f32_e32 v0, s0, v1'):
            with self.subTest(body=body), self.assertRaises(RuntimeError):
                extract(native(body))

    def test_unexpected_abi_and_scratch_are_rejected(self):
        with self.assertRaises(RuntimeError):
            extract(native().replace('s_setpc_b64 s[30:31]', 's_setpc_b64 s[28:29]'))
        with self.assertRaises(RuntimeError):
            extract(native(private_seg_size=16))

    def test_division_requires_vcc_authorization(self):
        parsed = extract(native('v_div_scale_f32 v2, vcc_lo, v1, v0, v1\nv_div_fixup_f32 v0, v2, v0, v1', vgpr=3, vcc=1))
        with self.assertRaisesRegex(RuntimeError, 'clobber'):
            remap(parsed, self.blocks[0])
        code, _, _ = remap(parsed, self.blocks[1])
        self.assertIn('v_div_scale_f32 v42, vcc_lo', code)

    def test_insufficient_pool_is_rejected(self):
        parsed = extract(native('v_mov_b32_e32 v7, v0\nv_mul_f32_e32 v0, v7, v1', vgpr=8))
        with self.assertRaisesRegex(RuntimeError, 'too small'):
            remap(parsed, self.blocks[0])

    def test_identity_helper_can_have_an_unused_second_argument(self):
        parsed = extract(native(body='', vgpr=1))
        _, _, writes = remap(parsed, self.blocks[0])
        self.assertEqual(set(writes), {2, 32, 33})


if __name__ == '__main__':
    unittest.main()
