# 多代理人抗生素用藥輔助決策 Prototype

**研究展示用／僅 synthetic 資料／非臨床使用。** 不提供劑量、頻率、療程、正式醫囑或自動開藥。

可在 Windows 本機瀏覽器操作：14 個可重現病例、病例 JSON 匯入／版本、展示規則、文件檢索、八節點 trace、人工審閱、四模式研究比較及 JSON 匯出。模型未設定時仍可使用 rule-only；mock 必須明確啟用。

## 最短啟動方式

需要 **Python 3.14** 與 **Node.js 24**（本次實測版本為 3.14.5／24.15.0），第一次安裝需要網路。下列命令從專案根目錄執行，不需要 Docker。重新安裝前先停止本專案服務，避免 Windows 鎖定依賴檔案。

```powershell
# 一次性安裝
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

終端機 A：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\run.ps1
```

終端機 B：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\frontend.ps1
```

開啟 [研究工作台](http://127.0.0.1:5173)，點「載入展示資料」。後端文件在 [API 文件](http://127.0.0.1:8000/docs)。兩個服務只綁定 127.0.0.1；在各終端機按 **Ctrl+C** 停止。

也可不開瀏覽器先初始化／seed：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\init_db.ps1
powershell -ExecutionPolicy Bypass -File .\backend\scripts\seed.ps1
```

seed 不刪除或覆蓋既有病例。病例／執行／引用／審閱保存在 `data/runtime/`；若透過 `PROTOTYPE_DB_PATH` 自訂，文件會跟隨 DB 目錄保存。備份請先停止服務並保存整個 runtime 目錄。

### 啟用 embedding RAG

預設使用本機 Ollama 的 `embeddinggemma`。先安裝 [Ollama](https://ollama.com/download/windows)，啟動 Ollama，再執行：

```powershell
ollama pull embeddinggemma
```

後端預設連接 `http://127.0.0.1:11434`，不需要 API key。可在 `backend/.env` 設定 `EMBEDDING_MODEL`、`EMBEDDING_BASE_URL`。文件資料庫可「重建向量索引」，首次搜尋也會補建缺少的向量。Ollama 未啟動或模型未下載時，搜尋會回報失敗且沒有證據；需要證據的分析無法產生可發布候選。LLM 的 mock／live 選擇與 embedding 設定互相獨立。

詳細設定、離線測試模式與限制見 [RAG 設定](docs/RAG_AND_PROVIDERS.md)。

## 5–10 分鐘展示

1. 載入展示資料，選 `case-01-complete`。
2. 選 `rule-only`、未設定模型，點「執行分析」。結果只使用虛構代碼。
3. 「證據與流程」查看來源文件、頁碼／行號、八個節點及規則版本。
4. 「人工審閱」輸入理由後接受，再點重新讀取；重新整理頁面、重選病例／執行仍可查閱。
5. 回病例工作台，選 `multi-agent`＋明確啟用 mock，再執行並確認 MOCK 標記。
6. 選 `case-03-allergy-unknown` 或 `case-04-allergy-match`，確認沒有可發布候選；審閱不能解除限制。
7. 文件資料庫匯入 synthetic Markdown，查看解析狀態與實際搜尋片段。
8. 研究與設定選 mock，執行四模式比較並匯出逐案例／摘要。這些分數只是 synthetic 軟體驗證，不能作為臨床研究結果。

## 測試

```powershell
# 後端 coverage、前端 TypeScript/build、元件測試
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1

# 再下載測試 Chromium 並執行瀏覽器驗收
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1 -E2E
```

E2E 自動使用 8001／5174 埠，建立獨立測試 DB 並停止測試伺服器，不需要先啟動展示服務。預設測試不呼叫任何付費模型。結果與限制見 [測試與實作狀態](docs/IMPLEMENTATION_STATUS.md)。

## 接入 API／WHO 文件／正式規則

- **API**：複製 `backend/.env.example` 為 `backend/.env`，設定 `LLM_PROVIDER=live`、base URL、model、key；重啟後端並在 UI 明確選外部模型。不要將 key 放進前端或提交 Git。
- **WHO PDF**：文件資料庫可保存原始 PDF；取消 synthetic 勾選。正式文件不會自動啟用展示工作流或變成臨床規則。
- **正式規則**：由臨床負責人確認後，另建版本化正式設定、adapter 與獨立測試；目前只允許 synthetic，不可直接將 demo 改名當作正式規則。

詳見 [文件與模型](docs/RAG_AND_PROVIDERS.md)、[資料與規則](docs/DATA_AND_RULES.md)。

## 文件索引

- [架構與工程決策](docs/ARCHITECTURE.md)
- [資料字典、規則與待確認事項](docs/DATA_AND_RULES.md)
- [RAG／Provider 設定與限制](docs/RAG_AND_PROVIDERS.md)
- [工作流、Trace、審閱與 Benchmark](docs/WORKFLOW_AND_BENCHMARK.md)
- [實作狀態與測試證據](docs/IMPLEMENTATION_STATUS.md)
- [病例 JSON Schema](contracts/case.schema.json)、[OpenAPI](contracts/openapi.json)

修改 schema 後執行 `backend/scripts/generate_contracts.ps1`，再於 frontend 執行 `npm run generate:types`，最後重新 build。

## 常見問題

| 狀況 | 處理 |
| --- | --- |
| 前端顯示無法連線 | 確认後端 8000 與前端 5173 已啟動；查看終端機錯誤 |
| 埠被占用 | 停止先前啟動的本專案服務，再啟動；不要關閉不明程序 |
| PowerShell 阻擋腳本 | 使用上面的 `powershell -ExecutionPolicy Bypass -File`，只對此次程序有效 |
| 模型 not_configured | rule-only 可用；mock 需明確選擇；live 需後端配置後重啟 |
| 文件沒有候選引用 | 查看 synthetic 標記、policy_refs、版本衝突、OCR／解析警告 |
| 舊病例無法反映更新的 seed | seed 刻意保留原版本；透過病例編輯建立新 revision |
| PDF 有表格或掃描頁 | 原型不做完整 OCR／表格結構化，需人工處理 |

本專案不包含正式登入授權、院端即時整合、正式 AST 標準、臨床驗證或公開部署。展示角色不提供存取權限保護。
