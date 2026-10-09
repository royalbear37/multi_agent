# v9驗證與1.3.5接續

## 暫停前收到Sol/high交接：兩項不建議也有來源問題

審查已保存AGENT_LED_V9_REVIEW.md並停止。levofloxacin的audit只引DailyMed卻歸因WHO，且缺本藥AST fact_refs；tetracycline所選WHO段落無該藥／交互作用／腎毒性內容，也缺AST fact_refs。兩筆最終avoid不可當已確認排除；恢復後優先處理排除聲明的來源一致性，再做新live。其餘16筆及audit18未全面核對。1.3.5 AST僅完成小範圍守門抽查，詳見報告；本輪不再擴大工作。

## 最新：v9完成後依額度暫停（五小時剩4%）

2026-10-07 本次直接明確同意已使用於一次v9 live，沒有第二次外送。run `66e190b6-7feb-456d-9b1f-7cdba2fd64f8`，agent-complete revision4／18AST／gpt-4.1-mini／1.3.4，六次呼叫、無格式錯誤、約163秒、172153tokens（prompt158467／completion13686）。0可供審閱、16待確認、2不建議。`data/local/agent_cases/live-complete-v9-source-options.json`及`live-complete-v9-export.json`已保存且API匯出一致。無執行中的live或測試，session64327/58533已結束。

進步：synthesis引用識別碼錯誤為0；ertapenem選定CLSI缺值時模型保持unknown。AST仍18unknown，其中17筆實際有正確CLSI來源，但同時列了同藥同類別原始報告refs，1.3.4 guard誤把額外比較来源當invalid；clinical仍18unknown。獨立audit竟18supported，不能據此宣稱語意正確；兩個avoid亦需來源核對。

本機新1.3.5已修AST來源比較：確定S/I/R必須有有效selected_basis且所有已引類別一致，可保留同類別比較來源；缺selected來源／CLSI缺值／其他藥／相反類別仍不通過。合法conflicting仍保留。新增四個回歸，完整後端292passed（4既有warnings），diff check通過。本輪無前端變更，沿用上一輪43tests/build成功；1.3.5尚未live。Sol/high已受託小範圍AST修正及v9 avoid來源審查，額度達門檻已通知停止，只保存當下觀察；恢復時先讀AGENT_LED_V9_REVIEW.md，缺報告或未完成須補驗，不假設已通過。

五小時已用96%（剩4%），每週已用15%（剩85%），依使用者要求停止。backend session82216/PID22812仍載入1.3.4（尚未重啟載入1.3.5），frontend33116沿用。恢復先查額度→讀Sol/high交接→完成1.3.5來源修正複查→在無進行中分析時重啟自己的backend→再取得新的具體一次授權才可live。不可重用v9授權。不要把舊v9當1.3.5驗證。

後續仍須核對audit18supported與兩項avoid的實際來源、逐藥風險證據涵蓋、正常事實誤列issues與重複摘要、未測AST選項、八情境／配對比較、候選至人工審閱及瀏覽器QA。未完成臨床驗收，禁止強行出藥。以下保留較早進度，以上方為準。
