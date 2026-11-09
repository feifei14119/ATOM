ROCM_PATH ?= $(shell hipconfig --path)
PYTHON ?= python3
DEVICE ?= 0
BUILD ?= ../build/compiler_boundary
# Override STAGE to consume a separately supplied binary. No source dependency
# is introduced for an overridden filename.
STAGE ?= ../build/clobber/stage.co
CONTRACT ?= ../clobber/stage_contract.json

.PHONY: all check run clean
all: check $(BUILD)/demo

../build/clobber/stage.co: ../clobber/stage.s ../clobber/Makefile
	$(MAKE) -C ../clobber ../build/clobber/stage.co ROCM_PATH="$(ROCM_PATH)"

# Small deterministic builds run on each check so changed toolchains and binary
# inputs cannot reuse a stale approval/report.
check: $(STAGE)
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) build.py --llvm-bin $(ROCM_PATH)/llvm/bin --stage $(STAGE) --contract $(CONTRACT) --output $(BUILD)

$(BUILD)/demo: demo.cpp Makefile
	@mkdir -p $(BUILD)
	$(CXX) -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include $< -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64 -o $@

run: all
	$(BUILD)/demo $(DEVICE) $(BUILD) $(STAGE) > $(BUILD)/gpu.log
	cat $(BUILD)/gpu.log

clean:
	rm -rf $(BUILD)
