# Project Testing & Regression Baseline

日期：2026-10-26（Asia/Taipei）。本報告是本機實際執行結果，不沿用原工作站的歷史通過數。測試初輪按 Backend → Frontend component → Build → Playwright 順序完成；之後只重跑受修正影響的 Backend 與 Playwright。

**結論：目前具備在這台 Windows 電腦上作為離線研究 Baseline 的基本工程條件。** 最終 Backend 396 passed、Frontend 68 passed、Playwright 8 passed，均無 Failed／Skipped；TypeScript/Vite build 通過。這表示軟體契約、資料流、來源驗證分支與保存操作通過既有測試，**不表示真實 LLM 的臨床推論正確性、引用語意支持性或 Multi-Agent 優越性已經驗證**。

## 1. 環境、Git 與隔離範圍

| 項目 | 本次狀態 |
| --- | --- |
| 工作目錄 | `C:\Users\呂宜學\Documents\ChatGPT\multi_agent` |
| Branch／HEAD | `main`／`1ad2648a349c28989c9fa3d41cd37bf56a40f0fd` |
| Baseline 的精確範圍 | 上述 HEAD **加上本次尚未提交的三個測試檔修正**；不是原始 HEAD 的測試全數通過 |
| 任務開始時 | tracked diff 空；已有三份 handover 文件為 untracked，這次未覆寫它們 |
| OS | Windows 11，build `10.0.26200`，64-bit |
| Python／SQLite | `.venv` Python `3.12.14`／SQLite `3.53.1` |
| Backend | FastAPI `0.141.1`、Starlette `1.6.0`、Pydantic `2.13.5`、uvicorn `0.53.0`、httpx `0.28.1`、pytest `8.4.2`、pytest-cov `6.3.0` |
| Node／npm | 專案本機 Node `24.19.0`／npm `11.6.2` |
| Frontend | React `19.2.0`、TypeScript `5.9.3`、Vite `7.1.12`、Vitest `3.2.4`、Playwright Test `1.56.1` |
| Browser | 本次免費下載 Chromium `141.0.7390.37`，Playwright build `1194`，含 headless shell／FFMPEG／Winldd 工具；只存於新的 runtime 目錄 |

本次證據目錄統一為：

```text
data/runtime/regression-20261026-161449/
```

以下以 `$R` 代表其絕對路徑。環境及各測試檔 SHA-256 在 [environment.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/environment.json:1>)；精確測試 patch 在 [test-only.patch](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/test-only.patch:1>)，其 SHA-256 為 `3525bd8e9e9b6a599694dc6a16b025190e63cd281a0017822f33ce039794b2c6`。這些是 ignored 的本機證據，沒有提交 Git；交接至另一台電腦時須另保存，不能只報 HEAD。

隔離措施：

- 不載入 `mock-check/Environment.ps1`，避免把 tmp／cache／DB 指向既有 Mock 目錄；只讀取其中的 Node/npm 執行檔。
- 新的 `Test-Environment.ps1` 設定 `PROTOTYPE_DB_PATH=$R/import-only.db`、缺席的測試 catalog、lexical、mock、自己的 TEMP/TMP/npm-cache，並清除繼承的 LLM key/base URL/model。執行前確認 `backend/.env` 不存在。
- Backend 每輪 pytest 使用獨立 basetemp，fixture 內再使用 tmp SQLite。pytest-cov 的資料與 JSON 都寫入 `$R`，未覆寫 `docs/coverage.json`。
- Embedding feature tests 使用顯式 `retrieval_mode="embedding"` 加 Fake/FlatMockEmbeddings 等測試替身；沒有啟動 Ollama 或呼叫真實向量服務。
- Playwright 沿用專案實際設定，以 **8001／5174** 啟動測試服務；DB 位於獨立 `data/runtime/e2e/test-<timestamp>/test.db`。日常 **8000／5173** 不被重用或停止。
- 沒有真實 LLM／付費服務呼叫。Backend 測試中的 live 名稱／標籤有使用 monkeypatch 或 HTTP double，不是 Live API 驗收。唯一新增的外部下載是免費 Playwright 瀏覽器。

依據：[測試環境腳本](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/Test-Environment.ps1:1>)、[Playwright config](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/playwright.config.ts:1>)、[既有 conftest fixture policy](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/conftest.py:1>)。

