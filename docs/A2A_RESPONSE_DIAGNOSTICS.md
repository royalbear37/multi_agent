# A2A Response Parse Diagnostics

日期：2026-10-28（Asia/Taipei）。本輪只有程式修改與完全離線測試，沒有發送 Live 請求、使用真實 Key、修改核心 Workflow 或提交 Git Commit。

## 功能範圍

新增可選的 `--diagnostic-out`。預設不收集；提供參數時，CLI 在任何 HTTP 請求前以 exclusive-create 保留全新檔案。路徑不存在／檔案已存在即拒絕，不覆寫、不發送請求。

捕捉範圍：完整收到 HTTP JSON 回應後，SendMessage／GetTask 的 JSON／RPC envelope／Message／Task 結構驗證失敗，以及 Task ID 不符或公開 Agent Card 解析失敗。不修改原 Parser 的接受條件，不將解析失敗包裝成成功。

保存資料：

- 原本的固定錯誤碼、HTTP status、RPC code。
- 本機 request_id／message_id（若該操作有）、operation、耗時、回應 byte 數、attempts。
- 去敏後的完整 JSON 結構與 `response_format`，可檢查對方是否使用不同的 result 包裝、欄位或型別。
- `untrusted=true`、`clinical_decision_eligible=false`、`gold_eligible=false`。

不收集 HTTP request body、任何 request／response headers、Endpoint URL，也不在 CLI stdout 顯示診斷 body。正常解析成功、標準 JSON-RPC Error、HTTP Error、Timeout 等不另存回應內容，保留檔只寫 `capture_status=not_recorded`。原本正常 CLI 的已遮蔽結果輸出行為不變。

## 憑證遮蔽與檔案界線

1. 先用 strict_json 解析，再遞迴遮蔽本次 runtime credential（包括出現在 JSON key／value 內及 JSON escape 後還原的字元）、Bearer 字串，以及 token／secret／authorization／api_key／password／cookie 等敏感欄位。
2. 全部去敏、序列化完成後才寫檔；不暫存未遮蔽 raw bytes，不存 base64 備份。
3. 無效 UTF-8、重複 JSON key、NaN 或截斷 JSON 無法可靠逐欄遮蔽，故不保存原文：`response=null`、`response_format=omitted_unparseable_json`，仍保存錯誤與大小資訊。
4. 去敏檔案預算為 2 MiB。超過時省略 response，記為 `omitted_size_limit`，不截斷原始內容。
5. 只保存第一個解析失敗；不覆寫既有檔案、不覆蓋為第二個失敗。每次 CLI 請使用新檔名。
6. 寫檔失敗僅設 `diagnostic_status=write_failed`；不輸出例外全文、不掩蓋原本解析錯誤、不重試。

這是憑證去敏，不是醫療資料去識別。回應仍可能包含研究／臨床文字，應留在本機忽略 Git 的 `data/runtime/`；分享前先人工檢查。刻意編碼成其他形式的秘密不保證可識別，不能把整份檔案直接公開。

## CLI 用法

以下為**未執行的後續 Live 範例**，不是本輪的測試命令或新的付費授權。須先在同一 PowerShell 視窗依 `A2A_MINIMAL_CLIENT.md` 安全輸入工研院 Token，並取得一次可能計費的 L1 操作批准。

```powershell
Set-Location -LiteralPath 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent\backend'
if ([string]::IsNullOrWhiteSpace($env:ITRI_A2A_API_KEY)) {
    throw 'ITRI_A2A_API_KEY is not set in this window.'
}
$env:ITRI_A2A_ENDPOINT = 'https://antibiotic-a2a.furryland.uk/a2a'
$taskId = [Guid]::NewGuid().ToString('N')
$taskDirectory = 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent\data\runtime'
$taskOutput = Join-Path $taskDirectory ('a2a-l1-' + $taskId + '.json')
$taskDiagnostic = Join-Path $taskDirectory ('a2a-l1-' + $taskId + '-diagnostic.json')
try {
    & .\.venv\Scripts\python.exe -X utf8 -B -m scripts.probe_itri_a2a `
      --live --text 'MIC 怎麼判讀？' `
      --out $taskOutput --diagnostic-out $taskDiagnostic | Out-Null
    Write-Host "CLI exit code: $LASTEXITCODE"
    Write-Host "Result: $taskOutput"
    Write-Host "Diagnostic: $taskDiagnostic"
}
finally {
    Remove-Item Env:ITRI_A2A_API_KEY -ErrorAction SilentlyContinue
}
```

每次仍只有一次 SendMessage，沒有 Retry／Redirect／GetTask 或額外 L3 操作。遠端如何路由 Skill 仍未確認；Task 回覆不會觸發自動 Polling。解析失敗時 CLI 仍為 2，主結果僅多出 `diagnostic_status=saved` 或 `write_failed`；不能把診斷檔存在當作推論成功。失敗或 Timeout 後停止，不直接重跑。

## 檔案與驗證

- 新增 `backend/app/integrations/a2a/diagnostics.py`：預先保留檔案、去敏、大小限制、保存一次。
- 修改 `backend/app/integrations/a2a/client.py`：可注入診斷物件，僅於解析錯誤捕捉。
- 修改 `backend/scripts/probe_itri_a2a.py`：新增 CLI 參數與安全錯誤摘要。
- 新增 `backend/tests/integrations/a2a/test_diagnostics.py`：合成 fixtures、封鎖網路。
- 更新 `docs/A2A_MINIMAL_CLIENT.md`：現行用法連結。

A2A Unit Tests：**170 passed**（0 failed／errors／skipped，0.82 秒）。涵蓋 JSON escaped Key、遞迴遮蔽、無效 JSON 省略、大小限制、重複檔案／路徑錯誤在連線前拒絕、寫檔失敗維持原錯誤、單次 HTTP、GetTask／Card 與 CLI 整合。

Backend Regression：**654 passed**（0 failed／errors／skipped，20.16 秒），含上述 A2A suite；有 4 個既有框架棄用警告，兩組通過數不可相加。另核對既有基線中的 5,753 個資料／Agent／Workflow／RAG／Evaluation 檔案，無變動或遺失。

本輪測試證據：`data/runtime/a2a-diagnostics-20261028-i50quzy_/`。runner 移除測試子程序憑證，封鎖外部 socket／DNS，使用獨立 DB／temp；不需 API、Ollama 或 GPU。Mock 診斷只驗證工程行為，不能代表工研院真實回覆或醫療能力。

先前 `a2a-l1-615be1ebae8242e8848c8b8cf0c29c1a.json` 只有 HTTP 200／INVALID_A2A_PAYLOAD 摘要，原文未保存，無法靠此功能回溯還原。需取得供應商去敏 fixture，或另行批准新的一次請求後，才能釐清實際契約差異。
