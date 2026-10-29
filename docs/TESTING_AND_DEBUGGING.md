# Testing & Debugging Guide

適用日期：2026-10-26；程式 Baseline：`1ad2648a349c28989c9fa3d41cd37bf56a40f0fd`，agent-led-1.6.0。本文是接手者的操作手冊；**以下測試指令在本次文件任務中沒有執行**。本機已驗證項目和版本見 `TECHNICAL_HANDOVER.md`。

操作約定：從 Repository root 的 PowerShell 開始；使用 `backend/.venv`，不用 WindowsApps 的 python 別名或 Codex 共用 Python。所有新測試資料寫到新的 `data/runtime/` 子目錄；不得把首次 Mock Run、原始交接資料或正式 DB 當測試暫存區。

## 1. 先辨別測試層級與現有指令

| 層級 | 現有實作 | 能證明／不能證明 |
| --- | --- | --- |
| Backend Unit／integration | pytest，`backend/tests/`；包含 FastAPI TestClient、SQLite、模擬 Provider | 驗證程式分支、契約與來源檢查；不是模型臨床正確性 |
| Frontend component | Vitest＋Testing Library，`frontend/src/*.test.tsx` | 驗證畫面、事件與 mock API；不代表真實前後端串接 |
| Frontend build | `npm.cmd run build`＝`tsc -b && vite build` | 型別與 production build；不是瀏覽器行為測試 |
| Browser E2E | Playwright，`frontend/tests/workflow.spec.ts` | 真實 local API／UI／隔離 DB；套件中有過時斷言，尚未本機驗證 |
| 人工本機 E2E | 保存的 validation.json／first-run.json／test-review.json | 已完成 Mock 流程、保存與重讀；不是自動套件通過證明 |
| Live verification | `backend/scripts/verify_agent_live.py`、`verify_live_workflow.py` 等 | 可能呼叫真實 API；不屬於預設離線測試，不能為了排錯直接執行 |

指令依據：[backend/scripts/test.ps1](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/scripts/test.ps1:1>)、[scripts/test.ps1](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/scripts/test.ps1:1>)、[frontend/package.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/package.json:6>)、[Playwright config](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/playwright.config.ts:1>)。

## 2. 準備一個不影響既有 Run 的測試程序

以下只影響當次 PowerShell 與其子程序。Environment.ps1 會建立／確認自己的 tmp 目錄；它不是純唯讀指令。

```powershell
Set-Location 'C:\Users\呂宜學\Documents\ChatGPT\multi_agent'
$taskRoot = (Get-Location).Path
if (Test-Path -LiteralPath (Join-Path $taskRoot 'backend/.env')) {
    throw '請在不帶 backend/.env 的專用測試副本操作；不要搬移或覆寫既有設定。'
}
. .\data\runtime\mock-check\Environment.ps1

# 每次給新路徑；避免 pytest 匯入 app.main 時碰到首次 Mock DB
$taskTestRoot = Join-Path $taskRoot ('data/runtime/test-handover/' + [guid]::NewGuid().ToString())
if (Test-Path -LiteralPath $taskTestRoot) { throw '測試目錄必須是新的。' }
$env:PROTOTYPE_DB_PATH = Join-Path $taskTestRoot 'prototype.db'
$env:RAG_RETRIEVAL_MODE = 'lexical'
$env:LLM_PROVIDER = 'mock'
# 此測試副本沒有 .env；清除程序繼承的 Live 設定
$env:LLM_API_KEY = ''
$env:LLM_BASE_URL = ''
$env:LLM_MODEL = ''

Get-Command python,npm.cmd -ErrorAction SilentlyContinue
& .\backend\.venv\Scripts\python.exe --version
& .\data\runtime\mock-check\tools\bin\node.exe --version
& .\data\runtime\mock-check\tools\bin\npm.cmd --version
$env:PROTOTYPE_DB_PATH
$env:PROTOTYPE_CATALOG_PATH
```

第一個 Get-Command 可能仍顯示 WindowsApps 的 python；後續只用明確的 `.venv` 執行檔。Windows PowerShell 5 對環境變數指定空字串可能等同移除，因此不可假設空字串能遮蔽 dotenv；上面的 guard 要求測試副本沒有 `.env`，目前這台電腦符合。若日後加入 Live 設定，請另建不帶設定與機密的測試副本，不修改原設定。catalog 目前沿用隔離 Mock catalog 供讀取，測試中需要變更 catalog 的情境會使用自己的 fixture。不要將這個測試程序拿來重啟日常 Mock 服務；日常服務應另用 Start-Services.ps1。

