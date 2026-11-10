"""Small, explicit gfx1100 kernel ABI used only by the clobber experiment."""

HEADER = '.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"\n.amdhsa_code_object_version 6\n'


def kernel(name, body, nargs, private=0, lds=512):
    return f'''
.text
.protected {name}
.globl {name}
.p2align 8
.type {name},@function
{name}:
{body}
.Lend_{name}:
.size {name}, .Lend_{name}-{name}
.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel {name}
  .amdhsa_group_segment_fixed_size {lds}
  .amdhsa_private_segment_fixed_size {private}
  .amdhsa_kernarg_size {8 * nargs}
  .amdhsa_user_sgpr_count 2
  .amdhsa_user_sgpr_kernarg_segment_ptr 1
  .amdhsa_system_sgpr_workgroup_id_x 1
  .amdhsa_system_vgpr_workitem_id 0
  .amdhsa_wavefront_size32 1
  .amdhsa_enable_private_segment {int(private != 0)}
  .amdhsa_uses_dynamic_stack 0
  .amdhsa_next_free_vgpr 256
  .amdhsa_next_free_sgpr 106
  .amdhsa_reserve_vcc 1
  .amdhsa_float_denorm_mode_32 3
  .amdhsa_float_denorm_mode_16_64 3
  .amdhsa_dx10_clamp 1
  .amdhsa_ieee_mode 1
  .amdhsa_workgroup_processor_mode 1
  .amdhsa_memory_ordered 1
  .amdhsa_forward_progress 1
.end_amdhsa_kernel
'''


def metadata(entries):
    text = '.amdgpu_metadata\n---\namdhsa.kernels:\n'
    for name, nargs, private, lds in entries:
        text += '  - .args:\n'
        for i in range(nargs):
            text += f'''      - .address_space: global
        .offset: {8 * i}
        .size: 8
        .value_kind: global_buffer
'''
        text += f'''    .name: {name}
    .symbol: {name}.kd
    .kernarg_segment_size: {8 * nargs}
    .kernarg_segment_align: 8
    .group_segment_fixed_size: {lds}
    .private_segment_fixed_size: {private}
    .wavefront_size: 32
    .sgpr_count: 108
    .vgpr_count: 256
    .max_flat_workgroup_size: 128
    .reqd_workgroup_size: [128, 1, 1]
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
'''
    return text + '''amdhsa.target: amdgcn-amd-amdhsa--gfx1100
amdhsa.version: [1, 2]
...
.end_amdgpu_metadata
.text
.p2alignl 7, 3214868480
.fill 96, 4, 3214868480
.section ".note.GNU-stack","",@progbits
'''
