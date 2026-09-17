#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$project_root/backend/.venv/bin/python" || ! -d "$project_root/frontend/node_modules" ]]; then
  echo "Dependencies are missing. Run: bash scripts/setup.sh" >&2
  exit 1
fi

run_e2e=false
if [[ "${1:-}" == "--e2e" ]]; then
  run_e2e=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: bash scripts/test.sh [--e2e]" >&2
  exit 2
fi

cd "$project_root/backend"
test_root="$project_root/data/runtime/tests"
mkdir -p "$test_root"
test_temp="$test_root/$(date +%s)-$$-${RANDOM:-0}"
if [[ -e "$test_temp" ]]; then
  echo "Test temporary directory must be new: $test_temp" >&2
  exit 1
fi

.venv/bin/python -m pytest \
  --basetemp "$test_temp" \
  --cov=app \
  --cov-report=term \
  --cov-report=json:../docs/coverage.json \
  -q --tb=short

cd "$project_root/frontend"
npm run build
npm test

if [[ "$run_e2e" == true ]]; then
  export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"
  npx --no-install playwright install chromium
  npm run e2e
fi

