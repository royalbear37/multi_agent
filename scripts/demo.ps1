$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $projectRoot 'backend')
try {
    # Explicit offline demonstration; does not overwrite backend/.env.
    $env:RAG_RETRIEVAL_MODE = 'lexical'
    $env:LLM_PROVIDER = 'mock'
    & .\.venv\Scripts\python.exe scripts/prepare_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Demo preparation failed.' }
    & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { throw 'Demo server stopped with an error.' }
} finally { Pop-Location }
