# Evaluation Framework Design

日期：2026-10-26；核心 HEAD：`1ad2648a349c28989c9fa3d41cd37bf56a40f0fd`；workflow：`agent-led-1.6.0`。工程 Baseline 包含未提交的三個測試修正，實測 Backend 396／Frontend 68／Playwright 8 passed，Backend statement coverage 92.28%；詳見 `TEST_BASELINE_REPORT.md`。這些數字不是模型品質分數。

本文件只做資料盤點、評估協定與實作設計。沒有建立 evaluator 程式、Gold 資料檔或臨床答案，沒有重跑分析、測試、服務或真實 API，也沒有修改病例、Run、Prompt、設定及既有文件。以下「已核實」來自交接檔與唯讀 DB；「設計」均尚未實作。連結行號固定於現行程式；資料同時提供 revision 與 JSON 路徑，避免只按檔名猜測情境。

## 1. Evaluation Readiness Audit

### 1.1 盤點範圍與資料一致性

- `data/handoff/manifest.json` 的 28 個 case 檔都是 **revision history array**，不是單一 Case JSON；總共 95 筆修訂。本盤點逐檔讀取最高 revision，沒有把所有修訂當獨立病例。
- 與日常 `data/runtime/mock-check/prototype.db` 的 28 筆 current case 比對：依現行 Case Schema 補齊省略的 null/default 後，**28／28 一致**。這是格式正規化比對，不是替病例作醫療判讀。
- 28 例皆保留同一來源檔 SHA-256：`76099ebbe1aca384dd4a83cd9e9cdbed1b21bf86294b1a54485cc1e66e453fe5`；全部 `source_record_id` 為 null。沒有原始個案識別鍵可確認病人／就診／培養之間的獨立性。
- 現有公開材料含來源 AST、人工臨床情境與來源檔識別；不含可重新驗證全部原始 CSV 個案的資料。因此可核實「交接資產內的記載」，不能宣稱已核實生物學真值或原始檢驗正確性。

依據：[handoff manifest](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/manifest.json:1>)、[handoff 說明](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/README.md:1>)、[Case Schema](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/schemas/case.py:156>)。

### 1.2 28 個病例實際涵蓋什麼

下列是資料內容對應的**可測功能**，不是已有專家答案。AST 數為列數；例如 conflict 的 19 列只有 18 種藥。G01–G09 是後述保守防洩漏分組提案，不是已證實的九位病人。E. coli＝ESCHERICHIA COLI；S. aureus＝STAPHYLOCOCCUS AUREUS。

| case_id | 最新 revision | AST 列數 | 實際情境／可測功能 | 分組 |
| --- | ---: | ---: | --- | --- |
| agent-complete | 4 | 18 | E. coli／URINE，下泌尿道情境；來源類別、完整人工 facts、逐藥分析與保存 | G01 |
| agent-ast-conflict | 4 | 19 | 同基礎病例，追加 amoxicillin_clavulanate 列，只翻轉 reported_sir；測跨欄位矛盾識別 | G01 |
| agent-allergy | 4 | 18 | nitrofurantoin 的 anaphylaxis／severe 記載；verification_status=not_recorded；測過敏事實與來源核對 | G01 |
| agent-renal | 4 | 18 | 人工 creatinine 2.6、eGFR 22、CrCl 25.9；測數值／單位保留與風險文件使用 | G01 |
| agent-evidence-mismatch | 4 | 18 | policy_refs 限定 agent-unrelated-evidence；測負向文件與不支持來源處理 | G01 |
| agent-interaction | 4 | 18 | tizanidine status=active、history=reviewed_list；測實際用藥欄位與 interaction 檢索 | G01 |
| agent-missing | 4 | 18 | infection_site=null、renal 欄位空、過敏 unknown；測缺漏／不確定傳遞 | G01 |
| agent-rapid-only | 3 | 0 | 同基礎情境但無 AST、報告 preliminary，保留 MALDI-TOF；測未測不得推定敏感 | G01 |
| agent-allergy-pair-unverified | 2 | 18 | amoxicillin 標籤未確認，反應／嚴重度未提供；測未知狀態保留 | G01 |
| agent-allergy-pair-severe | 2 | 18 | amoxicillin 嚴重反應，confirmed 及 reviewer 是人工情境設定；測不同藥名／複方的來源界線 | G01 |
| agent-allergy-pair-intolerance | 2 | 18 | amoxicillin nausea only、unverified；測不將紀錄直接變成免疫性過敏或解除標籤 | G01 |
| agent-allergy-pair-conflicting | 2 | 18 | amoxicillin 嚴重反應與後續排除紀錄矛盾；測衝突與待核對資訊 | G01 |
| api-demo-source-ast-001 | 5 | 17 | S. aureus／BLOOD，血流感染人工情境；API demo、修訂、來源 AST；AST 與 cohort-012 完全相同 | G09 |
| cohort-76099ebb-001 | 4 | 18 | E. coli／URINE；S/I/R/缺失均有，缺完整病史／用藥完整性；測來源型 baseline | G01 |
| cohort-76099ebb-001-allergy | 4 | 18 | 與 001 同 AST；同時加入 amoxicillin_clavulanate 蕁麻疹及 eGFR 35 | G01 |
| cohort-76099ebb-002 | 3 | 15 | S. aureus／RESPIRATORY_TRACT，pneumonia；13 S、2 類別缺失 | G02 |
| cohort-76099ebb-002-allergy | 3 | 15 | 與 002 同 AST；同時加入 clindamycin 蕁麻疹及 eGFR 35 | G02 |
| cohort-76099ebb-003 | 3 | 18 | E. coli／URINE；16 S、1 R、1 類別缺失 | G03 |
| cohort-76099ebb-003-allergy | 4 | 18 | 與 003 同 AST；同時加入 amoxicillin_clavulanate 蕁麻疹及 eGFR 35 | G03 |
| cohort-76099ebb-004 | 3 | 18 | E. coli／URINE；AST 與 003 完全相同，不當成新獨立藥敏樣本 | G03 |
| cohort-76099ebb-005 | 3 | 27 | E. coli／URINE；較大藥物 panel，24 S、1 I、2 類別缺失，測列數／輸出負載 | G04 |
| cohort-76099ebb-006 | 4 | 12 | S. aureus／RESPIRATORY_TRACT；11 S、1 類別缺失 | G05 |
| cohort-76099ebb-007 | 3 | 12 | 與 006 相同 AST；測重複指紋辨識，不當成獨立證據 | G05 |
| cohort-76099ebb-008 | 3 | 15 | S. aureus／RESPIRATORY_TRACT；8 S、5 R、2 類別缺失，測非 S 保留 | G06 |
| cohort-76099ebb-009 | 3 | 17 | S. aureus／BLOOD；9 S、4 R、1 I、3 類別缺失 | G07 |
| cohort-76099ebb-010 | 3 | 17 | 與 009 相同 AST；不可藉不同 case_id 增加有效樣本數 | G07 |
| cohort-76099ebb-011 | 4 | 18 | E. coli／BLOOD；12 S、3 R、1 I、2 類別缺失；不同感染部位的來源處理 | G08 |
| cohort-76099ebb-012 | 4 | 17 | S. aureus／BLOOD；12 S、1 R、1 I、3 類別缺失；與 API demo 同 AST | G09 |

cohort 的用藥多為 `status="current (simulated)"`，不是現行 Clinical query 組裝判斷的精確 `active` 值；`medication_history_status` 多未提供。這是輸入契約差異，不能預設所有病例都有同等完整的用藥資訊。三個 `-allergy` 配對**同時變動腎功能**，不是單因素 allergy ablation。

依據：[cohort 來源建構](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/adapters/microbiology.py:53>)、[配對變更](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/adapters/microbiology.py:113>)、[Agent 情境衍生](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/scripts/build_agent_cases.py:59>)、[四個過敏變體](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/scripts/build_allergy_cases.py:8>)。每列可由 `data/handoff/cases/<case_id>.json` 的最高 revision 自行核對。

### 1.3 同源性與防洩漏分組

已做兩種唯讀比對：完整 `ast_results` JSON 有 12 個不同值；再排除來源描述 prose、按以下欄位排序比較，得到 **11 個不同 AST 指紋**（其中包含空 AST 與追加矛盾列）：

