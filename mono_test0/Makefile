ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin
CLANG := $(LLVM)/clang++
DEVICE ?= 0
BUILD ?= build
# The supplied assembly is specific to gfx1100 / ROCm 7.2.
ARCH := gfx1100
STAGE_CO ?= $(BUILD)/stage_sub.co

HEADERS := mono_abi.h mailbox.h stages/sub_api.h stages/scale.h stages/relu.h
DEVICE_FLAGS := -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(ARCH) --offload-device-only -fgpu-rdc
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64

.DELETE_ON_ERROR:
.PHONY: all stage kernel host run inspect clean
all: host kernel
host: $(BUILD)/mono_demo
kernel: $(BUILD)/mono_kernel.co
stage: $(BUILD)/stage_sub.co

$(BUILD):
	mkdir -p $@

# This .co is a relocatable device-function object, not a launchable kernel.
$(BUILD)/stage_sub.co: stages/sub_kernel.s Makefile | $(BUILD)
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -c $< -o $@

# Standard separate compilation: HIP -> LLVM bitcode -> native GPU object.
# No inline asm injection, MIR editing, custom regmask or register limits.
$(BUILD)/mono_kernel.bc: mono_kernel.cpp $(HEADERS) Makefile | $(BUILD)
	$(CLANG) $(DEVICE_FLAGS) -c $< -o $@

$(BUILD)/mono_kernel.o: $(BUILD)/mono_kernel.bc Makefile
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -nogpulib -x ir -O2 -c $< -o $@

$(BUILD)/mono_kernel.co: $(BUILD)/mono_kernel.o $(STAGE_CO) Makefile
	$(LLVM)/ld.lld -shared --no-undefined $(BUILD)/mono_kernel.o $(STAGE_CO) -o $@

$(BUILD)/mono_demo: mono_demo.cpp mono_abi.h Makefile | $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

run: all
	$(BUILD)/mono_demo $(DEVICE) $(BUILD)/mono_kernel.co

# Optional reading material only; these files are never patched or linked.
inspect: kernel
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -nogpulib -x ir -O2 -S $(BUILD)/mono_kernel.bc -o $(BUILD)/mono_kernel.s
	$(LLVM)/llvm-readelf -h -s -r $(STAGE_CO) > $(BUILD)/stage_sub.elf.txt
	$(LLVM)/llvm-readelf -h -s -r -n $(BUILD)/mono_kernel.co > $(BUILD)/mono_kernel.elf.txt
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=mono_kernel,stage_sub_device $(BUILD)/mono_kernel.co > $(BUILD)/mono_kernel.disasm.txt

clean:
	rm -rf $(BUILD)
