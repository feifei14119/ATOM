ROCM_PATH ?= $(shell hipconfig --path)
HIP_CLANG ?= $(ROCM_PATH)/llvm/bin/clang++
HIP_LLD ?= $(ROCM_PATH)/llvm/bin/ld.lld
PYTHON ?= python3
DEVICE ?= 0
BUILD ?= ../build/clobber
CLOBBER_STAGE ?= $(BUILD)/stage.co
CONTRACT ?= stage_contract.json

.DELETE_ON_ERROR:
.PHONY: all run check clean
all: $(BUILD)/mono.co $(BUILD)/demo

$(BUILD)/stage.o: stage.s Makefile
	@mkdir -p $(BUILD)
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=gfx1100 -x assembler -c $< -o $@

$(BUILD)/stage.co: $(BUILD)/stage.o Makefile
	$(HIP_LLD) -shared --no-undefined $< -o $@

$(BUILD)/mono.s: generate.py abi.py $(CONTRACT) $(CLOBBER_STAGE) Makefile
	@mkdir -p $(BUILD)
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) generate.py --stage $(CLOBBER_STAGE) --contract $(CONTRACT) --llvm-bin $(ROCM_PATH)/llvm/bin --output $@

$(BUILD)/mono.o: $(BUILD)/mono.s Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=gfx1100 -x assembler -c $< -o $@

$(BUILD)/mono.co: $(BUILD)/mono.o Makefile
	$(HIP_LLD) -shared --no-undefined $< -o $@

$(BUILD)/demo: demo.cpp Makefile
	@mkdir -p $(BUILD)
	$(CXX) -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include $< -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64 -o $@

check: $(BUILD)/mono.co
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) verify.py --stage $(CLOBBER_STAGE) --contract $(CONTRACT) --module $(BUILD)/mono.co --llvm-bin $(ROCM_PATH)/llvm/bin --report $(BUILD)/report.json

run: all check
	$(BUILD)/demo $(DEVICE) $(BUILD)/mono.co $(CLOBBER_STAGE)

clean:
	rm -rf $(BUILD)
