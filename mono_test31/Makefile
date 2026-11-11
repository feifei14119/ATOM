PYTHON ?= $(if $(wildcard ../mono_test20/build/venv/bin/python),../mono_test20/build/venv/bin/python,python3)
GPU_PYTHON ?= python3
LLVM_BIN ?= /opt/rocm/lib/llvm/bin
ROWS ?= 6
RANK ?= 0
LAYERS ?= 40
DRAFT_LAYERS ?= 3
PART ?= all
PARTS ?= all
BUILD_DIR ?= build
TP4_DIR ?= build/tp4
TEST_MODE ?= all

.PHONY: all build build-tp4 test test-build test-gpu
all: build

build:
	$(PYTHON) build.py --llvm-bin $(LLVM_BIN) --build-dir $(BUILD_DIR) --rows $(ROWS) --rank $(RANK) --layers $(LAYERS) --draft-layers $(DRAFT_LAYERS) --part $(PART)

build-tp4:
	@for rank in 0 1 2 3; do \
	  for part in $(PARTS); do \
	    $(PYTHON) build.py --llvm-bin $(LLVM_BIN) --build-dir $(TP4_DIR)/rank$$rank/$$part --rows $(ROWS) --rank $$rank --layers $(LAYERS) --draft-layers $(DRAFT_LAYERS) --part $$part || exit $$?; \
	  done; \
	done

# No build or GPU execution is hidden in the CPU unit-test target.
test:
	MONO31_GPU_TEST=0 MONO31_BUILD_TEST=0 $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

test-build:
	MONO31_BUILD_TEST=1 MONO31_GPU_TEST=0 $(PYTHON) -m unittest discover -s tests -p test_build.py -v

test-gpu:
	MONO31_GPU_TEST=1 MONO31_TEST_MODE=$(TEST_MODE) MONO31_MANIFEST_ROOT=$(abspath $(TP4_DIR)) PYTHONPATH=$(CURDIR):$(abspath ..):$$PYTHONPATH $(GPU_PYTHON) -m torch.distributed.run --standalone --nproc_per_node=4 tests/test_gpu.py -v