```text
drug_code, mic, comparator, unit, method, standard, standard_version,
interpretation_basis, reported_sir, source_phenotype, clsi_2022_phenotype,
raw_measurement
```

排序只用於同源性比對，不會改 Run 內 AST index。Agent 基礎的 18 列與 cohort-001 的上述欄位相同，完整 JSON 的主要差異是 source 描述。另已確認完全相同的組合有 003/004、006/007、009/010、API demo/012；三個 cohort allergy 配對保留其 base AST。

防洩漏策略：以「明確 derivation 邊」和「非空 AST 指紋相同邊」建立連通分量。所有 revision、clinical variants、追加矛盾列及刪除 AST 的衍生例都跟 base 綁在一起；**不能用空 AST 相等把不相關病例合併**。提案分組為：

| group | 成員 | 分組證據 |
| --- | --- | --- |
| G01 | 全部 12 個 agent-*；cohort-001、001-allergy，共 14 例 | Agent builder 的 deepcopy／配對 provenance；再保守合併與 cohort-001 相同的觀察指紋 |
| G02 | cohort-002、002-allergy | 明確配對衍生 |
| G03 | cohort-003、003-allergy、004 | 明確配對＋非空相同 AST |
| G04 | cohort-005 | 暫無已確認的其他合併邊 |
| G05 | cohort-006、007 | 非空相同 AST |
| G06 | cohort-008 | 暫無已確認的其他合併邊 |
| G07 | cohort-009、010 | 非空相同 AST |
| G08 | cohort-011 | 暫無已確認的其他合併邊 |
| G09 | cohort-012、api-demo-source-ast-001 | 完全相同 AST |

這是 **9 個保守 leakage clusters 的提案**，不是九個獨立病人的證明。相同指紋可能來自不同人；沒有原始 group key 時寧可合併避免虛假泛化。相同來源檔不等於同一人；不同指紋也不能證明不同人。Gold metadata 要分別保存 `source_dataset_group`、`source_case_group`、`leakage_group`、`grouping_basis` 及 `lineage_status`，不可將推定 lineage 包裝成確定個案身分。

**五個 Pilot 全屬 G01**，且已經用來開發、除錯與討論，應定位為 development/pilot，不得事後聲稱是盲測 held-out。不能拆成五個獨立病人做顯著性檢定；95 revisions 或 18 drugs 也不能當獨立 n。這批資料可研究同源情境的功能敏感性，泛化研究仍需要未參與調參、來源可分組的新病例。

### 1.4 五個 Pilot 的實際符合程度

| 病例 | 已核實內容 | 可直接核對 | 不可直接當 Gold 的部分 |
| --- | --- | --- | --- |
| agent-complete v4 | 18 AST；15 selected Susceptible、1 Intermediate、1 Resistant、1 缺失；45歲女性、60kg、eGFR 92、CrCl 84.1、known_none、reviewed_none | 原始類別／欄位／數值、缺失與來源連結 | 名稱 complete 不證明臨床充分或任何藥適用 |
| agent-ast-conflict v4 | AST[0] amoxicillin_clavulanate reported_sir=S；追加 AST[18] 為 R；**兩列 source_phenotype 與 clsi_2022_phenotype 仍都是 Susceptible**，interpretation_basis 都是 CLSI_2022_pheno | reported_sir 跨列矛盾、追加列為模擬、選定欄位 S/S | 不能直接把本藥 classification Gold 寫成 resistant 或 conflicting；先制定並獨立裁決「選定來源類別」與「跨欄位矛盾」兩項任務的政策 |
| agent-allergy v4 | nitrofurantoin／anaphylaxis／severe；verification_status=not_recorded | 病例有此嚴重反應記載，並非 known_none；來源為人工情境 | 藥物適用性、交叉過敏及其他藥物風險須由專家判斷；不能當真實專科確診 |
| agent-renal v4 | 人工 creatinine=2.6 mg/dL、eGFR=22 mL/min/1.73m2、CrCl=25.9 mL/min、dialysis=none | 值／單位／計算說明保留；不得混同 eGFR 與 CrCl | 各藥風險、限制與 next_action 需閱讀版本化標示並由專家核對；不能僅靠數字寫 avoid Gold |
| agent-evidence-mismatch v4 | policy_refs=[agent-unrelated-evidence]；manifest 對應 `Unrelated evidence test` v1、test_negative_control | 指定檔只談實驗室設備儲存，沒有抗菌治療建議 | 不應憑名稱預設某次 retrieval 一定回空；需實際 Run 紀錄。文件相關性可人工閱讀標註，但沒有獨立臨床候選 Gold |

資料連結：[complete 最新 revision](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/cases/agent-complete.json:2511>)、[conflict](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/cases/agent-ast-conflict.json:2583>)、[allergy](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/cases/agent-allergy.json:2536>)、[renal](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/cases/agent-renal.json:2511>)、[mismatch](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/cases/agent-evidence-mismatch.json:2517>)、[負向控制原文](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/data/handoff/references/unrelated.md:1>)。

目前日常 Mock DB 只有 agent-complete 的保存 Run `51905060-412e-4e04-99f3-c9a1bbbbc596`；其他四個 Pilot 尚無該 DB 中可評估的 Run。Regression 測試 DB 的 synthetic fixture Run 是另一批資料，不可冒充 Pilot 結果。本次沒有為補齊資料而重新執行分析。

### 1.5 三種標註權限與 Ground Truth 的上限

| 層級 | 可建立內容 | 不代表 |
| --- | --- | --- |
| A：source-verifiable | revision/hash、AST 選定欄位值、missing/duplicate/矛盾旗標、fact_refs 是否指向正確值、引文是否位於指定片段、人工情境中明寫的過敏／用藥狀態 | 原始檢驗準確、真實病人病史或藥物臨床適用 |
| B：人工文件閱讀 | query relevance、版本化 evidence span、主題／產品／族群範圍、非醫療推論的字面支持或負向控制；讀者需有足夠文件理解能力 | 所有涉及醫學解釋的支持性均能由一般工程師裁決 |
| C：合適醫療專家 | infection applicability、過敏與交互作用含義、腎風險及處置、醫學 claim entailment、unsafe 標籤、可接受最終決策及條件 | 系統 Audit／醫師操作清單可以自動替代專家 Gold |

涉及醫學含義的 B 標註必須升級 C。A 層可由獨立 source extraction 協定產生並人工抽查，但不能呼叫 RuleEngine／AST Agent／Audit 產生答案後再評它自己。`confirmed` 或 reviewer 字串若來自人工情境，只是輸入事實。現有 expectations 是工程測試預期，不是臨床 Gold；`[MOCK TEST]` Review 也不得使用為臨床標準。

### 1.6 保存 Run 是否足夠？

**足夠做部分離線評估，但不足以完整重建所有研究條件。**

| 資訊 | 現行保存狀況／缺口 |
| --- | --- |
| 病例／版本 | case_snapshot、case_revision、mode/provider、versions；足以鎖定本次輸入，但評估仍應額外計算 case/run hash |
| 各 Agent | input/output、prompt_version/hash、input/output hash、attempts、時間、validation_details、unresolved_drugs；output 多已經過驗證／正規化，**不是所有原始模型字串** |
| Retrieval | agent-led 有 query/stage/drug/dimension、chunk_ids、primary_ids、status/method/elapsed；未完整保存 requested_k、全候選排名與全部未返回片段 |
| 來源 | evidence_snapshots 有原文、location、content_hash、版本、population、source_document_id/derivation；返回片段可離線核對，但完整 relevance 分母仍需固定 corpus manifest |
| Context selection | evidence_selection/coverage 與 node input 可區分取回、選入、未選來源；Synthesis 只附已引用 metadata，Audit 只收指定原文 |
| Claims／結果 | Synthesis claims、Audit checks、drug_assessments、output.candidates/pending、physician_candidates；足以對**可觀察輸出**評分，不能將後處理結果當未過濾模型草稿 |
| 用量／時間 | attempts.usage、finish_reason、output_token_limit、run.elapsed_ms；可能 null，不能補成 0；Live 可有 alias/span 索引，但本次 Mock 沒有真實 token |
| 其他三模式 | 通常沒有同格式逐 Agent／逐 query log；evidence_retrieval node 保存狀態／count／population，未保存完整 query/rank/k；只能標 partial/legacy capability，不得捏造排名 |
| 公開匯出 | API 會移除 quarantined raw_baseline payload，舊版本可隱藏節點內容、讀取時補 physician 清單；需標記 public_export 或 internal_snapshot，並指定 scoring target |
| 重現所缺 | 精確 Prompt 全文／請求參數、模型服務精確版本、seed、完整 corpus/parser/query 設定、price table、run 所用 Git diff、冷暖快取與 Benchmark 預計算計時，未全數自足保存 |

