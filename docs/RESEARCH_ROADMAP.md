# Research Roadmap：先建立可信評估，再改進 Multi-Agent

基準日期：2026-10-26。程式版本：`1ad2648a349c28989c9fa3d41cd37bf56a40f0fd`；現行 Multi-Agent：`agent-led-1.6.0`。本文件包含原始碼／保存 Run 的分析及未來工作提案；沒有實施提案、修改 Prompt／資料／設定或呼叫真實模型。

標記：**已確認**＝現行程式或本機保存資料可直接驗證；**推論**＝從已確認結構導出的風險，尚未做實驗量測；**計畫**＝尚未實作。新的工程師可先依 `TECHNICAL_HANDOVER.md` 找模組，再依 `TESTING_AND_DEBUGGING.md` 執行隔離測試。

## 1. 研究問題與目前證據的上限

建議主要研究問題是：在固定病例、可用證據與明確資源條件下，角色分工、逐藥來源連結及獨立 Audit 是否改善可驗證聲明的正確性，並以何種覆蓋率、拒答率、延遲與成本交換？不要把「更多 Agent」「更多候選」「少一點 pending」本身當研究成功。

本機唯一已保存 Run 為 `51905060-412e-4e04-99f3-c9a1bbbbc596`：agent-complete 第 4 版、18 AST、六次 Mock 呼叫、74 次 lexical 檢索、18 pending、AI candidates 0、physician_candidates 18。它證明軟體資料流與保存流程可運作，**不能估計任何真實 LLM 的正確率、Live latency、成本或 Multi-Agent 優勢**。已保存的 `[MOCK TEST]` 人工不採用紀錄也不是 Ground Truth。

## 2. 四模式能否公平比較？

目前具備比較執行器與部分固定條件，但不足以直接把差異歸因為 Multi-Agent 架構。

| 模式 | 現行生成資訊與控制（已確認） | 比較上的含義 |
| --- | --- | --- |
| Rule-only | 確定性 RuleEngine／來源 AST，無生成模型；仍做檢索與 evidence gate | 不是完全不使用文件的純規則；要將檢索與生成成本分開 |
| RAG-only | 單次生成看到病例 summary、來源藥名 allowlist、共同檢索；summary 有 ast_count，但沒有完整 ast_results；後處理仍有規則 | 不宜描述成完全無規則的 RAG；模型不見規則判決，但最終發布有規則篩選 |
| Single-Agent | 單次生成；在上述基礎加入完整 ast_results | 與 RAG-only 的差異包含資訊可見性，不只是 Agent 數 |
| Multi-Agent | 六節點、專責 Schema／Prompt、逐藥／逐風險檢索、來源驗證、獨立 Audit；不經舊 RuleEngine 判決 | 與 Single-Agent 同時改變呼叫數、檢索量、上下文、驗證器及發布門檻 |

來源：[baseline summary](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/engine.py:44>)、[baseline context／post-filter](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/engine.py:279>)、[rule-only runner](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/agents/runners.py:8>)、[現行路由](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/engine.py:382>)、[不呼叫 RuleEngine 的測試](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/tests/test_agent_led.py:72>)。

Benchmark 的已確認公平控制：

- 開始時固定病例版本；非 Multi-Agent 固定規則 snapshot。
- 整次 Benchmark 以 DocumentService snapshot 固定文件庫（支援該功能時）。
- 非 Multi-Agent 預先搜尋每例共同結果，再用 FrozenDocuments 給三模式重用。
- Multi-Agent 使用同一固定文件庫，但自行執行多次角色／逐藥檢索；不是重用同一組檢索片段。
- 有 mode／mock／workflow version 分組，但沒有完整研究用 manifest、重複抽樣與統計比較程序。

依據：[Benchmark snapshot](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/main.py:413>)、[固定病例及不同檢索路徑](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/main.py:424>)。

**推論，尚未量測**：用現有各 Run 的 elapsed_ms 直接比較延遲會受計時範圍影響：非 Multi-Agent 的共同檢索在模式執行前完成，FrozenDocuments 回傳很快；Multi-Agent 的多次實際檢索則在自身計時內。來源固定有助可重現，但不等於資源／輸入公平。其他三模式也沒有同等的獨立五維度 Audit，不能拿「通過各自 gate 的比例」直接當相同嚴格度的醫療正確率。

