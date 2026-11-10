; This IR is intentionally reviewable: the call contract is a backend feature,
; not inline asm, a MIR rewrite, or a final binary patch.
target triple = "amdgcn-amd-amdhsa"

declare i32 @llvm.amdgcn.workitem.id.x()
declare i32 @llvm.amdgcn.workitem.id.y()
declare i32 @llvm.amdgcn.workgroup.id.x()
declare i32 @llvm.amdgcn.workgroup.id.y()

declare i32 @contract_stage(i32, i32, i64, i32, i32, i32) #1

; Exactly 32x8 threads per block, grid_x is supplied explicitly by the host.
; 16-dword record per lane. Each callee changes record[0] to (old ^ mask)+factor.
define amdgpu_kernel void @contract_caller(ptr addrspace(1) %records,
                                          ptr addrspace(1) %uniform_seed,
                                          i32 %grid_x) #0 {
entry:
  %tx = call i32 @llvm.amdgcn.workitem.id.x()
  %ty = call i32 @llvm.amdgcn.workitem.id.y()
  %bx = call i32 @llvm.amdgcn.workgroup.id.x()
  %by = call i32 @llvm.amdgcn.workgroup.id.y()
  %row = mul i32 %by, %grid_x
  %block = add i32 %row, %bx
  %block_offset = mul i32 %block, 256
  %thread_row = mul i32 %ty, 32
  %local = add i32 %thread_row, %tx
  %index = add i32 %block_offset, %local
  %index64 = zext i32 %index to i64
  %word_offset = mul i64 %index64, 16
  %record = getelementptr i32, ptr addrspace(1) %records, i64 %word_offset
  %address = ptrtoint ptr addrspace(1) %record to i64
  %before = load volatile i32, ptr addrspace(1) %record, align 4
  %seed = load volatile i32, ptr addrspace(1) %uniform_seed, align 4
  %live_lane = xor i32 %before, 610839776
  %live_uniform = xor i32 %seed, -1515870811
  %r0 = call i32 @contract_stage(i32 %bx, i32 %by, i64 %address,
                                i32 %tx, i32 %ty, i32 37)
  %r1 = call i32 @contract_stage(i32 %bx, i32 %by, i64 %address,
                                i32 %tx, i32 %ty, i32 -1590330947)
  %combined = xor i32 %r0, %r1
  %p1 = getelementptr i32, ptr addrspace(1) %record, i32 1
  %p2 = getelementptr i32, ptr addrspace(1) %record, i32 2
  %p3 = getelementptr i32, ptr addrspace(1) %record, i32 3
  %p4 = getelementptr i32, ptr addrspace(1) %record, i32 4
  %p5 = getelementptr i32, ptr addrspace(1) %record, i32 5
  store i32 %r0, ptr addrspace(1) %p1, align 4
  store i32 %r1, ptr addrspace(1) %p2, align 4
  store i32 %live_lane, ptr addrspace(1) %p3, align 4
  store i32 %live_uniform, ptr addrspace(1) %p4, align 4
  store i32 %combined, ptr addrspace(1) %p5, align 4
  ret void
}

attributes #0 = { nounwind "amdgpu-flat-work-group-size"="256,256" "amdgpu-asm-full-wave-calls"="true" "amdgpu-no-gpr-spill" "amdgpu-no-private-memory" "target-cpu"="gfx1250" "target-features"="+wavefrontsize32" }
attributes #1 = { convergent noinline nounwind norecurse "amdgpu-asm-contract"="1" "amdgpu-asm-arg-regs"="s0,s1,v[0:1],v2,v3,s2" "amdgpu-asm-result-reg"="v4" "amdgpu-asm-clobbers"="s[4:6],s40,s48,s63,v[4:9],v64,v72,v95,scc" "amdgpu-asm-vgpr-count"="96" "amdgpu-asm-sgpr-count"="64" "amdgpu-asm-private-bytes"="0" }
