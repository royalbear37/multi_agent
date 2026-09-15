$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot
$pythonExe = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { 'python' }
& $pythonExe -c "import json; from app.main import app; from app.schemas.case import Case; open('../contracts/openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(),ensure_ascii=False,indent=2)); s=json.dumps(Case.model_json_schema(),ensure_ascii=False,indent=2); open('../contracts/case.schema.json','w',encoding='utf-8').write(s); import os; os.makedirs('../contracts/schemas',exist_ok=True); open('../contracts/schemas/case.schema.json','w',encoding='utf-8').write(s)"
Write-Output 'Generated contracts/openapi.json and case.schema.json.'
