# DailyMed 固定版本交接資料包

這裡保存目前 DEMO 使用的 20 份公開 DailyMed 標示：`*.xml` 是下載原件，`*.md` 是保留章節標題的檢索文字。`manifest.json` 記錄來源網址、SPL 版本、原產品名稱及兩份檔案的 SHA256。這不是最新版藥品資料庫。

使用固定檔案可重現文件內容；不要用依藥名搜尋後取第一筆的下載方式取代它，搜尋順序與標示版本可能改變。原件與來源網址提供查核依據，不表示內容經本專案臨床驗證。

注意：`imipenem.md` 原產品為 RECARBRIO（imipenem/cilastatin/relebactam 複方）。保留原檔以追溯歷史；不能當成單一 imipenem 標示。1.5.1 來源檢查會標出此範圍不符。Manifest 保留歷史文件簡稱，另列 `original_product_title`，不要只靠檔名判斷成分。

根目錄執行：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/install_reference_bundle.py --verify-only
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/install_reference_bundle.py
```

第一行只驗證檔案；第二行匯入目前設定的本機文件庫，不匯入病例、不呼叫模型。接著啟動後端，在「文件資料庫」選「參考文件」並按「重建向量索引」。詳細交接見 [GitHub 交接說明](../../../docs/GITHUB_HANDOFF.md)。
