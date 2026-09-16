# 操作教學：完整病例展示、OpenAI API 與 WHO RAG

研究展示用／僅 synthetic 病例／非臨床使用。以下命令均從專案根目錄的 PowerShell 執行。

## 1. 先跑出完整結果（不需要 API key 或 Ollama）

第一次安裝：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

終端機 A：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1
```

這個命令明確選用 **lexical 真實本機文字檢索＋mock 回答模型**，初始化病例與展示文件，預先保存成功的 rule-only 與 multi-agent 執行結果，再啟動後端。它不修改 `.env`，不呼叫付費 API，也不清空既有病例或審閱。相同準備命令重跑會重用既有準備結果。

終端機 B：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\frontend.ps1
```

開啟 [工作台](http://127.0.0.1:5173)。選完整病例，點既有執行紀錄即可查看預先產生的結果；或選 `multi-agent`、`mock` 再按「執行分析」建立新紀錄。新增的完整病例與預期見 [病例說明](../data/synthetic/README.md)。

展示順序：病例摘要 → AST → 分析結果 → 證據與流程 → 人工審閱。完整案例應為 `ready_for_review`／`awaiting_review`，沒有缺漏或執行錯誤；Human Review 的 `pending` 代表等待你實際操作，不是分析失敗。輸入理由並接受／修改／拒絕，重新讀取以確認保存。準備程式不會替你簽核。

注意：腎功能存在檢查、展示 AST、背景與文件引用都有實際執行；用藥清單目前只是保存的病例資料，尚未有藥物交互作用引擎。故障病例刻意保留，用來展示過敏未知、缺資料或衝突時的阻擋。

在兩個终端機按 Ctrl+C 停止。要切換下一節的正式配置，停止 demo 後改用一般 `backend/scripts/run.ps1` 啟動。

## 2. 設定 OpenAI 回答 API

本專案有兩個獨立模型用途：

| 用途 | 設定 | 現有 adapter |
| --- | --- | --- |
| 整理分析文字／候選結構 | `LLM_*` | OpenAI Chat Completions |
| 把文件和查詢轉成向量 | `EMBEDDING_*` | Ollama `/api/embed` |

OpenAI key 不會自動讓 Ollama 可用；也不能把 OpenAI URL 填進目前的 embedding URL，兩者協定不同。

1. 在 [OpenAI API 平台](https://platform.openai.com/api-keys) 建立供本專案使用的 API key，確認專案有可用 API 額度及模型權限。金鑰僅輸入本機設定檔，不貼到聊天。
2. 只在 `.env` 不存在時複製範本：

```powershell
if (-not (Test-Path .\backend\.env)) {
    Copy-Item .\backend\.env.example .\backend\.env
}
notepad .\backend\.env
```

3. 在編輯器設定以下欄位；`LLM_API_KEY=` 右側填自己的 key（範例刻意留空）：

```dotenv
LLM_PROVIDER=live
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=
LLM_TIMEOUT=60
LLM_RETRIES=2
RAG_RETRIEVAL_MODE=lexical
```

這裡以 `gpt-4.1-mini` 作為現有 adapter 的相容範例：官方列出支援 Chat Completions 與結構化輸出。可用權限仍以你的 API 專案為準。這不是替本次開發 subagent 更換模型；本次 subagent 是你指定的 `gpt-5.6-luna`／high。程式目前固定傳 `temperature=0` 與 JSON mode，沒有 reasoning effort 設定，不能假定任意模型只改名稱就相容。[OpenAI 模型文件](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

4. 重啟一般後端：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\run.ps1
```

5. 「研究與設定」檢查 configured 與模型名稱。這只是設定檢查，不是付費連線測試。選完整病例、`multi-agent`、外部模型 `live`，看完外傳提示再按執行，才會送出必要 synthetic 欄位與檢索片段，可能產生 API 費用。先試一個病例，再跑 benchmark。

後端實際讀的是 `LLM_API_KEY`，不是 `OPENAI_API_KEY`；HTTP Authorization 使用 Bearer key，key 必須留在伺服器端。[OpenAI API 認證說明](https://developers.openai.com/api/reference/overview)

若遇 `PROVIDER_HTTP_ERROR`，檢查 key、專案權限、model 和 URL；`PROVIDER_RATE_LIMIT` 檢查配額／速率；`PROVIDER_TIMEOUT` 檢查網路與 timeout；輸出驗證錯誤需查看 trace，不能以關閉安全檢查處理。此交付未呼叫真實 OpenAI API。

## 3. 啟用本機 embedding RAG

已安裝並啟動 Ollama 後：

```powershell
ollama pull embeddinggemma
```

在 `backend/.env` 設定：

```dotenv
RAG_RETRIEVAL_MODE=embedding
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_TIMEOUT=120
```

重啟一般後端。先對 synthetic 文件按「重建向量索引」，成功後測試完整病例。第一次 WHO 全書索引較久，請等待完成再搜尋；初次搜尋也可能觸發缺少向量的補建。

`indexed`／`indexed_with_warnings` 是解析切段狀態，**不代表向量已建好**；向量數量與重建結果另查。embedding 失敗不會自動退回 lexical。mock 回答模型也不會修復 embedding 服務。若要免 Ollama 的展示，使用第 1 節明確選擇 lexical。

## 4. 上傳這次附的 WHO PDF

附件位置為專案上一層的 `who_aware_antibiotic_book.pdf`。本次已實際保存到本機 runtime 文件庫；其他電腦仍須自行匯入，原檔不加入 Git。

1. 打開「文件資料庫」，選擇該 PDF。
2. 標題填 `The WHO AWaRe (Access, Watch, Reserve) antibiotic book`；版本填 `2022-user-supplied`。
3. **取消 synthetic 勾選**，按匯入。不要把 WHO 勾成 synthetic 來讓展示候選通過。
4. 搜尋範圍選「正式參考文件」，若採 embedding 先對這個範圍重建索引。
5. 搜尋 `pneumonia` 或 `urinary tract infection`，點片段的「開啟原始文件」，核對 PDF 實體頁序。參考文件檢索用來查原文，不會直接建立用藥候選。

本次附件：10,323,301 bytes、697 頁、解析出 1,442 chunks，狀態 `indexed_with_warnings`。第 2、44、310、592、644、696 實體頁沒有抽出文字，parser 統一標記 requires_ocr；這也可能是空白頁，不能直接認定每頁都需要 OCR。未人工逐頁驗證表格，文字成功抽出也不代表表格關係正確。

原檔、chunks 與向量位於 DB 同層的 `documents/`；預設為 `data/runtime/documents/`。相同 hash 重新匯入會回傳原紀錄，不會更新標題或版本；不同內容才會建立新文件。PDF 引用 `page` 是實體頁序，不是書面印刷頁碼。

WHO 的正式參考範圍與 synthetic 分開；病例分析仍僅使用 synthetic 文件與 DEMO 代碼。接上真實藥名／WHO 推薦／正式 AST 規則是另一階段，不能單靠上傳 PDF 完成。

## 5. 資料與常見問題

| 現象 | 如何處理 |
| --- | --- |
| 所有 multi-agent 都無候選 | 先用 demo.ps1＋mock；確認文件已 seed、retrieval 有片段 |
| 改 `.env` 沒生效 | 重啟一般後端；系統既有環境變數優先於 `.env`；demo.ps1 明確用 lexical/mock |
| WHO 已匯入但搜不到 | 選正式參考範圍，查看解析警告與該範圍索引結果 |
| 畫面仍有「非臨床／demo_only」 | 這是正確的研究標記，接 API 也不會消失 |
| 新病例沒有出現 | 再按載入展示資料，或跑 demo.ps1；seed 保留既有 revision |
| 完整病例的審閱節點 pending | 需由使用者操作人工審閱，不由 mock 自動完成 |

測試與缺口見 [本次需求核對](REQUIREMENTS_AUDIT.md)。備份前停止後端，保存整個 runtime 資料夾；不同資料庫請連同它旁邊的 documents 一起保存。
