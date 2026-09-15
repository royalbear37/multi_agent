$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot
$pythonExe = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { 'python' }
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw 'Backend server stopped with an error.' }
