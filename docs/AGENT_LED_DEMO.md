# Agent 主導 DEMO 操作稿

## 最新：2026-10-12，精簡選藥與證據畫面

1. 病例工作台選病例並開啟既有分析，不需重新付費。
2. 分析結果以逐藥總覽查看數量；可搜尋藥名、篩選候選／不建議，按「展開」查看整合、AST、風險、引用與缺口。
3. 證據與流程：展開需要的 Agent，再查看該藥理由；文件快照按版本分組，可搜尋文件或原文，再展開片段。WHO 全文與節錄的共同來源提醒仍保留。
4. 人工審閱預設只有「藥品 1」：從「增加藥物」選候選，再填醫師決定與理由；有條件採用另填條件。
5. 要選多項，按「＋ 繼續添加藥品」；誤加可移除。其他藥品選「自行輸入」，輸入名称並核對是否為已有藥品別名。未對應分析的名稱由醫師另行核對，不會冒充 Agent 候選。
6. 採用項目閱讀警示後確認，按「保存逐藥決策」。審閱歷史與匯出會保留人工新增標記及原系統評估。只有選中的藥品需要作決定。

以下為歷史操作紀錄。

## 最新：2026-10-11，1.6.0 醫師候選

重新整理前端並開啟最近一次 agent-complete 分析即可看到17項醫師候選，無須再次付費；tetracycline 因來源已核對抗藥另列。未完成的 AI 核對與用藥限制仍顯示，醫師可逐藥選擇採用／有條件採用／不採用。病例外送勾選已移除，舊紀錄不改寫。完整操作與測試數字見 [1.6.0 驗證](AGENT_LED_160_VALIDATION.md)。以下為歷史紀錄。

## 2026-10-10：GitHub 接手入口

目前病例已整理進 [交接病例包](../data/handoff/README.md)。新電腦不必重新處理原 CSV：完成 setup 後執行 `powershell -ExecutionPolicy Bypass -File scripts/handoff.ps1`，另開前端，即可載入28病例、95修訂及24份文件，用 lexical＋mock 操作。要做 live，停止 handoff、設定自己的模型／Ollama、重建 reference 向量；新版不需病例外送勾選。以下歷史紀錄中的 PID、session、data/local 路徑不代表接手電腦的狀態。

## 最新：2026-10-09，1.5.1 付費前修正完成

已補來源藥品／複方身分與逐項風險原文檢查，錯配降級而不牽連其他有效分項；全程預設780秒，保留整合及Audit各180秒，正常6次／最多8次呼叫。檢索使用獨立截止與請求timeout，不在分析中臨時補建索引；其他模式維持既有行為。

後端377／前端59測試、build及diff check通過；Sol/high已報問題修正複驗結案。v12離線18藥54分項重播有13項新增降為unknown，沒有模型呼叫，原檔及API匯出不變。後端session35091／PID3884已載入1.5.1，參考文件2111片段索引完整。

後續只剩新live驗證本輪修正的实际模型表現及逐項語意核對，需新一次明確授權；未取得授權不執行。表格篩選仍屬非阻擋改善。詳見 [1.5.1驗證與DEMO](AGENT_LED_151_VALIDATION.md)。以下為歷史狀態。

## 最新：2026-10-09，1.5.0 逐藥醫師決策

已實作採用／有條件採用／不採用、逐藥理由及使用條件、警示確認、保存及匯出；未選藥品不須逐一決定。一般用藥警語與病例缺漏分開，已明示無已知過敏不再逐藥重問；空白仍是未知。人工決策不會改寫 AI 分層或原始分析。

後端完整 348 通過，最終 API 9 項複驗通過；前端 58 通過、build／diff check 通過，Sol/high 三項審查發現已修正結案。服務已載入1.5.0（session40394／PID30404），舊 v12 匯出不變。醫師前端 QA 見最新報告；本輪未新增付費 live。

操作稿、測試及後續界線見 [1.5.0 驗證與逐步 DEMO](PHYSICIAN_DECISIONS_150_VALIDATION.md)。後续待辦：取得新一次具體授權後驗證1.4.2輸出預算及1.5.0提示；核對原 WHO／DailyMed 語意錯配，不將人工決策當成 AI 複核已通過。以下狀態為歷史。