`backend/tests/conftest.py` 會對大部分舊測試指定 `configs/demo/rules.json`、`data/synthetic`，對 reported cohort／prepare demo 測試另用缺席的測試 catalog。**通過這些合成軟體測試不等於已驗收 data/handoff 的實際病例。** 測試名稱含 live／real 常表示 monkeypatch 的模擬回應，請看 fixture，而不是按名稱當作真 API 成功。[fixture policy](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/conftest.py:1>)。

## 3. Backend Unit Tests

優先使用既有專用腳本，它以 UUID 建立新的 pytest basetemp，拒絕既存目錄，並檢查 exit code：

```powershell
# 在第 2 節的測試程序中，從 root 執行
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\test.ps1
```

需要縮小範圍時，使用同一腳本採用的 pytest 入口與既有檔案，例如：

```powershell
Push-Location (Join-Path $taskRoot 'backend')
try {
    $taskPytestTemp = Join-Path $taskTestRoot 'pytest-focused'
    if (Test-Path -LiteralPath $taskPytestTemp) { throw '請使用新的 basetemp。' }
    & .\.venv\Scripts\python.exe -m pytest tests/test_agent_led.py tests/test_ast_sources.py tests/test_audit_sources.py --basetemp $taskPytestTemp -q --tb=short
    if ($LASTEXITCODE -ne 0) { throw '定向測試失敗，請保留輸出。' }
} finally { Pop-Location }
```

這是對現有 pytest 測試的選取，不是新增測試框架。需要 coverage 時可使用已安裝 pytest-cov，但將 JSON report 指向新的 runtime 目錄。根目錄 `scripts/test.ps1` 會依序跑 backend coverage、前端 build、Vitest；它固定輸出 `docs/coverage.json`，**會改寫既有報告**，不適合要求只新增報告的稽核流程。本文不把既有 coverage.json 當作本機新測得結果。

Backend 測試多使用 tmp_path、TestClient 或 monkeypatch Provider／HTTP；例如 `test_acceptance.py` 將 Repository 換成 tmp SQLite，`test_agent_led.py` 的成功情境以固定的 specialist 回覆替代 Provider。[TestClient 隔離](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/test_acceptance.py:12>)、[六節點模擬測試](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/test_agent_led.py:72>)。

## 4. Frontend Tests 與 build

承接第 2 節載入的本機 PATH；不用全域 npm。可以分開執行，讓失敗歸因清楚：

```powershell
Push-Location (Join-Path $taskRoot 'frontend')
try {
    & npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw 'Vitest 失敗。' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'TypeScript/Vite build 失敗。' }
} finally { Pop-Location }
```

`vite.config.ts` 的 test 設定使用 jsdom，只收 `src/**/*.test.tsx`；不會因此執行 Playwright。重要測試檔：AgentLed（引用／來源／pending 語意）、PhysicianReview（選藥／條件／保存）、EvidenceLibrary（文件版本與原文）、Insights（狀態與指標）、App（API 畫面）、AllergyContext、ReviewEditor。[設定來源](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/vite.config.ts:1>)。

## 5. Browser End-to-End Tests

現有指令是 `npm.cmd run e2e`。Playwright 會自行啟動 backend **8001**、frontend **5174**；`reuseExistingServer=false`，不沿用日常 8000／5173。Backend DB 在新 `data/runtime/e2e/test-<timestamp>/test.db`；catalog、seed 也由 config 指向測試路徑，LLM_PROVIDER=unconfigured、RAG=lexical。測試會明確選 Mock，或使用無模型的 rule-only。不要手動改成 Live。

目前本機只有 `npm.cmd` shim，沒有 npx.cmd；根目錄 `scripts/test.ps1 -E2E` 會呼叫 npx.cmd，因此還有工具入口前置條件。可直接透過本機 npm 套件內已存在的 npx CLI 安裝 Chromium，不必做全域安裝：

```powershell
# 第一次才需要；會下載免費瀏覽器並寫入 frontend/.playwright
# 安裝不是本次交接文件任務已完成的步驟
$taskNode = Join-Path $taskRoot 'data/runtime/mock-check/tools/bin/node.exe'
$taskNpxCli = Join-Path $taskRoot 'data/runtime/mock-check/tools/npm/package/bin/npx-cli.js'
Push-Location (Join-Path $taskRoot 'frontend')
try {
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location).Path '.playwright'
    & $taskNode $taskNpxCli --no-install playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium 安裝失敗，先排除環境問題。' }
    & npm.cmd run e2e
    if ($LASTEXITCODE -ne 0) { throw 'E2E 失敗，請保留 test-results。' }
} finally { Pop-Location }
```

