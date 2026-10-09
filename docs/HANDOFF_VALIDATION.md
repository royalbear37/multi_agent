# 2026-10-10 交接驗證

本輪以 Git 暫存內容匯出乾淨副本，不含原工作站的 `.env`、私人 CSV、原 runtime、`.venv` 或 node_modules，再照 README 安裝。驗證環境為 Windows／Python 3.14／Node 24；套件以 lock 檔安裝，可使用套件下載快取，未借用原工作站虛擬環境。

提交資料：28個使用中的混合病例、95修訂、24份文件安裝清單、95藥／97菌字典；WHO原書、WHO章節、DailyMed原件與文字、研究論文及負向控制文件。病例保留來源 AST 與人工情境的區別，移除 source_record_id，重設外送許可。未執行付費分析。

| 項目 | 結果 |
| --- | --- |
| README `scripts/setup.ps1` | 全新 Python venv、requirements.lock、npm ci 與 DB 初始化成功 |
| 鎖定依賴 | 補齊 jsonschema、attrs、jsonschema-specifications、referencing、rpds-py，乾淨安裝通過 |
| 後端完整回歸 | 384 passed，4 項既有依賴棄用警告 |
| 前端完整回歸 | 59 passed |
| TypeScript／Vite build | 通過 |
| 公開資料包 | 20 組 DailyMed MD/XML hash 通過；病例、24份檢索文件與字典 hash、病例 schema、WHO 章節對原 PDF 核對通過 |
| 來源保留 | 95 修訂的 AST 及非授權／provenance 病例欄位逐一對原 DB 相同 |
| `scripts/handoff.ps1 -PrepareOnly` | 28 病例、95修訂、24文件匯入乾淨 DB；不依賴 CSV |
| 重複匯入 | 保留接手者既有病例及修訂，不重複建立文件 |
| 衝突預檢 | 既有同內容文件的族群／來源分類衝突，在任何資產匯入前拒絕；不悄悄修改標示 |
| API smoke | health、病例／文件列表、reference 搜尋、四模式、run 匯出、逐藥有條件採用與審閱匯出、四模式 Benchmark 及匯出均通過 |
| 提交內容掃描 | 未包含 `.env`、原始 CSV、runtime DB、data/local、虛擬環境；未命中常見 API key／私鑰格式 |
| Sol/high 審查 | WHO 族群衝突及 synthetic/reference 身分錯配兩項已修正，專項5測試通過，無剩餘已報阻擋項 |

API smoke 使用 `agent-complete` 第4版、18筆AST、lexical＋mock。rule-only、rag-only、single-agent 為 awaiting_review／ready_for_review，multi-agent 為 partial／needs_confirmation、六次 mock 呼叫；四模式 errors 均空。mock 不聲稱有臨床證據支持，多代理待確認是預期的保守測試結果。

本輪未重跑瀏覽器 E2E、未執行新付費 live、未在新副本建 Ollama 向量；不能將安裝與 mock 測試解讀為臨床正確性驗證。手動文件及 API 驗證亦不宣稱每一頁前端已重新由醫師操作。下一步 live 仍需接手者配置服務、索引與病例外送許可。

安全差異及操作步驟以 [病例包說明](../data/handoff/README.md)、[README](../README.md)、[交接清單](GITHUB_HANDOFF.md) 為準。歷史付費 run 與醫師決策沒有搬入新 DB，接手者可重新執行相同病例流程。
