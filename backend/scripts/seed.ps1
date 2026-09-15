$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot
$pythonExe = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { 'python' }
& $pythonExe -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); r=c.post('/api/seed'); print(r.json()); r.raise_for_status()"
if ($LASTEXITCODE -ne 0) { throw 'Synthetic seed failed.' }
