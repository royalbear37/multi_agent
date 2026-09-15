$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Could not create Python virtual environment.' } }
$requirementsFile = if (Test-Path requirements.lock.txt) { 'requirements.lock.txt' } else { 'requirements.txt' }
& .\.venv\Scripts\python.exe -m pip install -r $requirementsFile
if ($LASTEXITCODE -ne 0) { throw "Could not install $requirementsFile." }
& .\.venv\Scripts\python.exe -c "from app.main import repo; repo.migrate(); print('Backend environment and database ready.')"
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the backend database.' }
