#!/usr/bin/env bash
set -euo pipefail
TASK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TASK_PYTHON="${PYTHON:-$TASK_DIR/../mono_test20/build/venv/bin/python}"
if [[ "${1:-}" == "--build-only" ]]; then shift; fi
export PYTHONDONTWRITEBYTECODE=1
exec "$TASK_PYTHON" "$TASK_DIR/build.py" "$@"
