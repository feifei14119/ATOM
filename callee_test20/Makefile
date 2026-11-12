ROCM_PATH ?= /opt/rocm
LLVM ?= $(ROCM_PATH)/lib/llvm/bin
PYTHON ?= python3
BUILD ?= build
DEVICE ?=
CXX ?= c++
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -ffp-contract=off -fno-fast-math -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.PHONY: all build unit-test inspect check run clean

# Default builds both the code object and the host test binary; runs no tests.
all: build $(BUILD)/test

build:
	$(PYTHON) mixed_asm.py kernel.s --build-dir $(BUILD) --llvm-bin $(LLVM)

$(BUILD)/test: test.cpp Makefile
	mkdir -p $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

unit-test:
	$(PYTHON) -m unittest -v test_mixed_asm.py

inspect: build
	$(PYTHON) verify.py $(BUILD) $(LLVM)

check: all unit-test
	$(PYTHON) verify.py $(BUILD) $(LLVM)
	$(BUILD)/test $(BUILD)/demo.co $(DEVICE) | tee $(BUILD)/test.log

run: check

clean:
	rm -rf $(BUILD)
