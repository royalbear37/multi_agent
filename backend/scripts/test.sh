#!/usr/bin/env bash
set -Eeuo pipefail

backend_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
project_root="$(cd -- "$backend_root/.." && pwd)"
cd "$backend_root"

python_executable="${PYTHON:-python3}"
if [[ -x .venv/bin/python ]]; then
  python_executable=".venv/bin/python"
fi

test_root="$project_root/data/runtime/tests"
mkdir -p "$test_root"
test_temp="$test_root/$(date +%s)-$$-${RANDOM:-0}"
if [[ -e "$test_temp" ]]; then
  echo "Test temporary directory must be new: $test_temp" >&2
  exit 1
fi

"$python_executable" -m pytest --basetemp "$test_temp" -q --tb=short