依據：[agent-led retrieval log](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/agent_led.py:286>)、[Live wire 與 hash](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/agents/runtime_led.py:79>)、[baseline retrieval node](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/engine.py:235>)、[baseline Run](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/engine.py:369>)、[公開投影](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/main.py:117>)。

### 1.7 Benchmark 的重用邊界

可重用四模式執行、病例／規則／文件 snapshot、Run 保存與匯出，以及純函式 `benchmark.summarize()` 的**既有工程統計**：狀態、calls、已知 token、elapsed、missing precision/recall（有 eligible seed 標註時）、引用 ID/location、Schema 旗標等。

不能直接作研究 scorer：引用只看 candidates/avoid 的 ref 存不存在，未看語意；Audit verdict 是被評系統輸出；not_configured_ratio 混入 partial；retrieval 數量不是 Recall@k；citation_support_conclusion、appropriateness、expert_agreement、clinical_utility 明列 not_evaluated。現有摘要沒有本文件三層的獨立 Gold 指標、信賴區間或實驗 manifest。

`main._benchmark` 為非 Multi-Agent 預先搜尋後重用 FrozenDocuments，Multi-Agent 則在同一 corpus snapshot 自行逐藥搜尋。Case／corpus 固定有幫助，但來源輸入／計時不同；不得據此直接歸因 Agent 數帶來的效果。建議獨立 evaluation 模組，不把研究標註／scorer 塞入線上 workflow，也不改寫歷史 summary。

依據：[Benchmark 執行](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/main.py:413>)、[現有指標](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/benchmark.py:29>)、[未評項目](</C:/Users/呂宜學/Documents/ChatGPT/multi_agent/backend/app/workflow/benchmark.py:95>)。

## 2. Metrics Contract：共通規則

所有指標須輸出 `metric_version, scoring_target, value, numerator, denominator, n_requested, n_evaluable, n_missing_gold, n_invalid_output, status, reason`。缺資料不是 0；只評了部分標註必須同時報 Gold coverage。方法不產生某角色輸出是 not_applicable，不是模型錯誤。

固定四類主要結果：

- `evaluated`：輸出與 Gold 對齊、可計算；**實際錯誤**是此狀態下的 FP/FN／wrong label，而不是 missing_gold。
- `missing_gold`：對應標註未建立、未審查或不完整，不可拿系統自己補標。
- `not_evaluated`：不適用、未觀察的排名、內容被隔離、方法沒有該 Agent、或 execution failure 沒有語意輸出；保留 reason。
- `invalid_output`：預期應有的完成輸出不符合評估契約、非法值、無法解析的 refs 格式等；與「合法的 unknown/pending」分開。格式可解析但指錯來源的 link 是可評估的 attribution error，不能全部歸為無法評分。

無法解析 Run 檔或 case/corpus/hash 不相容另為 `invalid_input/alignment_error`，整筆不進正常 scorer。診斷可多個；不得靠一個總分遮蓋它們。失敗／非法輸出即使不能作語意評分，也要進工程失敗分母；另報 intent-to-evaluate 的任務成功率／召回下界，避免只留下成功案例。不能將無法辨識的輸出當安全拒答。

公式的集合預設限於版本化、審查完成且與輸入一致的 eligible domain。`0/0 → null`，附 reason；macro 僅平均有定義值並報各自 n。主要研究統計以 source/leakage group 配對，不將相同病例的 drugs、claims、revisions 當獨立樣本。除非預先宣告，禁止把不同層級的分母混算或用 zero_division=0/1 悄悄填值。

Scoring targets 必須分開：`normalized_agent_output`（節點已驗證回覆）、`normalized_synthesis_draft`（Audit 前）、`published_ai_candidates`（最終 AI）、`physician_selection`（人工工作清單，非 AI recommendation）。原始 wire 回覆未保存時不得評為 raw_model_output。人類最後採用與否也不是臨床正確性標籤。

## 3. Level 1：Retrieval Evaluation

### 3.1 單位與排名定義

query key 包含 case/revision/hash、stage、drug_code、dimension、query text/hash、corpus/parser/query-template 版本。先固定合法 corpus 與 scope，不能看到系統漏掉來源後再縮小 Gold 分母。

主指標為 **primary retrieval@k**：`D_q^k` 是 query q 的前 k 個唯一主要命中片段，使用保存的 primary_ids 順序；相鄰 context 不算主要命中。若舊檔沒 primary_ids/排名，不能從 evidence_snapshots 的全域去重順序猜回排名，標 not_evaluated。另報 `with_context` 與 `selected_input` 的 evidence coverage，但不混稱 primary@k。lexical 未明確排序仍可評「當次返回順序」，不能假稱其為 relevance score 排序。

Gold 的檢索單位綁定固定 artifact hash、parser/chunking 版本、locator、text hash；chunk_id 僅為 Run 內對照，不是跨 DB 永久 ID。完全相同 key 去重，重疊但不同片段按凍結協定標註；同源全文／節錄不能當獨立臨床證據。若有可靠原文 span 映射可另報 source-span deduplicated coverage，不能在跨切段實驗中只用舊 chunk_id 比對。

標註至少有 relevant / irrelevant / unjudged。Precision 要有 top-k 回覆的完整判讀；Recall 要有該 corpus 的完整相關集合或明確標為 pooled/incomplete。單一系統取回片段再人工標註，可做局部 precision，不能據此宣稱完整 Recall。

### 3.2 Recall@k

- **目的／層級**：每 query（可聚合到 drug/dimension/Agent/case），衡量可用相關片段是否被取回。
- **公式**：`Recall_q@k = |D_q^k ∩ R_q| / |R_q|`；R_q 為固定 corpus 中獨立標註的所有 relevant 片段。
- **Gold**：B 級文件閱讀；涉及感染適用性與醫療風險時 C 級裁決。標註者須看到適當來源池，而不是只看模型列出的 refs。
- **邊界**：R_q 已確認為空 → not_applicable/null，另評無證據時的正確暫緩；R_q 未知／未標完整 → missing_gold 或只報明確命名的 pool recall。成功查詢回空且 R_q 非空 → 0。k 必須正整數並來自實驗 manifest，不能用返回數反推。失敗查詢另報失敗率及 strict recall 下界，不偽裝成成功檢索。

### 3.3 Precision@k

- **目的／層級**：每 query，衡量前 k 個檢索位置的有用程度。
- **公式**：`Precision_q@k = |D_q^k ∩ R_q| / k`。固定 k；少於 k 個結果的空位置按未命中計。若另報 `P@returned=hits/returned`，必須獨立命名，不能替代 P@k。
- **Gold**：同 Recall；top-k 全部有 relevant/irrelevant 判讀。unjudged 不是 irrelevant，尚有 unjudged 時主 P@k 不計，只報 judged coverage 或具名上下界。
- **邊界**：k=0 屬非法參數；成功返回 0 且 k>0 → 0（前提 Gold 可判讀）。重複同 key 不重複給分；多個正確文件皆可 relevant，不能只容許單一模型剛好引用的文件。

### 3.4 Critical Evidence Missing Rate（CEMR）

