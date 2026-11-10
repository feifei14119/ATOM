#!/usr/bin/env bash
set -euo pipefail
mono_test_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$mono_test_dir"
mkdir -p build
export PYTHONDONTWRITEBYTECODE=1
mono_test_python="${PYTHON:-python3}"
mono_test_timeout="${MONO_TEST_TIMEOUT_SECONDS:-900}"
command -v "$mono_test_python" >/dev/null
command -v timeout >/dev/null
if [[ ! "$mono_test_timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo 'MONO_TEST_TIMEOUT_SECONDS must be a positive integer.' >&2
    exit 2
fi
# The deadline covers JIT as well as execution. Numerical PASS is emitted only
# by the Python checker. A timeout or a pipeline error remains a nonzero exit.
timeout --signal=TERM --kill-after=10s "${mono_test_timeout}s" \
    "$mono_test_python" -u "$mono_test_dir/run_test.py" "$@" 2>&1 | tee build/run.log
