# Live API DEMO 逐步操作稿與實跑紀錄（2026-09-22）

這次實跑使用 `api-demo-source-ast-001` revision 5、WHO 參考文件、本機 Ollama `embeddinggemma` 向量檢索，以及已設定的外部 `gpt-4.1-mini` 生成 API。病例為**去識別來源 AST 加模擬臨床情境**，不是已確認的真實菌血症。所有候選僅供研究審閱，不能當作醫囑或 WHO 已認可的用藥。

## 開場前確認

1. 在專案根目錄用兩個 PowerShell 視窗啟動後端與前端，分別執行 `powershell -ExecutionPolicy Bypass -File .\backend\scripts\run.ps1` 和 `powershell -ExecutionPolicy Bypass -File .\scripts\frontend.ps1`。各埠只開一份；瀏覽器開 <http://127.0.0.1:5173/>。
2. 前端選「病例工作台」→「目前病例」→ `api-demo-source-ast-001 · revision 5`。本例已保存允許必要欄位及引用片段送到外部模型的設定。只有在資料來源與文件授權仍允許時才重跑 live。
3. 開「研究與設定」確認文件檢索顯示 **語意向量搜尋 · embeddinggemma**、WHO 參考文件 **1,442／1,442** 個片段；來源字典為 **97 種菌名／95 種藥名**、規則版本 `reported-ast-1.0`。95 是全資料集藥名目錄，**17 才是本病例 AST 筆數**。
4. 這台機器的 `backend/.env` 目前為 `LLM_PROVIDER=unconfigured`，所以設定頁會寫「生成模型尚未啟用或設定未齊全」；但每次分析選 `live` 時，後端實際可使用已設定的 `gpt-4.1-mini`，以下保存紀錄均顯示該模型及 Token。展示時請直接以執行紀錄證明模型呼叫，別把設定頁文字解讀成這些 run 沒有呼叫 API。若要讓設定頁也顯示預設 live，需另改 `.env` 並重啟後端；本次沒有改動該設定。

## 前端照做順序

建議正式展示**點選下面已保存的 run ID**，畫面和數字最穩定，也不會再次產生 API 費用。若要現場重跑，在「病例工作台」選模式與「已設定模型（OpenAI／本機 Ollama）」後按「執行分析」；live 回覆可能改變，不能照念固定藥名或數量。

| 步驟 | 前端操作 | 本次實跑可講的重點 |
| --- | --- | --- |
| 1 | 選來源病例，看「病例摘要」、證據範圍、文件選擇與來源 AST 表格。 | 畫面標示混合來源／模擬欄位。17 筆 AST 保留來源報告與 CLSI 2022 資料集衍生判讀；病例未指定 `policy_refs`，因此會搜尋文件庫的參考文件。此處不要展開原始 JSON。 |
| 2 | 「比較模式」選 `rule-only`、模型選「未設定模型」，按「執行分析」；或在執行紀錄選 `43ec077d`。 | 這個模式不呼叫生成 API，但仍檢索 WHO。17 筆中 **11 項規則待審、6 項來源規則排除**；11 項不是 11 個臨床建議。 |
| 3 | 在「分析結果」看「藥品數量與去向」、「查看每項藥品去向」、「來源排除／待確認項目」。 | 可展示同一藥品從原始 AST、規則結果到候選的去向。`rule-only` 給每項規則待審藥附上檢索片段，**未逐藥確認片段內容支持它**。旁邊有「匯出 JSON」。 |
| 4 | 回工作台，模式選 `rag-only`，模型選「已設定模型（OpenAI／本機 Ollama）」後執行；或選保存紀錄 `af2e3baf`。 | 本次呼叫 `gpt-4.1-mini` 1 次、5,393 Token，產生 2 項待審候選；它看到病例摘要和檢索片段，沒有看到完整逐筆 AST。引用頁碼仍須核對。 |
| 5 | 回工作台，模式選 `single-agent`、模型選 live 後執行；或選 `ef5bd771`。 | 本次 1 次 API 呼叫、7,018 Token，產生 2 項待審候選。與 rag-only 主要差在模型也看到逐筆 AST。其引用 WHO 第 493 頁片段，不應直接視為本例感染情境的支持。 |
| 6 | 回工作台，模式選 `multi-agent`、模型選 live 後執行；或選 `9b432e65`。 | 本次 5 次 API 呼叫、20,981 Token。畫面顯示 17 筆 AST、6 項規則排除、3 項待審候選、8 項通過規則但未選入。病例、AST、證據、臨床背景 4 個 Agent 均顯示「需補資料或確認」，整合 Agent 仍完成；這是寬鬆 demo 的行為。 |
| 7 | 在該 multi-agent 結果按「查看證據與流程」，展開「09 證據核對 Agent」。 | 可看模型、1 次呼叫、5,480 Token、上游、待確認事項及逐藥支持。共 13 個流程節點、其中 5 個 Agent。節點「已執行」只代表流程完成。 |
| 8 | 回「分析結果」，展開任一候選的 `who · 第 566 頁`；也可看右側「本次使用的文件片段」或「開啟原始文件」。 | 本次 3 項候選都引用 WHO 實體第 566 頁同一片段；畫面所示文字**沒有列出這 3 項藥名**。模型卻聲稱逐藥受到文獻支持，這是本次 live DEMO 找到的引用核對問題。不要把候選當成建議。 |
| 9 | 左側「人工審閱」，看候選、病例情境與「需要補充或確認」。 | 本次已示範選「拒絕」、填寫可追溯原因、按「送出審閱」，再在審閱歷史看到 `demo-user` 的拒絕紀錄。若正式展示還要現場送出，請先建立**新 run** 再審閱，避免對同一 run 重複記錄。展示角色不是正式登入或醫師簽核。 |
| 10 | 左側「文件資料庫」，展開 `who · v1`。 | 已解析 1,442 個片段；可看解析細節、版本、原文連結、族群標示與變更依據。現有全書被標為「所有年齡」，對混合族群的 WHO 全書來說過於寬泛，不能取代逐章核對。畫面有「刪除此文件」，**不要刪唯一的 WHO 參考文件**。 |
| 11 | 在「本地文件檢索」選 `reference 正式參考文件`，輸入 `Staphylococcus aureus bloodstream infection adults`，按「檢索文件」。 | 本次 Ollama embedding 回傳 8 個帶頁碼片段。第一筆是第 529 頁關節感染相關表格，說明語意相似度（本次 0.509）**不是臨床可信度**；要對照原文、病原、感染部位與族群。解析警告收在可展開的「文件解析細節」內。 |
| 12 | 左側「研究與設定」，看向量索引、規則版本與 Benchmark 歷史；選 `fc1c31f6`。 | 這是透過本機 API 對**這 1 個病例 × 4 模式**執行的 live Benchmark，畫面可供審閱輸出 3／4、暫緩 1／4、阻擋 0／4。展開「各 Agent 用量與執行統計」、按「逐次執行結果」可追到個別 run，旁邊可匯出摘要 JSON。這不是臨床成功率。 |

