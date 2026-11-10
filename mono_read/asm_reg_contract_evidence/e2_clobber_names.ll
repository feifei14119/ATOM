target triple = "amdgcn-amd-amdhsa"
define amdgpu_kernel void @hi(ptr addrspace(1) %p) #0 {
  call void asm sideeffect "; clobber v300", "~{v300}"()
  ret void
}
define amdgpu_kernel void @rng(ptr addrspace(1) %p) #0 {
  call void asm sideeffect "; clobber range", "~{v[4:200]}"()
  ret void
}
define amdgpu_kernel void @tup(ptr addrspace(1) %p) #0 {
  call void asm sideeffect "; clobber tuple", "~{v[4:7]}"()
  ret void
}
define amdgpu_kernel void @lo(ptr addrspace(1) %p) #0 {
  call void asm sideeffect "; clobber v200", "~{v200}"()
  ret void
}
attributes #0 = { "amdgpu-flat-work-group-size"="256,256" }