## 最新：2026-10-09 v12已完成，1.4.2已通過本機驗證

v12=6d05f0aa-5f57-43b9-a54d-e133e81b9657，1.4.1／病例4／18AST；6calls/215587tokens/277.7秒。Clinical已完成，Synthesis兩次各用滿6000輸出token而無完整JSON；Audit未執行，18pending/0候選。165引文字面存在，但Sol/high仍發現逐藥語意錯配。一次授權已使用，無新的付費run。

1.4.2已提高整合/複核輸出預算至16000/24000，保存截斷原因並避免同預算重試；339後端/51前端/build/diff check及Sol/high審查完成，醫師誤導文案修正與複驗完成。後端session41976/PID21044載入1.4.2，v12不變；新版尚未live。

使用者新增關注：已known_none的病例不應每藥重問過敏。需優先分開一般標示提醒/病例缺漏/引用缺口，空白不能自動當無過敏；此最新改善尚未實作。完整結果、時間預算風險與下一步見 [v12驗證與1.4.2交接](AGENT_LED_V12_VALIDATION.md)。以下為歷史。

## 最新：2026-10-09，1.4.1本機驗證完成，v12待具體外送同意

334後端／49前端／build／diff check通過；v11離線重播Clinical155042、Synthesis72076字元，原AST與選段原文保留。Sol/high小範圍審查未見阻擋。後端session16533／PID27200已載入1.4.1，舊v11匯出不變。

使用者「同意執行付費分析」後，自動核准審查仍拒絕執行v12，要求明確連結資料與目的地；拒絕發生在程序啟動前，未呼叫模型。已發具體一次外送確認問題等待回覆，不重复提問。詳見 [1.4.1驗證及恢復步驟](AGENT_LED_141_VALIDATION.md)。以下為歷史。

## 最新狀態：v11已完成，1.4.1修正中，依額度暫停

2026-10-08：直接「同意」的一次授權已用於v11，run fbb4bb56-96e7-4ce9-889e-b952e0cae688，1.4.0／agent-complete revision4／18AST／gpt-4.1-mini。3calls、61227tokens、119.2秒；Clinical及Synthesis因輸入超限未呼叫，Audit未執行。0候選、0review_options、18pending。88段引文字面全存在，但Sol/high發現錯藥／感染情境／族群錯配；不能當獨立複核已通過。

已寫1.4.1來源metadata精簡、整合引用目錄縮小、選段包含metadata大小預算及前後端版本相容修正；只有新增3項後端測試通過，完整測試/build/修正審查/新live均未完成。五小時剩0%、每週剩39%，依門檻暫停。服務仍1.4.0；沒有執行中模型或測試。本次授權用完，先完成本機修正驗證再請新一次live授權。

詳見 [v11結果與完整交接待辦](AGENT_LED_V11_VALIDATION.md)、[Sol/high引用審查](AGENT_LED_V11_REVIEW.md)。以下為歷史進度。

## 2026-10-08 本轮接續完成

八病例API契約檢查通過，來源與版本保留，記錄在 `data/local/agent_cases/readiness-140.json`。醫師Sol/high已實際驗證歷史run前端，找到的版本／模型不清與待確認來源不清兩項已修復並複驗。前端48測試及build通過；後端程式本輪未改，沿用331通過結果。Sol/high程式審查的空導覽問題也已結案。

DEMO：打開歷史分析後先核對「分析當時病例」版本／模型；待確認表格按來源Agent區分，中文顯示片段省略，按「查看此步驟」或「查看錯誤步驟」可直接展開對應Agent。未保存的歷史欄位顯示未記錄。

前端5173 session6730；8000既有服務health與1.4.0契約正常。新版付費live仍未執行；先前的具體一次外送確認仍待直接回覆，不重複提問。收到同意後只執行一次agent-complete第4版／18AST／WHO與DailyMed／外部gpt-4.1-mini驗證，逐項核對來源及層級，保存新結果；舊v10不能當作新版驗收。詳見 [驗證報告](AGENT_LED_140_VALIDATION.md)、[醫師操作複驗](PHYSICIAN_UI_140_RECHECK.md)。下方舊狀態僅供歷史追溯。

