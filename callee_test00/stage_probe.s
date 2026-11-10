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
// ABI prologue: preserve only the callee-saved part of the overwritten range.
// Private frame: 96 VGPR words + 34 SGPR words = 520 bytes, rounded to 528.
// Leaf function: s32 is the incoming frame base and is never changed.
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)
	s_waitcnt_vscnt null, 0
	s_waitcnt_depctr 0
	scratch_store_b32 off, v72, s32 offset:0
	scratch_store_b32 off, v73, s32 offset:4
	scratch_store_b32 off, v74, s32 offset:8
	scratch_store_b32 off, v75, s32 offset:12
	scratch_store_b32 off, v76, s32 offset:16
	scratch_store_b32 off, v77, s32 offset:20
	scratch_store_b32 off, v78, s32 offset:24
	scratch_store_b32 off, v79, s32 offset:28
	scratch_store_b32 off, v88, s32 offset:32
	scratch_store_b32 off, v89, s32 offset:36
	scratch_store_b32 off, v90, s32 offset:40
	scratch_store_b32 off, v91, s32 offset:44
	scratch_store_b32 off, v92, s32 offset:48
	scratch_store_b32 off, v93, s32 offset:52
	scratch_store_b32 off, v94, s32 offset:56
	scratch_store_b32 off, v95, s32 offset:60
	scratch_store_b32 off, v104, s32 offset:64
	scratch_store_b32 off, v105, s32 offset:68
	scratch_store_b32 off, v106, s32 offset:72
	scratch_store_b32 off, v107, s32 offset:76
	scratch_store_b32 off, v108, s32 offset:80
	scratch_store_b32 off, v109, s32 offset:84
	scratch_store_b32 off, v110, s32 offset:88
	scratch_store_b32 off, v111, s32 offset:92
	scratch_store_b32 off, v120, s32 offset:96
	scratch_store_b32 off, v121, s32 offset:100
	scratch_store_b32 off, v122, s32 offset:104
	scratch_store_b32 off, v123, s32 offset:108
	scratch_store_b32 off, v124, s32 offset:112
	scratch_store_b32 off, v125, s32 offset:116
	scratch_store_b32 off, v126, s32 offset:120
	scratch_store_b32 off, v127, s32 offset:124
	scratch_store_b32 off, v136, s32 offset:128
	scratch_store_b32 off, v137, s32 offset:132
	scratch_store_b32 off, v138, s32 offset:136
	scratch_store_b32 off, v139, s32 offset:140
	scratch_store_b32 off, v140, s32 offset:144
	scratch_store_b32 off, v141, s32 offset:148
	scratch_store_b32 off, v142, s32 offset:152
	scratch_store_b32 off, v143, s32 offset:156
	scratch_store_b32 off, v152, s32 offset:160
	scratch_store_b32 off, v153, s32 offset:164
	scratch_store_b32 off, v154, s32 offset:168
	scratch_store_b32 off, v155, s32 offset:172
	scratch_store_b32 off, v156, s32 offset:176
	scratch_store_b32 off, v157, s32 offset:180
	scratch_store_b32 off, v158, s32 offset:184
	scratch_store_b32 off, v159, s32 offset:188
	scratch_store_b32 off, v168, s32 offset:192
	scratch_store_b32 off, v169, s32 offset:196
	scratch_store_b32 off, v170, s32 offset:200
	scratch_store_b32 off, v171, s32 offset:204
	scratch_store_b32 off, v172, s32 offset:208
	scratch_store_b32 off, v173, s32 offset:212
	scratch_store_b32 off, v174, s32 offset:216
	scratch_store_b32 off, v175, s32 offset:220
	scratch_store_b32 off, v184, s32 offset:224
	scratch_store_b32 off, v185, s32 offset:228
	scratch_store_b32 off, v186, s32 offset:232
	scratch_store_b32 off, v187, s32 offset:236
	scratch_store_b32 off, v188, s32 offset:240
	scratch_store_b32 off, v189, s32 offset:244
	scratch_store_b32 off, v190, s32 offset:248
	scratch_store_b32 off, v191, s32 offset:252
	scratch_store_b32 off, v200, s32 offset:256
	scratch_store_b32 off, v201, s32 offset:260
	scratch_store_b32 off, v202, s32 offset:264
	scratch_store_b32 off, v203, s32 offset:268
	scratch_store_b32 off, v204, s32 offset:272
	scratch_store_b32 off, v205, s32 offset:276
	scratch_store_b32 off, v206, s32 offset:280
	scratch_store_b32 off, v207, s32 offset:284
	scratch_store_b32 off, v216, s32 offset:288
	scratch_store_b32 off, v217, s32 offset:292
	scratch_store_b32 off, v218, s32 offset:296
	scratch_store_b32 off, v219, s32 offset:300
	scratch_store_b32 off, v220, s32 offset:304
	scratch_store_b32 off, v221, s32 offset:308
	scratch_store_b32 off, v222, s32 offset:312
	scratch_store_b32 off, v223, s32 offset:316
	scratch_store_b32 off, v232, s32 offset:320
	scratch_store_b32 off, v233, s32 offset:324
	scratch_store_b32 off, v234, s32 offset:328
	scratch_store_b32 off, v235, s32 offset:332
	scratch_store_b32 off, v236, s32 offset:336
	scratch_store_b32 off, v237, s32 offset:340
	scratch_store_b32 off, v238, s32 offset:344
	scratch_store_b32 off, v239, s32 offset:348
	scratch_store_b32 off, v248, s32 offset:352
	scratch_store_b32 off, v249, s32 offset:356
	scratch_store_b32 off, v250, s32 offset:360
	scratch_store_b32 off, v251, s32 offset:364
	scratch_store_b32 off, v252, s32 offset:368
	scratch_store_b32 off, v253, s32 offset:372
	scratch_store_b32 off, v254, s32 offset:376
	scratch_store_b32 off, v255, s32 offset:380
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s48
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:384
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s49
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:388
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s50
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:392
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s51
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:396
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s52
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:400
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s53
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:404
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s54
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:408
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s55
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:412
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s64
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:416
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s65
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:420
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s66
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:424
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s67
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:428
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s68
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:432
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s69
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:436
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s70
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:440
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s71
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:444
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s80
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:448
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s81
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:452
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s82
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:456
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s83
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:460
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s84
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:464
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s85
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:468
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s86
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:472
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s87
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:476
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s96
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:480
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s97
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:484
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s98
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:488
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s99
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:492
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s100
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:496
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s101
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:500
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s102
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:504
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s103
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:508
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s104
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:512
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v18, s105
	s_waitcnt_depctr 0
	scratch_store_b32 off, v18, s32 offset:516
	s_waitcnt_vscnt null, 0
