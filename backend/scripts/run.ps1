$ErrorActionPreference = 'Stop'
# Keep this file ASCII: Windows PowerShell 5.1 reads UTF-8 without a BOM as ANSI.
$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot

function Get-BackendSetting([string]$name, [string]$defaultValue) {
    $configured = [Environment]::GetEnvironmentVariable($name)
    if ($configured) { return $configured.Trim() }
    if (Test-Path -LiteralPath '.env') {
        $line = Get-Content -LiteralPath '.env' | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -Last 1
        if ($line) { return (($line -split '=', 2)[1]).Trim().Trim('"', "'") }
    }
    return $defaultValue
}

if ((Get-BackendSetting 'RAG_RETRIEVAL_MODE' 'embedding') -eq 'embedding') {
    $embeddingBaseUrl = (Get-BackendSetting 'EMBEDDING_BASE_URL' 'http://127.0.0.1:11434').TrimEnd('/')
    $embeddingModel = Get-BackendSetting 'EMBEDDING_MODEL' 'embeddinggemma'
    $embeddingTimeout = [int](Get-BackendSetting 'EMBEDDING_TIMEOUT' '120')
    $ollamaUrl = [uri]$embeddingBaseUrl

    try {
        $null = Invoke-RestMethod -Uri "$embeddingBaseUrl/api/tags" -TimeoutSec 3
    } catch {
        if ($ollamaUrl.Host -notin @('127.0.0.1', 'localhost', '::1') -or $ollamaUrl.Port -ne 11434) {
            throw "Embedding service is unavailable at $embeddingBaseUrl. Start the configured service and retry."
        }
        $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
        $ollamaExe = if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
        if (-not (Test-Path -LiteralPath $ollamaExe)) {
            throw 'Ollama is not running and ollama.exe was not found. Install or start Ollama, then retry.'
        }
        Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Seconds 1
            try {
                $null = Invoke-RestMethod -Uri "$embeddingBaseUrl/api/tags" -TimeoutSec 3
                $ready = $true
                break
            } catch { }
        }
        if (-not $ready) { throw "Ollama was started, but $embeddingBaseUrl is still unavailable." }
    }

    try {
        $body = @{ model = $embeddingModel; input = @('task: search result | query: startup check'); truncate = $false } | ConvertTo-Json -Compress
        $response = Invoke-RestMethod -Uri "$embeddingBaseUrl/api/embed" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec $embeddingTimeout
        if (-not $response.embeddings -or -not $response.embeddings[0].Count) { throw 'The response contains no embedding vector.' }
        Write-Host "Ollama embedding ready: $embeddingModel, $($response.embeddings[0].Count) dimensions."
    } catch {
        throw "Ollama embedding check failed for model $embeddingModel. Run 'ollama pull $embeddingModel' if the model is missing. Error: $($_.Exception.Message)"
    }
}

$pythonExe = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { 'python' }
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw 'Backend server stopped with an error.' }