## 1.4.0 新版操作

先讀 [1.4.0 DEMO步驟與驗證界線](AGENT_LED_140_VALIDATION.md)。新版分完整候選／有證據的待審閱選項／其他待確認／不建議或未選入，第二層顯示未完成原因且不能直接接受。已完成331後端／47前端／build及Sol/high複查，但尚未新live；舊v10不能用來展示新版實際模型結果。

## 最新實際操作：v10（2026-10-08）

1. 選 agent-complete 第4版的歷史run `bec1ebb1-1f48-4ea7-87ad-11b93e2f07e4`（1.3.6）。已實際執行六次呼叫，最終18項待確認。
2. 查看逐藥AST來源：15敏感、1抗藥已核對；ertapenem缺選定CLSI，levofloxacin有來源衝突。
3. 展開臨床風險，說明來源連結未完成，不能說病例缺全部資料；已確認無併用藥仍需要正確引用病例欄位。
4. 展開證據與獨立複核。初評有26段實際引文，但複核未選引文；新版前端會提示細項不是核對通過。不要把模型草稿讀成醫師建議。
5. 匯出run。API匯出已實際保存並核對一致；沒有候選所以不示範接受不存在的建議。

1.3.7本機欄位與提示修正已測試，但未live；本次一次授權已用完。詳見 [v10 驗證報告](AGENT_LED_V10_VALIDATION.md)。以下為历史。

## 最新展示界線：1.3.6（2026-10-07）

服務已載入1.3.6，後端308／前端45／build及Sol/high複查完成，但尚未跑新版live。現在仍應從歷史選v9作為實際模型執行紀錄；兩項「不建議」已查出來源不足，需說明是待重新分析的歷史模型判斷。不要把本機離線重驗當新run，也不要宣稱臨床驗收完成。

新live取得授權並完成後，逐藥展開「獨立引用複核」，分別說明AST來源核對、聲明一致性、引用／來源待確認原因，再對照引文位置和文件。来源一致不等於臨床適用。尚無候選時不展示接受不存在的建議。完整接續項目見 [1.3.6 驗證報告](AGENT_LED_136_VALIDATION.md)。下方舊版服務／額度狀態為歷史。

## 最新v9展示位置（2026-10-07）

選agent-complete revision4歷史run `66e190b6-7feb-456d-9b1f-7cdba2fd64f8`（1.3.4），六步完成、0可供審閱／16待確認／2不建議。可展示藥敏來源連結、三項臨床風險、引用原文及匯出；整合引用識別碼錯誤已為0。AST17筆因同時列入一致比較欄而被舊guard誤擋，不能說病例缺17筆資料；ertapenem選定CLSI則真正缺值。audit18supported尚未全面核對，兩個不建議亦不能宣稱專家確認。無候選，不演示接受不存在的建議。

v9 API匯出已執行並與保存run一致，檔data/local/agent_cases/live-complete-v9-export.json。1.3.5來源修正僅本機292後端測試通過，服務尚未重啟且未再live；五小時剩4%已暫停。詳見AGENT_LED_V9_VALIDATION.md。瀏覽器醫師QA仍未驗收。

## 2026-10-07 v8實際操作／新版1.3.4

1. 選`agent-complete`第4版，從歷史選run `eff53f5a-b59d-4f56-929b-d6deca1eb52e`（1.3.3）。這次已執行六次模型呼叫，0可供審閱、18待確認。
2. 在逐藥表說明「待確認不等於不適用」。展開藥敏草稿可見來源連結問題；ertapenem選定CLSI欄仍缺值，不能靠原始數字推敏感。
3. 展開臨床Agent可看三項風險細節；這次格式已成功，但unknown不等於確認沒有風險。病例整理的部分issues只是正常事實，不能示範為已證實缺資料。
4. 查看獨立引用複核，說明模型的supported仍需對照原文。這次六項supported只靠風險警語，來源審查已指出不充分；不宣稱已通過臨床驗收。
5. 展開引用／WHO同源說明，再查看證據準備表，分別說明片段存在、輸入覆蓋、語意適用是三件事。
6. 匯出此run；API run/trace/export已實際核對一致。沒有候選時不示範接受／修改不存在的選項。
7. 1.3.4已載入，新增明確来源選項與失敗診斷、逐聲明引用檢查。後端288、前端43及build通過，但未再次live。不要將歷史v8當新版執行結果。

