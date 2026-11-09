ROCM_PATH ?= /opt/rocm
LLVM := $(ROCM_PATH)/llvm/bin

.DELETE_ON_ERROR:
.PHONY: all check clean
all: dq_convert.inline.s dq_convert.inline.co dq_convert.inline.words.inc inline_contract.json dq_convert.inline.disasm.txt

dq_convert.inline.s dq_convert.inline.co dq_convert.inline.words.inc inline_contract.json dq_convert.inline.disasm.txt &: dq_convert.original.s prepare.py Makefile
	python3 prepare.py --llvm-bin $(LLVM)

check: all
	python3 verify.py --llvm-bin $(LLVM)

clean:
	rm -rf build __pycache__
	rm -f dq_convert.inline.s dq_convert.inline.co dq_convert.inline.words.inc inline_contract.json dq_convert.inline.disasm.txt verification.json
