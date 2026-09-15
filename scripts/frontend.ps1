$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $projectRoot 'frontend')
try {
    & npm.cmd run dev
    if ($LASTEXITCODE -ne 0) { throw 'Frontend server failed.' }
} finally { Pop-Location }