瀏覽器工具仍無可用surface，本稿為API實際操作及前端程式/測試對照，未宣稱醫師已實際走完介面。詳見AGENT_LED_V8_VALIDATION.md。

2026-10-06。此稿記錄已實作流程；live 尚有未完成項目，請搭配 `AGENT_LED_VALIDATION.md`，不要宣稱全部臨床判讀已驗證。

### 2026-10-07 最新操作補充

- 1.3.3最新：文件資料庫展開 WHO lower-UTI 節錄，可見「節錄自」及同源說明。新分析引用保留同原始文件識別，全文與節錄不能算多份獨立證據。這只是來源核對，不是用藥支持度；舊run不補寫新來源標識。
- 已執行本機來源核對：`python backend/scripts/link_who_source.py --references data/local/agent_references_v2 --apply`（使用backend虛擬環境；拿掉`--apply`只預覽）。原始PDF/節錄需均已匯入，雜湊與重抽取不符時停止，不依標題猜測。
- 最新驗證後端281、前端41及build通過；backend已載入1.3.3。以下較早測試數保留歷史，瀏覽器復驗及新live仍未完成。

- 選agent-complete目前顯示revision4；既有v7歷史仍顯示其執行時revision3，這是快照保留而非載入錯誤。其餘6個有AST基礎情境也為revision4；rapid-only仍revision3，過敏配對為revision2。
- 在待確認藥物列，先讀藥名旁的最終狀態，再展開「藥敏模型草稿」「模型證據草稿」「整合草稿與限制」。模型肯定句仍屬原始草稿，不是發布的建議。
- clinical失敗時看「病例快照已有…」與執行錯誤；未核對不表示要重填現有資料。其他Agent空缺漏清單若仍有逐藥待確認，會明示需注意項目數。
- 文件庫「第7頁表格需人工檢查」需對照PDF欄列；原代碼另折疊。族群依據未記錄會附註，不能把成人標籤當作適用性已驗證。過敏表單的新用語是「已有臨床評估：不支持此過敏標籤」，仍須填來源及確認紀錄。
- 已完成後端278、前端38測試及build；浏览器實際復驗因工具不可用尚未完成，修正後新live也尚未執行。