**重要的 Benchmark 操作差異：**目前前端的「執行四模式比較」按鈕會跑**全部 16 個病例 × 4 模式**，不是只跑上方選中的病例。若模型選 live，會觸發大量付費模型呼叫。正式 DEMO 請選已保存的單病例比較 `fc1c31f6`；要重新做單病例比較，使用下方的本機 API 範例指定 `case_ids`。

### 被問到「為什麼每個 Agent 的文字都差不多」

可直接回答：「這次不是前端把同一筆回覆貼到五張卡片。五個 Agent 有不同提示詞與輸入結構，AST、證據、臨床三個專責 Agent 都接收同一份病例事實和病例整理 Agent 的摘要；本次 `gpt-4.1-mini` 在自由文字的『限制』與『核對發現』大量沿用上游摘要，因此看起來幾乎一樣。它們的專屬結構化結果仍不同：AST Agent 核對 11 個藥名，證據 Agent 標出 3 個逐藥支持，臨床 Agent 列出 6 個排除，整合 Agent 才產生 3 個候選。這些是分工流程的展示，不能說五個 Agent 已各自獨立驗證同一個臨床結論。尤其這次證據 Agent 的逐藥支持引用有問題，我們已用人工審閱拒絕該 run。」

本次四個專責 Agent 都顯示「需補資料或確認」，但「缺少的資料」清單是空的；觸發狀態的是它們回覆的 `needs_confirmation` 與限制敘述，**不等於系統列出四組不同的必填欄位**。證據 Agent 另有一條 Demo 格式整理限制。現場若要展示差異，請看各 Agent 的專屬欄位，不要把重複的自由文字當作獨立佐證。這種重複也是目前輸出品質的限制，後續應改善提示詞和前端呈現。

## 本次實際 API 呼叫與保存結果

所有生成模式的 `provider_kind` 均為 `live`；`rule-only` 為 `unconfigured`，因它不需要回答模型。每次 `POST /api/runs` 會保存新 run；重跑結果可能不同。

