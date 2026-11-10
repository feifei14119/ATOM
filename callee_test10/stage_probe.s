// gfx1100 / wave32. Explicit ABI: bias v0, input v1:v2, record v3:v4,
// tx/ty/bx/by v5-v8; implicit packed thread ID v31, workgroup IDs s12/s13.
// The core overwrites v64-v255 and s40-s105, plus v0,v9-v17,s0,SCC,memory.
// Each executing wave must have at least one active lane; EXEC is unchanged.
	.amdgcn_target "amdgcn-amd-amdhsa--gfx1100"
	.amdhsa_code_object_version 6
	.text
	.globl stage_probe
	.hidden stage_probe
	.p2align 2
	.type stage_probe,@function
stage_probe:
// Extraction artifact only: NOT a standard-ABI callable device function.
.Lpayload_begin:
	.include "stage_body.inc"
.Lpayload_end:
	s_setpc_b64 s[30:31]
.Lstage_probe_end:
	.size stage_probe, .Lstage_probe_end-stage_probe
	.set stage_probe.payload_offset, .Lpayload_begin-stage_probe
	.set stage_probe.payload_size, .Lpayload_end-.Lpayload_begin
	.set stage_probe.num_vgpr, 256
	.set stage_probe.num_agpr, 0
	.set stage_probe.numbered_sgpr, 106
	.set stage_probe.num_named_barrier, 0
	.set stage_probe.private_seg_size, 0
	.set stage_probe.uses_vcc, 0
	.set stage_probe.uses_flat_scratch, 0
	.set stage_probe.has_dyn_sized_stack, 0
	.set stage_probe.has_recursion, 0
	.set stage_probe.has_indirect_call, 0
	.section ".note.GNU-stack","",@progbits
