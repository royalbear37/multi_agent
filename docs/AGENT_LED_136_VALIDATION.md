# Agent-led 1.3.6 本機驗證（2026-10-07）

目前完成軟體層的來源一致性修正，尚未執行 1.3.6 live。上一筆直接授權已用於 v9，不重複使用。

## 修正內容

- 1.3.5 的 AST 修正保留：選定判讀依據有效時，可同時引用同藥且類別一致的原始報告。相反類別、錯藥、缺少選定依據仍不能確認；不重算 MIC 斷點。
- 1.3.6 的獨立證據複核接收原始 AST 與可選來源，逐藥回傳來源類別、來源欄位及聲明中的類別。程式分別核對來源及聲明的一致性；未知／未測不能支持敏感聲明。
- 文件聲明只使用該聲明選定、且複核實際引用的片段檢查藥名及來源歸屬。風險引用不能補足另一個不相關的治療引用。只引 DailyMed 卻歸因 WHO、引用其他藥品段落等情況降為待確認。
- 組合藥名容許成分倒序、AND、常見鹽類與 clavulanic acid 拼法；不同句子的成分不能拼成同一藥名。逗號分隔仍可能保守降為待確認。
- 前端分開顯示 AST 來源狀態、聲明一致性及具體來源問題。不把來源確認呈現成臨床適用性確認。
- 舊 run 契約保持相容；新欄位只在新版模型輸出要求。未恢復 RuleEngine 前置筛選或人工審閱重判。

## 驗證結果

| 項目 | 結果 |
| --- | --- |
| 完整後端測試 | 308 passed；4 個既有 deprecation warnings |
| 前端測試 | 45 passed |
| 前端正式 build | 成功 |
| git diff --check | 通過；僅行尾轉換提示 |
| Sol/high 工作目錄審查 | 已修正藥名跨句誤配、風險引用借用及來源／聲明狀態混淆；最後小範圍複查無阻擋問題 |
| Ollama 啟動檢查 | embeddinggemma，768 維 |
| API 舊資料相容 | 重啟前後 v9 export 均與已保存 JSON 完全一致；health 200 |
| 新版 live／瀏覽器醫師驗收 | 尚未完成 |

## 保存資料的離線重驗

來源 run：`66e190b6-7feb-456d-9b1f-7cdba2fd64f8`（v9，1.3.4）。重驗檔：`data/local/agent_cases/v9-offline-source-regression.json`。未呼叫模型、未更新舊 run，也未替模型補寫新 ast_check。

AST 還原保存的模型判斷後再套目前來源檢查：15 susceptible、1 resistant、2 unknown。ertapenem 缺選定 CLSI 類別；levofloxacin 的原始／CLSI 類別有衝突，不能當確定一致。

兩筆歷史 avoid（levofloxacin、tetracycline）的 audit 重新核對均為 uncertain：除了舊契約未提供新增的独立 AST 核對，分別還有 WHO 歸因不符與引用未辨識該藥問題。這只證明目前來源守門會攔下保存的問題，不能代替新版模型的 live 驗證。

## 接續位置

backend session `12113`／PID `19676`，已載入 1.3.6；frontend 沿用 session `33116`。沒有進行中的 live 或測試。

1. 取得新一次直接授權後，以 agent-complete 第 4 版、18 AST、WHO／DailyMed、既有外部 gpt-4.1-mini 執行一次 live；預定輸出 `live-complete-v10-audit-provenance.json`，啟動前確認不存在。
2. 核對新版每項來源、語意及適用條件，包括全部 audit 與最終去向。模型對 claim_assessment 的辨識仍可能錯誤；最低程式檢查不等於語意或臨床認證。
3. 續作逐藥風險文件涵蓋、正常事實誤列缺漏、角色重複文字、未測 AST 的指引選項。
4. 八情境與論文相關過敏配對比較、候選至人工審閱、比較與匯出、瀏覽器醫師驗收仍未完成。沒有候選時不虛構接受流程。
5. 持續依使用者額度門檻停止：五小時剩餘 ≤5% 或每週剩餘 ≤3%。
