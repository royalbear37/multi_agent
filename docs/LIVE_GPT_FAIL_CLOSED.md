# 首次 Live Run：失敗後停止外傳的隔離保護

日期：2026-10-27。這是 `LIVE_GPT_READINESS.md` 之後的操作補充。新增保護僅在 `data/runtime/live-gpt-readiness-20261027/` 的獨立 Backend 啟動時安裝；未修改 backend/app、Agent、Prompt、臨床驗證或既有 Mock 系統。

原本六節點的 HTTP retries=0，但 Workflow 可能修復／重試，遇角色失敗仍會繼續後續角色。這不等於本次要求的「Timeout/API 失敗後不再付費」。本次加入程序內 transport gate，不更改核心 Workflow 原檔。

## 行為

- 只允許官方 OpenAI base URL、指定 snapshot、transport retries=0。
- 需先有單次提交 marker；只接受 request JSON 固定 ID、唯一一筆 running Run、指定 case/revision 1，且病例 snapshot hash 必須等於已準備的純合成病例。
- 任一 ProviderError 或未知 transport 例外後鎖住後續 GPT transport；第一次錯誤的 retryable 改為 false。
- 每次傳輸前讀本地 checkpoint；若先前 attempt 已 failed（包括 Workflow 在 transport 之外檢出的 stage timeout），封鎖後續 GPT 請求。
- Workflow 可以繼續作本地錯誤記錄／彙整，但後續模型傳輸被拒絕。因此可能看到後續節點 failed，並非又呼叫付費模型。
- 上限 8 個 transport attempts；這仍不是硬美元費用上限。requests_started 是保守傳輸嘗試計數，不是計費證明。
- 狀態存 `outbound-state.json`，只含版本、次數、鎖定與固定錯誤碼，不存 payload、headers 或 Key。若已有 transport 記錄，重啟不會自動恢復付費傳輸。
- `GET /api/live-smoke/guard` 可唯讀確認保護版本與狀態，不呼叫 OpenAI。
- 完整且局部有效的輸出仍可能保留原 Workflow 的修復行為；任何已標 failed 的 attempt 之後不再對外呼叫。沒有降低來源核對或發布門檻。

## 本機新增／修改

新隔離目錄內新增 `live_smoke_guard.py`、`run_live_backend.py`、`test_live_smoke_guard.py`、`Restart-Guarded-Backend.ps1`。

`Start-Live-Backend.ps1` 改用獨立 bootstrap；啟動確認詞改成 `START_BACKEND`，與付費核准分開。它仍只在本機隱藏提示輸入 Key，啟動後清除父程序憑證。

`Submit-Single-Run.ps1` 在提交前額外要求新 gate 存在、未鎖定、transport attempts=0；舊 Backend 沒有此 endpoint 時提交會拒絕，不會退回無保護模式。

## 離線驗證

15 tests passed，外部 socket／DNS 封鎖，只使用 synthetic credential／temp DB。涵蓋成功傳輸、Timeout、HTTP/429/5xx/無效回覆、缺授權 marker、錯 request/revision/snapshot、前次失敗 checkpoint、A2A endpoint 拒絕、次數上限與重啟防恢復。

其中一項直接跑原六節點 Workflow、注入 Provider Timeout：fake transport 只進入一次；後續傳輸被拒絕，結果保留錯誤且無候選。測試沒有真實 OpenAI 呼叫，不能當 API 驗收。

證據：同隔離目錄的 `guard-tests.xml`。執行入口為 `.venv` 的 pytest，檔案 `test_live_smoke_guard.py`。所有 PowerShell 腳本亦僅做語法解析；restart/launch/submit 均未由助理執行。

## 下一個單一步驟：本機重啟 Live Backend

Frontend 5175 保持開啟。在 PowerShell：

```powershell
Set-Location -LiteralPath 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent'
powershell -NoProfile -ExecutionPolicy Bypass -File .\data\runtime\live-gpt-readiness-20261027\Restart-Guarded-Backend.ps1
```

腳本確認尚無 Run／提交 marker、核對原 Backend PID／建立時間／執行檔及 8002 listener 的程序樹，只停止這組 Live Python 程序，保留舊 logs／PID 紀錄後重新啟動。若程序身分不符會拒絕，不碰 8000／5173。

依提示輸入 `START_BACKEND`，再於本機隱藏輸入 Key。這不是付費 Run 核准；仍須等人類明確說「我批准一次付費 Live Run」，才可執行 Submit-Single-Run.ps1。重啟會丟棄舊 Backend 記憶體中的 Key，助理不讀取或移轉它，因此需要本機再輸入一次。

第一次付費前須確認 `/api/live-smoke/guard` 回 enabled=true、version=live-smoke-fail-closed-1、requests_started=0、latched=false。若失敗鎖定，保留狀態／Run，停止，不刪鎖、換 request_id 或重送。

## Windows PowerShell 空陣列修正

重啟操作曾誤報已有 Run。唯讀核對實際 DB 為 0 Run，submission marker 不存在；原因是 `@(Invoke-RestMethod ...)` 將未展開的空 JSON array 當成一個 pipeline 物件。Restart／Submit 兩腳本已改為先接收回應，再以 `@($taskRunResponse)` 正規化計數，仍維持任何既有 Run 或 marker 都拒絕的保護。

`Test-Run-List.ps1` 在 Windows PowerShell 離線重現 old_count=1／實際空清單，並驗證 0、1、2 筆清單與 marker 開關共六組重啟 gate 條件通過。沒有 HTTP／GPT 呼叫。未刪鎖、未改 DB、未啟停程序。

## Windows console host 修正

第二次重啟檢查發現 Python 的正常子程序 `C:\Windows\System32\conhost.exe`，舊腳本因假定所有後代都是 Python 而拒絕。新版只排除該系統 console host，不直接停止它；Python 目標還須匹配原記錄或 .venv/pyvenv.cfg 的 executable，8002 listener 必須屬於已核對的 Python 目標。其他未知名稱／路徑仍拒絕。

新增 `Process-Safety.ps1`／`Test-Process-Safety.ps1`，四個合成案例通過；另在目前真實程序樹以 Windows PowerShell 執行 Restart 的 `-CheckOnly` 通過，辨識 Python PID 12300／27256，排除 console host。該模式不停止程序、不移動檔案、不讀取或詢問 Key。助理仍未執行正式重啟或提交。
