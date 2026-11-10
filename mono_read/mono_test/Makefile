ROCM_PATH ?= $(shell hipconfig --path)
HIP_CLANG ?= $(ROCM_PATH)/llvm/bin/clang++
HIP_LLD ?= $(ROCM_PATH)/llvm/bin/ld.lld
PYTHON ?= python3
GPU_ARCH ?= gfx1100
DEVICE ?= 0
TARGET := build/mono_demo
CODE_OBJECT := build/mono_kernel.hsaco
MONO_BITCODE := build/mono_kernel.bc
MONO_OBJECT := build/mono_kernel.o
MONO_ASSEMBLY := build/mono_kernel.s
MONO_CALL_ASSEMBLY := build/mono_kernel_call.s
MONO_CALL_OBJECT := build/mono_kernel_call.o
CALL_CODE_OBJECT := build/mono_kernel_call.hsaco
DEVICE_HEADERS := mono_abi.h mailbox.h stages/sub_api.h stages/scale.h stages/relu.h
# A vendor can supply this binary directly; no sub implementation source needed.
STAGE_SUB_OBJECT ?= build/stage_sub.o
SUB_BITCODE := build/sub.bc
SUB_OBJECT := build/sub.o
SUB_ASSEMBLY := build/sub.s
SUB_ASM_OBJECT := build/sub_from_asm.o
SUB_CODE_OBJECT := build/sub.hsaco
SUB_TARGET := build/sub_demo

.DELETE_ON_ERROR:

.PHONY: all host kernel kernel-call run-call check-branches stage-sub-object sub-object sub-asm sub-code-object run-sub run asm clobber run-clobber check-clobber boundary run-boundary check-boundary clean

all: host kernel

host: $(TARGET)

kernel: $(CODE_OBJECT)

sub-object: $(SUB_OBJECT)

# Library form: no standalone sub_kernel entry or metadata in this object.
stage-sub-object: $(STAGE_SUB_OBJECT)

build/stage_sub.o: $(SUB_ASSEMBLY) Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(GPU_ARCH) -x assembler -Wa,-defsym,SUB_DEVICE_ONLY=1 -c $< -o $@

# Editable gfx1100 assembly with a launchable entry, descriptor and metadata.
sub-asm: $(SUB_ASSEMBLY)

sub-code-object: $(SUB_CODE_OBJECT)

$(SUB_ASSEMBLY): stages/sub_kernel.s
	@mkdir -p build
	cp $< $@

$(SUB_ASM_OBJECT): $(SUB_ASSEMBLY) Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(GPU_ARCH) -x assembler -c $< -o $@

$(SUB_CODE_OBJECT): $(SUB_ASM_OBJECT) Makefile
	$(HIP_LLD) -shared --no-undefined $< -o $@

$(SUB_TARGET): sub_demo.cpp mono_abi.h Makefile
	@mkdir -p build
	$(CXX) -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include $< -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64 -o $@

run-sub: $(SUB_TARGET) $(SUB_CODE_OBJECT)
	./$(SUB_TARGET) $(DEVICE) $(SUB_CODE_OBJECT)

# HIP separate device compilation first emits LLVM bitcode. Lower it through
# the AMDGPU backend to a real relocatable ELF object with GPU machine code.
$(SUB_BITCODE): stages/sub.cpp stages/sub.h mailbox.h mono_abi.h Makefile
	@mkdir -p build
	$(HIP_CLANG) -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(GPU_ARCH) --offload-device-only -fgpu-rdc -c $< -o $@

$(SUB_OBJECT): $(SUB_BITCODE) Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(GPU_ARCH) -nogpulib -x ir -O2 -c $< -o $@

# The host uses a regular C++ compiler: it contains no GPU kernel or fat binary.
$(TARGET): mono_demo.cpp mono_abi.h Makefile
	@mkdir -p build
	$(CXX) -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include $< -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64 -o $@

# Compile only the caller and inline scale/relu stages. The external subtraction
# remains an undefined device symbol until the final ELF link.
$(MONO_BITCODE): mono_kernel.cpp $(DEVICE_HEADERS) Makefile
	@mkdir -p build
	$(HIP_CLANG) -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(GPU_ARCH) --offload-device-only -fgpu-rdc -c $< -o $@

$(MONO_CALL_OBJECT): $(MONO_BITCODE) Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(GPU_ARCH) -nogpulib -x ir -O2 -c $< -o $@

$(CALL_CODE_OBJECT): $(MONO_CALL_OBJECT) $(STAGE_SUB_OBJECT) Makefile
	$(HIP_LLD) -shared --no-undefined $(MONO_CALL_OBJECT) $(STAGE_SUB_OBJECT) -o $@

kernel-call: $(CALL_CODE_OBJECT)

run-call: host kernel-call
	./$(TARGET) $(DEVICE) $(CALL_CODE_OBJECT)

# Fuse the opaque leaf before assembly so short branches resolve locally.
$(MONO_ASSEMBLY): $(MONO_CALL_ASSEMBLY) $(STAGE_SUB_OBJECT) fuse_sub.py Makefile
	$(PYTHON) fuse_sub.py --caller $(MONO_CALL_ASSEMBLY) --stage $(STAGE_SUB_OBJECT) --output $@ --llvm-bin $(ROCM_PATH)/llvm/bin

$(MONO_OBJECT): $(MONO_ASSEMBLY) Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(GPU_ARCH) -x assembler -c $< -o $@

$(CODE_OBJECT): $(MONO_OBJECT) Makefile
	$(HIP_LLD) -shared --no-undefined $< -o $@

run: all check-branches
	./$(TARGET) $(DEVICE) $(CODE_OBJECT)

check-branches: $(CODE_OBJECT)
	$(ROCM_PATH)/llvm/bin/llvm-objdump --mcpu=$(GPU_ARCH) --disassemble-symbols=mono_kernel $< > build/mono_kernel.disasm.txt
	$(PYTHON) -c 'import pathlib,re; s=pathlib.Path("build/mono_kernel.disasm.txt").read_text(); assert "<mono_kernel>:" in s; assert not re.search(r"\bs_(?:getpc|setpc|swappc)_b64\b",s); print("PASS: mono_kernel has no getpc/swappc/setpc instructions")'

# Final assembly embeds the stage's machine-code words; *_call.s is the input.
asm: $(MONO_ASSEMBLY)

$(MONO_CALL_ASSEMBLY): $(MONO_BITCODE) Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(GPU_ARCH) -nogpulib -x ir -O2 -S $< -o $@

clobber:
	$(MAKE) -C clobber all ROCM_PATH="$(ROCM_PATH)" DEVICE="$(DEVICE)"

run-clobber:
	$(MAKE) -C clobber run ROCM_PATH="$(ROCM_PATH)" DEVICE="$(DEVICE)"

check-clobber:
	$(MAKE) -C clobber check ROCM_PATH="$(ROCM_PATH)" DEVICE="$(DEVICE)"

boundary:
	$(MAKE) -C compiler_boundary all ROCM_PATH="$(ROCM_PATH)" DEVICE="$(DEVICE)"

run-boundary:
	$(MAKE) -C compiler_boundary run ROCM_PATH="$(ROCM_PATH)" DEVICE="$(DEVICE)"

check-boundary:
	$(MAKE) -C compiler_boundary check ROCM_PATH="$(ROCM_PATH)" DEVICE="$(DEVICE)"

clean:
	rm -rf build
