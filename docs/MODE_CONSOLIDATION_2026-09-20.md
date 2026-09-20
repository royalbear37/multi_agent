# 模式整併與測試修復

2026-09-20 完成。CSV 規則重寫仍暫緩。

- 可執行模式固定為 rule-only、rag-only、single-agent、multi-agent。
- 移除舊 multi-agent 的一次生成分支與專用 node-summary prompt；原 multi-agent-v2 的五 Agent 流程改用 multi-agent 名称。新 API 不接受 multi-agent-v2。
- 保留內部 v2 契約、環境變數、workflow 版本及逐藥證據快照欄位，避免歷史資料失去解讀方式。
- 歷史 run 不改寫。舊 multi-agent、歷史 v2、Benchmark 聚合與逐筆結果均有對應標示；新流程在首次呼叫前失敗也不會誤標成 legacy。
- Demo 繼續逐項省略無效藥品／引用，保留有效項目。同藥候選與排除互相矛盾時移除候選，即使排除項本身無效也不讓候選因而留下。沒有有效候選時暫緩輸出並顯示需確認。
- 原 6 個嚴格拒絕整份結果的測試，改為檢查逐項過濾契約；另擴充三生成模式、有效與無效混合輸出、歷史隔離、API 舊模式拒絕與早期失敗標示回歸測試。人工審閱仍嚴格檢核。

## 驗證

- 完整後端：191 passed，0 failed，4 個既有套件 deprecation warnings。
- 前端單元測試：24 passed；TypeScript／Vite 建置成功。
- 本機 Chrome／Playwright：五 Agent 執行、trace 顯示與四模式 Benchmark 共 2 passed。使用獨立測試資料庫及 mock，沒有付費 live 呼叫。
- Sol／high 唯讀審查完成，所指出的歷史標示與文件問題已修復，最後無待處理 finding。
- 本機後端已用原啟動命令重新載入；重啟前確認沒有執行中的分析。

先前計畫驗收稽核文件中的 176 passed／6 failed 為當時快照，本文件記錄本次修正後結果；其他計畫缺口不因本次軟體測試通過而視為完成。
