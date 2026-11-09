ROCM_PATH ?= /opt/rocm
LLVM_BIN ?= $(ROCM_PATH)/llvm/bin
PYTHON ?= python3
SUPPLIER ?= /home/feifei/repo/aiter/hsa/gfx1250/fmha_v3_bwd/bwd_hd64_dq_convert_bf16.co

.DELETE_ON_ERROR:
.PHONY: all check
all: check

# Grouped outputs are regenerated only if the audited supplier or generator
# changes. Editing either .s then running make assembles that edited source.
GENERATED := dq_convert.original.s dq_convert.mono.s dq_convert.original.co contract.json dq_convert.original.disasm.txt dq_convert.original.elf.txt
$(GENERATED) &: prepare.py $(SUPPLIER)
	$(PYTHON) prepare.py generate --source $(SUPPLIER) --llvm-bin $(LLVM_BIN)

dq_convert.original.o: dq_convert.original.s Makefile
	$(LLVM_BIN)/clang++ --target=amdgcn-amd-amdhsa -mcpu=gfx1250 -x assembler -c $< -o $@

dq_convert.roundtrip.co: dq_convert.original.o Makefile
	$(LLVM_BIN)/ld.lld -shared --no-undefined $< -o $@

dq_convert.mono.o: dq_convert.mono.s Makefile
	$(LLVM_BIN)/clang++ --target=amdgcn-amd-amdhsa -mcpu=gfx1250 -x assembler -c $< -o $@

dq_convert.mono.co: dq_convert.mono.o Makefile
	$(LLVM_BIN)/ld.lld -shared --no-undefined $< -o $@

check: dq_convert.roundtrip.co dq_convert.mono.co $(GENERATED)
	$(PYTHON) prepare.py verify --llvm-bin $(LLVM_BIN)