計畫建立兩種互補比較，分開報告：

1. **系統實用性比較**：各模式保留原有策略，以相同病例與文件庫比較最終效果及全流程成本；結論僅稱完整系統差異。
2. **受控機制比較**：固定原始事實、候選 universe、證據包及獨立評分器，再改分工／Audit 等單一因素。另做資源接近的設定，避免品質改善只是更多 token／查詢。

## 3. 分工與資訊獨立性

**已確認**：六節點有不同角色任務、輸出契約與資訊投影。前四角色順序執行，並非相互辯論；前四個 Input.assessments 預設都是空。Synthesis 才合併前四報告，Audit 不取得前置支持判決或最終狀態。

| 角色 | 具有差異的輸入／輸出 |
| --- | --- |
| Case | 原病例 facts＋AST；輸出問題／缺漏；不負責選藥 |
| AST | 原 AST＋額外 resistance_context；輸出來源類別判讀及 refs |
| Evidence | 感染／指引／逐藥檢索池；輸出適用性與選段 |
| Clinical | 病例風險欄位＋allergy/renal/interactions 檢索池；輸出 risk_details |
| Synthesis | 四角色報告、原病例及 AST；已用來源 metadata，不重複傳全文 |
| Audit | 聲明、精簡 facts、原 AST、上游指定原文；獨立輸出來源核對與 claim_checks |

依據：[角色定義](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/agents/runtime_led.py:68>)、[角色輸入投影](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:348>)、[Synthesis 壓縮報告](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:59>)、[Audit 隔離 context](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:366>)。

**限制**：這是任務／上下文分離，不是認知或統計獨立的證據。預設所有角色使用同一 LLM_MODEL；可用每角色環境變數改模型，但本機未驗證。工作流串行、不具動態規劃／工具自主調用／互辯迭代。**推論**：共享模型與共同來源可能造成相關錯誤；需要 Gold 與錯誤重疊實驗才能量測，不應直接宣稱 Audit 與 Synthesis 互相獨立可靠。[模型選擇](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/agents/runtime_v2.py:104>)。

## 4. RAG 品質：已知現象與未確認原因

**本次已觀察**：amoxicillin_clavulanate 的感染查詢及三種 Clinical 風險查詢，都取回 DailyMed 的標頭、適應症 part 0/1，而非對應的風險專節。74 次搜尋全為 ok，只證明執行成功；Evidence 收到 63 片段，Clinical 58，兩者沒有長度省略，仍不能確保內容相關。

**程式已確認**：

- lexical FTS 將 query tokens 用 OR 連接，主要 SQL 有 LIMIT，沒有明確 relevance ORDER BY；字詞命中不等於風險段落命中。
- search_agent_context 會依 scope、document_kind 及藥名路由；主要命中再補相鄰 chunk。limit=2 可能回 3 個以上片段。
- Evidence 與 Clinical 分別搜尋後做 context 預算選取；Audit 只拿指定來源，無法補救未被檢索／選取的證據。
- WHO 全書與下泌尿道節錄有 source_document_id／derivation 關係，不能當兩份獨立研究證據；文件 population 也不能自動證明每個片段都適合成人。
- Embedding 有模型／維度／prompt 身分及 cosine search，但本機 vectors=0、沒有實際驗收；不能宣稱它會改善上述問題。

依據：[lexical SQL](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/rag/service.py:1037>)、[路由／鄰段](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/rag/service.py:282>)、[來源身分與版本](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/rag/service.py:565>)、[embedding search](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/rag/service.py:878>)、[Run 查詢保存](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/runtime/mock-check/first-run.json:16658>)。

**尚不可推論**：無 relevance Gold，不能報整體召回率低於某值，也不能把此例推廣到所有藥物或 Live 模型。先測切段是否保留標題／表格、風險來源是否存在、路由是否漏掉、排名是否失準，再選擇需要改哪一層。

## 5. Evidence Audit 的能力與限制

| 已有能力（確認） | 不能因此聲稱 |
| --- | --- |
| 驗證 quote 是否屬於指定 chunk 原文、refs 是否可定位 | 引文必然支持整個結論 |
| AST 必須連到同藥、選定依據中的非空類別 | 能從 raw MIC 自動套用完整臨床 breakpoint |
| 檢查 fact_refs、五維度、產品／主題／來源歸因 | 有完整藥理、交叉過敏、腎劑量或交互作用推理引擎 |
| 模型獨立回覆 infection/population/drug match | 模型判決可當人工 Gold |
| 裁切 Audit context 時保留聲明並記錄 omitted_refs | 所有需要的來源都已送入、或所有省略都無影響 |
| claim_checks_complete／validation_status | 檢查已全部通過或臨床安全 |

