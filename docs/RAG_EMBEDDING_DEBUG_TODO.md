# RAG embedding 查詢失敗：修復與驗證紀錄

## 2026-09-16 恢復後的結果

- Ollama 對兩個查詢都成功回傳 768 維向量。
- 原文件庫有 WHO 的 1,442 個片段，但沒有已提交的 WHO 向量；另有 8 個展示文件向量。保留資料庫副本後，以一般連線完成 SQLite 殘留 journal 的恢復，完整性檢查為 `ok`。設定 API 隨後可正常讀取。
- 使用真實 SQLite 小快取重現：重建索引和搜尋時自動補索引，都會在等待下一批 embedding 時持有寫入交易；快取溢寫後，另一個讀取連線得到 `database is locked`。這是已確認的程式問題；先前執行中的後端已關閉，未取得當時 traceback，因此不能斷言所有先前錯誤都出於同一原因。
- 修復：先算完並檢查各批向量，再於短暫交易中寫入；重建失敗仍保留舊索引。代價是計算時暫存完整待寫向量於記憶體，文件庫大幅擴充時應改為磁碟暫存或背景索引工作。
- 新增兩項回歸測試，修改前皆重現鎖定、修改後皆通過；RAG 24 項、完整後端 83 項測試通過（4 項既有 deprecation warnings）。
- 在副本完成 WHO embedding，以 chunk ID、文字、文件 hash 與版本對照後，將 1,442 個向量存回原文件庫。寫入前備份：`data/runtime/rag-diagnostic-00c24e50-665e-470e-996c-2ed78dd81aa1/before-index-install.sqlite3`。
- 用 FastAPI TestClient 呼叫實際後端路由，搭配原文件庫與真實本機 Ollama：`/api/config` 回傳 200；reference 索引為 1442/1442、缺漏 0。`pneumonia` 與 `urinary tract infection` 均為 HTTP 200、status=ok，各回傳 8 個附頁碼片段，約 1.30／1.11 秒。
- 這是 API 與實際 embedding 驗證，未宣稱瀏覽器操作或臨床檢索品質已完成驗證。PDF 原有空文字／OCR 及長段切分警告仍保留。

下一步操作：啟動後端與前端，在文件庫選「正式參考文件」範圍搜尋；目前無需再次重建。這次沒有啟動或終止使用者服務。

## 先前暫停紀錄（保留）

日期：2026-09-16。依使用者要求，在五小時額度剩 5% 時暫停。

## 問題

使用者選擇 embedding 模式並重建向量索引後，查詢 `pneumonia` 或 `urinary tract infection` 都顯示 `embedding_failed`。尚未確認重建索引的回應是否成功。

## 已確認

- `GET http://127.0.0.1:11434/api/tags` 成功，已安裝 `embeddinggemma:latest`，回報 embedding capability 與 768 維。
- `GET http://127.0.0.1:8000/api/config` 回傳 HTTP 500，尚未取得後端 traceback，不能認定與查詢失敗同一原因。
- `backend/app/rag/service.py` 的重建與查詢會將非預期例外統一轉成 `embedding_failed`；此訊息本身不足以判定原因。
- 工作流程與文件庫有 synthetic/reference 兩種搜尋範圍，WHO 應使用 reference。
- 尚未測試實際 `/api/embed`，尚未讀取秘密設定、修改程式或重新啟動使用者的服務。

## 繼續時的待辦

1. 取得正在執行後端的 traceback，先定位 `/api/config` 的 500；檢查目前程式、資料庫 schema 及 migration 是否一致。
2. 只確認非秘密的 embedding 模型、URL、timeout 與 retrieval mode，避免輸出 `.env` 或 API key。
3. 用短查詢測試本機 Ollama `/api/embed`，只輸出 HTTP 狀態、向量數量與維度，不需輸出整個向量。
4. 重現 reference 範圍的兩個查詢，確認重建結果、有效 fingerprint、已索引／缺漏片段數。
5. 在隔離環境捕捉被統一錯誤訊息遮蔽的原始例外，區分 provider、SQLite/schema、向量格式、維度或結果組裝問題。
6. 依確定原因修復並增加針對性回歸測試；驗證兩個真實查詢可以回傳附頁碼的 WHO 片段。查詢成功不等於臨床內容已驗證。
7. 若需重新啟動後端，先告知使用者；不要直接終止使用者服務，也不要刪除文件或索引來猜測修復。

## 額度

暫停時五小時額度已使用 95%，週額度已使用 61%。尚未完成根因診斷。
