ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin
CLANG := $(LLVM)/clang++
BUILD ?= build
# Leave empty to auto-select gfx1100. Example: make check DEVICE=0
DEVICE ?=
ARCH := gfx1100
DEVICE_FLAGS := -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(ARCH) --offload-device-only -fgpu-rdc -I$(BUILD)
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64
# Resource contract for the opaque external ASM; not a register allocation cap.
CODEGEN_FLAGS := -mllvm -amdgpu-assume-external-call-stack-size=528
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.PHONY: all stage inspect check run clean
all: $(BUILD)/caller.co $(BUILD)/test
stage: $(BUILD)/stage_probe.co

$(BUILD):
	mkdir -p $@

# ET_REL device function, not a launchable HSACO.
$(BUILD)/stage_probe.co: stage_probe.s Makefile | $(BUILD)
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -c $< -o $@

$(BUILD)/caller.bc: caller.cpp stage_api.h test_types.h Makefile | $(BUILD)
	$(CLANG) $(DEVICE_FLAGS) -c $< -o $@

$(BUILD)/caller.o: $(BUILD)/caller.bc Makefile
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -nogpulib -x ir -O2 $(CODEGEN_FLAGS) -c $< -o $@

$(BUILD)/caller.co: $(BUILD)/caller.o $(BUILD)/stage_probe.co Makefile
	$(LLVM)/ld.lld -shared --no-undefined $(BUILD)/caller.o $(BUILD)/stage_probe.co -o $@

$(BUILD)/test: test.cpp test_types.h Makefile | $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

# Reading material only. Neither .ll nor .s is patched or fed into the build.
inspect: all
	$(LLVM)/llvm-dis $(BUILD)/caller.bc -o $(BUILD)/caller.ll
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -nogpulib -x ir -O2 $(CODEGEN_FLAGS) -S $(BUILD)/caller.bc -o $(BUILD)/caller.s
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=caller_kernel,stage_probe $(BUILD)/caller.co > $(BUILD)/caller.disasm.txt
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=stage_probe $(BUILD)/stage_probe.co > $(BUILD)/stage_probe.disasm.txt
	$(LLVM)/llvm-readelf -h -s -r -n $(BUILD)/caller.co > $(BUILD)/caller.elf.txt

check: inspect
	python3 verify.py check device $(BUILD)
	$(BUILD)/test $(BUILD)/caller.co $(DEVICE) | tee $(BUILD)/test.log

run: all
	$(BUILD)/test $(BUILD)/caller.co $(DEVICE)

clean:
	rm -rf $(BUILD)
