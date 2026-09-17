# 多代理人抗生素用藥輔助決策 Prototype

Linux 本機研究工作台，使用本機 CSV 的實際菌種、測試藥品與藥敏判讀，搭配明確標示的模擬臨床情境、WHO 文件檢索（RAG）、八節點分析、表單審閱與四模式研究比較。

**研究展示用／非臨床使用。** 預設流程不再使用虛構菌種／藥品。來源 S 判讀僅建立待審選項，不等於治療建議；不重新計算 CLSI/EUCAST 界值、不提供給藥方案。WHO 可進入病例 RAG，但檢索到片段不代表已驗證臨床適用性。

## 目錄

- [1. 首次安裝](#install)
- [2. 建立設定檔與保護金鑰](#env)
- [3. OpenAI 與 Ollama 設定](#models)
- [4. 啟動、停止與重新啟動](#start)
- [5. 免 API 的完整展示](#demo)
- [6. 病例匯入、編輯與版本](#cases)
- [7. 分析模式與結果解讀](#analysis)
- [8. 證據與流程](#evidence)
- [9. 人工審閱與角色](#review)
- [10. 文件上傳與 WHO RAG](#documents)
- [11. 研究設定與 Benchmark](#benchmark)
- [12. 匯出、保存與備份](#backup)
- [13. 開發、測試與 API](#development)
- [14. 常見問題](#faq)
- [15. 限制與詳細文件](#limits)

<a id="install"></a>
## 1. 首次安裝

先安裝 Python 3、`venv`、Node.js 與 npm。Vite 7 要求 Node.js `20.19+` 或 `22.12+`，本專案 lockfile 已在 Node.js 24 使用。首次安裝需要網路，不需要 Docker。Ubuntu／Debian 可先執行：

以下命令一律從**專案根目錄**執行，也就是可以看到這份 README、`backend`、`frontend`、`scripts` 的資料夾。如果目前在 `backend`，先執行 `cd ..` 回到根目錄。

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
python3 --version
node --version
npm --version
```

請另外用發行版、nvm 或組織核准的套件來源安裝符合上述版本的 Node.js；不要用 `sudo npm install` 安裝本專案依賴。

安裝前後端套件並初始化資料庫：

```bash
bash scripts/setup.sh
```

安裝入口在根目錄的 `scripts/`，會處理以下依賴：

| 檔案／資料夾 | 用途 |
| --- | --- |
| `backend/requirements.txt` | Python 套件與允許版本範圍 |
| `backend/requirements.lock.txt` | 固定版本清單，安裝腳本優先使用 |
| `backend/.venv/` | 安裝後建立的 Python 虛擬環境 |
| `frontend/package.json`、`frontend/package-lock.json` | 前端套件與固定版本 |
| `backend/.env` | 本機設定檔，需自行建立，和 `.venv` 不同 |

requirements 保留在 backend，由根目錄 setup 統一安裝即可。重新安裝前先停止本專案服務。

<a id="env"></a>
## 2. 建立設定檔與保護金鑰

setup 不會自動建立 `.env`。執行以下命令，只在檔案不存在時複製範本，避免覆蓋已填好的 key：

```bash
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi
${EDITOR:-nano} backend/.env
```

- 真實 key 只放在 `backend/.env`，不要填進 `.env.example`、前端或聊天。
- `.gitignore` 已忽略 `.env`；`.env.example` 是會提交 Git 的空白範本。
- `.env` 不會隨 Git clone 出現，每台電腦需自行建立。檔名必須是 `.env`，不是 `.env.txt`。
- 修改後要重新啟動後端；既有系統／程序環境變數優先於 `.env`。

確認 Git 沒有追蹤金鑰檔：

```bash
git check-ignore -v backend/.env
git ls-files -- backend/.env
```

第一行應顯示 `.gitignore` 的 `.env` 規則，第二行正常應無輸出。不要用 `git add -f` 強制加入。若 key 曾被提交，加入忽略規則不會刪除歷史中的 key，應撤銷並更換。

<a id="models"></a>
## 3. OpenAI 與 Ollama 設定

本專案將「生成回答」與「找文件」分開設定：

| 元件 | 功能 | 設定方式 |
| --- | --- | --- |
| OpenAI 回答模型 | 整理分析文字與結構化候選 | `.env` 的 `LLM_*` |
| Ollama embedding 模型 | 把文件與查詢轉成向量，用來檢索 | `.env` 的 `EMBEDDING_*` |
| lexical | 本機文字檢索，不需要 embedding 模型 | `RAG_RETRIEVAL_MODE=lexical` |
| mock | 固定的離線回答模板 | 畫面選 mock，或使用 demo 啟動腳本 |

### 3.1 設定 OpenAI API

到 [OpenAI API 平台](https://platform.openai.com/api-keys) 建立 key，確認 API 專案有可用額度與模型權限。在 `backend/.env` 填入：

```dotenv
LLM_PROVIDER=live
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=
LLM_TIMEOUT=60
LLM_RETRIES=2
PROTOTYPE_DB_PATH=../data/runtime/prototype.db
```

把你的 key 填在 `LLM_API_KEY=` 後面；上面刻意留空。程式讀取的是 `LLM_API_KEY`，不是 `OPENAI_API_KEY`。

目前 adapter 使用 Chat Completions、`temperature=0` 和 JSON mode。`gpt-4.1-mini` 是相容設定範例，模型權限以你的 API 專案為準；更換模型前需確認參數相容。目前沒有 reasoning effort 設定。[OpenAI 模型文件](https://developers.openai.com/api/docs/models/gpt-4.1-mini)、[API 認證說明](https://developers.openai.com/api/reference/overview)。

重啟一般後端後，在「研究與設定」確認模型名稱與 configured。**configured 代表設定齊全，不代表真實連線已成功。** 選完整病例、multi-agent、外部模型，再執行一次，才會呼叫回答 API，傳送必要病例欄位（來源病例須先確認可外送並開啟病例設定）與檢索片段，可能產生費用。

### 3.2 安裝 Ollama 與 embedding 模型

依 Ollama 官方 Linux 安裝方式完成安裝，啟動服務：

```bash
ollama serve
```

另開終端機下載並檢查模型：

```bash
ollama --version
ollama pull embeddinggemma
ollama list
curl -fsS http://127.0.0.1:11434/api/tags
```

模型列表應包含 `embeddinggemma`，最後一行確認 Ollama 服務可連線。若使用 systemd 安裝，可用 `systemctl status ollama` 檢查；已經有服務執行時不必再啟動第二份。

在同一份 `backend/.env` 加入：

```dotenv
RAG_RETRIEVAL_MODE=embedding
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_TIMEOUT=120
```

搭配上一節就是 **OpenAI 回答＋Ollama 向量檢索**。OpenAI key 不會讓 Ollama 自動安裝或啟動。現有 embedding adapter 使用 Ollama `/api/embed`，不能直接把 OpenAI URL 填進 `EMBEDDING_BASE_URL`。以上 Ollama 設定也不會將回答模型改成 Ollama。

### 3.3 暫時不使用 Ollama

在 `.env` 設定以下內容並重啟後端：

```dotenv
RAG_RETRIEVAL_MODE=lexical
```

仍可搭配 OpenAI 或 mock，但這是文字檢索，不是向量檢索。embedding 失敗不會自動回退 lexical；mock 只模擬回答，也不會替代 embedding。

<a id="start"></a>
## 4. 啟動、停止與重新啟動

終端機 A：啟動後端，保持視窗開著。

```bash
bash backend/scripts/run.sh
```

成功時會看到 `Uvicorn running on http://127.0.0.1:8000`。

另開終端機 B：同樣在專案根目錄啟動前端，保持開著。

```bash
bash scripts/frontend.sh
```

| 位址 | 用途 |
| --- | --- |
| [127.0.0.1:5173](http://127.0.0.1:5173) | 操作畫面，請開這個網址 |
| [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | 互動 API 文件 |
| [127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) | 正常回傳 `status: ok` |

直接開 `8000/` 出現 404 是正常的，首頁在 5173。使用 embedding 時，Ollama 也要保持執行。

停止時在對應終端機按 **Ctrl+C**。修改 `.env` 後先停止舊後端，再執行後端命令；不要同時啟動兩份。前端沒有修改時，通常只需重新整理瀏覽器。

<a id="demo"></a>
## 5. 免 API 的完整展示

先完成第 10 節 WHO 匯入，再依第 6 節準備本機 CSV 病例。終端機 A 使用：

```bash
bash scripts/demo.sh
```

此命令明確選擇 lexical＋mock，為前兩個來源病例各保存 rule-only、mock multi-agent 結果，再啟動後端。WHO 已匯入後，不需 key 或 Ollama。終端機 B 照第 4 節開前端。

選 `cohort-...` 病例 → 開啟執行紀錄 → 查看藥敏選項與排除理由 → 查看證據與流程 → 以表單審閱。`-allergy` 是加入模擬過敏與腎功能下降的配對情境，並非來源病人的真實追蹤紀錄。mock 只測資料流程，不代表模型已做推理。

重跑會新增分析，不覆蓋病例或審閱；若資料仍缺漏會回報具體問題。改用 OpenAI／Ollama 時，停止 demo，再用一般後端啟動命令。

<a id="cases"></a>
## 6. 病例匯入、編輯與版本

### 6.1 準備本機 CSV

CSV 為結構化資料，請使用匯入腳本，不要放進 RAG 文件上傳框。先在文件庫找到 WHO 的 `doc_id`（文件詳細資料），由專案根目錄執行：

```bash
backend/.venv/bin/python backend/scripts/import_microbiology.py \
  ./microbiology_cohort_deid_tj_updated.csv \
  --policy-ref doc_c9543071373005e1bf0a \
  --install
```

上面的文件 ID 對應目前本機已匯入的 WHO；其他電腦請換成自己的參考文件 ID。`--per-site 4` 是預設，每種檢體最多選 4 個來源培養，再新增 3 個配對情境。CSV 全檔採串流掃描，兩次通讀以完整收集不相鄰的藥敏列，不把 496 萬列都當成病人匯入資料庫。

本機產物：

- `data/local/microbiology/catalog.json`：全檔名稱字典，97 種菌種名稱、95 種測試藥品名稱；包含不同微生物與測試項目，收錄不等於適用於抗生素治療。
- `profile.json`：欄位分布與原檔 SHA-256。
- `cases.json`：15 個初始來源／模擬混合病例。初步、多菌種與陰性資料不自動生成完整單菌種情境；原始數值仍以字串保留。

這些檔案與根目錄 `microbiology*.csv` 已由 Git 忽略。腳本不送出網路請求、不呼叫 LLM。`--install` 將準備好的病例加入本機資料庫；同 ID 已存在時保留使用者修改。重啟後端、重新整理前端即可選取，或按「載入已準備的來源病例」。

舊版虛構病例仍保留歷史資料，預設列表及新 benchmark 不納入；需要稽核舊資料可用 `GET /api/cases?include_legacy=true`。舊 `data/synthetic` 與 `configs/demo` 僅供歷史回歸測試，不是預設種子或規則。

### 6.2 資料來源標示與病例 JSON

在「匯入病例 JSON」使用 canonical 格式。所有新增欄位向後相容，日期仍須有時區。

| 資料類型 | 欄位 |
| --- | --- |
| 全部合成 | `is_synthetic: true`、`data_origin: synthetic` |
| 純去識別來源 | `is_synthetic: false`、`data_origin: deidentified`、填 `provenance.source_system` |
| 來源藥敏＋模擬臨床情境 | `is_synthetic: false`、`data_origin: hybrid`、另列 `provenance.simulated_fields` |

`evidence_scope: reference` 與 `policy_refs: [文件 ID]` 決定病例引用哪些參考文件。不得把去識別來源直接標成全部合成。來源檔的偏移日期不拿來補真實病歷時間；症狀、年齡、體重、腎功能、過敏及目前用藥是明確補寫的情境。

原始 `AST_pheno` 與 `CLSI_2022_pheno` 分開保存。預設使用後者，未提供則不偷偷回退成另一欄。I、R、SDD、NS、缺漏與前後不一致都不自動變成 S。AST_val1/val2 未有單位，不一律當成 MIC，也不以數值推算界值。

來源病例預設可用 rule-only、mock 或本機 Ollama。若來源資料使用條款允許外送，可在病例摘要勾選「允許此病例的必要分析欄位送至外部模型」，會保存新版本；之後選 live 才會呼叫已設定的 OpenAI 等服務。傳送資料不含來源病人 ID、就醫 ID、原檔列或偏移日期。**此勾選本身不授予資料使用權。**

### 6.3 編輯與歷史

選病例 →「編輯並建立新版本」→ 修改 JSON、保留同一 case_id →「保存新版本」。不儲存時按「取消編輯」。展開「歷史版本」查舊資料，「全部病例資料與轉換警告」查完整紀錄。

修改後需重新分析。舊 run 和審閱保留原快照，不自動套用到新版本。

<a id="analysis"></a>
## 7. 分析模式與結果解讀

選病例 → 選「比較模式」→ 選「模型執行方式」→ 按「執行分析」。等待回應後閱讀分析結果，不要重複送出。

| 模式 | 做什麼 | 未設定回答模型時 |
| --- | --- | --- |
| rule-only | 來源判讀規則與模板選項，不呼叫回答模型 | 可執行 |
| rag-only | 病例摘要與檢索證據的研究基線生成 | partial／not_configured |
| single-agent | 病例、來源 AST 與證據的一次主要生成 | partial／not_configured |
| multi-agent | 多節點整理、規則、檢索、安全與候選呈現 | partial／not_configured |

模型執行方式可選未設定、mock、外部模型 live。mock 與 live 皆須通過輸出檢核。來源病例的基線模式取得已測試藥品名稱，multi-agent 取得規則篩選後集合；mock 基線只挑第一項，遇過敏等限制可能被最後檢查阻擋，這不是 API 連線失敗。multi-agent 目前是確定性多節點加一次主要生成，不是多個 LLM 互相討論。rule-only 仍可能執行檢索節點供 trace 使用，Ollama 故障時要查看該節點狀態。

結果包含候選、避免項目、原因、規則／證據引用及限制。來源 AST 的 S/I/R 和系統展示判讀分開，不代表已用正式 breakpoint 重新驗證。

| 狀態 | 意思／下一步 |
| --- | --- |
| ready_for_review | 可送展示審閱，並非臨床安全認證 |
| awaiting_review | 等待使用者審閱 |
| needs_confirmation | 查缺漏、規則與證據問題，補齊後重新分析 |
| blocked | 禁止候選發布，查看硬性限制，不能靠接受解除 |
| partial／not_configured | 必要模型未設定，已完成節點仍可看 |
| failed | 查節點錯誤，可能是 provider、解析或輸出驗證 |
| skipped | 節點無適用資料或不需執行 |
| pending | 等待執行或人工操作 |

再次執行會建立新 run_id，保留歷史；點「執行紀錄」只讀取結果。服務重啟時會標記被中斷的 running 紀錄，不當成成功。

<a id="evidence"></a>
## 8. 證據與流程

先選一筆結果，再按「查看證據與流程」：

1. 查看八節點：病例完整性、AST、抗藥背景、快速鑑定、證據檢索、安全閘門、候選呈現、人工審閱。
2. 在「工作流 Trace」展開節點，查狀態、耗時、規則／證據參照、輸出與錯誤。
3. 在「版本固定的證據快照」閱讀實際片段，按「開啟原始文件」核對來源。

PDF page 是從 1 開始的實體頁序，不一定等於印刷頁碼；Markdown／文字使用行號，Markdown 可另有標題路徑。舊 run 固定保存當時片段與規則版本，更新文件不改寫舊快照。引用有效只代表能定位，是否支持結論仍需人工閱讀。

<a id="review"></a>
## 9. 人工審閱與角色

1. 左側角色可選醫師、藥師或研究／管理人員；這是展示角色，不是正式登入。
2. 選 run，按「前往人工審閱」。目前使用者 ID 固定為 `demo-user`。
3. 「決定」選接受、修改或拒絕，填「審閱理由」。
4. 修改時使用藥物選單、判斷理由與證據勾選，可新增符合條件的候選或移除候選；「比較原始結果」可核對原文。來源排除項目由後端保留，不得移回候選。醫師不用編輯 JSON。
5. 按「送出審閱」，看到「審閱已保存」後按「重新讀取審閱」。
6. 在歷史展開「原始／修改內容」，查看前後內容與時間。

沒有可發布 output 時不能接受；拒絕可留下理由。修改要重新通過安全驗證。審閱是獨立紀錄，不改原 run trace，不自動訓練模型或啟用規則。重新整理後，重選病例與 run 可讀回歷史。

<a id="documents"></a>
## 10. 文件上傳與 WHO RAG

### 10.1 上傳文件

1. 開啟「文件資料庫」，選 PDF、UTF-8 `.md` 或 `.txt`，單檔上限 20 MiB。
2. 輸入標題與版本，例如 `demo-policy-notes`／`v1`。
3. 虛構文件勾選「虛構展示文件」，真實文件取消勾選。
4. 按「匯入並解析文件」，查看 processing_status、warnings、chunk_count。
5. 展開「文件版本」中的紀錄，查看 metadata 或開啟原檔。

`indexed` 表示解析切段完成，**不代表向量已建好**。同 hash 重複上傳回傳舊紀錄，不更新標題、版本或 synthetic 標記；不同內容另建文件。原始檔保存在本機 runtime。

### 10.2 WHO 抗生素書

本機附件原位於專案上一層 `who_aware_antibiotic_book.pdf`。2026-09-15 已匯入當時本機 runtime；其他電腦 clone 不會帶入原檔，需自行上傳。

- 標題：`The WHO AWaRe (Access, Watch, Reserve) antibiotic book`
- 版本：`2022-user-supplied`
- **取消「虛構展示文件」勾選**。

上傳後選 `reference 正式參考文件（例如 WHO）`；embedding 模式先按「重建向量索引」，等完成再查詢 `pneumonia` 或 `urinary tract infection`。點片段的「開啟原始文件」核對 PDF 頁面。

附件歷史實測：697 頁、1,442 chunks、indexed_with_warnings；第 2、44、310、592、644、696 實體頁無抽取文字，可能是空白頁或需 OCR。未逐頁驗證表格。檢索可能找到目錄或參考文獻，不可只憑排序認定相關。

### 10.3 搜尋、索引與政策關聯

| 範圍 | 文件 | 目前病例工作流是否使用 |
| --- | --- | --- |
| synthetic | 明確虛構的展示文件 | 是，且需符合病例 policy_refs |
| reference | WHO 等參考文件 | 是，病例 evidence_scope 為 reference 且符合 policy_refs |

選「文件範圍」→ 填「查詢」→ 按「檢索文件」。首次 embedding 搜尋會補建缺少向量。「重建向量索引」針對所選範圍；更換模型、服務位置或同名模型權重後，重啟並重建。WHO 全書首次索引可能較久。

向量保存在 SQLite，重啟可重用。相似度不是可信度機率。lexical 模式重建向量會顯示 skipped，但仍可文字檢索。

新增 synthetic 文件不一定被病例引用：病例 policy_refs 會限制文件。UI 上傳沒有政策 tag 欄位；若要用自訂文件，可將文件的 `doc_id` 加入病例 `policy_refs`，並讓 `evidence_scope` 對應文件分類，保存新版本後分析。不要把 WHO 標成 synthetic 來通過展示閘門。

相同標題的不同版本可能造成衝突，需核對來源與政策參照。解析失敗、OCR／表格警告、無證據或衝突時，不用模型補造來源。目前沒有完整 OCR／表格還原流程。

預設 embedding 送至本機 Ollama；若自行設定遠端 URL，搜尋／索引會將該範圍片段和查詢傳往該服務。

<a id="benchmark"></a>
## 11. 研究設定與 Benchmark

設定頁以「生成模型」「文件檢索」「病例規則」分別說明；設定已填齊不代表 API 連線測試成功，索引數對應 WHO 等 reference 參考文件。

比較歷史會顯示本機時間、病例數、模式數、執行筆數及模型方式，初次載入預設顯示最新紀錄。「可供審閱輸出率」表示通過安全條件且有輸出，不表示人工已核准；每個病例在每種模式各算一筆執行。各指標可展開中文定義、分子與分母；原始 JSON 保留於詳細資料和匯出檔案。整體失敗比例為零仍可能有歸入「已阻擋」的模型檢核錯誤，請同時查看錯誤摘要與逐次結果。

「證據與流程」中的分析步驟會先顯示中文用途、實際結果、提醒及耗時，再展開「詳細資料（原始 JSON）」查看完整 trace。步驟已執行不代表檢核通過；人工審閱節點是執行當時的快照，後續審閱決定以人工審閱頁為準。「審閱紀錄角色（展示）」只用於保存身分標記，不影響分析或權限。

「研究與設定」可查看 provider、檢索方法、模型、索引統計與展示規則版本。設定畫面不提供 key 編輯，請改後端 `.env`；配置查詢不呼叫付費回答 API。一般配置的 RAG 統計預設對應 reference。

1. 先確認完整單病例能執行，文件與規則版本符合預期。
2. 在「Benchmark 模型」選未設定、mock 或外部模型。
3. 按「執行四模式比較」。UI 會跑**全部已保存病例×四模式**，不是只有目前病例；16 例即 64 筆模式結果，live 可能多次付費。
4. 等待完成，查看 summary 並展開「逐案例結果」。
5. 按「匯出逐案例結果與摘要」下載 JSON；點歷史 benchmark 可讀回。

| 指標 | 解讀 |
| --- | --- |
| 完成／失敗／阻擋／未設定比例 | 軟體流程結果分布 |
| 規則測試通過率 | 與有標註的獨立預期比較 |
| 缺漏 precision／recall | 預測缺漏命中比例／實際標註缺漏找到比例 |
| 阻擋召回／不必要阻擋 | 應攔是否攔住／應可完成是否被誤擋 |
| 引用有效率 | 是否存在於此次快照、是否有位置，不評估結論支持性 |
| schema／白名單 | 格式與允許集合檢查 |

null 表示 N/A、無分母或未評估，不是零分。token 只有 provider 提供才保存，成本未設定為 null。修改過病例可能不再適用 seed 標註；mock/live 分開看。臨床適當性、專家一致率、引文支持性仍未評估，不能以 mock 成績證明模型優劣。

<a id="backup"></a>
## 12. 匯出、保存與備份

- 單筆分析：選 run，在「分析結果」按「匯出 JSON」，包含公開結果、trace、規則與證據快照。
- Benchmark：按「匯出逐案例結果與摘要」。
- 審閱：在人工審閱區查閱，或用 `GET /api/reviews?run_id=...`；run 匯出不是完整審閱／資料庫備份。
- 病例：工作台可查看／複製 JSON，API 可取得病例與 revision。UI 沒有整庫一鍵匯出或 CSV 功能。

預設 DB 為 `data/runtime/prototype.db`，原始文件、chunks 與向量在同層 `documents/`。自訂 `PROTOTYPE_DB_PATH` 時文件跟隨 DB 目錄；相對路徑以 backend 解析。

備份前先停止後端，保存整個 runtime 資料夾。還原前先備份目前資料，在服務停止時還原或指定另一個 DB 路徑；不要漏掉 documents。Git 不包含 runtime、`.env`、`.venv`、node_modules；全新 clone 需重新安裝、設定、seed 與匯入 WHO。

<a id="development"></a>
## 13. 開發、測試與 API

### 初始化與資料準備

不用開前端也可初始化／seed：

```bash
bash backend/scripts/init_db.sh
bash backend/scripts/seed.sh
```

只準備離線結果，不啟動後端：

```bash
backend/.venv/bin/python backend/scripts/prepare_demo.py
```

`scripts/generate_synthetic.py` 僅重建歷史回歸測試 fixture，不供新流程載入；新病例請使用第 6 節 CSV 匯入器。

### 測試

```bash
# 後端 coverage、前端型別檢查/build、元件測試
bash scripts/test.sh

# 第一次先安裝 Chromium 與 Linux 系統依賴，再執行瀏覽器驗收
(cd frontend && npx playwright install --with-deps chromium)
bash scripts/test.sh --e2e
```

E2E 自動啟停測試服務，使用獨立 DB 及 8001／5174 埠，請保持這兩個埠可用。預設測試不呼叫付費 API。2026-09-15 驗證記錄：後端 81 項、coverage 86%、元件 4 項、E2E 4 項、build 通過；這是歷史結果，不代表真實 OpenAI／Ollama 已測通。

### API 與契約

開 [API 文件](http://127.0.0.1:8000/docs)，選 endpoint → Try it out → 填參數 → Execute。POST 匯入、分析、審閱與 benchmark 會保存資料；live 分析可能付費。

| 功能 | 主要 API |
| --- | --- |
| 健康／設定／schema | `GET /api/health`、`/api/config`、`/api/schema` |
| 病例 | `GET /api/cases`、`POST /api/cases/import`、`GET /api/cases/{case_id}/revisions` |
| 執行 | `POST /api/runs`、`GET /api/runs/{run_id}`、`GET /api/runs/{run_id}/trace`、`GET /api/runs/{run_id}/export` |
| 文件 | `POST /api/documents/import`、`GET /api/documents`、`GET /api/documents/{doc_id}/source` |
| 正式參考搜尋／索引 | `GET /api/documents/search?q=pneumonia&scope=reference`、`POST /api/documents/reindex?scope=reference` |
| 審閱 | `POST /api/reviews`、`GET /api/reviews?run_id=...` |
| 規則／比較 | `GET /api/rules`、`POST /api/benchmarks`、`GET /api/benchmarks/{benchmark_id}/export` |

病例 import body 為 `{"payload": {...}, "format": "canonical"}`，文件使用 multipart。API benchmark 可指定 case_ids／modes 做小批比較，完整參數以互動文件為準。

schema 修改後從根目錄更新契約與前端型別：

```bash
bash backend/scripts/generate_contracts.sh
npm --prefix frontend run generate:types
npm --prefix frontend run build
```

<a id="faq"></a>
## 14. 常見問題

| 問題 | 處理 |
| --- | --- |
| 只有 .venv、沒有 .env | 按第 2 節從範本建立，確認不是 .env.txt |
| `No module named venv` | 安裝 `python3-venv`，移走未完成的 `backend/.venv` 後重跑 setup |
| 找不到 requirements | 在根目錄執行 `bash scripts/setup.sh`，後端清單在 backend |
| 找不到 ollama 命令 | 安裝後重新開終端機，確認 PATH 與安裝位置 |
| 11434 無法連線 | 啟動 Ollama，查 /api/tags，確認 embeddinggemma 已下載 |
| 8000/ 顯示 404 | 正常，操作頁在 5173；API 文件在 8000/docs |
| `Address already in use` | 在舊後端終端機按 Ctrl+C，或用 `ss -ltnp` 確認占用程序 |
| 沒有 Uvicorn running | 看終端機最後錯誤、目前目錄，再用 health 確認，勿反覆啟動 |
| 前端無法連線 | 兩個終端機保持執行，確認 health，再按畫面「重新連線」 |
| shell script 無執行權限 | 使用 `bash scripts/setup.sh`；若要用 `./scripts/setup.sh`，先執行 `chmod +x scripts/*.sh backend/scripts/*.sh` |
| .env 改了沒生效 | 重啟一般後端，確認未使用 demo.sh、未被既有環境變數覆蓋 |
| 模型 not_configured | 用 mock 展示，或補齊 LLM 設定、重啟並在 UI 選 live |
| PROVIDER_HTTP_ERROR | 核對 key、API 專案權限、model 與 URL，勿貼出 key |
| RATE_LIMIT／TIMEOUT | 查配額／速率或網路／timeout，先測單病例 |
| mock 仍沒有證據 | mock 只模擬回答；確認 embedding 或明確使用 lexical |
| WHO 匯入但搜不到 | 選 reference，核對解析警告與該範圍向量結果 |
| indexed 但向量失敗 | indexed 是解析狀態，向量另需模型連線與索引 |
| OCR／表格警告 | 人工核對原頁，需要時做 OCR 或整理可靠文字並保留來源 |
| 沒有候選 | 查 gate、缺漏、policy_refs、衝突；先試已匯入的 cohort 病例，不關閉安全檢核 |
| seed 後舊病例沒變 | seed 保留原修改；要更新請建立 revision |
| Human Review pending | 人工審閱需操作；審閱獨立保存，原 run trace 不被覆寫 |

健康檢查：

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

找不到占用 8000 的終端機時，先查 PID 及命令：

```bash
ss -ltnp | grep ':8000'
ps -fp 12345

# 把 12345 換成剛查到的 PID，確認是本專案 uvicorn 後才停止
kill 12345
```

<a id="limits"></a>
## 15. 限制與詳細文件

目前可操作的是來源藥敏＋模擬臨床情境的研究 prototype。正式 AST breakpoint、腎功能調整、藥物交互作用、正式登入、院端整合及臨床驗證仍未完成；真實 OpenAI／Ollama 需在自己的環境驗證，WHO 切段與檢索品質尚未完整人工評估。本專案僅本機執行，不包含公開部署流程。

- [需求核對與待辦](docs/REQUIREMENTS_AUDIT.md)
- [實作狀態與測試證據](docs/IMPLEMENTATION_STATUS.md)
- [架構與工程決策](docs/ARCHITECTURE.md)
- [資料字典、規則與待確認事項](docs/DATA_AND_RULES.md)
- [RAG／provider 技術說明](docs/RAG_AND_PROVIDERS.md)
- [工作流、審閱與 Benchmark 指標](docs/WORKFLOW_AND_BENCHMARK.md)
- [歷史回歸測試病例說明](data/synthetic/README.md)
- [OpenAI／WHO 集中教學](docs/USER_GUIDE_ZH_TW.md)
- [病例 JSON Schema](contracts/case.schema.json)、[OpenAPI 契約](contracts/openapi.json)
