$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & (Join-Path $projectRoot 'backend/scripts/setup.ps1')
    Set-Location (Join-Path $projectRoot 'frontend')
    & npm.cmd ci --cache .npm-cache --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    Write-Host 'Ready. Run backend/scripts/run.ps1 and scripts/frontend.ps1 in two PowerShell terminals.'
} finally { Pop-Location }