### 1.1 既有資料與服務保全結果

測試前後以 SQLite `mode=ro` 讀取兩個 Mock DB 的所有資料表，對排序後完整列內容做 SHA-256；另核對 catalog、first-run、test-review、services.json 檔案 hash。結果 **全部相同**，不是只比較筆數。

| 保留項目 | 測試後 |
| --- | --- |
| mock-check/prototype.db | 邏輯內容 hash 相同；28 cases、95 case_revisions、1 run、1 review |
| 已保存 Mock Run | `51905060-412e-4e04-99f3-c9a1bbbbc596` 原紀錄保留 |
| 已保存測試 Review | `032218e1-913e-4a5e-9a9a-1493246f040d` 原紀錄保留 |
| mock-check/documents/rag.sqlite3 | 所有資料表內容 hash 相同；24 documents、2111 chunks、0 embeddings |
| 日常 Backend | 原 PID `12800` 仍監聽 8000；GET /api/health = ok |
| 日常 Frontend | 原 PID `16920` 仍監聽 5173；HTTP 200 |
| 測試服務 | 測試結束後 8001／5174 無監聽程序 |

證據：[preservation-before.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/preservation-before.json:1>)、[preservation-after.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/preservation-after.json:1>)（`unchanged=true`）、[services-after.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/services-after.json:1>)。

## 2. 實際指令與結果

最終結果不是把多輪重跑加總；以各範圍最後有效執行為準。Build 沒有測試案例數，不能填成 1 個 unit test passed。

| 階段／輪次 | Passed | Failed | Skipped | 工具報告耗時 | 結果 |
| --- | ---: | ---: | ---: | --- | --- |
| Backend 最初工具沙箱執行 | N/A | N/A | N/A | 外層 105.13 秒後中止 | 停留第一個 TestClient 案例，沒有完整報告；不是測試失敗數 |
| Backend 未修正測試、正常使用者環境 | 384 | 12 | 0 | pytest 59.21 秒 | exit 1；假 Embedding 測試繼承 lexical |
| Frontend unit/component | 68 | 0 | 0 | Vitest 17.42 秒 | 7 個測試檔，exit 0 |
| TypeScript＋Vite build | N/A | N/A | N/A | 外層 5.33 秒 | 兩階段均成功，exit 0 |
| Playwright 原測試 | 3 | 5 | 0 | 88.62 秒 | exit 1，過時斷言／操作 |
| Backend 定向修正驗證 | 30 | 0 | 0 | pytest 1.18 秒 | test_rag＋interactive synthetic，exit 0 |
| Backend 完整 regression | **396** | **0** | **0** | pytest 57.63 秒 | 4 warnings，exit 0 |
| Playwright 第一次 regression | 5 | 3 | 0 | 74.40 秒 | 新走到的 selector／選項 matcher／Benchmark 操作問題 |
| Playwright 最終 regression | **8** | **0** | **0** | 8.53 秒 | exit 0，report flaky=0 |

耗時依 console 或 JSON 量測範圍會略有不同；每輪外層 elapsed 與 UTC 起點另存 `*-result.json`，pytest XML 的 time 也略異於 console。沒有增加 timeout 掩蓋失敗，沒有加入 skip／fixme 或排除失敗案例。最終通過不代表已量測長期 flakiness。

### 2.1 實際執行入口

從 Repository root 呼叫本次獨立 runner；它只組裝既有 pytest/npm/Playwright 指令與報告位置。下列各指令都實際執行過；相同 Label 的 log 已存在，runner 會拒絕覆寫，未來重跑應使用新目錄或新 Label。

```powershell
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage backend -Label initial
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage backend -Label normal-user
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage frontend -Label initial
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage build -Label initial
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage browser-install -Label initial
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage e2e -Label initial
# 測試修正後
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage backend -Label regression
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage e2e -Label regression
& .\data\runtime\regression-20261026-161449\Run-Stage.ps1 -Stage e2e -Label regression-2
```