舊人工病例要升級來源文字，可先執行不加`--apply`的預覽，再執行：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/upgrade_case_source_descriptions.py --cases data/local/agent_cases --apply
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/upgrade_case_source_descriptions.py --cases data/local/allergy_pairs --apply
```

已有人工修改的source、不同來源、AST改動或並行新revision都會保留並跳過；不更改原始檢驗值或舊run。結果記錄於對應資料夾的source-label-upgrade.json。

### v7目前可展示的實際結果

選 `agent-complete` revision3 最新run `91ddb348-f6a6-4576-9926-989df2447128`：7次呼叫、0候選／18待確認。展開臨床Agent可見格式失敗；這不代表病例未填過敏/腎功能/用藥。引用獨立複核的「有支持」是模型回報，人工原文核對已發現錯配，不可把這筆當成功用藥建議範例。

1.3.2前端將逐藥最終狀態放在藥名旁，待確認文字收進「模型證據草稿／整合草稿與限制」，展開後可追溯原始輸出。「逐藥證據準備與呼叫情況」分開顯示已準備片段及是否呼叫/收到回覆；準備不等於送達或支持。後端最新AST來源檢核需重啟載入；最後草稿UI改動尚待測試復驗。現階段可展示分析與匯出，不演示接受不存在的候選。

1.3.1 新增操作：在逐藥決策表下展開「逐藥證據送入情況」。逐列對照 Agent、藥品、用途、檢索狀態、找到／送入／未送入數，展開來源片段。說明「找到幾筆」不是支持幾個藥品，未送入片段未參與該 Agent 分析；檢索失敗不能解讀成不適用。舊 run 沒有此欄位時不顯示此表。

### 最新功能說明（agent-led-1.3）

1. 八個情境目前為 revision 3。查看「用藥清單完整性」；一般舊病例仍為未知。核對清單後按「確認目前無用藥」或「確認目前列出的用藥清單完整」，會保存新版本，需重新分析。
2. 在逐藥決策表及臨床 Agent 展開過敏／腎功能／交互作用。各自顯示病例依據、文件原文、缺漏與下一步；未知不代表沒有風險。
3. 一般注意事項若資料完整且通過獨立複核，可以附提醒供人工審閱。複核未支持或關鍵資料缺失仍為待確認；不能宣稱所有 caution 都會產生候選。
4. 引用複核也會核對排除及未選理由。展開查看病例事實、文件適用性與三項風險複核；沒有可複核聲明時顯示未執行，不算通過。
5. 文件庫已加入 `1.pdf` 的 UK 成人過敏標籤研究，分類為觀察性研究／背景，不能拿來證明本例某藥適用。四個 `agent-allergy-pair-*` 已可由病例選單選取；四模式比較尚未 live 驗收。

重新產生套件後，若要升級舊人工情境的用藥史 metadata，可在安裝命令加 `--upgrade-authored-medication-history`。僅相符來源、原人工用藥清單未改且尚未確認者會新增 revision；保留其他現行欄位，不改舊 run。

## 準備一次

根目錄執行（Python 需有 requirements 內的 pypdf）：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/build_agent_cases.py --source microbiology_cohort_deid_tj_updated.csv --out data/local/agent_cases
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/prepare_agent_references.py --case data/local/agent_cases/agent-complete.json --who who_aware_antibiotic_book.pdf --out data/local/agent_references_v2
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/install_agent_package.py --cases data/local/agent_cases --references data/local/agent_references_v2
powershell -ExecutionPolicy Bypass -File backend/scripts/run.ps1
```

另一個終端執行 `powershell -ExecutionPolicy Bypass -File scripts/frontend.ps1`。開啟 http://127.0.0.1:5173/ 。文件資料庫選參考文件範圍，完成向量索引再開始計時。資料集及產物在 `data/local/`，不提交 Git。重建參考文件時可加 `--supersede-package-documents`，只替換前次套件清單內的文件，歷史 run 引用快照仍保留。

## 逐步展示

