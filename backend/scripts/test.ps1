$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot
$pythonExe = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { 'python' }
$testTemp = Join-Path $backendRoot ('../data/runtime/tests/' + [guid]::NewGuid().ToString())
if (Test-Path -LiteralPath $testTemp) { throw 'Test temporary directory must be new.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $testTemp) | Out-Null
& $pythonExe -m pytest --basetemp $testTemp -q --tb=short
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
