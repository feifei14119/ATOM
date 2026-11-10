ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin
CLANG := $(LLVM)/clang++
BUILD ?= build
DEVICE ?=
ARCH := gfx1100
DEVICE_FLAGS := -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(ARCH) --offload-device-only -fgpu-rdc
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.PHONY: all stage inspect check run clean
all: $(BUILD)/caller.co $(BUILD)/test
stage: $(BUILD)/stage_probe.co

$(BUILD):
	mkdir -p $@

# Fully self-contained assembly, no .inc and no inline machine-code embedding.
$(BUILD)/stage_probe.co: stage_probe.s Makefile | $(BUILD)
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -c $< -o $@

$(BUILD)/caller.bc: caller.cpp stage_api.h test_types.h Makefile | $(BUILD)
	$(CLANG) $(DEVICE_FLAGS) -c $< -o $@

# Change only the two target calls' preservation masks BEFORE register
# allocation. Continue LLVM codegen and assemble the resulting caller normally.
$(BUILD)/caller.s: $(BUILD)/caller.bc $(BUILD)/stage_probe.co callsite_regmask.py Makefile
	python3 callsite_regmask.py --bitcode $(BUILD)/caller.bc --stage $(BUILD)/stage_probe.co --output $@ --llvm-bin $(LLVM)

$(BUILD)/caller.o: $(BUILD)/caller.s Makefile
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -c $< -o $@

$(BUILD)/caller.co: $(BUILD)/caller.o $(BUILD)/stage_probe.co Makefile
	$(LLVM)/ld.lld -shared --no-undefined $(BUILD)/caller.o $(BUILD)/stage_probe.co -o $@

$(BUILD)/test: test.cpp test_types.h Makefile | $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

inspect: all
	$(LLVM)/llvm-dis $(BUILD)/caller.bc -o $(BUILD)/caller.ll
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=caller_kernel,stage_probe_lowctx $(BUILD)/caller.co > $(BUILD)/caller.disasm.txt
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=stage_probe_lowctx $(BUILD)/stage_probe.co > $(BUILD)/stage_probe.disasm.txt
	$(LLVM)/llvm-readelf -h -s -r -n $(BUILD)/caller.co > $(BUILD)/caller.elf.txt

check: inspect
	python3 verify.py $(BUILD)
	$(BUILD)/test $(BUILD)/caller.co $(DEVICE) | tee $(BUILD)/test.log

run: check

clean:
	rm -rf $(BUILD)