.Lpayload_begin:
// Conservative boundaries/dependency waits keep this teaching example simple.
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)
	s_waitcnt_vscnt null, 0
	s_waitcnt_depctr 0
// Actual overwrite of EVERY numbered GPR in the requested ranges.
// v_mov affects only active lanes; inactive lanes and EXEC stay untouched.
	.irp r, 64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255
	v_mov_b32_e32 v\r, 0xdeadbeef
	.endr
	.irp r, 40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105
	s_mov_b32 s\r, 0xbaadf00d
	.endr
	s_waitcnt_depctr 0
	v_mov_b32_e32 v10, v1
	v_mov_b32_e32 v11, v2
	s_waitcnt_depctr 0
	global_load_b32 v9, v[10:11], off
	v_and_b32_e32 v12, 0x3ff, v31
	v_bfe_u32 v13, v31, 10, 10
	v_mov_b32_e32 v14, s12
	v_mov_b32_e32 v15, s13
	s_xor_b32 s0, s12, s13
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
// Change input memory so the caller cannot reload its original live snapshot.
	v_xor_b32_e32 v17, 0x9e3779b9, v9
	s_waitcnt_depctr 0
	global_store_b32 v[10:11], v17, off
// result = ((loaded ^ 0x13579bdf) + bias + tx + (ty<<8)
//           + (bx<<16) + (by<<24)) ^ (implicit_bx ^ implicit_by).
	v_xor_b32_e32 v16, 0x13579bdf, v9
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v0, v16
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v5, v16
	v_lshlrev_b32_e32 v17, 8, v6
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v17, v16
	v_lshlrev_b32_e32 v17, 16, v7
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v17, v16
	v_lshlrev_b32_e32 v17, 24, v8
	s_waitcnt_depctr 0
	v_add_nc_u32_e32 v16, v17, v16
	s_waitcnt_depctr 0
	v_xor_b32_e32 v16, s0, v16
	v_mov_b32_e32 v10, v3
	v_mov_b32_e32 v11, v4
	s_waitcnt_depctr 0
