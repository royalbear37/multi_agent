# Agent-led 1.4.0 唯讀審查

範圍：本輪只檢查 `wire_validation.py`、`partial_agents.py`、`claim_checks.py`、`agent_led.py` 的逐藥補正與第二層 `review_options` 邊界，以及直接相關的 wire 契約與前端顯示。審查過程僅更新本文件，未改程式、未執行 live 或外部模型；父任務回報既有 312 項與新增 19 項 1.4 回歸測試通過，這裡不把它解讀為 live 已驗證。

## 已確認的修正

- 原始 `Decision.claims` 現需長度 5 且五個面向各一次；wire 將 `claims` 設為 required 並限制 `minItems=maxItems=5`，`validate_claim_checks()` 也用 `original_complete` 避免重複面向經 dict 覆蓋後變成完整核對。重複 claims 的回歸測試涵蓋感染與腎功能。
- Evidence Agent 的 `original_drugs` 在首次呼叫前固定，補正時即使 `data.drugs` 縮成新增藥 X，來源具名檢核仍以原清單判斷。無關引文不能藉第二次呼叫使 X 成為既有藥。
- 正常路徑下，Clinical Agent 頂層或任一分項回報 `avoid` 時，`classify_options()` 不將待確認項升為 `review_option`，並列 `reported_avoid` blocker。`model_status` 在後續來源檢核降級前保存。
- 合併補正輸出時，被補正藥的舊 `issues` 由新回覆替換，其他藥與全域 `issues` 保留；可避免已撤回的逐藥 blocking issue 持續誤擋。

## 追加發現與修正後覆核

1. **原始 claims 缺失的提升路徑已封住。** 新 audit 的 `atomic_claims_required=True` 會經 `Input` 保留到逐藥驗證，縱使原始 `claims=[]` 仍呼叫 `validate_claim_checks()`。每筆 check 產生程式端 `validation_status=checked`；原始五面向不完整時，各 check 轉 `uncertain`。`infection_supported()` 另要求 checked 標記，不能把尚未核對的模型 `supported` 直接升為 `review_option`。新增「synthesis 省略 claims、audit 回 supported」回歸覆蓋此路徑。
2. **清理給藥文字前的避用狀態已保留。** `validate_output()` 在處方文字清理前複製 Clinical Agent 原回覆的風險列，後續以該副本記錄頂層與三分項 `model_status`。因此即使清理使當前狀態降為 `unknown`，`classify_options()` 仍讀得到原回覆的 `avoid` 並禁止提升；新增回歸覆蓋頂層 avoid 加給藥文字的情境。

依上述小範圍路徑及回歸，**目前未見這兩個已報邊界仍可繞過**；沒有以此推論所有模型語意、引用適用性或下一次 live 結果。

## 其他範圍與界限

模型呼叫在每次呼叫前檢查上限，`max_calls` 被限制至 8，底層 provider 設 `retries=0`；所讀路徑未見超過八次呼叫的繞過。`review_options` 從最終 `pending` 複製，Review API 的候選邊界仍只含真正候選。沒有全面審定所有感染、族群、藥敏或臨床語意；模型語意核對不能由 schema／prompt 改善保證。

## 2026-10-08 前端小幅修正唯讀審查

範圍：`App.tsx` 的歷史 run 來源資訊與確認事項導覽、`Insights.tsx` 的模型及角色標籤、`AgentLed.tsx` 的確認事項去重與節點定位。未執行 live、外部模型或完整 1.4 後端測試；前端測試由父任務另行執行。

1. **P2：確認事項可導向不存在的 Agent 節點。** `AgentIssues` 只檢查 `x.agent_id` 就繪製「查看此步驟」按鈕（`frontend/src/AgentLed.tsx:29`）；`App.tsx:73-77` 在找不到 `agent-step-${agentTarget}` 時仍清除目標並留在流程頁。現有 `App.test.tsx:174` 的歷史 run 測試資料即包含 `clinical_agent` 確認事項、卻只保存 `evidence_agent` 節點，因此第二個按鈕可重現空導覽。建議由 `RunIssues` 傳入實際存在且可定位的 Agent ID 集合，僅對其中的確認事項顯示按鈕；找不到目標時保留目前頁面或顯示明確訊息。錯誤步驟按鈕已在 `Insights.tsx:243` 檢查節點存在，可沿用相同條件。

   **修正後覆核：已結案。** `Insights.tsx:244` 現從歷史 run 的 `nodes` 收集實際 `agent_id` 節點並傳入 `availableAgents`；`AgentLed.tsx:29` 只有該集合包含確認事項的角色時才顯示導覽按鈕。重新讀取這兩段程式後，前述只有 `evidence_agent` 節點的資料不再出現 `clinical_agent` 空導覽；父任務另在前端整合測試加入按鈕數量斷言。

其餘所讀範圍中，`RunProvenance` 使用 run 自身的 `case_revision`、`case_id`、`created_at`，缺值時有文字替代；Agent 問題去重鍵包含角色、藥品、欄位、影響、動作與 blocking，沒有把不同角色的相同問題合併。沒有發現這些路徑另有可重現的資料錯置。