**靜態已確認的現有測試落差，尚未實跑：**

- `workflow.spec.ts:14,23` 斷言只有 5 個 Agent；現行 runtime 定義 6 個。
- `:21` 尋找舊的 `clinical_assessment`，目前 Synthesis 使用 `assessments.clinical_agent`。
- `:243–244` 期待舊候選畫面和非空 `.candidate`；目前 Mock 刻意不產生 AI reviewable candidates，UI 也改成逐藥表。

因此不要在看到失敗時先改核心演算法讓舊斷言通過。先將截圖、response JSON 和失敗 assertion 保存，確認是否只是契約遷移未同步；後續另行修改測試，核對六節點、18 pending／醫師清單等正確語意。本次沒有修改它們，也沒有宣稱實際 E2E 已失敗或已通過。[過時斷言](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/tests/workflow.spec.ts:3>)、[舊候選期望](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/tests/workflow.spec.ts:237>)。

## 6. 不呼叫真實 API 的 Multi-Agent 測試方式

有兩種用途，不要混用：

1. **固定 Mock 行為測試**：執行 `test_agent_led.py` 中 `test_missing_data_no_longer_skips_agents_and_mock_never_certifies`，或在新隔離 DB／網頁選 multi-agent + mock + lexical。預期可有六個執行紀錄，但輸出 unknown／uncertain／pending，AI candidates 為 0；這不是測試失敗。
2. **可發布路徑／故障注入測試**：沿用該測試檔的 `successful` fixture，monkeypatch `runtime_led.Provider.complete`，提供具體類別來源、原文選段、分項風險與 Audit 結果，再測 wrong drug、缺引用、格式壞列、timeout、repair。這些是人工測試回應，不是 Mock 模型已具備推理能力。

`backend/scripts/replay_agent_context.py` 是另一個離線診斷工具：會重新執行工作流，以保存的查詢和回覆替代已完成部分，剩餘用 Mock。它不是單純查看原 Run 的指令；若需求是「不重跑」，請用下一節的唯讀方式。任何 replay 結果都必須另標為重播，不得偽裝成原始觀測。

原始碼：[Mock 固定回覆](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/agents/runtime_led.py:134>)、[partial validation](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/partial_agents.py:6>)、[replay 腳本](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/scripts/replay_agent_context.py:1>)。

## 7. 找到並解析某次 Run：先讀取，不重跑

已知 Baseline Run：`51905060-412e-4e04-99f3-c9a1bbbbc596`。後端已在線時，以下只讀既有紀錄：

```powershell
$taskRunId = '51905060-412e-4e04-99f3-c9a1bbbbc596'
$taskRun = Invoke-RestMethod ("http://127.0.0.1:8000/api/runs/" + $taskRunId)
$taskRun | Select-Object run_id,case_id,case_revision,mode,provider_kind,status,gate_status
$taskRun.nodes | Select-Object node_id,status,elapsed_ms,retry_count
$taskRun.drug_assessments | Where-Object drug_code -eq 'amoxicillin_clavulanate' | ConvertTo-Json -Depth 100
# 其他唯讀 API：/api/runs/{id}/trace、/export、/api/reviews?run_id={id}
```

前端選病例 → 執行紀錄 → 選既有 Run；不要再按「執行分析」。`chooseRun()` 只 GET run 和 reviews。[前端入口](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/src/App.tsx:160>)。

不啟動服務時，從 root 直接讀 SQLite，避免 import app.main 造成初始化：

```powershell
@'
from pathlib import Path
import sqlite3, json
db = (Path.cwd() / "data/runtime/mock-check/prototype.db").resolve()
run_id = "51905060-412e-4e04-99f3-c9a1bbbbc596"
with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
    row = conn.execute("SELECT run_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        raise SystemExit("RUN_NOT_FOUND：先核對資料庫及 run_id")
    run = json.loads(row[0])
    print(json.dumps({"run_id": run["run_id"], "case_revision": run.get("case_revision"),
                      "status": run["status"], "gate_status": run.get("gate_status")}, ensure_ascii=False))
    for node in run["nodes"]:
        if node.get("agent_id"):
            print(node["node_id"], node["status"], len(node.get("attempts", [])))
    drug = next(x for x in run["drug_assessments"] if x["drug_code"] == "amoxicillin_clavulanate")
    print(json.dumps(drug, ensure_ascii=False, indent=2))
'@ | & .\backend\.venv\Scripts\python.exe -X utf8 -B -
```

