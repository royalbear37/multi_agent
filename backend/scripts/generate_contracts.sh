#!/usr/bin/env bash
set -Eeuo pipefail

backend_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$backend_root"

python_executable="${PYTHON:-python3}"
if [[ -x .venv/bin/python ]]; then
  python_executable=".venv/bin/python"
fi

"$python_executable" -c "import json; from pathlib import Path; from app.main import app; from app.schemas.case import Case; root=Path('..'); (root/'contracts').mkdir(exist_ok=True); (root/'contracts'/'schemas').mkdir(exist_ok=True); (root/'contracts'/'openapi.json').write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2),encoding='utf-8'); schema=json.dumps(Case.model_json_schema(),ensure_ascii=False,indent=2); (root/'contracts'/'case.schema.json').write_text(schema,encoding='utf-8'); (root/'contracts'/'schemas'/'case.schema.json').write_text(schema,encoding='utf-8')"
echo "Generated contracts/openapi.json and case.schema.json."