| 本機 API 動作 | 已保存 ID／觀察結果 |
| --- | --- |
| `GET /api/config`、`GET /api/cases/api-demo-source-ast-001` | Ollama embedding；WHO 1,442／1,442；病例 revision 5、17 筆 AST、reference 範圍、外送設定已開。 |
| `POST /api/runs`：`rule-only` | `43ec077d-4284-47c9-acf4-148e49583e66`；11 候選、6 排除、8 個證據快照、無生成模型呼叫。 |
| `POST /api/runs`：`rag-only` live | `af2e3baf-69fa-4449-8e34-7e90925e6833`；2 候選、6 排除、5,393 Token。 |
| `POST /api/runs`：`single-agent` live | `ef5bd771-e0ff-46ec-9c86-db90fa680fad`；2 候選、6 排除、7,018 Token。 |
| `POST /api/runs`：`multi-agent` live | `9b432e65-b336-45ca-b4d3-14938831a723`；5 次 Agent 呼叫、3 候選、6 排除、20,981 Token；4 個專責 Agent 留下需確認。 |
| `GET /api/runs/{run_id}`、`GET /api/runs/{run_id}/trace` | 已核對結果與 13 個流程節點／5 個 Agent；live 模型名稱和用量可追溯。 |
| `GET /api/rules`、`GET /api/documents`、`GET /api/cases/{case_id}/revisions` | 規則 `reported-ast-1.0`；1 份 WHO v1、1,442 chunks；本例 5 個歷史版本。 |
| `GET /api/documents/search?q=Staphylococcus%20aureus%20bloodstream%20infection%20adults&scope=reference` | `ollama_embeddings`，狀態 `ok`，8 個片段，頁碼 529、313、322、538、522、542、552、566。 |
| `POST /api/benchmarks`：1 case × 4 modes live | `fc1c31f6-5bfa-4e23-be5a-26fddf4fa664`；4 筆結果、3 筆有待審輸出、1 筆暫緩。這是**第二輪** live 呼叫，沒有重用上面四個獨立 run。 |
| `POST /api/reviews`：拒絕前述 multi-agent run；`GET /api/reviews?run_id=...` | 審閱 `70df4138-d307-4978-be34-2514fc944489`，`demo-user`／`physician` 展示角色，2026-09-22 20:24:40；原因是 WHO 第 566 頁片段沒有支持 3 項候選的逐藥聲明。 |
| `GET /api/runs/{run_id}/export`、`GET /api/benchmarks/{benchmark_id}/export` | 兩種 JSON 匯出皆回 HTTP 200；供保存輸入快照、流程及研究比較，不要求觀眾閱讀 JSON。 |

單病例 Benchmark 的四筆子 run：`rule-only` `ba1ce225-d11a-439a-9533-10b8746cbfe2`（11 候選）、`rag-only` `64c10c70-0a41-4438-bb15-5fb79a67efac`（4 候選）、`single-agent` `62af6ffb-a5c0-4c97-ae96-99cdfa7da183`（無發布候選，`NO_VALID_CANDIDATES`）、`multi-agent` `d86b063c-02d6-41a4-82e8-986cc060d459`（1 候選）。與獨立 run 的數量不同，展示時應明確說明是兩組分開保存的 live 結果。

若要在 PowerShell 重新做**僅一個病例**的四模式 live 比較，使用以下範例。這會再次呼叫外部模型並產生費用；同一個 `request_id` 重試可避免重複建立這一次比較。

```powershell
$requestId = 'presentation-' + [guid]::NewGuid().ToString('N')
$body = @{
    case_ids = @('api-demo-source-ast-001')
    modes = @('rule-only', 'rag-only', 'single-agent', 'multi-agent')
    provider_kind = 'live'
    request_id = $requestId
} | ConvertTo-Json -Compress
$benchmark = Invoke-RestMethod 'http://127.0.0.1:8000/api/benchmarks' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 300
$benchmark.benchmark_id
```

## 有入口，但這次只展示、沒有寫入

- 「病例工作台」支援 canonical／alternate **JSON** 匯入、編輯並建立新版本、查看歷史版本、改用文件庫全部參考文件或指定 `policy_refs`。本次保留既有 revision 5，沒有新匯入或改病例。來源 CSV 是預先轉換進病例庫，不能在 JSON 上傳框直接選 CSV。
- 「文件資料庫」支援 PDF／Markdown／文字匯入、族群標示附理由、重建向量索引、開原文與刪除。這次只搜尋及查看 WHO，沒有上傳、重建、修改族群或刪除。
- 「人工審閱」有接受、修改、拒絕；本次只實測拒絕。接受／修改仍需核對原文和病例，且系統會再檢核不得新增規則不允許的藥物或無效引用。
- `LLM_PROVIDER=unconfigured` 的設定頁文案、WHO 全書的「所有年齡」標示，以及本次 live 證據 Agent 把無關片段判成逐藥支持，都是公開展示時應坦白指出的限制。這次**沒有修正引用支持性判斷**；保存的拒絕紀錄示範人工把關。
