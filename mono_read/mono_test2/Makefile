ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin
CLANG := $(LLVM)/clang++
BUILD ?= build
DEVICE ?= 0
ARCH := gfx1100
STAGE_CO ?= $(BUILD)/stage_sub.co
HEADERS := mono_abi.h mailbox.h stages/sub.h stages/scale.h stages/relu.h
DEVICE_FLAGS := -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(ARCH) --offload-device-only -fgpu-rdc -I$(BUILD)
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64

.DELETE_ON_ERROR:
.PHONY: all stage host kernel run inspect check clean
all: host kernel
host: $(BUILD)/mono_demo
kernel: $(BUILD)/mono_kernel.co
stage: $(BUILD)/stage_sub.co

$(BUILD):
	mkdir -p $@

$(BUILD)/stage_sub.co: stages/sub_kernel.s Makefile | $(BUILD)
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -c $< -o $@

$(BUILD)/sub_words.inc: $(STAGE_CO) embed_sub.py Makefile | $(BUILD)
	python3 embed_sub.py --stage $(STAGE_CO) --output $@ --llvm-bin $(LLVM)

# The .long payload is part of inline asm at the HIP -> IR compilation step.
$(BUILD)/mono_kernel.bc: mono_kernel.cpp $(HEADERS) $(BUILD)/sub_words.inc Makefile
	$(CLANG) $(DEVICE_FLAGS) -c $< -o $@

$(BUILD)/mono_kernel.o: $(BUILD)/mono_kernel.bc Makefile
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -nogpulib -x ir -O2 -c $< -o $@

# Only the caller object is linked. The binary stage is already embedded in it.
$(BUILD)/mono_kernel.co: $(BUILD)/mono_kernel.o Makefile
	$(LLVM)/ld.lld -shared --no-undefined $< -o $@

$(BUILD)/mono_demo: mono_demo.cpp mono_abi.h Makefile | $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

run: all
	$(BUILD)/mono_demo $(DEVICE) $(BUILD)/mono_kernel.co

inspect: kernel
	$(LLVM)/llvm-dis $(BUILD)/mono_kernel.bc -o $(BUILD)/mono_kernel.ll
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -nogpulib -x ir -O2 -S $(BUILD)/mono_kernel.bc -o $(BUILD)/mono_kernel.s
	$(LLVM)/llvm-readelf -h -s -r -n $(BUILD)/mono_kernel.co > $(BUILD)/mono_kernel.elf.txt
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=mono_kernel $(BUILD)/mono_kernel.co > $(BUILD)/mono_kernel.disasm.txt

check: inspect
	python3 verify.py $(BUILD)

clean:
	rm -rf $(BUILD)
