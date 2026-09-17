#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root/backend"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing backend/.venv. Run: bash scripts/setup.sh" >&2
  exit 1
fi

export RAG_RETRIEVAL_MODE=lexical
export LLM_PROVIDER=mock

.venv/bin/python scripts/prepare_demo.py
exec .venv/bin/python -m uvicorn app.main:app \
  --host "${BACKEND_HOST:-127.0.0.1}" \
  --port "${BACKEND_PORT:-8000}"