依據：[check_quotes](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:45>)、[AST 獨立驗證](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/audit_sources.py:8>)、[claim checks](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/claim_checks.py:10>)、[source_scope](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/source_scope.py:53>)、[context 裁切](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/audit_context.py:6>)。

本次 Audit 的 evidence=[] 源於空引用，不是服務失敗；classify_options 卻也會加 retrieval_empty。這是已確認的診斷分類語意問題，可在後續改善 observability，但不能先為了提高完成率移除 Audit。需要測 Audit 的 false acceptance（錯誤聲明放行）和 false rejection（正確聲明被擋），並同時包含 supported／unsupported／uncertain；一味全回 uncertain 不能算好審核器。

## 6. 缺少哪些 Ground Truth？

現有 `data/synthetic/expectations.json` 是 missing_fields、expected_block、rule_evaluations 等軟體預期，並非臨床 Gold。Benchmark 還要求病例內容與 eligible seed 一致才套用標註；handoff 的 hybrid agent-complete 不應被假定自動獲得這些標籤。[expectations 套用條件](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/main.py:455>)。

原始 S/I/R 可用來檢查類別來源連結，但不等於最終藥物適用性。人工編製臨床情境是輸入，不是專家判讀答案；醫師操作清單和測試 Review 也不是 Gold。

建議分開建立以下標註（計畫）：

| 評估單位 | 需要的標註 | 來源／審查方式 |
| --- | --- | --- |
| Case | 明確缺漏、矛盾、已知無／未知、模擬欄位、所屬情境及 split group | 來源與 schema 人工核對；保留未知值 |
| Case × Drug AST | 選定類別、原欄位路徑、衝突／缺失／未測 | 原病例＋來源規範；不重算未授權 breakpoint |
| Query × Drug × Dimension | 必要文件／章節／片段 relevance 等級 | 固定文件版本；人工選段，列出可接受替代片段 |
| Atomic Claim | supported／unsupported／insufficient，正確 fact_refs、證據與限制 | 獨立專家盲審；分開判定引文定位與語意支持 |
| Case × Drug 五維度 | infection/AST/allergy/renal/interactions 判斷及需補資訊 | 藥師／醫師依相同病例和來源審查，允許多種合理判斷 |
| Final Result | 可供審閱／待確認／避用的可接受集合、理由與必要條件 | 專家裁決；不要強迫每例只有單一正確藥物 |
| Audit | 注入錯誤的類型、真假、應放行／擋下／要求資訊 | 人工設計最小反例，再盲審，不沿用 Audit 自評 |

每筆標註需 annotation_version、case revision/hash、document hash/版本/location、annotator、裁決理由、unknown policy、盲審與分歧紀錄。至少雙人獨立標註及裁決流程；測 inter-rater agreement，不能把同一人的 Prompt 調整與測試集答案混在一起。資料有限時先做小型 pilot 檢查可標註性，再依變異估計決定正式樣本量。

切分以病例來源／配對情境群組為單位，不把同一病例不同 revision 隨機分散到 train/dev/test。handoff 移除了來源識別碼，需另外建立受控、不公開的 grouping 對照或人工分組；**尚未確認有測試洩漏**，目前是缺乏可證明無洩漏的 split manifest。

## 7. 現有 Benchmark 為何不足？

已實作的 completion、執行耗時、token、引用 ID、狀態分布適合軟體監控，但仍有以下缺口：