- **目的／層級**：query×drug×dimension 的必要證據需求，區分「有片段」和「有足夠關鍵證據」。
- **Gold**：專家／合格讀者預先列必要 evidence requirements `C_q`；每項有 `acceptable_bundles`。一個 bundle 內來源需全部具備（AND），不同 bundle 是替代方案（OR），避免只找到一半風險條件就算完成。
- **公式**：令 V(D) 為 D 的片段在正確文件版本上完整涵蓋的 Gold span IDs；`sat(g,D)=1` 當且僅當存在完整 bundle B，使 `B ⊆ V(D)`。`CEMR@k = Σ_q Σ_(g∈C_q) [1-sat(g,D_q^k)] / Σ_q |C_q|`。以需求數為分母，不是查詢數；另報 query-any-critical-missing 比例但不得混用名稱。
- **變體**：同一要求分別評 `retrieved@k`、`with_context`、`selected_input`；可定位檢索失敗或 context 遺漏。條件充分的 bundle 可包含多個 span，查找結果需完整涵蓋而不是字面重疊一小段。
- **邊界**：沒有 critical 需求 → null/not_applicable；未完成 critical 標註 → missing_gold。若需求來源根本不在允許 corpus，task-level CEMR 計 missing，原因標 `corpus_absent`，另給只針對 corpus-available 需求的 retrieval 指標；不能把資料包缺源全算排名器錯誤，亦不能刪掉這項系統限制。

## 4. Level 2：Agent-level Evaluation

### 4.1 AST Classification Accuracy

- **目的／單位**：case×drug，驗證對指定來源類別的忠實分類；不是用藥適當性。
- **公式**：對有完成 Gold 的單位 T，`Accuracy = Σ_(i∈T) 1[pred_i ∈ acceptable_labels_i] / |T|`。通常 acceptable_labels 是單一值；多答案必須在看系統結果前由政策裁決，不能臨時放寬。
- **Gold**：A 級原欄位＋獨立規格；記 interpretation_basis、每列 JSON pointer、原值、同藥重複／矛盾。分類 domain 包含 susceptible/intermediate/resistant/unknown/conflicting；未測 availability 另外記錄。AST Agent 不接受 untested 類別，無 AST 的未被指派藥物不當成遺漏錯誤。
- **邊界**：source 選定欄位有 S，合法輸出 unknown 是來源分類的未命中／abstention，不是 unsafe recommendation。source 本來缺類別時，unknown 可以正確。agent-ast-conflict 的 S/S 選定來源與 S/R reported 矛盾要先裁決政策，不能自動設 conflicting Gold。未完成政策者標 missing_gold，不拿 validator.source_validation 當答案。
- **輔助**：已知類別 accuracy、含 unknown 的 overall accuracy、各類 confusion matrix、abstention、輸出完整率分開。完整輸出缺預期藥列是 invalid_output；另在 strict task accuracy 分母中算未成功，不隱藏失敗。

### 4.2 Source Attribution Accuracy

- **目的／單位**：每條 claim→fact 或 claim→document/span attribution link；識別引用到錯藥、錯欄位、錯版本或不支持該 claim 的來源。
- **公式**：`AttributionAccuracy = 正確 attribution links / 有完整 attribution Gold 的所有預測 links`。正確＝落在 Gold 的可接受 source/span 關係，且符合 claim、drug、version 與 scope；多條重複同 link 只算一次。
- **Gold**：fact path／值可用 A；document 適切性用 B/C。機械的 `reference_resolution_rate=可定位links/全部links` 另列，不能冒充本指標。還需報 required-claim attribution coverage，防止完全不引用反而看似優秀。
- **邊界**：空 links → accuracy null，但有必要引用的 claim 之 coverage 為 0；不存在／錯版本的 link 是已知錯誤，不是 missing_gold。來源存在但語意沒標 → missing_gold。不同正確來源以預先定義的 alternatives/bundles 接受；不從 Audit supported 倒推正確引用。

### 4.3 Claim Support Precision / Recall / F1

**主定義採分類任務，避免把「已生成聲明裡有幾個正確」誤稱 Recall。** 先凍結可評估的 atomic proposition inventory U，含 Gold supported 與不支持的對照命題、適用的 facts/evidence pack、等價表述及明確 required/optional 範圍。每種報告需以版本化規則／盲審對齊命題；不是把五個 dimension 名稱當五個已支持命題。

- **目的／單位**：逐 Agent×case×drug×atomic proposition；判斷 Agent 將哪些命題宣告為已支持。Evidence/Audit 可使用明確 status；Synthesis 的肯定句需獨立語意對齊，不能只用關鍵字或讓 LLM 自評。
- **定義**：G 為同一 eligible inventory 中 Gold supported 的集合；A 為 Agent 判定 supported／實際肯定主張的集合。`TP=|A∩G|`、`FP=|A\G|`、`FN=|G\A|`。
- **公式**：`P=TP/(TP+FP)`；`R=TP/(TP+FN)`；`F1=2TP/(2TP+FP+FN)`。三者必須使用同一 inventory／同一 TP，不能把所有自由生成聲明的 precision 與必要命題 coverage 湊成 F1。
- **Gold**：每命題由 B/C 標 supported/contradicted/insufficient_evidence；只有審查完成且適用的命題進 domain。Gold 包含模型沒有說出的必要命題，不能只標系統已產生的聲明。
- **自由生成限制**：若只取得當次輸出的人工支持判讀，可報 `generated_claim_support_precision`，但不能估真正召回，主 Recall/F1 為 not_evaluated:incomplete_claim_inventory。inventory 外的新主張須盲審並版本化對齊，不能默認錯誤、也不能忽略其風險。
- **邊界**：無肯定預測時 P=null；若 G 非空則 R=0，F1 依直接公式為 0；TP=FP=FN=0 時 F1=null。完全沒有 Gold positives，R=null，不填 100%。合法 uncertain 對 Gold supported 是 FN／拒答，另報拒答率；對 unsupported 不是 FP。Mock「未核對」不是五個臨床肯定句；缺完整命題對照時不能硬算五個錯誤。
- **多答案**：同一意義的合法表述／替代引用先映射同一 proposition，最多得一次分；optional 命題另列 precision，不混入主 required inventory 的召回分母。

### 4.4 Audit Error Detection Rate

- **目的／單位**：對固定、獨立標註的錯誤肯定聲明，量測 Audit 是否真正識別錯誤，而非一律回 uncertain。
- **公式**：E 為 Gold contradicted 或缺必要支持的肯定主張；`StrictDetection = |{e∈E: audit明確unsupported}|/|E|`。逐原子 claim 對齊，不能拿整藥 verdict 替代每個聲明。
- **Gold**：B/C 盲審原聲明、病例與確切提供的證據；可加入預先人工設計的錯藥／錯族群／錯來源／錯 AST 等受控錯誤。Fault injection 不是臨床真實病例，須獨立標示。
- **必報對照**：`conservative_withholding = unsupported或uncertain / |E|`；false acceptance=`錯誤被supported/|E|`；false rejection=`正確Gold被unsupported/正確Gold數`；uncertain rate 另報。避免全 uncertain 取得看似完美的偵錯成績。
- **邊界**：E 空 → null/not_applicable；沒有獨立 Gold → missing_gold；只有整藥 Audit、沒有可對齊 claim checks → granular 指標 not_evaluated。從 normalized Audit output 評分會包含程式驗證效果，不能稱純 LLM Audit 效果；原始模型判斷缺失時無法把兩者分離。

### 4.5 Unsupported Claim Rate

- **目的／單位**：所有可觀察的實質肯定聲明；衡量未被來源支持的主張負擔。
- **公式**：`UCR = (Gold contradicted + Gold insufficient_evidence 的肯定聲明數) / 已完成Gold判讀的全部實質肯定聲明數`。
- **Gold**：B/C 對 statement＋case＋實際可用證據獨立判讀，含 qualifier 與 next_action，不以引文存在或 Audit verdict 取代。
- **邊界**：沒有實質肯定聲明 → null，不填 0% 並宣稱最佳；同時報 assertion coverage/abstention。未標註的主張不自動視為錯或對，必報 judged fraction，必要時上下界。insufficient_evidence 是缺支持，不等於醫學上必然為假。normalized specialist、Synthesis draft、final published 的 UCR 分開；原始回覆被過濾的部分未保存就不可估。

## 5. Level 3：System-level Evaluation

### 5.1 Candidate Precision / Recall

