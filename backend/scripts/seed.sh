#!/usr/bin/env bash
set -Eeuo pipefail

backend_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$backend_root"

python_executable="${PYTHON:-python3}"
if [[ -x .venv/bin/python ]]; then
  python_executable=".venv/bin/python"
fi

"$python_executable" -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); r=c.post('/api/seed'); print(r.json()); r.raise_for_status()"

