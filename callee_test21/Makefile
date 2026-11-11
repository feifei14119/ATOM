ROCM_PATH ?= /opt/rocm
LLVM ?= $(ROCM_PATH)/lib/llvm/bin
BUILD ?= build
DEVICE ?=
# Reuse the already available FlyDSL environment; override on another machine.
PYTHON ?= $(if $(wildcard ../mono_test20/build/venv/bin/python),../mono_test20/build/venv/bin/python,python3)
CXX ?= c++
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -ffp-contract=off -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.PHONY: all build inspect check run clean

all: build $(BUILD)/test

build:
	$(PYTHON) build.py --build-dir $(BUILD) --llvm-bin $(LLVM)

$(BUILD)/test: test.cpp Makefile
	mkdir -p $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

inspect: build
	python3 verify.py $(BUILD) $(LLVM)

check: all
	python3 verify.py $(BUILD) $(LLVM)
	$(BUILD)/test $(BUILD)/demo.co $(DEVICE) | tee $(BUILD)/test.log

run: check

clean:
	rm -rf $(BUILD)
