# 目前工作站的病例與文件交接包

2026-10-10 匯出：28 個使用中的混合測試病例、95 筆病例修訂。包括八個 Agent 情境、四個過敏配對情境、API demo 與 15 個來源／配對病例。`agent-complete` 保留第 4 版、18 筆 AST。所有臨床情境仍記錄為人工編製；來源 AST 不改判、不改成全部合成。

在根目錄完成 `scripts/setup.ps1` 後：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/install_handoff.py --verify-only
powershell -ExecutionPolicy Bypass -File scripts/handoff.ps1
```

另開終端執行 `scripts/frontend.ps1`，選 `agent-complete`，用 mock 執行四種模式。只匯入而不啟動服務可用 `scripts/handoff.ps1 -PrepareOnly`。要用一般後端設定，停止此 mock 服務，依根目錄 README 設定自己的 `.env`、Ollama，再用 `backend/scripts/run.ps1`。

安裝內容：

若既有同內容文件的族群／分類與包內不同，安裝會在匯入任何資產前停止，並指出該檔及欄位。尤其舊機 WHO 的 `all` 與本包 `mixed` 不同：請人工核對後在文件庫修改族群，或在執行指令前設定 `$env:PROTOTYPE_DB_PATH = '../data/runtime/receiving/prototype.db'` 使用新 DB；不要刪掉舊 DB。以後的一般後端也須使用相同 DB 設定。

- 病例依修訂順序重新匯入；全新 DB 保留原修訂號。既有同 ID 病例不覆寫，報告會列出略過項目。
- 24 份文件：WHO 原書、下泌尿道章節、20 份 DailyMed 檢索文字、過敏研究論文、負向控制文件。原書與 DailyMed 不重複存檔，manifest 指向 Git 內檔案。DailyMed XML 原件另由其資料包保存。
- 逐檔核對 SHA256，WHO 章節重新對原 PDF 擷取核對後建立來源關聯。新 doc_id 會不同；病例中的文件 ID 會按對照表替換。歷史病例若指向已刪除文件，保留原待確認狀態，不補造來源。
- 95 個藥品名稱、97 個菌種名稱的字典，匯入到 `data/local/microbiology/catalog.json`。只有名称與彙總筆數，不含 CSV 明細。既有不同字典不覆寫。
- 病例內原有的抗藥背景彙總仍保留；它不是院內 antibiogram。

安全差異：移除病例 `source_record_id`，每版的 `external_model_allowed` 設為 false；不提供原始 CSV、raw_payload、API key、`.env`、本機帳號／路徑、完整 runtime DB、歷史模型回覆及審閱者記錄。1.6.0 已移除外送勾選；external_model_allowed 僅為舊 metadata，不影響執行，選 live 即使用設定的模型。

WHO 原書在原工作站曾標示「所有年齡」，此包改為「混合」，避免把全書當成每段都適用於所有族群。其餘文件內容、來源分類、版本與病例分析欄位均保留。這項明示的修正可能改變其他三模式的候選檢核結果。

`agent-renal-revision-example.json` 是額外的編輯展示範例，未自動套用。可在工作台選 agent-renal → 編輯並建立新版本 → 貼上該檔內容 → 保存，再比較新舊分析。

匯入不建立向量、不呼叫模型。向量需在接手者機器上重建；mock 只驗證流程，新的 live 回覆不保證與原工作站逐字一致。安裝報告 `handoff-install.json` 保存於 DB 同層，含文件 ID 對照及略過病例清單。
