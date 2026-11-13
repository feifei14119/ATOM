ROCM_PATH ?= /opt/rocm
LLVM ?= $(ROCM_PATH)/lib/llvm/bin
BUILD ?= build
DEVICE ?=
CXX ?= c++
MC_FLAGS := -triple=amdgcn-amd-amdhsa -mcpu=gfx1250 -mattr=+wavefrontsize32,+real-true16 -filetype=obj
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.PHONY: all objects inspect host check run clean

# Default builds binaries only, without executing the host test.
all: $(BUILD)/demo.co

$(BUILD):
	mkdir -p $@

$(BUILD)/kernel_A.o: kernel_A.s Makefile | $(BUILD)
	$(LLVM)/llvm-mc $(MC_FLAGS) $< -o $@

$(BUILD)/kernel_B.o: kernel_B.s Makefile | $(BUILD)
	$(LLVM)/llvm-mc $(MC_FLAGS) $< -o $@

objects: $(BUILD)/kernel_A.o $(BUILD)/kernel_B.o

$(BUILD)/demo.co: $(BUILD)/kernel_A.o $(BUILD)/kernel_B.o Makefile
	$(LLVM)/ld.lld -shared --no-undefined --build-id=none $(BUILD)/kernel_A.o $(BUILD)/kernel_B.o -o $@

inspect: $(BUILD)/demo.co
	$(LLVM)/llvm-readelf -h -s -r $(BUILD)/kernel_A.o > $(BUILD)/kernel_A.elf.txt
	$(LLVM)/llvm-readelf -h -s -r $(BUILD)/kernel_B.o > $(BUILD)/kernel_B.elf.txt
	$(LLVM)/llvm-readelf -h -s -r -n $(BUILD)/demo.co > $(BUILD)/demo.elf.txt
	$(LLVM)/llvm-objdump -dr --mcpu=gfx1250 $(BUILD)/kernel_A.o > $(BUILD)/kernel_A.disasm.txt
	$(LLVM)/llvm-objdump -dr --mcpu=gfx1250 $(BUILD)/kernel_B.o > $(BUILD)/kernel_B.disasm.txt
	$(LLVM)/llvm-objdump -d --mcpu=gfx1250 $(BUILD)/demo.co > $(BUILD)/demo.disasm.txt

$(BUILD)/test: test.cpp Makefile | $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

host: $(BUILD)/test

# Explicitly requested commands only: check runs offline checks, run uses GPU.
check: inspect
	python3 verify.py $(BUILD)

run: $(BUILD)/demo.co $(BUILD)/test
	$(BUILD)/test $(BUILD)/demo.co $(DEVICE)

clean:
	rm -rf $(BUILD)
