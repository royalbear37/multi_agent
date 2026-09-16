# 文件、模型與設定

研究展示用／僅 synthetic 資料／非臨床使用。

## 匯入 PDF、Markdown 或文字

1. 啟動後至「文件資料庫」，選擇原始 PDF／UTF-8 `.md`／`.txt`。
2. 輸入可辨識標題及版本；真實 WHO 或其他正式文件必須取消 synthetic 勾選，不能冒充展示文件。
3. 匯入後查看 processing_status、warnings 與 chunk_count。原始檔保留於 runtime 文件目錄。
4. 檢索頁預設查詢 synthetic 片段；選「reference 正式參考文件」可搜尋 WHO 等非 synthetic 文件。PDF page 表示從 1 開始的實體頁序，不是假定的印刷頁码；Markdown 使用行號與標題路徑。

目前展示工作流只使用 synthetic 文件。正式 WHO 文件可保存、檢索與檢查；要連到正式候選輸出仍需确认病例範圍與正式規則。匯入本身不會啟用臨床規則或傳送全文至模型；主動搜尋／重建向量時才會將該範圍片段送至配置的 embedding 服務。

相同 hash 避免重複原檔；不同內容版本保持不可變。搜尋遇到未解決的文件版本衝突不提供可發布證據。病例 policy_refs 可限制文件。掃描 PDF 需要 OCR；表格／欄位解析不可靠者標記需審閱並限制使用。這是保守啟發式檢查，未做完整 OCR 或醫療表格結構化。

原始檔只用伺服器產生的檔名保存；API 限制檔案大小與副檔名。上傳檔案與病例文字都是資料，不能提供系統指令。

## Embedding 語意檢索

預設 `RAG_RETRIEVAL_MODE=embedding`，使用本機 Ollama 的 `/api/embed`。匯入會先解析並保存片段；搜尋會為符合政策的片段補建向量，將查詢以同一模型轉為向量，再按 cosine similarity 排序。向量保存於既有 `rag.sqlite3`，重啟可重用，不需重新上傳文件。

```dotenv
RAG_RETRIEVAL_MODE=embedding
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_TIMEOUT=30
```

1. 安裝並啟動 [Ollama for Windows](https://ollama.com/download/windows)。
2. 執行 `ollama pull embeddinggemma` 下載模型。
3. 重啟後端；「研究與設定」顯示非敏感配置。配置存在不代表已通過連線驗證。
4. 「文件資料庫」點「重建向量索引」，或直接搜尋。索引失敗會顯示 warning；確認 Ollama 啟動與模型名稱。
5. 更換模型或服務位置後重啟，再重建索引。不同設定的向量不混用；原始文件、chunk ID 與歷史引用保持不變。

若同一模型名稱下載了新的權重，也請按「重建向量索引」；名稱本身無法識別底層權重的變更。EmbeddingGemma 使用查詢／文件各自的檢索前綴，其他模型需確認其推薦輸入格式後再評估效果。

Embedding 服務失敗時不會暗中切回關鍵字。測試或舊檢索比較可明確設定 `RAG_RETRIEVAL_MODE=lexical`；這個模式不使用語意向量。回答模型的 `LLM_PROVIDER=mock` 不會把 embedding 自動改成 mock。

工作流向量搜尋仍只處理 synthetic 且符合 policy_refs 的文件，仍檢查版本衝突。文件庫明確選 reference 後，非 synthetic 文件也會送至配置的 embedding 服務；預設為本機 Ollama。若自行設定遠端 URL，選定範圍的片段與查詢會傳至該服務。

API：`GET /api/documents/search?q=pneumonia&scope=reference`、`POST /api/documents/reindex?scope=reference`。省略 scope 維持 synthetic。完整 OpenAI 與 WHO 操作見 [使用教學](USER_GUIDE_ZH_TW.md)。

這是小型語料的精確向量掃描，沒有近似最近鄰資料庫。相似度不是可信度機率；需要用實際查詢與人工相關性標註評估召回率。離線 fake 向量測試驗證索引與排序邏輯，不能證明真實模型的檢索品質。

協定依據：[Ollama embeddings](https://docs.ollama.com/capabilities/embeddings)、[Generate embeddings API](https://docs.ollama.com/api/embed)。

## 外部回答模型

在後端 `.env` 或環境變數設定（不要在聊天中貼金鑰）：

```dotenv
LLM_PROVIDER=live
LLM_BASE_URL=https://YOUR-COMPATIBLE-SERVICE/v1
LLM_MODEL=
LLM_API_KEY=
LLM_TIMEOUT=20
LLM_RETRIES=2
```

此 adapter 使用 OpenAI-compatible `/chat/completions` HTTP 協定，不宣稱所有服務相容。重啟後端後檢查「研究與設定」的非敏感配置狀態；在病例頁明確選擇外部模型並執行才會送出必要 synthetic 欄位與檢索片段，可能產生費用。

預設 provider 為 unconfigured。模型未設定時，rule-only 仍可運作，其餘模式保留獨立節點結果並標示未完成。明確選 mock 可測試離線流程，結果標示 is_mock，不能混入真實模型比較。

模型输出必須通過欄位、藥品代碼、引用與用藥方案檢查；API timeout／429／服務錯誤可有限重試，輸出不合法或安全阻擋不得重試繞過。错误不回傳金鑰、HTTP header 或供應商原始錯誤內容。

新增不相容供應商時，實作 `BaseProvider.status()` 與 `generate(context)` 並加 fake HTTP contract tests；domain／規則不應因此改寫。真實連線 smoke test 必須明確啟用，預設測試套件不呼叫付費 API。本次未提供 API key，不能宣稱已完成真實供應商連線。
