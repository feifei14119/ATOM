ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin
HIP_CLANG := $(LLVM)/clang++
DEVICE ?= 0
BUILD ?= build
# This is an existing gfx1100 assembly snapshot; changing -mcpu cannot port it.
ARCH := gfx1100
# Override STAGE_CO to consume a supplied ELF REL binary without its assembly.
STAGE_CO ?= $(BUILD)/stage_sub.co
VGPR_FIRST ?= 40
VGPR_COUNT ?= 8

DEVICE_FLAGS := -x hip -std=c++17 -O2 -Wall -Wextra --offload-arch=$(ARCH) --offload-device-only -fgpu-rdc
HOST_FLAGS := -std=c++17 -O2 -Wall -Wextra -D__HIP_PLATFORM_AMD__ -I$(ROCM_PATH)/include
HOST_LIBS := -L$(ROCM_PATH)/lib -Wl,-rpath,$(ROCM_PATH)/lib -lamdhip64
HEADERS := mono_abi.h mailbox.h stages/sub_api.h stages/scale.h stages/relu.h

.DELETE_ON_ERROR:
.PHONY: all stage kernel host run inspect check clean FORCE
all: host check
host: $(BUILD)/mono_demo
kernel: $(BUILD)/mono_kernel.co
stage: $(BUILD)/stage_sub.co

$(BUILD):
	mkdir -p $@

# The .co suffix here names a linkable ELF REL object, not a launchable module.
# SUB_DEVICE_ONLY suppresses the standalone kernel and its descriptor/metadata.
$(BUILD)/stage_sub.co: stages/sub_kernel.s Makefile | $(BUILD)
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -Wa,-defsym,SUB_DEVICE_ONLY=1 -c $< -o $@

# HIP RDC emits bitcode first; a second compilation lowers it to native ELF REL.
$(BUILD)/mono_kernel.bc: mono_kernel.cpp $(HEADERS) Makefile | $(BUILD)
	$(HIP_CLANG) $(DEVICE_FLAGS) -c $< -o $@

$(BUILD)/mono_kernel.o: $(BUILD)/mono_kernel.s Makefile
	$(HIP_CLANG) --target=amdgcn-amd-amdhsa -mcpu=$(ARCH) -x assembler -c $< -o $@

FORCE:

$(BUILD)/regmask.config: FORCE | $(BUILD)
	@python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); s="\n".join(sys.argv[2:])+"\n"; p.write_text(s) if not p.exists() or p.read_text()!=s else None' "$@" "$(VGPR_FIRST)" "$(VGPR_COUNT)" "$(abspath $(STAGE_CO))"

$(BUILD)/mono_kernel.s: $(BUILD)/mono_kernel.bc $(STAGE_CO) callsite_regmask.py Makefile $(BUILD)/regmask.config
	python3 callsite_regmask.py --bitcode $< --stage $(STAGE_CO) --output $@ --llvm-bin $(LLVM) --vgpr-first $(VGPR_FIRST) --vgpr-count $(VGPR_COUNT)

$(BUILD)/mono_kernel.co: $(BUILD)/mono_kernel.o $(STAGE_CO) Makefile
	$(LLVM)/ld.lld -shared --no-undefined $(BUILD)/mono_kernel.o $(STAGE_CO) -o $@

$(BUILD)/mono_demo: mono_demo.cpp mono_abi.h Makefile | $(BUILD)
	$(CXX) $(HOST_FLAGS) $< $(HOST_LIBS) -o $@

run: host check
	$(BUILD)/mono_demo $(DEVICE) $(BUILD)/mono_kernel.co

inspect: kernel $(BUILD)/mono_kernel.s
	$(LLVM)/llvm-dis $(BUILD)/mono_kernel.bc -o $(BUILD)/mono_kernel.ll
	$(LLVM)/llvm-readelf -h -s -r $(STAGE_CO) > $(BUILD)/stage_sub.elf.txt
	$(LLVM)/llvm-readelf -h -s -r $(BUILD)/mono_kernel.o > $(BUILD)/mono_kernel.object.txt
	$(LLVM)/llvm-readelf -h -s -r -n $(BUILD)/mono_kernel.co > $(BUILD)/mono_kernel.elf.txt
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=stage_sub_device $(STAGE_CO) > $(BUILD)/stage_sub.disasm.txt
	$(LLVM)/llvm-objdump --mcpu=$(ARCH) --disassemble-symbols=mono_kernel,stage_sub_device $(BUILD)/mono_kernel.co > $(BUILD)/mono_kernel.disasm.txt

check: inspect
	python3 checks/check_link.py $(BUILD) $(STAGE_CO)

clean:
	rm -rf $(BUILD)
