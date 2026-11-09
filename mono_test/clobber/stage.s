// Supplier-owned standalone ASM kernel. Consumer needs only the .co and contract.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"
.amdhsa_code_object_version 6

.text
.protected clobber_stage
.globl clobber_stage
.p2align 8
.type clobber_stage,@function
clobber_stage:
// ABI: s[0:1]=kernarg, s2=blockIdx.x, v0=threadIdx.x, block=128.
s_load_b128 s[4:7], s[0:1], 0
s_lshl_b32 s2, s2, 7
s_nop 3
v_add_nc_u32 v1, s2, v0
s_nop 3
v_lshlrev_b32 v1, 2, v1
s_waitcnt lgkmcnt(0)
global_load_b32 v8, v1, s[4:5]
s_waitcnt vmcnt(0)
v_add_f32 v8, -1.0, v8
v_lshlrev_b32 v2, 2, v0
s_nop 3
// Deliberately overwrite the operator's entire 512-byte LDS allocation.
ds_write_b32 v2, v8
s_waitcnt lgkmcnt(0)
s_barrier
ds_read_b32 v8, v2
s_waitcnt lgkmcnt(0)
global_store_b32 v1, v8, s[6:7]
s_waitcnt_vscnt null, 0
s_barrier
// Destroy every numbered VGPR and SGPR. No preserved GPR anchor exists.
.irp r,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255
  v_mov_b32 v\r, 0
.endr
.irp r,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105
  s_mov_b32 s\r, 0
.endr
s_mov_b32 vcc_lo, 0
s_mov_b32 exec_lo, 0
s_cmp_lg_u32 0, 0
s_endpgm

.Lend_clobber_stage:
.size clobber_stage, .Lend_clobber_stage-clobber_stage
.section .rodata,"a",@progbits
.p2align 6
.amdhsa_kernel clobber_stage
  .amdhsa_group_segment_fixed_size 512
  .amdhsa_private_segment_fixed_size 0
  .amdhsa_kernarg_size 16
  .amdhsa_user_sgpr_count 2
  .amdhsa_user_sgpr_kernarg_segment_ptr 1
  .amdhsa_system_sgpr_workgroup_id_x 1
  .amdhsa_system_vgpr_workitem_id 0
  .amdhsa_wavefront_size32 1
  .amdhsa_enable_private_segment 0
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
.amdgpu_metadata
---
amdhsa.kernels:
  - .args:
      - .address_space: global
        .offset: 0
        .size: 8
        .value_kind: global_buffer
      - .address_space: global
        .offset: 8
        .size: 8
        .value_kind: global_buffer
    .name: clobber_stage
    .symbol: clobber_stage.kd
    .kernarg_segment_size: 16
    .kernarg_segment_align: 8
    .group_segment_fixed_size: 512
    .private_segment_fixed_size: 0
    .wavefront_size: 32
    .sgpr_count: 108
    .vgpr_count: 256
    .max_flat_workgroup_size: 128
    .reqd_workgroup_size: [128, 1, 1]
    .uniform_work_group_size: 1
    .uses_dynamic_stack: false
amdhsa.target: amdgcn-amd-amdhsa--gfx1100
amdhsa.version: [1, 2]
...
.end_amdgpu_metadata
.text
.p2alignl 7, 3214868480
.fill 96, 4, 3214868480
.section ".note.GNU-stack","",@progbits
