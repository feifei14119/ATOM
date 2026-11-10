target triple = "amdgcn-amd-amdhsa"
declare i32 @llvm.amdgcn.workitem.id.x()
define internal void @frag(i64 inreg %args, i64 %buf) #1 {
  call void asm sideeffect "; FRAG args=$0 buf=$1", "s,v,~{s2},~{s3},~{s40},~{s41},~{v4},~{v5},~{v40},~{v41},~{scc},~{memory}"(i64 %args, i64 %buf)
  ret void
}
define amdgpu_kernel void @caller(ptr addrspace(1) %p, i64 %a) #0 {
  %t = call i32 @llvm.amdgcn.workitem.id.x()
  %g = getelementptr i32, ptr addrspace(1) %p, i32 %t
  %v = load i32, ptr addrspace(1) %g
  %pi = ptrtoint ptr addrspace(1) %g to i64
  call void @frag(i64 inreg %a, i64 %pi)
  %w = add i32 %v, 7
  store i32 %w, ptr addrspace(1) %g
  ret void
}
attributes #0 = { "amdgpu-flat-work-group-size"="256,256" }
attributes #1 = { noinline convergent }
