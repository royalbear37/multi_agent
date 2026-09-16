# 實作狀態與接續事項

更新：2026-09-15。

## 本次使用教學與整合病例更新（最新）

本次工作目錄為 `multi_agent`。以下是本次實際驗證，後面的 embedding 改版紀錄保留作為歷史，不代表全部需求已完成。

- 新增 2 個完整 synthetic 病例，總數 16；新增 `scripts/demo.ps1` 明確使用 lexical＋mock，預先產生並保存結果。
- 現有本機 DB 已產生兩個新病例各 2 筆成功結果（rule-only／mock multi-agent）：4 筆皆 ready_for_review、missing_fields=[]、errors=[]，等待使用者審閱。
- 舊 seed 的相同文件可能沒有 policy_refs；準備程式新增標記清楚的展示副本，保留舊文件與病例修改。
- WHO 附件本機匯入 697 頁、1,442 chunks、indexed_with_warnings；正式參考 scope 的實際 lexical 搜尋成功。6 頁空文字警告，未逐頁驗證表格；未建真實 Ollama 向量。
- 正式參考文件可獨立索引、搜尋與開啟原始頁面；工作流仍只使用 synthetic 證據。設定畫面改顯示參考文件數量。
- 後端：**81 passed、4 warnings**，coverage **86%**（RAG **84%**）；Windows Python 3.14.5。
- 前端：TypeScript/Vite build 通過，**4 項元件測試通過**；**4 項 Playwright E2E 通過**，含上傳／正式參考檢索隔離、分析→審閱→重新讀取、安全阻擋、mock／benchmark。
- 前端首次在 sandbox 內被 esbuild 目錄讀取權限擋住；核准在 sandbox 外重跑後通過。首次 E2E 與前一測試程序占埠，停止該次測試後重跑通過。
- 未呼叫付費 OpenAI API，未測真實 Ollama；fake embedding 測試只證明程式行為。沒有重新全新安裝依賴。

完整 [操作教學](USER_GUIDE_ZH_TW.md) 與 [需求核對／待辦](REQUIREMENTS_AUDIT.md)。

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

