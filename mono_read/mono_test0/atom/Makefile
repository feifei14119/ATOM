ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin
CLANG := $(LLVM)/clang++

.DELETE_ON_ERROR:
.PHONY: all inspect check clean
all: dq_convert.device.co

# The generated .s is standalone and can also be assembled directly.
dq_convert.device.s resources.json &: dq_convert.original.s prepare.py
	python3 prepare.py

dq_convert.device.co: dq_convert.device.s Makefile
	$(CLANG) --target=amdgcn-amd-amdhsa -mcpu=gfx1250 -x assembler -c $< -o $@

inspect: all
	$(LLVM)/llvm-readelf -h -s -r dq_convert.device.co > dq_convert.device.elf.txt
	$(LLVM)/llvm-objdump --mcpu=gfx1250 -d dq_convert.device.co > dq_convert.device.disasm.txt

check: inspect
	python3 verify.py --llvm-bin $(LLVM)

clean:
	rm -f dq_convert.device.co dq_convert.device.elf.txt dq_convert.device.disasm.txt verification.json
	rm -rf build
