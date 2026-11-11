#!/usr/bin/env bash
set -euo pipefail
test_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
atom_dir="$(cd -- "$test_dir/.." && pwd)"
mkdir -p "$test_dir/build"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$atom_dir${PYTHONPATH:+:$PYTHONPATH}"
py="${PYTHON:-python3}"
deadline="${MONO_TEST_TIMEOUT_SECONDS:-1800}"
# the deadline covers the JIT as well as the launches; PASS is printed only by run_test.py
timeout --signal=TERM --kill-after=10s "${deadline}s" "$py" -u "$test_dir/run_test.py" "$@" 2>&1 \
    | grep --line-buffered -v '^\[aiter\]' | tee "$test_dir/build/run.log"
