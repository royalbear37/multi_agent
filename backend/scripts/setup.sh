#!/usr/bin/env bash
set -Eeuo pipefail

backend_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$backend_root"

python_command="${PYTHON:-python3}"
if [[ -d .venv && ! -x .venv/bin/python ]]; then
  echo "Existing backend/.venv is not a Linux virtual environment." >&2
  echo "Move or remove it, then run setup again." >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  "$python_command" -m venv .venv
fi

requirements_file="requirements.txt"
if [[ -f requirements.lock.txt ]]; then
  requirements_file="requirements.lock.txt"
fi

.venv/bin/python -m pip install -r "$requirements_file"
.venv/bin/python -c "from app.main import repo; repo.migrate(); print('Backend environment and database ready.')"

