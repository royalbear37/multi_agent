# Offline Evaluator MVP 驗收紀錄

日期：2026-10-26。HEAD `1ad2648a349c28989c9fa3d41cd37bf56a40f0fd`，Python 3.12.14，使用既有 `backend/.venv`。本次未安裝套件、未提交 Commit。程式版本為 HEAD＋先前的三個測試修正＋本次新增 evaluation 模組，不能只以原 HEAD 重現新增功能。

## 1. 本次新增檔案

```text
backend/app/evaluation/__init__.py
backend/app/evaluation/schemas.py
backend/app/evaluation/io.py
backend/app/evaluation/alignment.py
backend/app/evaluation/metrics.py
backend/app/evaluation/evaluator.py
backend/app/evaluation/export.py
backend/app/evaluation/cli.py
backend/tests/evaluation/test_offline_evaluator.py
docs/OFFLINE_EVALUATOR_MVP.md
docs/OFFLINE_EVALUATOR_VALIDATION.md
```

既有 workflow、benchmark.py、RAG、Prompt、設定、病例與交接文件均未改動。工作目錄仍顯示三個既有測試修改：test_interactive_synthetic_cases.py、test_rag.py、workflow.spec.ts；本次核對其 SHA-256 與前次 Baseline 完全相同，並非本輪修改。

本機 ignored 證據位於 `data/runtime/evaluator-mvp-20261026/`，主要為：

- `saved-run.json`：以唯讀 SQLite 取得既有 Run 的 JSON 副本。
- `pilot-run-manifest.json`：該 Run 的精確 case snapshot hash、revision、來源分組與 18 藥 universe；不是 Gold。
- `report-final/report.json`、`report-final/observations.csv`：正式 MVP smoke report。
- `unit-final.xml`、`regression-final.xml`、`regression-final.log`：實際測試結果。
- `preservation-before.json`、`preservation-after.json`：資料與原始碼保全證據；after 另記八個新增模組檔的 SHA-256。
- `Run-Regression.ps1`：本次專用隔離測試入口，DB/tmp/log/basetemp 全在這個目錄。

## 2. 實際測試結果

| 範圍／輪次 | Passed | Failed | Skipped | 說明 |
| --- | ---: | ---: | ---: | --- |
| Evaluation 初版 | 57 | 0 | 0 | Loader、alignment、指標與匯出 |
| Evaluation 擴充契約 | 66 | 0 | 0 | 加入未來 Gold payload、邊界驗證 |
| 完整 Backend（正常使用者環境第一輪） | 462 | 0 | 0 | 原有 396＋當時新增 66；4 個既有 deprecation warnings |
| **Evaluation 最終版** | **67** | **0** | **0** | 另驗證 failed Run 無最終輸出時為未評估，console 0.93 秒 |
| **完整 Backend 最終版** | **463** | **0** | **0** | 原有 396＋新增 67，console 18.16 秒；4 warnings |
| 現有 Mock Run CLI | 成功 | — | — | exit 0；153 observations，無 invalid_output／alignment_error |
| 實例 JSON／CSV 核對 | 153 列一致 | — | — | metric、status、value、details 逐列比對 |

測試不能跨輪相加。最終依 `unit-final.xml`／`regression-final.xml` 判定。JUnit XML 與 console 的計時範圍略有差異。

最初完整 Backend 在工具沙箱內完成部分輸出後停滯，沒有完整 summary/XML；依命令列同時包含 `-m pytest tests` 與本次 evaluator runtime 路徑，確認並只停止兩個本次 pytest 程序，之後以同一隔離設定在正常使用者環境重跑通過。該沙箱輪不能算 pass／fail，也未據此斷言核心程式 deadlock。沒有終止日常前後端程序。

4 warnings 均為既有 FastAPI／Starlette 的 httpx、BlockingPortal、startup on_event deprecation。沒有為消除警告變更依賴或 production code。

Frontend、Build、Playwright 本次未重跑：新增模組沒有 API／前端引用或合約變更。前次 68／Build 通過／8 passed 僅是歷史 Baseline，不作本輪驗收數。也未重新量測 coverage，前次 92.28% 不適用於新增模組後的分母。

## 3. 實際指令

從 `backend/` 執行最終 unit tests：

