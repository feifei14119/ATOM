// Experimental external device-call contract, gfx1250 wave32, full EXEC.
// s0=block_x, s1=block_y, s2=factor, v0:v1=record address, v2=tx, v3=ty.
// Return v4; return PC s30:s31. No stack, LDS, or implicit dispatch inputs.
.amdgcn_target "amdgcn-amd-amdhsa--gfx1250"
.amdhsa_code_object_version 6
.text
.globl contract_stage
.hidden contract_stage
.p2align 6
.type contract_stage,@function
contract_stage:
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_waitcnt_depctr 0
    global_load_b32 v4, v[0:1], off
    s_wait_loadcnt 0
    v_mov_b32 v6, s2
    v_mov_b32 v7, s0
    v_mov_b32 v8, s1
    global_store_b32 v[0:1], v6, off offset:24
    global_store_b32 v[0:1], v7, off offset:28
    global_store_b32 v[0:1], v8, off offset:32
    global_store_b32 v[0:1], v2, off offset:36
    global_store_b32 v[0:1], v3, off offset:40
    global_store_b32 v[0:1], v4, off offset:44
    global_store_b32 v[0:1], v0, off offset:48
    global_store_b32 v[0:1], v1, off offset:52
    // Drain store source operands before overwriting the loaded value v4.
    s_wait_storecnt 0
    v_xor_b32 v9, 0x9e3779b9, v4
    v_add_nc_u32 v9, s2, v9
    global_store_b32 v[0:1], v9, off
    v_xor_b32 v4, 0x13579bdf, v4
    v_add_nc_u32 v4, s2, v4
    v_add_nc_u32 v4, v2, v4
    v_lshlrev_b32 v5, 8, v3
    v_add_nc_u32 v4, v5, v4
    s_lshl_b32 s4, s0, 16
    s_lshl_b32 s5, s1, 24
    s_xor_b32 s6, s0, s1
    v_add_nc_u32 v4, s4, v4
    v_add_nc_u32 v4, s5, v4
    v_xor_b32 v4, s6, v4
    global_store_b32 v[0:1], v4, off offset:56
    // Deliberately overwrite high registers, including default ABI CSRs.
    v_mov_b32 v64, 0x64
    v_mov_b32 v72, 0x72
    v_mov_b32 v95, 0x95
    s_mov_b32 s40, 0x40
    s_mov_b32 s48, 0x48
    s_mov_b32 s63, 0x63
    s_wait_loadcnt 0
    s_wait_storecnt 0
    s_waitcnt_depctr 0
    s_setpc_b64 s[30:31]
.Lcontract_stage_end:
.size contract_stage, .Lcontract_stage_end-contract_stage
.set contract_stage.num_vgpr, 96
.set contract_stage.numbered_sgpr, 64
.set contract_stage.num_agpr, 0
.set contract_stage.private_seg_size, 0
.set contract_stage.num_named_barrier, 0
.set contract_stage.uses_vcc, 0
.set contract_stage.uses_flat_scratch, 0
.set contract_stage.has_dyn_sized_stack, 0
.set contract_stage.has_recursion, 0
.set contract_stage.has_indirect_call, 0
.section .note.GNU-stack,"",@progbits