Backend 最初在工具沙箱內停滯；按「命令含 pytest＋本次專用目錄」識別並只終止該測試的兩個 Python 程序，之後在正常使用者環境完整執行。日常服務 PID 沒被停止。沙箱外重跑解除了停滯，但未進一步量測底層阻塞原因；不能將其斷言成核心程式 deadlock，也不能算套件通過。

展開後真正的測試指令如下（`$R` 為上述完整路徑；Backend cwd=`backend`，前端 cwd=`frontend`）：

```powershell
# Backend 初次完整執行 Label=normal-user；最終 Label=regression
& .\.venv\Scripts\python.exe -X utf8 -B -m pytest `
  --basetemp "$R/pytest-regression" --junitxml "$R/pytest-regression.xml" `
  --cov=app --cov-report=term "--cov-report=json:$R/coverage-regression.json" -q --tb=short
# 同時設定 COVERAGE_FILE=$R/.coverage-regression

# Backend 定向驗證（cwd=backend，實際採相對路徑）
& .\.venv\Scripts\python.exe -X utf8 -B -m pytest `
  tests/test_rag.py tests/test_interactive_synthetic_cases.py `
  --basetemp ../data/runtime/regression-20261026-161449/pytest-embedding-focused `
  --junitxml ../data/runtime/regression-20261026-161449/pytest-embedding-focused.xml -q --tb=short

