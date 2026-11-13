// gfx1250 / wave32. Launch one workgroup of 1..256 threads.
// A(a, b, out): out[tid] = C(B(a[tid], b[tid]), 3) + 1, modulo 2^32.
// B is ASM; C is HIP. Both definitions are in separate native object files.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text
.protected kernel_A
.globl kernel_A
.type kernel_A,@function
.p2align 8
kernel_A:
    // Dispatch supplies kernarg pointer in s[0:1], workitem ID in v0.
    s_set_vgpr_msb 0
    s_load_b64 s[4:5], s[0:1], 0
    s_load_b64 s[6:7], s[0:1], 8
    // Preserve the output address and byte offset across the HIP CCC call.
    // s36:s37 and v40 are callee-saved in the ordinary AMDGPU device ABI.
    s_load_b64 s[36:37], s[0:1], 16
    v_lshlrev_b32 v40, 2, v0
    s_wait_kmcnt 0
    s_waitcnt_depctr 0
    s_nop 7
    global_load_b32 v2, v40, s[4:5]
    global_load_b32 v3, v40, s[6:7]
    s_wait_loadcnt 0

    // Custom leaf ABI: arguments v2, v3; result v2; return PC s[30:31].
    // s_getpc returns the address of the following s_add instruction.
    // Its 64-bit literal is 4 bytes after that address. REL64 + 4 thus
    // makes PC + relocated_literal equal the final address of kernel_B.
    s_getpc_b64 s[16:17]
    s_add_nc_u64 s[16:17], s[16:17], kernel_B@rel64+4
    s_swappc_b64 s[30:31], s[16:17]

    // B returned v2=a+b. Adapt it to C's compiler-generated CCC arguments.
    // unsigned C(unsigned value, unsigned multiplier): v0, v1 -> v0.
    v_mov_b32 v0, v2
    v_mov_b32 v1, 3
    s_waitcnt_depctr 0
    s_nop 7
    s_getpc_b64 s[16:17]
    s_add_nc_u64 s[16:17], s[16:17], kernel_C@rel64+4
    s_swappc_b64 s[30:31], s[16:17]

    // C returned v0=3*(a+b)+7. A continues, adding one and storing the result.
    v_add_nc_u32 v0, v0, 1
    s_waitcnt_depctr 0
    s_nop 7
    global_store_b32 v40, v0, s[36:37]
    s_wait_storecnt 0
    s_endpgm
.Lkernel_A_end:
.size kernel_A, .Lkernel_A_end-kernel_A
// End-of-code instruction prefetch padding (not part of the function size).
.p2alignl 7, 0xbf9f0000
.fill 96, 4, 0xbf9f0000

.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel kernel_A
    .amdhsa_group_segment_fixed_size 0
    .amdhsa_private_segment_fixed_size 0
    .amdhsa_kernarg_size 24
    .amdhsa_user_sgpr_count 2
    .amdhsa_user_sgpr_kernarg_segment_ptr 1
    .amdhsa_user_sgpr_kernarg_preload_length 0
    .amdhsa_user_sgpr_kernarg_preload_offset 0
    .amdhsa_wavefront_size32 1
    .amdhsa_enable_private_segment 0
    .amdhsa_uses_dynamic_stack 0
    .amdhsa_system_sgpr_workgroup_id_x 0
    .amdhsa_system_sgpr_workgroup_id_y 0
    .amdhsa_system_sgpr_workgroup_id_z 0
    .amdhsa_system_vgpr_workitem_id 0
    // Cover A, B and C, including A's callee-saved state. No scratch is used.
    .amdhsa_next_free_vgpr 41
    .amdhsa_next_free_sgpr 38
    .amdhsa_reserve_vcc 0
    .amdhsa_named_barrier_count 0
    .amdhsa_float_round_mode_32 0
    .amdhsa_float_round_mode_16_64 0
    .amdhsa_float_denorm_mode_32 3
    .amdhsa_float_denorm_mode_16_64 3
    .amdhsa_memory_ordered 1
    .amdhsa_forward_progress 1
.end_amdhsa_kernel

.amdgpu_metadata
---
amdhsa.version: [1, 2]
amdhsa.target: amdgcn-amd-amdhsa--gfx1250
amdhsa.kernels:
  - .name: kernel_A
    .symbol: kernel_A.kd
    .kernarg_segment_size: 24
    .kernarg_segment_align: 8
    .group_segment_fixed_size: 0
    .private_segment_fixed_size: 0
    .wavefront_size: 32
    .sgpr_count: 38
    .vgpr_count: 41
    .max_flat_workgroup_size: 256
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
    .args:
      - .name: a
        .offset: 0
        .size: 8
        .value_kind: global_buffer
        .address_space: global
      - .name: b
        .offset: 8
        .size: 8
        .value_kind: global_buffer
        .address_space: global
      - .name: out
        .offset: 16
        .size: 8
        .value_kind: global_buffer
        .address_space: global
...
.end_amdgpu_metadata
.section .note.GNU-stack,"",@progbits