這段只輸出節錄，不新增匯出檔。API 的 `_public_run` 是公開投影，DB 是內部保存資料，應標記資料來源；既有 first-run.json 的日期曾由 PowerShell 顯示成 +08:00，但與 DB UTC 代表同一時刻。保存輸出若要另寫檔，先確認新檔不存在，並記錄 commit、run_id、hash；不要覆寫 first-run.json。

建議讀取順序：case_snapshot → versions/provider → nodes[].input → attempts → nodes[].output → retrievals/evidence_selection/evidence_coverage → drug_assessments → output → physician_candidates → reviews。節點 output 通常已經過 Schema 與來源驗證，不保證是未加工的原始模型字串；沒有保存的資料不可補造。

## 8. 檢查 RAG Retrieval Logs

```powershell
$taskRun.retrievals |
    Where-Object { $null -eq $_.drug_code -or $_.drug_code -eq 'amoxicillin_clavulanate' } |
    Select-Object stage,dimension,query,status,count,method,elapsed_ms
$taskRun.evidence_selection | Format-Table
$taskRun.evidence_coverage |
    Where-Object drug_code -eq 'amoxicillin_clavulanate' | ConvertTo-Json -Depth 100
```

逐項核對：

1. `retrievals`：查詢是否真的執行、stage/drug/dimension、方法、狀態、primary_ids 與含鄰段的 chunk_ids。count 是返回片段數，不是相關片段數。
2. `evidence_snapshots`：用 chunk_id 找實際 text、location、文件版本、population、document_kind、source_document_id；不可只看 title。
3. `nodes[].input.evidence`：節點實際收到哪些片段；快照有 68 個不表示每個 Agent 都讀 68 個。
4. `evidence_selection/coverage`：選入與 omitted 是否因長度或預算；空來源和未納入輸入要分開。
5. `quotes`／statement 的 `evidence_refs`：Agent 是否真的選取來源。coverage 的 evidence_refs 是「已準備片段」，與聲明選取的 refs 用途不同。

本次例子：74 次 status=ok；Evidence 63 片段、Clinical 58、Synthesis/Audit 0。amoxicillin_clavulanate 的三個風險查詢都返回同一標頭／適應症三片段。Synthesis/Audit 為 0 是 Mock 沒選引用，不是初始檢索完全失敗。Audit 的空 requested_refs 又被 classifier 標成 retrieval_empty；不要因此重建整個索引。

原始碼：[查詢與選取](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:286>)、[FTS OR 與 LIMIT](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/rag/service.py:1037>)、[空引用 blocker](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/claim_checks.py:84>)。

## 9. 區分執行失敗、格式錯誤與需要確認

| 觀察位置／欄位 | 解讀與下一步 |
| --- | --- |
| node.status=failed；attempt.error_code | 執行／設定／來源讀取／格式等硬失敗，按 error_code 分類，不能只看 overall status |
| MODEL_NOT_CONFIGURED | Provider.check 未取得有效配置；先查 request provider_kind 與啟動程序，不要輸出 key |
| AGENT_INPUT_TOO_LARGE | 組裝後超過字元上限；先看 input/coverage，這不是 token 數量的精確量測 |
| AGENT_STAGE_TIMEOUT／AGENT_BUDGET_EXCEEDED | 角色／全域時間預算；查 timeout_seconds、reserved_downstream_seconds、retrieval elapsed、重試 |
| AGENT_OUTPUT_TRUNCATED、finish_reason=length | 輸出截斷；先核對 output_token_limit 與回應列數，不能把不完整 JSON 當模型拒答 |
| AGENT_SCHEMA_INVALID 或 validation_status=invalid | Pydantic／wire／內容驗證錯誤；查看 validation_details 與 feedback；原始不合法文字可能沒有保存 |
| attempt completed，但 validation_status=partial | 部分藥列可用、部分格式／引用待修復；看 unresolved_drugs、requested_drugs、retry_count，不要丟棄全部有效列 |
| node.status=needs_confirmation | 可以是格式有效但內容 unknown/uncertain/pending/caution，或仍有未解決藥列；不等於 HTTP 失敗 |
| audit.claim_checks_complete=true | 五維度有齊，不等於支持性通過；再看 verdict、validation_issues、ast_check_validation |
| overall partial／gate needs_confirmation | 沒有可發布 AI candidates 等情況；Mock 也會如此，不能直接歸因未設定模型 |
| errors=[]、missing_fields=[] | 只表示這些清單空；還需讀逐藥 blockers，不能當沒有問題 |
| candidate_presentation completed／published=false | 候選整理步驟執行完，但沒有發布；與六個模型節點分開 |
| INTERRUPTED | 服務重啟恢復將未完成 Run 標失敗；不是原模型回傳錯誤 |