- **目的／單位**：case×drug 的**可供審閱選項**，不是處方、唯一最佳藥或療程評估。
- **預測集合**：P 只取最終 `output.candidates`，並核對與 drug_assessments.reviewable 一致。`physician_candidates`、pending、review_options 或醫師自行加藥均不混入。另可評 Synthesis draft，但要不同 scoring_target。
- **Gold**：C 級在固定 drug universe 中定義可接受選項 G、不可接受／unsafe、insufficient_information，以及條件。可接受多種藥物；這不是要求每位專家挑同一種。條件式適用需核對對應條件，不能只藥名相同就 TP。
- **公式**：`CandidatePrecision=|P∩G|/|P|`；`CandidateRecall=|P∩G|/|G|`，交集須符合 Gold 的條件匹配政策。
- **邊界**：P 空 → Precision=null；G 非空則 Recall=0。G 已裁決為空 → Recall=null；若仍有候選則 Precision=0（在封閉、完整 Gold universe 前提）。G 未標完整 → missing_gold，不以原 AST 的 S 集合替代。
- **多答案／集合**：主 Recall 是可接受選項的覆蓋率，不是最優治療成功率；若研究問題只需一個可接受決策，另用預先標註的 acceptable decision bundles 評「至少一組符合」，不能要求提出所有互斥療法。GT universe 外輸出必須保留；受控封閉任務可算 task FP，但不能自動算臨床 unsafe。

### 5.2 Unsafe Recommendation Rate

- **目的／單位**：最終 AI 肯定候選；量測明確不安全選項是否被發布。
- **公式**：Gold unsafe 集合為 H，`URR=|P∩H|/|P|`，要求 P 中全部候選皆有完成的 unsafe 判讀。另報 `case-level unsafe rate = 至少一個unsafe候選的病例數 / 可完整判讀且有候選的病例數`。
- **Gold**：C 級專家依病例、適用範圍、條件與文件版本裁決。AST 非 S、缺資料、來源不支持、臨床 unsafe 不是同義詞；可另做來源違反 proxy，但不得命名為臨床 URR。
- **邊界**：P 空 → null，不是 0% 安全。部分候選無 unsafe Gold → missing_gold 或具名 partial/上下界，不能把未標部分當安全。pending 和 physician 工作清單不是推薦；必須同時報 CandidateRecall/coverage，避免全拒答看似安全。

### 5.3 Pending / Abstention Rate

- **目的／單位**：固定 case×drug universe U，衡量未形成肯定／否定判斷的比率。
- **公式**：`PendingRate = 有合法最終pending狀態的藥物數 / |U|`；U 由來源去重藥物＋預先指定指引選項構成，不因系統輸出少而縮小。AST 19 列但 18 藥不能用 19 當分母。
- **層級對應**：case-level no-candidate rate 另報；AST unknown、Evidence/Audit uncertain、Clinical unknown 分別作 role abstention rate。`avoid/not_selected` 是結論，不自動當 abstention；review_options 保留其原 pending 屬性另分層。
- **Gold／邊界**：描述率不需臨床 Gold，只需完整合法狀態與預定 U；判斷「拒答是否合理」才需要 C 級 Gold。missing row／failed stage 不是 pending，應報 invalid/missing-output rate；U 空則 null。未知可接受藥品 universe 時，只能報明確命名的 source-drug rate，不冒充完整系統率。

### 5.4 Latency

- **目的／單位**：每次完整執行與每階段，量測可實際使用的時間代價。
- **定義**：同一 monotonic clock 的 `end-to-end latency = 最終保存完成時刻 - 請求開始時刻`；可另列 retrieval、Agent attempts、validation、persist 時間。不要用不同機器的 wall timestamp 相減當精確 latency。
- **來源**：本次 Run.elapsed_ms／node.elapsed_ms／retrievals.elapsed_ms 為已測工程數據；未保存的 queue／precompute 不能事後補造。報 N、median、p95（樣本不足明示）、timeout/失敗分布，cold/warm 分開；成功條件化的 latency 另列，不能刪掉慢失敗。
- **比較限制**：既有 Benchmark 為其他三模式預先搜尋，該時間不完整包含在個別 Run.elapsed_ms；研究需另用外層實驗計時／sidecar 記錄或明確只比已有範圍。本次 Mock 的 255.518ms 不能當 Live latency。

### 5.5 Token Usage / Estimated Cost

- **目的／單位**：每 attempt、Agent、Run；量測資源與品質交換，含失敗、修復與重試。
- **Token 定義**：`T_in=Σ input_tokens_attempt`、`T_out=Σ output_tokens_attempt`；只有資料完整才給完整總數；部分用量只報 known subtotal 與 coverage。run aggregate 與 attempts 不重複相加。
- **Cost 公式**：有 price version 時，`Ĉ = Σ_attempt[(T_uncached_in*r_in + T_cached_in*r_cached + T_out*r_out)/10^6] + C_embedding + 其他已宣告費用`；需 currency、有效日期、精確模型／計費類別與估算政策。本文不提供或猜測任何即時費率。
- **來源**：usage 是量測資料，不是人工 Gold；price table 是外部設定快照，不是模型自報成本。只有 prompt/completion tokens、沒有 cache 明細時不能假裝精確折扣；可報具名無折扣估算或界限。
- **邊界**：null usage／缺費率 → not_evaluated，不填 0。Rule-only 若已確認無生成呼叫，生成 token=0 合理；Mock 根本沒有模型推論，token/cost-quality 比較標 not_applicable。baseline Provider 內部 retry 不一定有每次用量，不能聲稱已計完整成本；本機硬體耗電／GPU 成本不由 token 冒算。

所有品質指標均須另外按 mode、workflow、model、source group、case、drug、dimension、mock/live 分層；Mock 僅用來檢查算式／缺資料狀態，禁止混進真實能力平均。

## 6. Pilot Gold Schema（設計，尚未建立檔案）

### 6.1 組織方式與共同欄位

建議一份 release manifest，加上多個 JSONL record type；也接受單一 JSON 的同名陣列。不是將所有標註塞進一列寬表。每個紀錄有 `schema_version, record_type, record_id, annotation_version`，並引用 manifest 中的 case／corpus／experiment。

| record_type | 必填識別／資料 | 說明 |
| --- | --- | --- |
| case_drug | case_id、revision、case_snapshot_sha256、source_case_group、leakage_group、drug_code、ast_ground_truth、clinical_risk、final_decision | 逐藥來源事實與臨床標註分開 |
| retrieval_query | query_id、case/revision/hash、stage、drug_code（global 可 null）、dimension、query_text/hash、corpus_id、scope、requested_k、ranking_basis、judgments、critical_requirements | 查詢原文與文件相關性；明示 complete/pool/unjudged |
| evidence_span | span_id、artifact_sha256、document_version、parser/text_unit_version、locator、text_unit_sha256、start/end、quote_sha256、source_family_id | 不以本機 doc_id 當跨機器身份；來源版本與 span 精確鎖定 |
| proposition_inventory | task_id、case/drug/dimension、proposition_id、acceptable_paraphrases、required/optional、support_label、acceptable_evidence_bundles、fact_sources | 用於真正的 claim Recall；不由模型輸出自行列真答案 |
| run_claim | run_content_sha256、node_id、drug_code、dimension、claim_index、statement/hash、proposition_binding、support_label、evidence_spans、fact_sources | 綁定當次可觀察 statement；自由生成句須另行人工對齊 |
| audit_item | run/claim hash、error_type、gold_error_label、expected_detection_class、evidence_pack_sha256 | 外部判斷 Audit，不拿其 verdict 當標準 |
| adjudication | record_id、independent_annotations、disagreement、adjudicated_label、rationale、reviewers | 保留分歧與裁決，不覆蓋原始標註 |

所有可評分標籤各自帶：

```text
label / acceptable_labels / required_conditions
ground_truth_tier: A_source | B_document | C_clinical
review_status: draft | in_review | adjudicated | rejected
annotation_provenance:
  source_assets + hashes + JSON pointers / document locators
  extraction_protocol / annotation_guideline_version
  annotator_id + qualification_role + timestamp
  reviewer_ids + adjudication_id + rationale
```

