# A2A Task Response Compatibility

日期：2026-10-28（Asia/Taipei）。本輪只有 Parser 修正、離線測試與 GetTask 指令準備，未讀取真實 Key、未發送 GetTask／SendMessage 或其他網路請求，未提交 Commit。

## 已觀察事實與修正

上次工研院回應的 JSON-RPC `result` 直接包含 Task：`id`、`contextId`、`status`、`metadata`。Task ID 為 `29f4d601440343918e32dbc8e6c099a8`，狀態 `TASK_STATE_SUBMITTED`，status.message 為「已受理，排隊中」。這是觀察到的排隊受理回應，不是最終模型答案、L1 路由證明或 Clinical Gold。

`backend/app/integrations/a2a/contracts.py:parse_response` 現在讓 SendMessage／GetTask 接受兩種 Task 包裝：

- `result.task` 包含 Task。
- `result` 本身是 Task。

兩者都進入原本相同的 Task 驗證：非空字串 id、object status、八種已知 state；status.message、history、artifacts 等保留原有驗證。不以存在 id 為充分條件，不修改收到的資料，不做版本切換、二次請求或猜測修補。wrapped Message 維持原行為；GetTask 不接受 Message。

`message`／`task` 同時存在，或包裝與直接 Task 的 id／status 混在同一層，均拒絕。JSON-RPC version／id 對應、result/error 互斥、數字 RPC error、嚴格 JSON 驗證仍先執行，不吞掉 RPC error 或無效狀態。

## Fixture 與離線結果

新增 `backend/tests/integrations/a2a/fixtures/itri_submitted_task_redacted.json`，保存去敏 response 與來源 provenance，測試不依賴 runtime 原檔存在。

- 類型：`observed_redacted_transport_response`，clinical_gold=false。
- 來源：`data/runtime/a2a-l1-ee1338fbc099498fa742474d7554ff47-diagnostic.json`。
- 原檔 SHA256：`aec3f3fc94497f5e46ac8a34636a3bd65c3d6dc13b8cf7c33f41cedc30535ef3`。
- 原始 fixture replay 保留實際 RPC ID／Task ID／狀態／文字；其他 state 與 invalid cases 明確為 synthetic variants。

新增 `test_task_layouts.py`；既有診斷測試中原本用 valid direct Task 當解析失敗輸入，改成 history 型別錯誤的 Task，保留「真正解析失敗才保存」的原測試目的。

本輪 A2A tests：**242 passed，0 failed／errors／skipped，0.90 秒**。包括兩種包裝、八種狀態、缺失欄位、只有 id 的任意物件、歧義包裝、RPC error、Message、GetTask ID、單次 transport 與 CLI 不重送／不進入下一輪 Polling。全程使用 socket／DNS 封鎖及 MockTransport，沒有讀取真實 Key。

證據：`data/runtime/a2a-task-parser-20261028-nl9974x8/unit.xml`、`run_offline.py`、`protected-check.json`。原始診斷 hash 未變；對既有基線中的 5,753 個 data／Agent／Workflow／RAG／Evaluation 檔案核對，無變動或遺失。本輪未重跑完整 Backend Regression；前一輪的 654 passed 不當作本輪結果。

## 唯一一次 GetTask：僅準備，未獲准執行

此指令將透過 `ITRI_A2A_API_KEY` 讀取同一 PowerShell 視窗中安全輸入的**新工研院 Token**，不讀 LLM_API_KEY 或舊 Grant。上次 CLI finally 已清除 Token，獲准執行後須先依 Minimal Client 文件重新安全輸入，不能貼進聊天或命令文字。

**下列為未執行的準備命令，必須等研究者明確批准一次 GetTask。**

```powershell
Set-Location -LiteralPath 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent\backend'
if ([string]::IsNullOrWhiteSpace($env:ITRI_A2A_API_KEY)) {
    throw '請先在同一視窗安全輸入新的工研院 Token。'
}
$env:ITRI_A2A_ENDPOINT = 'https://antibiotic-a2a.furryland.uk/a2a'
$taskLabel = [Guid]::NewGuid().ToString('N')
$taskDirectory = 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent\data\runtime'
$taskOutput = Join-Path $taskDirectory ("a2a-gettask-$taskLabel.json")
$taskDiagnostic = Join-Path $taskDirectory ("a2a-gettask-$taskLabel-diagnostic.json")
try {
    & .\.venv\Scripts\python.exe -X utf8 -B -m scripts.probe_itri_a2a `
      --live --task-id '29f4d601440343918e32dbc8e6c099a8' --poll-count 1 `
      --out $taskOutput --diagnostic-out $taskDiagnostic | Out-Null
    Write-Host "CLI 結束碼：$LASTEXITCODE"
    Write-Host "結果檔：$taskOutput"
    Write-Host "診斷檔：$taskDiagnostic"
}
finally {
    Remove-Item Env:ITRI_A2A_API_KEY -ErrorAction SilentlyContinue
}
```

對應 JSON-RPC method=`GetTask`、params=`{"id":"29f4d601440343918e32dbc8e6c099a8"}`；RPC id 自動產生新 UUID。`--poll-count 1` 明確限制只查一次，不 Sleep、不 Retry、不 SendMessage、不作 L3 提交或建立新 Task。若 Task 過期／不存在／失敗或認證被拒，保存結果後停止，不自動重建 Task。

服務端既有 Task 的處理不會因本機尚未查詢而自動取消；本輪只能確認保存時的 SUBMITTED 狀態。GetTask 是否計費仍依供應商規則，不能宣稱免費。
