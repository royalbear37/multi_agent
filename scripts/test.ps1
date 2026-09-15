param([switch]$E2E)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $projectRoot 'backend')
try {
    $testTemp = Join-Path $projectRoot ('data/runtime/tests/' + [guid]::NewGuid().ToString())
    if (Test-Path -LiteralPath $testTemp) { throw 'Test temporary directory must be new.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $testTemp) | Out-Null
    & .\.venv\Scripts\python.exe -m pytest --basetemp $testTemp --cov=app --cov-report=term --cov-report=json:../docs/coverage.json -q --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
    Set-Location (Join-Path $projectRoot 'frontend')
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    & npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    if ($E2E) {
        $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.playwright'
        & npx.cmd --no-install playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Browser installation failed.' }
        & npm.cmd run e2e
        if ($LASTEXITCODE -ne 0) { throw 'Browser tests failed.' }
    }
} finally { Pop-Location }