# Frontend
npm.cmd test -- --reporter=default --reporter=json "--outputFile=$R/vitest-initial.json"
npm.cmd run build
npm.cmd run e2e -- --reporter=list,json "--output=$R/playwright-artifacts-regression-2"
# E2E 的 PLAYWRIGHT_JSON_OUTPUT_FILE=$R/playwright-regression-2.json
```

Browser 安裝實際使用專案 Node 執行 `data/runtime/mock-check/tools/npm/package/bin/npx-cli.js --no-install playwright install chromium`，`PLAYWRIGHT_BROWSERS_PATH=$R/browsers`。沒有全域安裝、沒有改永久 PATH、沒有修改 lockfile。

完整命令、cwd、exit code、開始時間及外層 elapsed 見 [Run-Stage.ps1](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/Run-Stage.ps1:1>) 與同目錄 `*-result.json`；機器可讀彙總見 [summary.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/summary.json:1>)。

## 3. 實際失敗、原因與修正

### 3.1 Backend：12 個失敗是測試模式未固定

原測試將 FakeEmbeddings 等注入 `DocumentService`，但沒指定 retrieval_mode；服務依設計仍讀取環境變數。整套測試以 lexical 啟動，導致本來要測向量的案例走 lexical/reindex skipped。這不是向量演算法失敗，也不是需要 Ollama；以假 Provider 明確指定 embedding 後，原有斷言全部通過。

| 原失敗案例 | 訊息節錄 |
| --- | --- |
| test_complete_interactive_cases_run_with_mock_embedding_and_llm | `skipped != ok` |
| test_reindex_recovers_changed_dimensions_and_preserves_old_on_failure | `skipped != ok` |
| test_reference_scope_reindex_isolated_from_synthetic_index | `skipped != ok` |
| test_embedding_retrieval_finds_semantic_match_and_persists | `no_results != ok` |
| test_embedding_search_ranks_by_cosine_after_normalization | `no_results != ok` |
| test_embedding_dimension_mismatch_returns_no_evidence_and_does_not_index | `no_results != failed` |
| test_embedding_index_excludes_non_synthetic_documents | `skipped != ok` |
| test_embedding_model_switch_creates_new_fingerprint | `no_results != ok` |
| test_embedding_failure_returns_no_evidence | `no_results != failed` |
| test_invalid_embedding_vectors_are_rejected | `no_results != failed` |
| test_embedding_policy_filter_and_limit_one_version_guard | `no_results != conflict` |
| test_reindex_rolls_back_partial_batch_on_provider_failure | `skipped != failed` |

最小修正：`test_rag.py` 13 處 constructor（含重開索引／切模型的實例）、`test_interactive_synthetic_cases.py` 1 處，明確加 `retrieval_mode="embedding"`。保留所有 score、維度驗證、transaction rollback、scope、持久化與故障預期；Provider 仍是離線假物件，不將全套測試切成真 Embedding。

來源：[test_rag.py](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/test_rag.py:28>)、[interactive synthetic](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/test_interactive_synthetic_cases.py:35>)。原始 log：[backend-normal-user.log](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/backend-normal-user.log:1>)；定向 30 passed；完整回歸 [backend-regression.log](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/backend-regression.log:1>) 為 396 passed。

### 3.2 Playwright：原始 5 個失敗

| 保留的測試目的 | 原失敗／過時假設 | 修正及影響範圍 |
| --- | --- | --- |
| Multi-Agent 保存與 UI 流程 | Expected length 5、received 6；同案後面還期待舊 clinical_assessment 與舊輸入 JSON 控制 | 驗證六個固定角色、六 calls、每節點一次成功 attempt；UI 看 Synthesis 藥物理由，trace API 檢查新 assessments 結構及 Audit context，GET Run 再驗證保存 |
| 成人配兒科文件不得發布 | 期待舊 population preflight 文字出現在 agent-led；現行 Multi-Agent 沒有那個前置 gate | 保留 Multi-Agent pending/不發布驗證，另外在同案走 single-agent，確認 population_filter.mismatched=1、generation skipped、output=null 及 UI 說明；沒有取消族群驗證 |
| 分析→證據→修改審閱→重讀 | 全頁第一個 ceftriaxone 是收合病例表內的隱藏 td | 改用可見候選卡內 heading；更新 JSON 控制標籤、展開文件群組／片段，再確認來源連結；完整保存與 reload 仍執行 |
| 未知過敏不能接受 | 點擊 disabled 的送出按鈕，60 秒 timeout，期待點擊後 alert | 驗證 accept/modify 選項 disabled property、submit disabled；再直接送 API accept，必須 HTTP 422 且 reviews 仍空，確認不能繞過 UI |
| 明確 Mock＋四模式 Benchmark | 期待舊「可供審閱的藥敏選項」與非空 AI candidate 卡 | 驗證逐藥表、0 AI 完整核對、pending 與 physician verification incomplete；Benchmark 明確選病例，使用新按鈕「執行所選比較」，檢查四模式及其中 Multi-Agent 真實回應 |

第一輪新走到的介面問題也保留紀錄：

- population 文字同時出現在 empty 摘要與限制列表，Playwright strict mode 命中兩處；改 exact match，不刪斷言。
- Playwright 1.56.1 的 `toBeDisabled()` 對本案 `<option disabled>` 回報 enabled；改檢查原生 `disabled` JS property。提交按鈕仍用 toBeDisabled，API 422 也實測通過，沒有放寬安全條件。
- 舊 Benchmark 按鈕已改名，且現在必須選病例；補上明確病例選取，而非增加 timeout。

最終保留原 **8 個案例，沒有跳過／刪除**。新增 helper `expectPendingMock` 檢查版本、Mock 身分、partial/needs_confirmation、errors 空、六角色順序、六 calls、attempt 成功、Case completed／其餘 needs_confirmation、AI candidates 空、pending 覆蓋來源藥物、醫師候選全部 incomplete。不是只把 `5` 改成 `6`。

新 Schema 核對：Synthesis `input.assessments` 包含 case_agent/ast_agent/evidence_agent/clinical_agent；Clinical 回報 unknown；Audit `assessments={}`、每藥有五個 claims。現行 AgentStep 沒有舊的原始 input JSON 展開控制，因此在 trace API 核對資料，UI 仍驗證角色與逐藥理由。這是介面遷移的測試更新，不是新增核心功能。

來源：[workflow.spec.ts](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/tests/workflow.spec.ts:1>)。初始失敗 [e2e-initial.log](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/e2e-initial.log:1>)；中間結果 [e2e-regression.log](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/e2e-regression.log:1>)；最終 [e2e-regression-2.log](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/e2e-regression-2.log:1>)。各輪 Playwright JSON、失敗截圖與 error-context 在同目錄，不覆蓋前輪證據。

## 4. 修改檔案與未修改範圍

| 檔案 | 本次變更 |
| --- | --- |
| backend/tests/test_rag.py | 固定假 Embedding 測試的模式，13 個 constructor |
| backend/tests/test_interactive_synthetic_cases.py | 固定 FlatMockEmbeddings 的模式，1 個 constructor |
| frontend/tests/workflow.spec.ts | 更新過時流程、Schema 與 locator；補六節點、pending、incomplete、API 安全與保存驗證 |
| docs/TEST_BASELINE_REPORT.md | 新增本報告；建立前確認不存在 |

新增 ignored 資產：`$R` 內測試 runner、環境／hash、原始測試備份、patch、logs、JUnit/Vitest/Playwright JSON、coverage、browser、暫存 DB；Playwright 設定產生的 `data/runtime/e2e/` DB；前端 `dist/` 與 `test-results/` 建置／截圖產物。它們不屬於核心程式修改。

Build 自動改寫了 tracked 的 `frontend/tsconfig.tsbuildinfo`；本輪結束前已按原 HEAD 內容還原，沒有留下此變更。沒有改 Agent Prompt、core app、資料集、醫療文件、設定、lockfile、既有三份交接文件，也沒有 Git commit。

## 5. 尚未修正的問題與限制

本次沒有發現「必須修改核心才能讓上述測試通過」的執行缺陷；不代表核心不存在缺陷。以下保留、不在本次測試修正範圍內：

1. **已確認 UI 文案過時**：病例工作台仍寫「通常 5 次獨立模型呼叫、遇缺漏或失敗提早停止」，現行 agent-led 六節點不符合此描述；研究設定畫面已寫六次。未修改 `App.tsx`。[舊文案](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/frontend/src/App.tsx:500>)。
2. **兩條流程的族群控制不同**：baseline 有 population 前置篩選；agent-led 由角色／Audit 處理，Mock 只回不確定。本次證明兩者不發布已驗證 AI candidates，不能據此證明 Live 模型能正確識別全部族群錯配，更不能把 physician_candidates 當通過名單。
3. **原始 input 的 UI 可見性**：現行 AgentStep 不提供舊測試期待的 input JSON 控制，需從 trace API 讀取；未把它偽裝成 UI 已具備。
4. **四個 deprecation warnings**：StarletteTestClient 使用 httpx、BlockingPortal alias、FastAPI/Starlette on_event/lifespan（後兩處各一警告）。沒有為消除警告升級依賴或改核心生命週期。
5. **研究指標缺口**：Benchmark 的 citation support、appropriateness、expert agreement、clinical utility 尚未獨立評估；既有軟體測試不能替代 Gold。[指標定義](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/benchmark.py:95>)。

測試程序早期在工具沙箱停滯是環境觀察；正常使用者環境執行成功。未用它推論真實部署的死鎖風險或效能。

## 6. 已覆蓋的功能範圍

Backend 完整測試涵蓋 Case contract／修訂、來源 AST／衝突／缺漏、規則 baseline、RAG 解析與版本／scope／lineage、假向量 cosine／維度／索引 rollback／持久化、六節點輸入與 call/time/output budget、wire/citation span、partial row／repair、來源／claim／risk Audit、AI 與醫師候選分離、Review 驗證、API／SQLite 重讀與 Benchmark 分母等。

Frontend 68 案涵蓋 App、AllergyContext、ReviewEditor、EvidenceLibrary、AgentLed、Insights、PhysicianReview 的呈現與互動。Build 包含 `tsc -b` 型別檢查與 Vite production build。

Playwright 8 案實際覆蓋：六節點 Run/trace／UI、reference/synthetic 文件隔離、population metadata 保存、成人／兒科錯配及生成略過、rule-only 分析至修改審閱和 reload、未知過敏 UI/API 阻擋、Mock 四模式執行／匯出入口，以及單模式／四模式 Benchmark 歷史區分。新增斷言保留原測試目的；使用的是測試自己的單藥 synthetic fixture，不是原 Mock DB。

### 6.1 本次量測的 coverage

| 範圍 | Statement coverage |
| --- | ---: |
| 全部 backend app | **92.28%**：4029／4366 statements，337 未覆蓋，11 excluded lines |
| RAG service | 89.39% |
| agent_led workflow | 96.91% |
| audit_sources | 98.08% |
| claim_checks | 92.22% |
| benchmark aggregation | 100% |

依據：[coverage-regression.json](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/regression-20261026-161449/coverage-regression.json:1>)。本次沒有開 branch coverage，也沒有收 frontend coverage；不能從 statement coverage 推論全部語意分支、產品需求或臨床情境均已測試。Benchmark 程式 100% 不表示指標足以評估醫療效益。

## 7. 尚未具備的驗證

| 缺口 | 目前可說／不可說 |
| --- | --- |
| 真實 LLM 請求與語意能力 | 有 fake transport/wire 測試；沒有本輪 Live endpoint、截斷率、模型漂移或臨床正確性驗收 |
| 真實 Embedding 品質 | 假向量演算法與故障分支通過；沒有 Ollama 模型權重、實際語意 Recall@k／nDCG Gold |
| 獨立醫療 Ground Truth | 沒有人工專家盲審 Gold、引用支持性／五維度風險標註，沒有可估計的臨床準確率 |
| 受控架構比較 | 四模式能執行，不代表資訊、檢索、預算、validator 相同；沒有已完成受控 ablation／置信區間 |
| 自動完整 handoff 瀏覽器流程 | Backend 有 handoff 測試；本次 E2E 用單藥 fixture，沒有自動以 agent-complete v4/18 AST 跑完整瀏覽器流程；原 18 AST 手動 Run 保留作另層證據 |
| 長時間／部署條件 | 未驗證長期 flakiness、負載／多使用者、斷電一致性、跨 Windows 版本／乾淨機器重建、正式認證與權限；已有重啟／持久化單元情境不代表這些全部完成 |

## 8. 未來修改時的 Regression Gate

先跑對應的現有定向測試，再按跨模組影響跑完整套件。所有命令沿用隔離環境／新 basetemp，不覆寫本報告或本次證據。RAG 的真實模型與 Prompt 的研究效果驗證需另立實驗，不在工程回歸中偷偷啟用付費 API。

| 修改類型 | 至少執行 | 跨模組合併前 |
| --- | --- | --- |
| RAG 排名／路由／切段／索引 | test_rag、test_reference_bundle、test_document_delete、test_agent_retrieval_budget、test_source_scope、test_input_context | 完整 Backend；EvidenceLibrary/AgentLed component；Playwright 全 8 案；另用固定 corpus 的 relevance Gold 評估研究效果 |
| Agent 資訊／協調／預算／Prompt | test_agent_led、test_agent_led_140、test_agent_time_budget、test_agent_output_budget、test_agent_retrieval_budget、test_citation_spans、test_input_context | 完整 Backend；AgentLed/Insights/PhysicianReview；Build；Playwright 全 8 案；Prompt 變更另做版本化 Gold 評估 |
| Evidence Audit／risk／claim／source | test_ast_sources、test_audit_sources、test_risk_dimensions、test_source_scope、test_allergy_provenance、test_safety_regressions | 完整 Backend；AgentLed/PhysicianReview；Build；Playwright 全 8 案，確認 UI 與 API 不可繞過 |
| Result／醫師清單／審閱 | test_physician_candidates、test_physician_review、test_backend_contract、test_acceptance | Component＋Build＋Playwright 保存／reload、pending/incomplete 分離 |
| Benchmark scorer／aggregation | test_workflow、test_acceptance、Insights component | 分子分母／N/A 手算對照、小型四模式、版本化外部 scorer；不能只比較完成率 |

日常測試範例與新環境建立方式見 `TESTING_AND_DEBUGGING.md`。該文件是先前靜態交接快照，內文「尚未執行／舊 E2E 斷言」是當時狀態；以本報告為本次實測更新，不回寫或抹去先前文件的歷史。

## 9. 工程 Baseline 判定

可開始建立 Evaluation Framework、離線 trace 分析與受控改進實驗：已有可重跑的隔離工程測試、修正後六節點 E2E、獨立保存證據，且原始 Mock DB／Run／Review 和日常服務保持不變。使用條件是固定 **HEAD＋本次測試 patch＋lockfile＋環境 manifest**，保留全部失敗與修復紀錄，而不是只記最後綠燈。

仍不能以這份報告宣稱「模型判斷正確」「可用於臨床」「Multi-Agent 比 Single-Agent 好」。下一個研究門檻是獨立 Gold、共同離線 scorer 與分母定義，再用相同病例／來源條件進行有授權的實驗；Mock pending 全部通過只證明未確認內容沒有被誤包裝成已驗證 AI 候選。
