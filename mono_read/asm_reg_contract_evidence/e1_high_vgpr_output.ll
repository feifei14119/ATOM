target triple = "amdgcn-amd-amdhsa"
define amdgpu_kernel void @hi_out(ptr addrspace(1) %p) #0 {
  %x = call i32 asm sideeffect "v_mov_b32 $0, 1", "={v300}"()
  store i32 %x, ptr addrspace(1) %p
  ret void
}
attributes #0 = { "amdgpu-flat-work-group-size"="256,256" }
