$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot
$pythonExe = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { 'python' }
& $pythonExe -c "from app.main import repo; repo.migrate(); print('Database migrations applied.')"
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
