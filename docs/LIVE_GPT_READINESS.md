# 首次 GPT Multi-Agent Live Run：Readiness Check

日期：2026-10-27。HEAD：`1ad2648a349c28989c9fa3d41cd37bf56a40f0fd`。本輪僅閱讀、查官方文件、建立新的離線隔離資料與啟動／提交腳本，未啟動 Live 服務、執行 Live Run、讀取實際 API Key 或呼叫任何付費 API／工研院服務。

**結論：本機離線準備已完成；付費執行尚未授權。** 沒有發現本次建議模型必須先修改核心 Provider 的相容性阻擋；帳號權限、額度、API 可達性、實際格式遵從與候選品質尚未驗證。讀完本文件不等於授權自動執行。

## 1. 模型與 API 契約

建議首次使用 **`gpt-4.1-mini-2025-04-14`**，鎖定 snapshot。原因是符合現有 Chat Completions 路徑、JSON mode、非 reasoning 的既有參數組合，且 32,768 output tokens 足以容納程式預設的 Audit 24,000 token 上限。這是對現行程式的短期相容性選擇，不是長期預設或臨床能力認證。[官方模型頁](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

**時間限制**：官方已公告此系列 deprecated、2027-01-14 下線。因此本次只能作近期測試；若帳號已不可用，不自動換模型重送，應先另做新模型參數適配與離線測試。[官方 Deprecations](https://developers.openai.com/api/docs/deprecations)

程式沒有 GPT model allowlist，也沒有自動選型／模型能力偵測；LLM_MODEL 的字串直接送給服務。不能據此說所有 GPT 都已受支援。gpt-4o-mini 的 output 上限小於目前 Audit 的預設請求預算，並非不改設定即可替換的首選；其他新 GPT／reasoning 模型是否接受同一組 temperature/max_tokens，這輪未驗證，不推薦盲換。

實際 Provider：

- `providers/service.py:174`：base URL 後加 `/chat/completions`，Bearer 認證；本次將使用 `https://api.openai.com/v1`，不是 A2A endpoint。
- `agents/runtime_v2.py:104`：讀 LLM_MODEL、LLM_BASE_URL、LLM_API_KEY；每角色 `LLM_V2_<AGENT_ID>_MODEL` 可覆寫，隔離 launcher 會清除這六個覆寫，避免混用其他模型。
- `runtime_v2.py:122`：system＋user messages、temperature=0、response_format.type=json_object、max_tokens；只將 finish_reason=stop 的 content 解析為 JSON。
- `runtime_led.py:78`：引用 chunk aliases／span_ids／AST source options → 模型回應 → wire validation → 還原來源 → Pydantic 與來源／聲明驗證。

目前是 **JSON mode＋Prompt 中 output_schema＋本機驗證**，沒有送 `response_format=json_schema, strict=true`；JSON 合法不保證吻合 Schema。不能宣稱 API 已替本系統保證所有輸出欄位。[官方 Structured Outputs 指南](https://developers.openai.com/api/docs/guides/structured-outputs)

## 2. 六角色、呼叫數與費用

依序 Case → AST → Evidence → Clinical → Synthesis → Evidence Audit。前四角色專責原始資料與不同證據池，Synthesis 才整合四份報告；Audit 取得聲明與被選原文再核對。每個角色最多兩次嘗試，總額度限制較優先。

正常完整流程約 **6 次付費呼叫**；本次準備設定 `LLM_V2_MAX_CALLS=8`，最多允許兩次額外修復嘗試，**不是 6×2=12 次**。早期失敗、時間不足、Audit 無聲明可核對時可能少於六次。輸出無效的已送出請求也可能計費。

六節點使用的 HTTP transport `retries=0`；Workflow 仍可能按剩餘預算重試格式／來源問題或 retryable 失敗。不要把 A2A 的「不重試」套用成六角色完全不重試。依據：`agent_led.py:270`、`:418`；`runtime_v2.py:125`。

輸出額度（上限，不是實際使用量）：前四角色各 6,000；Synthesis 16,000；Audit 24,000。總時間預算 780 秒、硬設定界限 900 秒；前四角色各自 cap 60 秒、後兩者各 180 秒，並保留後續角色時間。LLM_TIMEOUT 不是本六節點的主要 timeout 控制。

官方模型頁 Standard 文字價格：每百萬 input tokens **US$0.40**、output **US$1.60**。先不假定 cache 折扣。[官方模型價格](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

`estimated_USD = sum(prompt_tokens) × 0.40 / 1,000,000 + sum(completion_tokens) × 1.60 / 1,000,000`

- 示意算例（不是測量）：整筆 60,000 input＋20,000 output → **US$0.056**。
- 兩個虛構藥的單 Run 可先規畫 **US$0.02–0.20**，建議討論 **US$0.50 的操作預算**；這不是嚴格費用上限或保證報價。
- 回覆長度、實際 schema/context、額外藥物、修復、失敗／timeout、cache、費率及帳號條件都影響金額；實際要比對保存 usage 與 OpenAI Usage。缺 usage 時不能補零。
- 程式沒有美元預算硬閘門；max_calls 只限制單 Run 呼叫數，不阻止使用者再建立另一 Run，也不限制整個服務當天費用。

## 3. 本次病例與外傳範圍

使用既有 **`data/synthetic/case-15-integrated-complete.json`**，原件未改：

- is_synthetic=true、data_origin=synthetic、evidence_scope=synthetic；虛構 DEMO_ORGANISM_A。
- AST 只有 DEMO_DRUG_A／DEMO_DRUG_B，皆為虛構判讀。
- 合成腎功能、過敏、用藥與快速鑑定情境。
- 文件只有 `data/demo_documents/synthetic_policy.md` 與 `synthetic_resistance.txt`；兩者明示非臨床指引。
- 原 fixture 的 medication_history_status 正規化後為 unknown；原文件不提供足夠的真實臨床支持。**即使用 GPT，合理結果仍可能全部 Pending。** 不修改情境／虛構指引來製造綠燈。

這次可證明 GPT 通訊、角色輸出、引用與保存機制；不能證明真實抗生素任務的臨床推理品質，也不能與 agent-complete 的 18 藥 Mock 當成同病例成效比較。

**不使用 agent-complete revision 4**：它含來源 AST 與人工情境，是 hybrid，沒有找到足夠的獨立外傳授權證據。provenance 還要求接收工作站取得許可。is_synthetic／data_origin 是來源標籤；deprecated external_model_allowed 不是權限閘門。不能因你有 API Key 就推定來源 AST／醫療文件已准許外傳。

本次隔離文件庫沒有 handoff 原文、DailyMed／WHO、Mock Run 或 Review。API Key 僅在 Authorization header；不進病例／Agent input。沒有任何 A2A imports 或 endpoint 路由進入六節點，並明確設定 ITRI_A2A_ENABLED=false。

## 4. 已建立的獨立環境

根目錄：`data/runtime/live-gpt-readiness-20261027/`（ignored，本機資產；未提交 Git）。

| 內容 | 本輪結果 |
| --- | --- |
| `prototype.db` | 1 case、revision 1、2 AST、0 Run、0 Review |
| `fixtures/case-15-integrated-complete.json` | 原件逐 byte 複本；用 fixture 目錄讓 UI 顯示 DEMO 病例，未改原件 |
| `documents/` | 2 份 synthetic 文件與 lexical SQLite 索引；查詢測試 ok／2 chunks |
| `readiness.json` | 病例／文件 hash、隔離路徑、限制、建議模型；不是已核准的資料外傳紀錄 |
| `single-run-request.json` | 事先固定的一個 request_id；provider_kind=live、mode=multi-agent；尚未提交 |
| `protected-before.json`／`preservation.json` | 213 個原始來源、既有程式／文件及 Mock DB／RAG 檔案 hash 不變 |
| `provider-tests.xml` | Provider／輸出額度的 22 項離線測試通過；socket/DNS 封鎖、僅假憑證 |

同目錄新增四個本機操作腳本，**只做 PowerShell syntax parse，全部未啟動／未提交**：

- `Environment.ps1`：獨立路徑、模型、額度；預設 provider=unconfigured，移除程序繼承的 LLM/A2A 憑證。
- `Start-Live-Backend.ps1`：本機安全提示輸入 Key；獨立 8002、隱藏背景程序、專屬 logs，不提交 Run。
- `Start-Frontend.ps1`：使用現有 Node／Vite，獨立 5175，API_TARGET=8002。
- `Submit-Single-Run.ps1`：必須帶 -ApprovePaidRun；核對設定、既有 Runs、持久化提交 guard，再只 POST 一次。

原 Mock 8000／5173、prototype.db、病例及歷史 Run/Review 不必停止或切換設定。這次沒有啟停任何服務。Frontend 5175 透過 Vite 同源 proxy，不需要修改 FastAPI CORS 白名單。

## 5. 實際需要的環境變數

以下已寫在新環境腳本，並非套用到正在執行的 Mock 程序：

```text
PROTOTYPE_DB_PATH=<新隔離目錄>/prototype.db
PROTOTYPE_CATALOG_PATH=<新隔離目錄>/absent-catalog.json
PROTOTYPE_RULE_CONFIG=<repo>/configs/demo/rules.json
PROTOTYPE_FIXTURE_DIR=<新隔離目錄>/fixtures
RAG_RETRIEVAL_MODE=lexical
LLM_PROVIDER=live                 # 只由 Live launcher 在新子程序設定
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini-2025-04-14
LLM_API_KEY=<只由本機隱藏輸入注入；沒有儲存值>
LLM_V2_MAX_CALLS=8
LLM_AGENT_LED_TIMEOUT_SECONDS=780
LLM_AGENT_LED_MAX_OUTPUT_TOKENS=6000
LLM_AGENT_SYNTHESIS_MAX_OUTPUT_TOKENS=16000
LLM_AGENT_AUDIT_MAX_OUTPUT_TOKENS=24000
ITRI_A2A_ENABLED=false
API_TARGET=http://127.0.0.1:8002    # 新前端程序使用
```

本專案讀的是 LLM_API_KEY，**只設定 OPENAI_API_KEY 不會自動生效**。catalog 故意指定隔離目錄內不存在的檔名，避免載入日常來源字典；demo rules 與合成病例仍可顯示。Multi-Agent 不依 demo RuleEngine 替代 Agent 決策。

## 6. 核准後才操作：Windows 與 Key

下列命令是待核准的操作說明，本輪沒有執行。Key 不放命令列、檔案、Git、聊天或啟動參數。

### A. 啟動新 Backend

```powershell
Set-Location -LiteralPath 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent'
powershell -NoProfile -ExecutionPolicy Bypass -File .\data\runtime\live-gpt-readiness-20261027\Start-Live-Backend.ps1
```

Launcher 會要求 APPROVED，接著 `Read-Host -AsSecureString` 讓你在本機輸入 Key。SecureString → 短暫 BSTR → 該 launcher 的程序環境 LLM_API_KEY → Start-Process 子程序繼承。啟動後立即 ZeroFreeBSTR／Dispose／移除父程序環境變數，只有新的 Backend 仍持有運作需要的憑證。

這能避免 shell 命令歷史和檔案留 Key；環境變數與子程序記憶體仍是明文認證，不是祕密保管庫，也不保證 managed memory 全清零。要移除 Backend 持有的 Key，需停止那組 Live Backend。不要輸出 env／process environment 或開 request body/header debug。

```powershell
Invoke-RestMethod 'http://127.0.0.1:8002/api/health'
$check = Invoke-RestMethod 'http://127.0.0.1:8002/api/config'
$check.provider | Select-Object kind,configured,model
$check.rag | Select-Object retrieval_mode,retrieval_method
```

預期 live／configured=true／建議 snapshot、lexical。configured 只是設定已填齊，不是帳號或模型連線驗收。若 port 8002 已占用，先辨識，不能停止原 Mock 程序來騰位置。新啟動的 stdout／stderr 在新隔離目錄內。

### B. 啟動獨立前端

在另一個 PowerShell：

```powershell
Set-Location -LiteralPath 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent'
powershell -NoProfile -ExecutionPolicy Bypass -File .\data\runtime\live-gpt-readiness-20261027\Start-Frontend.ps1
```

開 `http://127.0.0.1:5175/`。原本 `http://127.0.0.1:5173/` 仍是 Mock。這不是同一個 UI 的 DB 切換按鈕，而是兩組不同的前端 proxy／Backend DB。

### C. 唯一一次付費提交

得到人類明確同意模型、合成外傳內容與預算後，才執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\data\runtime\live-gpt-readiness-20261027\Submit-Single-Run.ps1 -ApprovePaidRun
```

此腳本不詢問或讀取 API Key，僅呼叫本機已啟動的 8002。固定 request_id 用於現有 Repository idempotency，且已有 Run 或 submission-started.lock 即拒絕再提交。鎖在 POST 前建立，timeout 後也保留。網頁「執行分析」每次會產生新 request_id，因此**本次不要用該按鈕提交或重跑，也不要執行 Benchmark**。

這是操作層防重，不是對所有 API/UI 的全域封鎖；其他程式仍可送新 request_id 建新 Run。如果發生 timeout，先 GET /api/runs，確認後端是否仍在執行；不要刪鎖、換 UUID、重新 POST 或停止進行中的 Run。

本機 API 的 timeout 設為 1000 秒以涵蓋 780 秒 Workflow。即使客戶端中斷，遠端 OpenAI 呼叫仍可能完成並計費，請先查保存狀態與 OpenAI Usage。

### D. 成功後從網頁讀取

1. 5175 → 目前病例 → case-15-integrated-complete revision 1。
2. 在執行紀錄選新 Run；頁面須顯示 GPT model／provider_kind=live、is_mock=false。不要另按執行分析。
3. 分析結果看逐藥結果與 Pending 原因；證據與流程展開六角色、來源片段、用量與 Audit；匯出 JSON 保留當次 snapshot。
4. partial／needs_confirmation 不等於 GPT 沒執行；須看節點 attempts、response_id、usage、format/source validation。判定「完成一次通訊」與「六角色有效輸出」及「有核對通過候選」是三個不同完成層級。
5. 即使 API 成功，未知風險、假文件或引用未驗證仍保留 Pending；不得放寬檢核只為讓 Demo 有 candidates。

### E. 明天只展示結果時，移除 Key 的方式

結束推論並確認 Run 已保存後，辨識只屬於 8002 的 Backend 程序與 launcher 紀錄 `backend-process.json`，核對後停止它；Windows .venv 可能有 parent／listener 不同 PID，不能只停父程序就假定 credential-bearing worker 已停止。原 Mock 8000 不動。

另開無 Key 的 PowerShell，載入本次 Environment.ps1（預設 unconfigured 並清除 Key），再直接以 .venv 啟動同一 DB 的 8002，即可讓 5175 唯讀展示已保存 Live Run：

```powershell
Set-Location -LiteralPath 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent'
. .\data\runtime\live-gpt-readiness-20261027\Environment.ps1
Push-Location backend
try { & .\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8002 }
finally { Pop-Location }
```

這時設定頁為未配置，但歷史 Run 仍保留原 Live model、輸入／輸出與用量；不要誤認為保存結果被改成 Mock。前端不需要 Key。前景 Viewer／Frontend 可各按 Ctrl+C 停止。

## 7. 驗證、風險與批准前條件

已執行：

- 原始純合成 JSON 經現有 normalize_case／Case Schema 接受；原件複本與 hash 保留。
- 只在新目錄初始化 Repository／DocumentService；socket connect 與 DNS 被封鎖；lexical 檢索返回 ok、2 chunks。
- `tests/test_providers.py`＋`tests/test_agent_output_budget.py`：**22 passed，0 failed**；外網封鎖、只用 synthetic credential。命令入口：`.venv/Scripts/python.exe -X utf8 -B -` 內呼叫 pytest.main，XML 在新隔離目錄。
- 四個 PowerShell 腳本僅 syntax parse PASS，未執行；實際啟動、繼承、port 可用性仍待本機操作確認。
- 213 個受保護檔案前後 hash 相同；既有 Mock DB、RAG DB、原病例／handoff、既有程式／文件未變。

尚未執行：帳號／模型 access check、餘額／TPM/RPM 確認、GPT API、Live Run、完整 Regression／前端 E2E。本輪沒有修改核心程式，因此沒有為測試改參數語意或降低安全門檻。

批准前需明確同意：**一筆 case-15 純合成資料＋兩份合成文件、snapshot 模型、正常六／上限八呼叫、費用估算不是硬美元上限**。API 專案需有該模型權限與計費額度；Key 只由操作者在本機輸入。若模型不可用、401/403/429 或格式不符，先記錄，不自動改模型或反覆扣費。

這輪準備已停止，沒有自動排程、Live 服務或等待中的付費請求。