// Record each argument separately, not just a checksum of all arguments.
	global_store_b32 v[10:11], v0, off offset:0
	global_store_b32 v[10:11], v9, off offset:4
	global_store_b32 v[10:11], v5, off offset:8
	global_store_b32 v[10:11], v6, off offset:12
	global_store_b32 v[10:11], v7, off offset:16
	global_store_b32 v[10:11], v8, off offset:20
	global_store_b32 v[10:11], v12, off offset:24
	global_store_b32 v[10:11], v13, off offset:28
	global_store_b32 v[10:11], v14, off offset:32
	global_store_b32 v[10:11], v15, off offset:36
	global_store_b32 v[10:11], v16, off offset:40
	s_waitcnt_vscnt null, 0
	v_mov_b32_e32 v0, v16
	s_waitcnt_depctr 0
.Lpayload_end:
// ABI epilogue: restore the saved values before the device return.
	scratch_load_b32 v72, off, s32 offset:0
	scratch_load_b32 v73, off, s32 offset:4
	scratch_load_b32 v74, off, s32 offset:8
	scratch_load_b32 v75, off, s32 offset:12
	scratch_load_b32 v76, off, s32 offset:16
	scratch_load_b32 v77, off, s32 offset:20
	scratch_load_b32 v78, off, s32 offset:24
	scratch_load_b32 v79, off, s32 offset:28
	scratch_load_b32 v88, off, s32 offset:32
	scratch_load_b32 v89, off, s32 offset:36
	scratch_load_b32 v90, off, s32 offset:40
	scratch_load_b32 v91, off, s32 offset:44
	scratch_load_b32 v92, off, s32 offset:48
	scratch_load_b32 v93, off, s32 offset:52
	scratch_load_b32 v94, off, s32 offset:56
	scratch_load_b32 v95, off, s32 offset:60
	scratch_load_b32 v104, off, s32 offset:64
	scratch_load_b32 v105, off, s32 offset:68
	scratch_load_b32 v106, off, s32 offset:72
	scratch_load_b32 v107, off, s32 offset:76
	scratch_load_b32 v108, off, s32 offset:80
	scratch_load_b32 v109, off, s32 offset:84
	scratch_load_b32 v110, off, s32 offset:88
	scratch_load_b32 v111, off, s32 offset:92
	scratch_load_b32 v120, off, s32 offset:96
	scratch_load_b32 v121, off, s32 offset:100
	scratch_load_b32 v122, off, s32 offset:104
	scratch_load_b32 v123, off, s32 offset:108
	scratch_load_b32 v124, off, s32 offset:112
	scratch_load_b32 v125, off, s32 offset:116
	scratch_load_b32 v126, off, s32 offset:120
	scratch_load_b32 v127, off, s32 offset:124
	scratch_load_b32 v136, off, s32 offset:128
	scratch_load_b32 v137, off, s32 offset:132
	scratch_load_b32 v138, off, s32 offset:136
	scratch_load_b32 v139, off, s32 offset:140
	scratch_load_b32 v140, off, s32 offset:144
	scratch_load_b32 v141, off, s32 offset:148
	scratch_load_b32 v142, off, s32 offset:152
	scratch_load_b32 v143, off, s32 offset:156
	scratch_load_b32 v152, off, s32 offset:160
	scratch_load_b32 v153, off, s32 offset:164
	scratch_load_b32 v154, off, s32 offset:168
	scratch_load_b32 v155, off, s32 offset:172
	scratch_load_b32 v156, off, s32 offset:176
	scratch_load_b32 v157, off, s32 offset:180
	scratch_load_b32 v158, off, s32 offset:184
	scratch_load_b32 v159, off, s32 offset:188
	scratch_load_b32 v168, off, s32 offset:192
	scratch_load_b32 v169, off, s32 offset:196
	scratch_load_b32 v170, off, s32 offset:200
	scratch_load_b32 v171, off, s32 offset:204
	scratch_load_b32 v172, off, s32 offset:208
	scratch_load_b32 v173, off, s32 offset:212
	scratch_load_b32 v174, off, s32 offset:216
	scratch_load_b32 v175, off, s32 offset:220
	scratch_load_b32 v184, off, s32 offset:224
	scratch_load_b32 v185, off, s32 offset:228
	scratch_load_b32 v186, off, s32 offset:232
	scratch_load_b32 v187, off, s32 offset:236
	scratch_load_b32 v188, off, s32 offset:240
	scratch_load_b32 v189, off, s32 offset:244
	scratch_load_b32 v190, off, s32 offset:248
	scratch_load_b32 v191, off, s32 offset:252
	scratch_load_b32 v200, off, s32 offset:256
	scratch_load_b32 v201, off, s32 offset:260
	scratch_load_b32 v202, off, s32 offset:264
	scratch_load_b32 v203, off, s32 offset:268
	scratch_load_b32 v204, off, s32 offset:272
	scratch_load_b32 v205, off, s32 offset:276
	scratch_load_b32 v206, off, s32 offset:280
	scratch_load_b32 v207, off, s32 offset:284
	scratch_load_b32 v216, off, s32 offset:288
	scratch_load_b32 v217, off, s32 offset:292
	scratch_load_b32 v218, off, s32 offset:296
	scratch_load_b32 v219, off, s32 offset:300
	scratch_load_b32 v220, off, s32 offset:304
	scratch_load_b32 v221, off, s32 offset:308
	scratch_load_b32 v222, off, s32 offset:312
	scratch_load_b32 v223, off, s32 offset:316
	scratch_load_b32 v232, off, s32 offset:320
	scratch_load_b32 v233, off, s32 offset:324
	scratch_load_b32 v234, off, s32 offset:328
	scratch_load_b32 v235, off, s32 offset:332
	scratch_load_b32 v236, off, s32 offset:336
	scratch_load_b32 v237, off, s32 offset:340
	scratch_load_b32 v238, off, s32 offset:344
	scratch_load_b32 v239, off, s32 offset:348
	scratch_load_b32 v248, off, s32 offset:352
	scratch_load_b32 v249, off, s32 offset:356
	scratch_load_b32 v250, off, s32 offset:360
	scratch_load_b32 v251, off, s32 offset:364
	scratch_load_b32 v252, off, s32 offset:368
	scratch_load_b32 v253, off, s32 offset:372
	scratch_load_b32 v254, off, s32 offset:376
	scratch_load_b32 v255, off, s32 offset:380
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:384
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s48, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:388
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s49, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:392
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s50, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:396
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s51, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:400
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s52, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:404
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s53, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:408
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s54, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:412
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s55, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:416
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s64, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:420
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s65, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:424
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s66, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:428
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s67, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:432
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s68, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:436
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s69, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:440
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s70, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:444
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s71, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:448
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s80, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:452
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s81, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:456
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s82, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:460
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s83, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:464
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s84, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:468
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s85, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:472
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s86, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:476
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s87, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:480
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s96, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:484
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s97, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:488
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s98, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:492
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s99, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:496
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s100, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:500
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s101, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:504
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s102, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:508
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s103, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:512
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s104, v18
	s_waitcnt_depctr 0
	scratch_load_b32 v18, off, s32 offset:516
	s_waitcnt vmcnt(0)
	s_waitcnt_depctr 0
	v_readfirstlane_b32 s105, v18
	s_waitcnt_depctr 0
	s_setpc_b64 s[30:31]
.Lstage_probe_end:
	.size stage_probe, .Lstage_probe_end-stage_probe
	.set stage_probe.payload_offset, .Lpayload_begin-stage_probe
	.set stage_probe.payload_size, .Lpayload_end-.Lpayload_begin
	.set stage_probe.num_vgpr, 256
	.set stage_probe.num_agpr, 0
	.set stage_probe.numbered_sgpr, 106
	.set stage_probe.num_named_barrier, 0
	.set stage_probe.private_seg_size, 528
	.set stage_probe.uses_vcc, 0
	.set stage_probe.uses_flat_scratch, 1
	.set stage_probe.has_dyn_sized_stack, 0
	.set stage_probe.has_recursion, 0
	.set stage_probe.has_indirect_call, 0
	.section ".note.GNU-stack","",@progbits