`annotator_id=null` 表示尚未標註，不可製造 reviewer 名稱。病歷內的 verified_by 或 authored-test-reviewer 不會自動成為 Gold annotator。臨床標籤只有適當專家完成獨立標註與裁決才 eligible；工程師建立草稿不得升格。A 層的可重複 extraction 可以有程式／協定版本，但仍須證明讀取來源，不能填成 Agent 的判決。

### 6.2 Manifest 與身份對齊

- **Case**：保存整個 history asset 的檔案 hash、抽取的 revision，以及 canonical snapshot hash。canonicalization 版本需固定（包含 null/default 政策、key ordering、數字／時間表達）；不能以今日 Schema 靜默改寫舊輸入。raw asset hash 和 case snapshot hash 不是同一個值。
- **Lineage**：source_dataset_group 綁來源 CSV hash；source_case_group 記 builder／provenance 的衍生關係；leakage_group 可按保守指紋合併。grouping_basis 須列 confirmed_derivation / observation_fingerprint / unresolved，不填真實病人 ID。
- **Corpus**：固定檔案 hash、版本、population、document_kind、derivation/source family、parser/chunking/query 版本及允許 scope。WHO 全書與節錄共享來源 family，不當兩份獨立臨床支持。
- **Evidence**：起迄採原始保存 text 的 Unicode code point 索引，`[start,end)`；不在載入時改行尾／空白。Python 與 JavaScript UTF-16 索引不同，不可直接交換。另保存 exact text_unit hash 與 quote hash；PDF 頁面／Markdown heading/line 為定位輔助，不替代內容核對。
- **Run**：分別保存原檔 blob hash、版本化 normalized content hash，以及 input_kind（public_export/internal_snapshot/benchmark_result）。若正規化時間字串，須明確版本化；不能改 quote 字元。相同 run_id 不同內容不能靜默去重。
- **任務**：manifest 宣告 drug universe、claim inventory、critical set、k、condition matching policy、clinical safety 定義與 split。未標註的空集合與已裁決的 empty set 使用不同狀態。

### 6.3 AST、文件與臨床欄位的具體形狀

`ast_ground_truth` 至少包含：availability、interpretation_basis、source_rows（index/JSON pointer/raw selected value/其他類別值）、source_data_flags、target_task、accepted_labels、policy_version、review_status。raw reported_sir 矛盾與 selected category 矛盾分開表示。source_rows 的 index 對原病例陣列，不能先排序後回填 fact_refs。

`retrieval_query.judgments` 每項包含 evidence unit ID、document hash/version、relevance=`relevant|irrelevant|unjudged`、dimension、理由與 reviewer；`critical_requirements` 每項有 importance、必要範圍、acceptable_bundles、corpus_available。Critical 的判斷可比一般 relevance 更嚴格，不能由是否被檢索決定。

`run_claim.support_label` 使用 `supported|contradicted|insufficient_evidence|not_substantive|not_applicable`。`clinical_risk` 逐 allergy/renal/interactions 記錄專家語意、所需資訊及條件；不必直接複製系統 status enum。`final_decision` 可使用 `acceptable_option|unacceptable_unsafe|not_indicated|insufficient_information`，加 acceptable_conditions／decision bundles；到系統 reviewable/pending 的對應由版本化 policy 決定，不由模型自己定義。

### 6.4 節錄模板：只有來源事實，臨床標籤保持未標

以下是**擬議 Schema 的草稿模板**，不是可直接拿去評分的正式 Gold；其中病例名、revision、AST[0] 的兩個類別值與路徑是本次核對的實際資料。hash、annotator 與所有判讀留 null；沒有捏造臨床答案。正式評分時 manifest/hash 必須補齊，且需要的 label 已 adjudicated。

```json
{
  "schema_version": "eval-gold-0.1-proposed",
  "record_type": "case_drug",
  "record_id": null,
  "case_id": "agent-complete",
  "revision": 4,
  "case_snapshot_sha256": null,
  "source_case_group": "G01-provisional",
  "leakage_group": "G01-provisional",
  "grouping_basis": ["builder_derivation", "observation_fingerprint"],
  "drug_code": "amoxicillin_clavulanate",
  "ast_ground_truth": {
    "target_task": "selected_source_classification",
    "interpretation_basis": "CLSI_2022_pheno",
    "source_rows": [{
      "index": 0,
      "field": "/ast_results/0/clsi_2022_phenotype",
      "value": "Susceptible",
      "reported_sir": "S"
    }],
    "accepted_labels": null,
    "ground_truth_tier": "A_source",
    "policy_version": null,
    "review_status": "draft"
  },
  "retrieval_query_ids": [],
  "evidence_span_ids": [],
  "claim_support_labels": [],
  "clinical_risk": {
    "allergy": {"label": null, "review_status": "draft"},
    "renal": {"label": null, "review_status": "draft"},
    "interactions": {"label": null, "review_status": "draft"}
  },
  "final_decision": {
    "label": null,
    "acceptable_conditions": null,
    "review_status": "draft"
  },
  "annotation_provenance": {
    "case_asset": "data/handoff/cases/agent-complete.json",
    "case_asset_sha256": "2b0e6074d7e14a537018966d585f072b46f75f323d751d6b76cd2560f0108fe3",
    "annotation_guideline_version": null,
    "annotator_id": null,
    "qualification_role": null,
    "reviewer_ids": [],
    "adjudication_id": null
  }
}
```

空 retrieval/claim 陣列在 draft 狀態是「尚未標」，不是「已裁決沒有任何相關證據」。真實 supported/unsafe labels 不在本文件產生。多個標註者先保留個別記錄，計 agreement 後由第三方裁決；無法裁決就保留 insufficient/unknown，不能用 Audit 作最後裁決。

### 6.5 Pilot 工作包

1. **A 包**：五病例所有原 AST 的來源欄位、選定依據、缺失／重複／矛盾、病例 facts 與版本。先凍結 conflict 政策；所有 Gold producer 與被評 validator 分離，防止共同 bug。
2. **B 包**：對固定 query 和 corpus 建 relevance／critical spans；優先核對目前真正取回的標頭／適應症與所需風險專節，加入獨立正反例。pool 要跨方法／來源擴充，不能只標同一個 Agent 已用的片段。
3. **C 包**：由專家選定小型、事前固定的 drug/dimension 範圍，建立 claim、risk、final decision Gold。部分標註先做 partial 評估，不可宣稱已評完整 18 藥的 Candidate Precision/URR；新輸出超出標註範圍須補標或報 missing_gold。
4. 五病例都作 dev pilot；另選不共享來源觀察、未用於 Prompt 調整的資料作後續驗證。不能將相同來源的五個變體切成 train/dev/test。

## 7. Offline Evaluator 架構（建議獨立模組）

### 7.1 為何不直接擴寫 benchmark.py

benchmark.py 的價值是既有可追溯工程摘要與 N/A 分母；它直接理解 workflow 狀態／candidate flags／synthetic expectations，不具 Gold 身份、語意標註、claim 對齊、不同能力版本及分組統計契約。把這些硬塞入線上 Benchmark 會讓 scorer 與被評系統共用判決，也增加重新執行模型或改 DB 的風險。

建議保留其輸出原樣，可由 evaluation adapter 引用純統計作附錄；品質評分完全由獨立 Gold 與純函式完成。評分器不 import `app.main`、Repository、Provider、RuleEngine，不啟動服務、不建 DB、不更改 Run，也不執行生成／檢索來補不存在的觀測。

### 7.2 推薦目錄（全為提案，尚不存在）

```text
backend/app/evaluation/
  schemas.py           Gold/manifest/metric result 契約，與 Agent Schema 分開
  io.py                JSON/JSONL/Run array/Benchmark results 讀取、hash、去重
  adapters.py          agent-led/legacy baseline/public/internal 能力映射
  alignment.py         case/revision/hash、corpus、span、claim/proposition 對齊
  eligibility.py       missing_gold/not_evaluated/invalid_output 與診斷
  metrics/
    retrieval.py       純 Recall/Precision/Critical coverage
    ast_sources.py     獨立 Gold 對照；不呼叫 production validator
    claims_audit.py    固定 inventory confusion counts／claim labels
    decisions.py       候選、unsafe、pending 與 universe
    resources.py       已觀察 latency/token，版本化費率估算
  aggregate.py         micro/macro、分組、配對與 coverage
  export.py            JSON、CSV、版本與 provenance
  cli.py               離線入口，不 import API
backend/tests/evaluation/
  test_alignment.py
  test_metric_contracts.py
  test_missing_and_invalid.py
  test_exports.py
  fixtures/            純算式 toy data，不是真實臨床 Gold
evaluation/            manifest、annotation guideline、schema 說明
data/local/evaluation/ 受控人工標註／未公開案例（依交接政策管理）
data/runtime/evaluation/<evaluation_id>/ 只寫新評估結果
```