1. citation_support_conclusion、appropriateness、expert_agreement、clinical_utility 明列 not_evaluated；Audit verdict 分布是系統輸出，不是獨立評分。
2. 引用 ID/location 只統計 output.candidates/avoid，不涵蓋所有 pending／逐維度 claims。沒有獨立引用支持 precision、claim coverage。
3. schema_validity 看候選整理旗標；agent-led 只要有 Synthesis output 就可標 schema_valid，不代表六角色全部 wire 一次成功；缺 first-pass／repair success 分析。
4. not_configured_ratio 把 partial 一起算；本次正常 Mock 不確定也落入。retrieval failed_queries 只算 failed/budget_exceeded，不全面描述 no_results／budget_reserved／省略。
5. returned_chunks 可跨查詢重複，沒有 relevance 分母、Recall@k、nDCG、每維度 evidence sufficiency；Audit 沒選來源造成的空 coverage 也應單獨分類。
6. 沒有正式成本費率、重複執行變異、配對統計與信賴區間、每情境／每藥／每維度分層、穩健性評估。缺少完整事前註冊的比較條件與共同外部 scorer。
7. completion 門檻跨模式不同；clinical utility 更需要獨立使用者研究，不能從人工選藥次數直接推算。

依據：[指標累計](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/benchmark.py:29>)、[指標輸出與 N/A](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/benchmark.py:87>)、[agent-led presentation flag](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:544>)。

## 8. Phase 1 — Project Handover & Reproducibility

**優先級最高；先做低風險基礎，不改演算法。**

具體工作：

1. 將本次三份文件、固定 commit／lock／handoff hashes 與本機驗證證據整理成 manifest。分開 tracked source、ignored runtime、工具安裝與機密設定；不提交 runtime／API key／病人來源。
2. 在新的隔離 DB 重建 handoff，驗證 28 cases／95 revisions／24 docs、agent-complete v4/18 AST。記錄 import ID mapping，不能因 doc_id 隨機不同就判重現失敗。
3. 執行現有 pytest、Vitest、build，保存本機首份報告。把既有失敗與新增回歸分開。
4. 更新過時 Playwright 測試：六 Agent、Synthesis 新結構、Mock pending 與醫師清單分離、審閱保存；不降低來源驗證要求。補足本機 npx／瀏覽器安裝入口文件或工具。
5. 以獨立操作手冊讓另一位接手者從乾淨環境重建；runtime 啟停腳本目前 ignored，未來應另設可版本控制且不含機器私有路徑的 bootstrap／launcher。
6. 建立 backup/restore 演練（新位置）：一致性 SQLite backup、文件 originals、catalog、manifest、Run／Review 分別保存。不要拿舊主 DB 做破壞性測試。

需修改／新增：文件、`frontend/tests/workflow.spec.ts`、測試／bootstrap 腳本與未來 CI；產物在獨立 runtime 報告目錄。若加 CI，先以 lexical + fake/mock 固定離線回歸，不讓 CI 取得付費 key。

預期交付：環境 manifest、首份完整測試報告、修正後 E2E、可重建流程、備份還原報告、已知失敗清單。上述是未來交付，不是本次已新增內容。

完成條件：另一位工程師不用聊天記錄即可重建、啟停、讀回 Run/Review；測試 exit code／資料 counts 有證據；所有失敗都有明確歸因與阻擋政策；未修改原始來源。單有歷史 396/68 passed 不算完成。

下一階段依賴：沒有穩定版本與測試環境，Gold scorer 的差異無法和環境漂移區分；Phase 2 可先寫標註規範，但正式批次評估需通過此門檻。

## 9. Phase 2 — Evaluation Framework

**先定義答案與共同評分器，再花模型預算。**

具體工作：

1. 先定任務、主要終點與分母：Case／Drug／Dimension／Claim／Query。對 abstention、未測、資料不足、格式失敗、上下文省略各有獨立標籤；不把不確定一律當錯，也不當對。
2. 依第 6 節建立 pilot Gold 與標註規範；雙盲審、裁決與 agreement；固定 group split，開發時不看 held-out 答案。
3. 新增離線 evaluator，讀保存 Run／API export／Gold，不 import app.main、不修改 Run、不呼叫模型；對四模式用共同可觀察欄位映射，保留 missing/NA，不能替缺少的 claims 補答案。
4. 新增 retrieval relevance dataset 與 ranking evaluator；先用固定 corpus/chunk hashes 跑 lexical。跨切段實驗用來源位置／文字 span 作 GT 對照，避免 chunk_id 改了就失效。
5. 新增 experiment manifest：commit、dirty diff hash、runtime/lock、case revision/hash、corpus/derivation、query／retrieval設定、模型精確識別與角色覆寫、Prompt/schema hash、calls/token/time、cache policy、run IDs、scorer/Gold版本。只記 key 是否存在，不記 key。
6. 建立兩條比較協定：完整系統比較，以及固定 facts/evidence/validator 的受控比較；預先記錄重複次數、停止規則、資源預算。Live 執行須另有授權，先以保存／合成回覆驗證 scorer。

