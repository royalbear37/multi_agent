# 獨立代理協作 v2

`multi-agent-v2` 是新增的可選模式。舊四模式、現有資料庫與人工審閱繼續可用。v2 目前為有明確依賴的單輪協作：每個 Agent 分別接收結構化輸入、執行自己的 prompt 和模型呼叫，再回傳經驗證的輸出。同一模型可擔任不同角色，也可按 Agent 設定不同模型；無需為各 Agent 部署獨立服務。

## 執行順序與訊息

前置資料／規則／族群／檢索檢查 → 病例整理 → 藥敏、證據、臨床背景三個專責 Agent → 結果整合 → 最終確定性安全檢查 → 人工審閱。

三個專責 Agent 都讀取病例整理 Agent 的輸出，目前按固定順序執行。整合 Agent 讀取全部四份結果；沒有無限對話、自動討論迴圈或投票覆蓋安全規則。

| Agent | 輸入 | 輸出 |
| --- | --- | --- |
| case_agent | 去除來源識別欄位的必要病例事實 | 發現、缺漏、限制、是否需確認 |
| ast_agent | 病例事實、病例整理、來源 AST、規則允許集合 | 已核對藥品、發現、限制、是否需確認 |
| evidence_agent | 病例事實、病例整理、已篩選的引用片段 | 支持藥品、每藥引用及說明、限制、是否需確認 |
| clinical_agent | 病例事實、病例整理、允許集合、硬性排除 | 額外排除、發現、限制、是否需確認 |
| synthesis_agent | 四份 Agent 結果、必要事實、引用及縮小後集合 | 候選、避免、限制 |

輸入／輸出型別在 `backend/app/agents/contracts_v2.py`；角色及 prompt 在 `runtime_v2.py`；協調器在 `backend/app/workflow/v2.py`。`GET /api/agents/v2/contracts` 提供版本、各角色 prompt 和完整 JSON Schema。

## 安全邊界

- 前置檢查重用原 `rule-only` 工作流，停用生成；未達 ready_for_review 就不呼叫五個 Agent。檢索可能依現有設定呼叫 embedding 服務。
- 每份輸出須通過嚴格 schema、引用 ID、藥品集合、文字內容檢查後才傳給下一步。病例缺漏或任何專責 Agent 回報不確定，均暫緩結果。
- 整合集合取規則允許、AST 已核對、證據支持的交集，再扣除臨床背景與規則排除。空集合不呼叫整合模型。
- 每藥必須有自己的引用連結；整合與人工修改都不能擴大該次保存的藥品／引用邊界。硬性排除不因模型省略而消失。
- 最終輸出再次經原有 review validator；模型錯誤不回退成舊流程的候選。
- 上傳資料與其他 Agent 的訊息作為不可信資料傳入；不要求或保存模型內部思維鏈。Trace 保存結構化 findings 與依據。
- 來源病例在每次外部呼叫前檢查 external_model_allowed；所有角色皆排除來源病人／就醫 ID、CSV 原始列、來源日期與 provenance 識別欄位。自由文字與引用仍須符合資料使用權及外送條件，欄位投影不等於完整去識別化。
- 不通過整體檢核時，中間輸入／輸出留在本機受控 run 紀錄，正常 API、trace API、JSON 匯出及 benchmark 回應只呈現狀態／錯誤等中繼資料。原始不合法模型回覆不保存。

程式檢查能驗證引用是否存在及是否符合保存的範圍；無法證明該引用在臨床上支持結論。AST 敏感性、臨床適用性及模型說明仍須人工核對。

## 操作

1. 依原啟動方式重新啟動後端及前端。
2. 選擇已備妥的病例，在「比較模式」選 `獨立代理協作 v2（研究）`。
3. 初次選 `明確啟用 mock（離線展示）`，按「執行分析」。MOCK 為訊息協定測試，不代表真正模型推理；要完整離線，檢索也須設 lexical。
4. 在「證據與流程」展開五個 Agent，可查看輸入、輸出、模型、上游依賴、各次呼叫與重試。
5. 「研究與設定」預設四模式；勾選加入 v2 才會執行五模式比較。摘要另列每個 Agent 的呼叫、失敗、略過、已知 Token 與耗時。

## 模型與預算

各 Agent 預設使用原有 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。`.env.example` 列出五個可選的 `LLM_V2_<AGENT_ID>_MODEL` 覆寫。使用目前相容的 Chat Completions、temperature=0、JSON mode；不同 API 模型的參數相容性須另行確認。

| 設定 | 預設 | 程式限制 |
| --- | --- | --- |
| LLM_V2_MAX_CALLS | 8 | 每個 run 共 1–10 次嘗試，含重試 |
| LLM_V2_MAX_RETRIES | 1 | 每 Agent 0–1 次，只重試暫時連線／429／伺服器錯誤 |
| LLM_V2_TIMEOUT_SECONDS | 120 | 10–300 秒協調截止時間 |
| LLM_V2_MAX_OUTPUT_TOKENS | 2000 | 每次回覆 256–8000 tokens |

完整成功路徑通常 5 次生成呼叫，MOCK 也記錄五次模擬呼叫。每次 HTTP timeout 不超過 20 秒且會縮短至剩餘時間；完成後再次檢查截止時間，遲到結果不得發布。此為同步 HTTP 的 timeout 與階段截止檢查，不是可強制取消所有底層網路讀取的硬即時上限。

每次呼叫記錄開始／結束、錯誤、回覆 ID、用量、驗證狀態。Agent trace 另記 input/output hash、prompt 版本／hash、span ID、parent span IDs。未知用量保留 null；`usage_complete=false` 表示已知用量可能低於帳單總量，cost 維持 null。

一般 `/api/runs` 在每次呼叫前及 Agent 結束後保存 checkpoint；服務中斷後可查既有片段，不會自動重跑付費呼叫。Benchmark 目前仍以完成一筆 run 後保存為單位。

## 版本與回復

v2 是新模式，不遷移舊 run，也不刪除既有流程。改選舊模式即可繼續既有工作。歷史 TODO 的完成紀錄保留，新增的架構與後續驗證記錄在 MULTI_AGENT_V2_TODO.md。本次開發前的程式快照保存在工作區根目錄 `v2-before-2026-09-18.zip`，只用於參考；不要用它覆蓋後續的新變更。