公開／私有 Gold 的實際存放與 Git ignore 政策需在實作時明確決定；本輪不建立這些目錄、不修改 .gitignore。現有 `data/local`／`runtime` 已被忽略，不代表任意 Gold 都適合公開。

### 7.3 輸入與資料處理契約

1. 接受單一 Run、Run 檔案集合、JSON array 或 Benchmark JSON.results。明確選擇 normalized/public/internal target，不因同一 ID 自動偏好較完整的另一筆。完全相同內容去重並記錄；同 ID 不同內容需指定版本或報衝突。
2. 驗證 JSON 及必要結構，保留原檔 hash；依 workflow 版本建立 capability matrix。歷史 baseline 沒有原子 claim/ranked query，對那些指標回 not_evaluated；仍可評 final candidates。不得補造角色、primary IDs 或 raw response。
3. 對齊 Gold 的 case revision＋snapshot hash、corpus/hash/version、drug universe 與 annotation release。case_id/revision 相同但內容不同必須阻擋，不可默默取最新版；由版本化 adapter 處理 default/null/time 表達差異，原始文字不變。
4. 對每一 requested case/drug/Agent/query/claim 建 observation row。Gold 未完成→missing_gold；合法 pending→可評 abstention；方法沒有 Agent→not_applicable；失敗 stage 沒語意輸出→not_evaluated:execution_failed 並進工程失敗計數；完成 stage 的格式壞列→invalid_output。
5. 將模型聲明與 inventory 的對齊當成獨立、可審查資產。自由文字未能確定對齊時需人工 binding，不偷呼叫 LLM，也不因 dimension 同名就視為語意等價。未知新主張保留並進 Gold coverage 分母。
6. 純函式計算逐 query／drug／role／system 指標及分子分母；統計器不讀 DB、不改原 JSON。全域摘要須同時列 omitted/invalid/failed/unjudged 數，不只輸出一個平均。
7. 只輸出到新的 evaluation_id 目錄，若已存在則拒絕覆寫；Gold、Run 都唯讀。所有版本與命令參數寫 result manifest，重評同一輸入得到相同內容；evaluation_created_at 等非確定 metadata 另列。

### 7.4 CSV / JSON 交付格式

建議輸出：`evaluation_manifest.json`、`summary.json`、`observations.jsonl`、`per_case.csv`、`per_drug.csv`、`per_agent.csv`、`per_query.csv`、`per_claim.csv`、`diagnostics.csv`。CSV 每列是一個具名評分單位／metric，包含 case/revision/group、drug、role/dimension、run/claim/query ID、metric_version/target、status/reason、value、numerator/denominator、Gold coverage；null 欄位留空並用 status 說明，不輸出假 0。

JSON 保留 nested diagnostics、refs、標註／版本 provenance；CSV 用穩定欄位，list 類用明確編碼，不把條件或多個正確來源丟掉。API／DB 回應不同的動態 physician 清單只作可觀察輔助，AI 主指標仍從保存的 AI output 取得。

### 7.5 必須先測的算式與契約

| 測試 | 預期行為 |
| --- | --- |
| 無 Gold 或 draft Gold | missing_gold；value=null，不當預測錯誤或正確 |
| 已裁決 R 為空 | Recall null/not_applicable；不是缺標註 |
| 成功查詢回空、R 非空 | Recall=0；P@k=0；有 critical 需求則 missing |
| 不足 k 個結果 | P@k 固定分母 k；P@returned 另算 |
| 兩個可接受來源／AND bundle | 任一完整替代 bundle 可成功；只有半個 AND bundle 不給分 |
| 相同藥不同版本、錯 fact index | attribution mismatch；不因同藥名當正確 |
| AST selected category 缺失 | unknown 的政策依 source Gold；不由 raw number 補 S |
| reported S/R、selected S/S | 來源旗標可核對；drug classification 沒裁決不硬計分 |
| 全 pending／無肯定句 | candidate P/URR null；有 Gold positives 時 Recall=0；不把 Mock 模板當實質 claims |
| TP=0、FP=0、FN>0 | P null、R=0、F1=0；TP=FP=FN=0 時 F1 null |
| 不合法輸出或執行失敗 | diagnostics／工程分母保留，不冒充 pending 或 missing_gold |
| 舊 Run 沒 ranked logs | retrieval@k not_evaluated，但可評已保存 final output |
| 缺 token/price | known subtotal／missing coverage；不報完整零成本 |
| 相同 ID 不同 hash／跨 split group | 明確拒絕或診斷；不能靜默合併 |
| 重複執行相同輸入 | 除時間 metadata 外，評分與排序完全一致 |

這些先用不帶醫療含義的 toy IDs 測算式，再用保存 Mock Run 做 adapter／status smoke test；不能為了讓測試有數字而造臨床 Gold。

## 8. 研究實驗 A：End-to-End Pipeline Comparison

**研究問題**：四套現行系統在相同病例／可用文件條件下，最終品質、覆蓋率、可靠性與資源代價如何？結論是完整 pipeline 差異，不是單純 Agent 數的因果效應。

| 條件 | 必須固定／記錄 | 不能消除而必須報告的差異 |
| --- | --- | --- |
| 資料 | 同一 case revision/hash、group split、同一 Gold release、同一候選任務定義 | 目前 28 例單一來源檔，Pilot 只有一個 lineage group，不能代表跨病人／跨院泛化 |
| 文件 | 同一 corpus/derivation/population/parser/chunking snapshot、scope、catalog | Multi-Agent 多 query／逐風險路由；其他模式共同檢索，不是相同 evidence pack |
| 規則 | research reported-phenotype rules 與 catalog hash 固定；不可沿用 pytest demo 規則當研究規範 | 三個 baseline 的規則／後處理與 agent-led 不同，這是系統組成差異 |
| 模型 | 生成模式先共用同一精確模型版本／參數；每角色 override 顯式列出；Rule-only 記無模型 | Single/RAG 一次主要生成、Multi 六節點加可能修復，呼叫／上下文不等量 |
| 評分 | 共同外部 scorer、候選／命題／風險 Gold、盲化呈現，原輸出與後處理分層 | 各自 gate 不是共同醫療正確性標準，完成率只能當工程結果 |
| 資源 | 同一機器／服務配置、cache policy、總calls/token/time上限與實耗、完整測量邊界 | 保留原系統 budget 的比較與資源接近比較分開，不以 6:1 calls 當公平證據 |

執行協定（未執行）：

1. 先在保存輸出上驗證 adapter、Gold 與分母；Mock 結果只做軟體控制組，不與真實模型品質混算。
2. 預先指定主要終點、可評 scope 與失敗政策。建議初期以 source fidelity、claim support 與 critical evidence coverage 為主；Unsafe/Candidate 指標只在 C Gold 充分時啟用，不事後挑最好看的指標。
3. 每例每條件採配對重複，Pilot 可先規劃 3–5 次估變異與成本，**不是已達足夠統計 power 的承諾**。正式 R 由 pilot 變異／預算決定並事前凍結。Rule-only 決策無隨機性，仍需重複計時；同一個答案重複五次不增加獨立 n。
4. 按 group/case block 隨機交錯條件執行，避免模型服務時段／網路／快取全偏向某一模式。固定可控制 temperature/top_p 等參數；即使 temperature=0 也不保證 deterministic。provider 不支援 seed 就記 null，支援時記實際採用值與重複 ID，不捏造 reproducibility。
5. 暖機／索引建置另記；cold 與 warm 分開。每個 attempt、截斷、修復、timeout 都保存，不能只留成功 Run。統一外層計時納入 Benchmark 預先檢索，或明確將預計算成本另報；不能直接比較範圍不一的 elapsed_ms。
6. 由同一 Gold scorer 對每例作 paired difference，再依 leakage/source group 聚合；可用 group bootstrap，但目前 Pilot 一組不能建立有意義的群體 CI。新獨立 group 的 held-out 才能支撐泛化結論。