建議新增模組（路徑是提案，尚不存在）：`backend/app/evaluation/`（獨立 scorer、schema、Run adapter）、`backend/scripts/evaluate_saved_runs.py`、受控 Gold/manifest 儲存區、對應 `backend/tests/test_evaluation_*.py`。現有 `workflow/benchmark.py` 保留為流程摘要，未來只追加版本化外部評分，不改歷史摘要語意。

| 建議指標（尚未實作） | 定義要點 |
| --- | --- |
| AST source accuracy／link accuracy | 每藥與選定類別 GT 對照；未知／未測／衝突單列 |
| Retrieval Recall@k／nDCG@k | 只對有 relevance Gold 的 query 計算；primary hits 和含鄰段結果分開 |
| Claim support precision／coverage | 已確認正確支持的聲明／提出聲明；另報覆蓋了多少必要聲明，避免全不回答取巧 |
| Risk dimension macro-F1 | 五維度分開，標註可接受狀態與不足資料；不把多藥列視為獨立病人 |
| Audit false acceptance／rejection | 對人工判定真假聲明及充分來源情境；同報 unsure 比例 |
| Selective risk／coverage | 有回答部分的錯誤率與回答覆蓋率一起報；不強迫沒有 confidence 的模型產生假機率 |
| Operational reliability | first-pass schema、repair成功、未完成列、timeout、截斷、省略、calls與usage完整性 |
| 全流程 latency／cost | 包含檢索預計算；cold/warm分開，p50/p95；沒有usage／費率時保留unknown，不填0 |

統計單位以病例或來源群組作配對／bootstrap；同病例 18 種藥高度相關，不能當 18 位獨立病人。合適檢定與樣本量由 pilot 的終點／變異決定，不預先捏造顯著改善門檻。

完成條件：scorer 對手算小樣本與故意錯誤案例一致；零分母／缺標註／部分輸出有測試；Gold來源可追溯且有裁決；同一保存 Run 重評完全一致；完成一份無 Live 呼叫的 pilot 報告。不得把 Mock 固定輸出當真實能力評估樣本。

下一階段依賴：Phase 3 的失敗分類與比例必須來自這套版本化分母／Gold；否則只能做個案描述。

## 10. Phase 3 — Failure Analysis

**先量測在哪裡失敗，再決定改哪裡。**

具體工作：

1. 從保存 Run 建立 case → drug → dimension → query → selected source → claim → audit → final decision 的 trace join；保留不存在的關聯，不人工補成成功鏈。
2. 建立互斥主因＋可多選副因的 taxonomy：來源未提供／資料不足、查詢路由、排名、切段／表格、context省略、無引用／錯來源、AST連結、格式／截斷、timeout／repair、整合誤用、Audit誤放／誤擋、顯示／指標誤分類。
3. 先用本次 Mock 驗證 trace join 和分類，不把 Mock 的固定 unknown 計成 Live 醫療錯誤。再用可取得且有明確來源的保存 Live Run 做人工核對；不假設舊文件提及的 Live Run 已隨 Git 交付。
4. 建立 source-sufficient 與 source-insufficient 切片，區分 RAG 沒找到、Agent 沒選、Audit 沒收到；將 Audit 空引用與查詢失敗分開。
5. 用固定回覆／證據的離線 replay 做故障定位和回歸。Replay 驗證傳遞／validator，不證明重新生成會改善。需要新的 Live pilot 時另定授權與資源上限。
6. 依 Gold 嚴重性、發生率、影響病例群及修復風險排序；每個假說要有反例與可否證條件。

需新增／修改：evaluation 的 trace/taxonomy/report adapter；必要時 additive telemetry 與分類，新的離線診斷腳本；以現有 `replay_agent_context.py`、retrievals、attempts、coverage 為起點。先不調 Prompt／生成算法。

交付：來源可回查的錯誤 atlas、逐維度 confusion table、關鍵瓶頸 Pareto 圖、每類代表 Run/claim/source、建議修復與預估風險。明列 observed／inferred／unknown，不靠系統 Audit 自評當正確答案。

完成條件：優先失敗都能定位至保存輸入／輸出／來源；至少有人工複核與分類一致性；可區分缺證據和模型誤解；每個 Phase 4 實驗都有測量過的動機與對應 regression fixture。

