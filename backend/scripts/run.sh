#!/usr/bin/env bash
set -Eeuo pipefail

backend_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$backend_root"

python_executable="${PYTHON:-python3}"
if [[ -x .venv/bin/python ]]; then
  python_executable=".venv/bin/python"
fi

exec "$python_executable" -m uvicorn app.main:app \
  --host "${BACKEND_HOST:-127.0.0.1}" \
  --port "${BACKEND_PORT:-8000}"