```powershell
./.venv/Scripts/python.exe -m pytest tests/evaluation -q --tb=short `
  --basetemp ../data/runtime/evaluator-mvp-20261026/pytest-unit-final `
  --junitxml ../data/runtime/evaluator-mvp-20261026/unit-final.xml
```

從 Repository root 執行最終 regression：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File data/runtime/evaluator-mvp-20261026/Run-Regression.ps1 -Label final
```

該腳本實際呼叫 `python -X utf8 -B -m pytest tests -q --tb=short --basetemp <新的 pytest-final> --junitxml <regression-final.xml>`。再次執行時使用新 Label，腳本拒絕既存 basetemp；不覆寫這輪證據。

腳本確認沒有 backend/.env，設定：

```text
PROTOTYPE_DB_PATH=<本次runtime>/regression-import-final.db
PROTOTYPE_CATALOG_PATH=<本次runtime>/absent-catalog.json
PROTOTYPE_RULE_CONFIG=<repo>/configs/research/rules.json
RAG_RETRIEVAL_MODE=lexical
LLM_PROVIDER=mock
TEMP/TMP=<本次runtime>/tmp
PYTHONDONTWRITEBYTECODE=1
```

並清除繼承的 LLM_API_KEY／BASE_URL／MODEL；既有 pytest fixtures 仍自行選擇暫存 DB、Fake Provider、Fake Embeddings。沒有呼叫真實模型、付費服務、Ollama 或 GPU。

從 `backend/` 評估既有 Run：

```powershell
./.venv/Scripts/python.exe -m app.evaluation.cli `
  --runs ../data/runtime/evaluator-mvp-20261026/saved-run.json `
  --manifest ../data/runtime/evaluator-mvp-20261026/pilot-run-manifest.json `
  --out ../data/runtime/evaluator-mvp-20261026/report-final
```

這個輸出目錄已存在；重現時換成新的 `--out`，不能覆寫本次結果。CLI exit 0 並不表示所有品質指標都已評估，missing_gold 是正常且必要的研究狀態。

## 4. 資料保全與實際結果

前後以 SQLite `mode=ro` 讀取 prototype.db 與 documents/rag.sqlite3 **每張資料表的完整列**，排序序列化後比對 SHA-256；另對開始時所有 backend/app 原始檔與 data/handoff 資產比對檔案 hash。共 79 項 top-level assets/table maps，全數相同。測試前後的 schema／原始核心程式沒有改動。

既有 Run `51905060-412e-4e04-99f3-c9a1bbbbc596` 與 Review `032218e1-913e-4a5e-9a9a-1493246f040d` 所在資料表內容不變；醫療文件、病例 history、AST 與正式 Run 皆未覆寫。

最終報告讀取保存資料：六節點完整、18/18 pending、0 AI candidates、Run elapsed 255.518 ms。AST source consistency 1/18（5.56%）只表示 Mock 的全 unknown 與來源缺失項相符；沒有提供研究／臨床 Gold，AST Gold accuracy、retrieval／claim／audit／clinical／candidate／unsafe 品質指標皆沒有假造分數。空引用為 null；Mock token/cost 為 not_evaluated。

## 5. 尚存限制與後續驗收

- Source consistency 是獨立來源欄位比對，並非臨床 breakpoint／處方判定。conflict case 尚需政策裁決；偵測能力還缺結構化 prediction binding。
- Gold Schema 與 provenance 可驗格式，無法自動保證人工標註正確、資格真實或資料無洩漏。需要獨立審閱流程。
- MVP 的詳細 Agent adapter 僅覆蓋 agent-led-1.6.0；其他版本／模式保守回 not_evaluated，不推測舊 Schema。
- 未來 Gold 指標僅有資料契約與未評狀態，尚無 Retrieval／Claim／Audit／Clinical／Candidate scorer；提供 Gold 並不會自動啟用它們。
- 真實模型成本、端到端額外時間、未保存重試、被丟棄的 raw output 無法從這筆 Mock Run 復原。
- 下一個最小研究工作包為：五個 dev Pilot 的身份固定、A_source 標註與 conflict 政策、固定 corpus 的 B relevance／critical spans；之後才加入語意與臨床標註／scorer。

新增 evaluator 或 Gold 指標時先跑 `tests/evaluation`，若修改共用資料契約／API，擴大至完整 Backend、Frontend／Build／Playwright。保持 Gold 與被評 validator 獨立，繼續保留 failed／invalid／missing 的分母資訊。