依據：[呼叫、修復與錯誤保存](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:413>)、[節點狀態判定](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:470>)、[重啟恢復](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/repositories/sqlite.py:109>)。

## 10. 修改後的最小回歸範圍

先定向、再按跨模組影響擴大；不要用鏡像實作的測試取代行為驗證。

| 修改範圍 | 優先既有測試 | 合併前補充 |
| --- | --- | --- |
| Case Schema／Adapter／修訂 | test_backend_contract、test_handoff、test_reported_cohort | 合約生成差異、App/AllergyContext、完整 backend |
| AST／來源欄位／rules | test_reported_cohort、test_ast_sources、test_workflow、test_audit_sources | Agent-led、醫師清單與 safety regression |
| RAG／切段／population／lineage | test_rag、test_reference_bundle、test_document_delete、test_source_scope | agent_retrieval_budget、input_context、EvidenceLibrary |
| Orchestration／Prompt／Provider | test_agent_led、test_agent_led_140、agent_time/output/retrieval_budget、test_providers | citation_spans、input_context、完整 backend；Prompt 調整另走 Gold 評估，不以 Mock 為效果證據 |
| Audit／risk／claims | test_audit_sources、test_risk_dimensions、test_source_scope、test_allergy_provenance | test_agent_led、test_safety_regressions、AgentLed UI |
| Aggregation／醫師選藥 | test_physician_candidates、test_physician_review、test_safety_regressions | PhysicianReview/ReviewEditor/AgentLed、API 審閱保存重讀 |
| DB／API／匯出 | test_backend_contract、test_acceptance、test_handoff、test_document_delete | 新 DB＋舊 DB 副本 migration、完整 backend、修正後 E2E |
| Benchmark／指標 | test_workflow、test_acceptance、Insights.test.tsx | 人工核對分子分母／null、固定小批四模式；不能自動升級成 Live |
| 純前端 | 對應 Vitest＋build | 涉及流程時跑修正後 Playwright；保存截圖與 response |

每次測試報告至少記：commit、工作目錄 diff、命令、OS／runtime 版本、fixture/rules/retrieval/provider、時間、exit code、pass/fail/skip、log/report 新檔位置。未執行就寫未執行。若第一次全套出現失敗，先留存「原 Baseline 失敗」與「修改引入回歸」的區別。

## 11. 常見環境排錯與操作界線

- Python 找不到：用 `.venv/Scripts/python.exe`；不改全域 PATH／Windows 別名。
- npm 找不到：載入本機 Environment 或直接使用 tools/bin/npm.cmd；npx 安裝瀏覽器走第 5 節，不做全域安裝。
- Backend 404 Run：先核對 DB 路徑與 run_id，不重新匯入或重新分析來掩蓋路徑錯誤。
- 8000／5173 占用：用既有 Stop-Services 身分驗證停止本組程序；不要 taskkill 所有 Python/Node。E2E 則檢查 8001／5174。
- Embedding unavailable：檢查當次 retrieval mode；目前離線測試應明確 lexical，不需安裝 Ollama／GPU。
- 切換環境無效：既有服務沒有繼承新終端環境，或 Start-Backend 又套回 Mock。先核對啟動入口，再有計畫地重啟。
- 新 clone 沒有 .venv／tools／runtime：這是 Git ignore 的預期結果。取得可用 Python/Node/npm 後，依鎖定檔在本機 venv 和 frontend 執行安裝；官方 setup/import 會初始化資料，必須先指向新 DB。現有電腦不需重裝。
- `verify_*live*.py`、`POST /api/runs`、`POST /api/benchmarks`、`/documents/reindex` 不是唯讀診斷；是否呼叫服務／寫資料取決於操作與設定。唯讀分析優先使用保存的 Run 和 mode=ro SQLite。