下一階段依賴：Phase 4 只優先改善已證實的高影響瓶頸；沒有證據的優化先列候選假說。

## 11. Phase 4 — Multi-Agent Improvement & Ablation Study

依前階段實測重新排序；下面是初始的風險順序，並非宣稱必然有效。

| 順序／風險 | 工作與可能模組 | 實驗與交付 |
| --- | --- | --- |
| 1／較低 | RAG 排名、標題／風險專節路由、query variants；`rag/service.py` 與查詢組裝 | 固定 corpus／Gold，比較 lexical Baseline、單一排名變更；先看 Recall/nDCG，再看下游；不先換整個向量框架 |
| 2／中 | Context 與引用覆蓋；`input_context.py`、`audit_context.py`、selection telemetry | 固定查詢／回覆，量測來源保留與遺漏；再評估真生成。不能用縮短輸入換取漏掉關鍵風險而只報成功率 |
| 3／中 | Wire／輸出修復、逐藥輸出長度與budget；`runtime_led.py`、`partial_agents.py`、`time_budget.py` | 固定模型與Prompt內容，分開測schema通過、截斷、repair、成本；保持後續角色預算與有效列 |
| 4／較高 | 角色分工／整合／Audit Prompt、可選每角色模型 | 做可比較的分工、Audit與資訊範圍 ablation；所有設定經共同外部 scorer，不以自己gate放行率作主指標 |

必要的 Ablation 設計（計畫）：

- **Single vs Multi**：固定原病例與同一 evidence pack，使用相同模型與外部 scorer；另報不限資源與資源接近兩種結果。現行 four-mode summary 不直接當受控 ablation。
- **Audit on/off**：先離線比較同一 Synthesis 草稿被外部 Gold 評分的表現及 Audit 的增益；無 Audit 僅在研究隔離流程觀察，不能去掉產品閘門後拿來操作臨床流程。
- **角色貢獻**：移除／合併 AST、Evidence 或 Clinical 的報告，其他資訊與資源條件明確固定；若任務定義被改變，另列不可直接配對的設定，不把「少資料」錯稱「無角色效果」。
- **Retrieval**：lexical／排名改善／embedding，先固定 corpus、cutting、query，再單獨變更檢索器。Embedding 權重／服務／warm cache納入manifest，另報索引建立成本。
- **Context budget**：比較原預算與候選選取法；固定來源身份與 Gold span，報 omitted、五維度覆蓋與下游影響。
- **模型相關錯誤**：同模型 Audit vs 不同模型 Audit 的實驗，只有在已有錯誤重疊證據、預算與授權時才進行；不能預設較多模型必然改善。

需要修改／新增：以可選且版本化的 experiment 配置接入 workflow/RAG/validator，不改既有 Baseline 預設；新增 experiment runner、結果 adapter、統計報告與 ablation tests。所有實驗寫新 DB／新 Run，保留 baseline commit、Gold與Prompt版本，任何 Prompt 修改均有新版本與 hash。

交付：事前實驗表、成對 Run manifest、各設定品質／coverage／可靠性／latency／cost 表、病例分層與信賴區間、失敗案例及負結果、是否回收進產品的決策紀錄。

完成條件：改善在 held-out 的預先定義主指標上可重現，且來源核對與安全不變量回歸通過；若樣本不足只報探索性結果，不宣稱有效。效益需與成本、拒答、錯誤放行一同報告；沒有改善也應完整保存，不能只挑成功案例。

## 12. 最先做的三件事

1. **完成本機可重複軟體 Baseline**：先跑並保存 pytest／Vitest／build，再修正已確認過時的 Playwright 斷言，隔離驗證六節點、保存／重讀與候選語意。
2. **建立小型人工 Gold 與離線共同 scorer**：先讓「來源類別、檢索相關性、聲明支持、風險與拒答」可被獨立評分；鎖定病例群組與文件版本。
3. **用保存 trace 做 RAG→引用→Audit 的逐維度 failure analysis**：本次已看到風險查詢命中適應症及空引用分類問題；先量化普遍性，再決定排名、context 或 Agent 哪一層需要實驗改善。

第一項解除環境／測試不確定性，第二項建立研究判準，第三項才為改進提供證據。這三項完成前，不以擴增 Agent、換模型或提高候選數作為主要開發方向。