| 次序 | 操作 | 要說明的重點／預期 |
|---|---|---|
| 1 | 病例工作台選 `agent-complete` | 摘要集中顯示來源 AST＋人工臨床情境；18 筆是此份培養的 AST，95 是全 CSV 藥名數，不能混為同一病人檢驗。 |
| 2 | 展開病史、生命徵象、抗藥背景 | 背景為 CSV E. coli 尿液資料集，顯示 S/I/R、分母、缺漏、衝突與來源雜湊，不是院內 antibiogram。eGFR 與 CrCl 不同；測試計算值有 provenance。 |
| 3 | 查看文件選擇與外送設定 | 預設查文件庫全部參考文件，可另存指定文件範圍。WHO 為感染指引；DailyMed 為美國藥品標示，不是院內政策。 |
| 4 | 模式選 multi-agent，模型選已設定模型，執行分析 | 會傳送此病例必要欄位及文件片段並產生模型費用。Mock 僅驗證流程，不能代替這一步。正常六次呼叫，失敗重試共用上限。 |
| 5 | 分析結果看逐藥決策表 | 對照原始／CLSI 2022 判讀、MIC 是否提供、風險、文件支持、獨立複核、最終去向。未測 AST 的指引選項單獨標示，不能說是敏感。 |
| 6 | 證據與流程逐一展開六張卡 | 病例缺漏、逐藥 AST、文件適用性、過敏／腎功能／併用藥、分歧整合、独立引用複核。查看具體需補欄位、影響與下一步；局部失敗時其他有效報告保留。 |
| 7 | 展開引用 | 核對原文、章節、文件版本、來源網址。引用存在不代表語意支持；WHO 成人與兒童頁不可混用。 |
| 8 | 有可供審閱項目時前往人工審閱 | 選角色，輸入審閱者和原因，可接受／修改／拒絕。修改只選本次已複核選項與其引用；新增未評估藥品需重跑。沒有有效候選不可為展示而強制接受。 |
| 9 | 病例工作台選 `agent-renal`，編輯病例，貼入 `agent-renal-revision.json`，保存新版本 | 更新腎功能後重跑，舊執行仍保留舊病例及證據快照。先查看本機 revision，勿假設一定從 1 開始。 |
| 10 | 選 `agent-interaction` 查看 live 記錄 | 活躍用藥 tizanidine 的風險必須有標示支持；不能只看敏感就放行。模型對其他同類藥的泛化仍需核對。 |
| 11 | 選 `agent-evidence-mismatch` | 此例刻意固定無關文件。應保留 AST 分析，但不能發布有文件支持的候選。 |
| 12 | 文件資料庫搜尋、展開版本、查看原檔 | 展示來源、適用族群、檢索片段及索引狀態。誤傳檔可刪除，歷史引用快照保留；指定已刪除文件的病例需改文件範圍。勿刪實際展示所需 WHO 或藥品標示。 |
| 13 | 研究與設定勾一個病例、兩種模式 | 執行前預覽應為兩筆。已實測 `agent-complete` × rule-only/multi-agent，選 Mock，結果兩筆且新模式規則指標不適用。 |
| 14 | 展開比較結果和歷史 | 比較呼叫數、已知 token、檢索量、引用複核和流程版本；不能用有候選比例當臨床正確率。 |
| 15 | 分析頁「匯出 JSON」、比較頁「匯出逐案例結果與摘要」 | 匯出帶病例、來源、版本、原文及審閱歷史，供之後重現。 |

## 八情境驗收矩陣

### 新增：論文延伸的過敏流程

1. 在病例工作台查看「過敏標籤與確認紀錄」；舊病例顯示確認狀態未提供，不能解說為已確認過敏。
2. 展開「補充過敏紀錄（保存為新病例版本）」，填寫反應、來源、時間及既有評估。若選已有確認／排除紀錄，需填評估內容、來源、紀錄者及含時區時間。
3. 保存後顯示新 revision，再重新分析；歷史分析使用舊快照。評估排除紀錄仍與原標籤一同保存，不是模型自動解除標籤。
4. 文件匯入選「研究文章（背景證據）」及「觀察性研究」，填來源與地區。本論文已匯入，用於標籤影響的群體研究背景，不直接當個人用藥支持。
5. 四個配對案例檔案在 `data/local/allergy_pairs/`，已匯入病例庫。可在 Benchmark 勾選同一組病例與四模式。16 筆僅為一次比較的執行數，非已完成 16 次 live。
6. 結果若零可審閱，查看是否為引用／格式／輸入限制或真正的臨床不適用；新前端會明示兩者不能等同。

重新產生配對檔案：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/build_allergy_cases.py --base data/local/agent_cases/agent-complete.json --out data/local/allergy_pairs
```

### 原八情境

| 病例 | 必須核對的行為 |
|---|---|
| agent-complete | 完整18筆 AST、來源一致、逐藥理由、獨立複核；指引未測選項可提出但不可聲稱敏感 |
| agent-renal | eGFR 22、CrCl 25.9、creatinine 2.6 各自保留；有依據的腎功能風險 |
| agent-allergy | nitrofurantoin anaphylaxis，不能被後續整合忽略 |
| agent-interaction | active tizanidine；核對逐藥交互作用而非整類泛化 |
| agent-ast-conflict | 原始18筆不改，另附有 provenance 的矛盾測試列；不得隱藏衝突 |
| agent-rapid-only | 無 AST，不可推定敏感；區分快速鑑定與尚未完成培養 |
| agent-evidence-mismatch | 引文不足／不適用應待確認，不硬湊候選 |
| agent-missing | 過敏未知、腎功能及感染部位缺失，顯示具體影響 |

病例建構測試涵蓋八情境資料與來源保留；這不是八病例的 live 臨床驗收通過聲明。