必備 experiment manifest：protocol/experiment/condition/trial ID、Git HEAD＋dirty patch hash、版本／lock、case/group/split、corpus/catalog/rules/parser/query hash、Gold/scorer版本、模型精確識別與參數、Prompt/schema hash、資源預算、cache與計時政策、價格快照、全部 Run IDs／hash與失敗。費用／真實模型呼叫需另取得授權，本次不執行。

## 9. 研究實驗 B：Controlled Multi-Agent Ablation

**研究問題**：在相同資訊與評估標準下，角色報告、Synthesis、Audit 分別貢獻什麼？需要另外的研究 runner／sidecar，不能僅改 Benchmark mode 名稱。此輪只設計，不改正式 pipeline 或解除產品 gate。

共同控制：固定 case facts/AST 順序、drug universe（不允許某條件額外擴充藥物而不記錄）、每 role 可見 evidence pack／spans、文件版本、共用模型、Prompt/schema 版本、Gold/scorer、calls/token/time上限、trial與可控制隨機性。資料與證據必須取自任務合法來源，不給 Gold rationale 或專家最終答案當上游訊息。

| Ablation | 具體比較 | 因果解讀界線 |
| --- | --- | --- |
| Role specialization | 完整分工 vs 合併角色／移除單一 specialist 報告；Synthesis 的原始 facts/evidence 與其他報告保持不變 | 移除的是 role report，不暗中移除其他條件仍可見的原始事實；不使用 Gold oracle 補缺；記明缺失角色提示政策 |
| Synthesis contribution | 凍結同一組 specialist 報告，LLM Synthesis vs 事前定義的透明 deterministic combiner | combiner 不是事後照 Gold 寫答案；來源驗證與共同 scorer 一致；評整合前後的錯誤傳遞／覆蓋率／矛盾 |
| Evidence Audit contribution | 凍結同一份 Synthesis draft、case與所選原文，對比 Audit 前後；另以人工 faulty/correct claims 測 error detection | Audit-off 只是研究用未核對草稿，不能發布為安全候選；Gold 由外部判斷，不能用 Audit supported 當真值 |
| LLM Audit vs 程式 validator | 有條件分開觀察模型回覆與驗證後結果 | 現有檔大多只保存 normalized output，若 raw 不在，就只能評整個 Audit＋程式組合；不能從既有資料假造兩者各自增益 |
| Retrieval as separate factor | 固定 evidence pack 先比較協調，再另外比較 lexical／排名改善／embedding | 不把檢索改善同時改進協調後的差異全部歸因 Agent；索引建置／模型成本另計 |
| Resource control | 原生策略的實耗比較；另做相同總預算上限的比較 | 移除角色省下的 calls 不自動挪給其他角色；是否重分配要另列條件。可增加預先定義的單角色反覆精煉作資源對照，但不能聲稱等同分工 |

重要分析：同一 claim 的 specialist → Synthesis → Audit → final 的 TP/FP/FN 轉移、錯誤保留／新增、正確主張被拒率、critical coverage、pending與unsafe的交換；使用固定 trial 配對，不能把相同中間報告複製十次當十個獨立樣本。

離線 replay 可測訊息傳遞與 validator 的反事實過濾，但**不能證明沒有某角色時 LLM 會生成什麼**。要測新協調策略，仍需要新條件下的合法保存輸出與共同 Gold；若使用新模型呼叫，另按授權／預算執行，不把 Mock 補完的重播當真實模型實驗。

Pilot 的 G01 只適合功能性／探索性機制分析。若對外主張 Multi-Agent 有普遍增益，還需未調參、獨立 lineage/source groups 的資料；目前無法由這五個變體推論此結論。

## 10. 最小可行實作計畫與完成條件

| 優先序 | 工作 | 可交付成果／完成條件 | 相依 |
| --- | --- | --- | --- |
| 1 | 凍結資料身份、lineage與評估協定 | 五 Pilot 的 revision/hash、G01 dev 身分、完整 corpus/query/target manifest；conflict 的兩項任務政策有獨立裁決 | 本文件與來源盤點 |
| 2 | Schema／loader／alignment／eligibility | 單 Run、多 Run、Benchmark JSON 可讀；Gold JSON/JSONL 可驗；missing/invalid/NA 不混；不 import API、不寫 Run、重複 ID/hash 有測試 | 1 |
| 3 | A 層 scorer 與工程統計 | source-classification／來源機械核對、pending、已知 latency/token；用純算式 fixtures＋保存 Mock 做 adapter smoke；所有 Gold缺口清楚輸出 | 2＋獨立 A 標註 |
| 4 | B 層 Retrieval scorer | 固定 rank/k、relevance與critical bundles；P/R/CEMR 純函式、JSON/CSV、分母及Gold coverage可手算核對 | 2＋B標註及corpus manifest |
| 5 | C 層 claim／Audit／decision scorer | proposition inventory／run bindings、專家雙人標註與裁決；Candidate/Unsafe 不再全部 missing_gold；支援多答案與條件 | 2＋C標註 |
| 6 | 小型研究 pilot | 共同 scorer、已授權的非Mock保存輸出、事前條件／預算／重複協定；產出 paired描述結果及全部失敗 | 3–5＋實驗manifest |

MVP 不需要新 Agent、資料庫服務、LLM-as-judge、GPU、向量框架或 UI。先交付可重現的**讀檔／對齊／狀態／算式／匯出**，再接標註；品質資料不足時應產出誠實的 missing_gold，而不是硬湊分數。對應 regression 至少包含獨立 evaluation unit tests、既有 Backend、Frontend/Build 與 Playwright（若改到共用合約／API才擴大），不得重寫舊 Benchmark summary。

### 10.1 現在可做的評估

- 可直接盤點／核對來源 AST 類別與事實、refs/quote 的可定位性、同源指紋、Run能力與輸出完整性。
- 可用保存 Run 描述六節點／74次查詢／68片段、18 pending／0 AI candidates 等工程行為，讀取已量測 latency 與 missing usage。這不是臨床品質分數。
- 凍結 A 層政策與來源標籤後，可對現有 agent-complete Mock 做 source-fidelity／metric status 的 smoke 評估；Mock不是推論能力樣本。完整 Source Attribution 的語意正確性不能只憑 refs 存在就立即算。
- 可離線實作／測試 evaluator 的算式與 JSON/CSV 契約；**本輪尚未實作，因此目前沒有新產出的 evaluation score 或 Gold 檔**。

### 10.2 必須等待標註的評估

- Retrieval Recall/Precision/CEMR：需要 B/C relevance、固定來源池與 critical 需求，不能用「有取回文件」替代。
- Claim 支持性、Source Attribution 語意、Audit Detection：需要獨立 statement／source 判讀；Recall/F1 還需完整命題 inventory，不只是生成句清單。
- Clinical risk、Candidate Precision/Recall、Unsafe Recommendation：需要適合的醫療專家對病例、條件與版本化文件裁決。
- Generalization／顯著性：需要不共享 pilot lineage、未被調參污染的病例群；目前五 Pilot 不足。

### 10.3 距第一次可量化 Multi-Agent 研究實驗還缺什麼

必要條件是：獨立 evaluation 程式與測試、凍結的 metrics/manifest、完成且可追溯的相應 Gold、五個病例（或明確子集）的可評估 Run、共同對照與資源／隨機性協定。要量測**真實 Multi-Agent 推論效果**，還需可合法使用的非 Mock 保存輸出；目前日常 DB 只有一筆 Mock，其他四例也沒有對應 Run，不能直接比較模型能力。

第一個可量化的工作可以是 A/B 層的離線 retrieval/source-fidelity pilot；第一個真實推論比較需先補 Gold 與有授權的模型輸出。若只使用 G01，結果限於同源情境的探索性描述；若要宣稱一般性 Multi-Agent 改善，必須再補獨立 held-out groups。工程測試綠燈使實作可開始，並沒有替這些研究必要條件背書。
