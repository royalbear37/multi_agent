# 實作狀態與接續事項

更新：2026-09-15。

## 中斷位置查核

本機專案為 `multi_agent-main`。此次重新執行修改前的後端測試：**66 passed**；先前聊天中未找到可獨立核對的「65 passed」記錄。修改前 RAG 為 FTS5／關鍵字檢索。

## 此次修改

- 預設改為 Ollama `embeddinggemma` 語意向量檢索，保留明確選用的 lexical 測試模式。
- 文件與查詢使用相同模型及各自的 task prefix；向量正規化後依 cosine similarity 排序。
- 向量保存在 SQLite，設定指紋區分模型／服務／輸入格式；舊文件可補建索引。
- 保留 synthetic、policy_refs、文件版本衝突及引用位置限制；embedding 失敗時不退回關鍵字。
- 新增重建索引 API／UI、模型狀態及相似度顯示；工作流 trace 記錄檢索方式與模型。

## 驗證

- 修改前後端：66 項通過。
- 前端 TypeScript 與 Vite build 通過；4 項元件測試通過。
- API 整合檢查通過：配置、重建後索引數量、embedding 搜尋（注入測試向量）。
- 修改後後端：77 項通過，整體 coverage 87%，RAG 模組 84%；4 個既有 deprecation warnings。本次執行環境 Python 3.12.7、Node 24.19.0。
- 本次尚未驗證真實 Ollama 模型連線，也未執行 Playwright 瀏覽器驗收。測試向量不代表真實模型品質。

## 啟用與待辦

1. 安裝並啟動 [Ollama for Windows](https://ollama.com/download/windows)，執行 `ollama pull embeddinggemma`。
2. 重啟後端，開啟「文件資料庫」，按「重建向量索引」，確認成功。
3. 使用實際文件與人工標註的相關片段建立查詢集，評估召回率與排序品質。
4. 更換相同名稱的模型權重後重新建索引；保留完整 runtime 備份。

詳細設定見 [RAG_AND_PROVIDERS.md](RAG_AND_PROVIDERS.md)。

