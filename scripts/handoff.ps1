param([switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $projectRoot 'backend')
try {
    $env:RAG_RETRIEVAL_MODE = 'lexical'
    $env:LLM_PROVIDER = 'mock'
    & .\.venv\Scripts\python.exe scripts/install_handoff.py
    if ($LASTEXITCODE -ne 0) { throw 'Handoff import failed; inspect the error before starting the server.' }
    if (-not $PrepareOnly) {
        & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
        if ($LASTEXITCODE -ne 0) { throw 'Handoff server stopped with an error.' }
    }
} finally { Pop-Location }
