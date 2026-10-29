# AST Evaluation Policy Decision Package

日期：2026-10-27。狀態：**待研究者決策**。依據 `AST_GOLD_POLICY_REVIEW_PILOT_DRAFT.md`、`AST_SOURCE_GOLD_POLICY.md`、Pilot provisional dataset 與現有 Offline Evaluator 靜態核對。本文件只提出政策與後續計畫，未核准政策、修改程式或建立 Clinical Gold。

## 1. 決策範圍與已確認事實

四種標記：**F＝資料已確認**；**R＝推薦研究政策**；**D＝等待研究者核准**；**V＝仍需獨立來源複核**。機械讀取相符不等於已有人員核實，也不代表臨床正確。

F：`data/local/evaluation/pilot-a-source-v0.1-provisional/` 包含 91 observations、90 case-drug drafts。五例 agent-complete、agent-ast-conflict、agent-allergy、agent-renal、agent-evidence-mismatch 皆 revision 4，history index 3，暫定同源 G01-provisional。90 筆×4 任務共 **360 個 labels 均為 draft**，答案為 null；正式 Gold=0。

F：列級分布為 80 三欄一致、1 reported/selected 矛盾、5 levofloxacin 歷史 phenotype 差異、5 ertapenem selected 缺失。全部 basis=CLSI_2022_pheno。86 列 selected 非空，映射為 85 個已知類別 case-drug；這些是潛在評分範圍，不是已合格 Gold 分母。

F：「historical」是目前文件對非選定 source_phenotype 的稱呼，沒有獨立日期證據可保證時間順序或差異成因。原 CSV source_record_id 已移除，交接包來源核實的上限是指定資產內記載，不能宣稱原檢驗生物學真值。

## 2. 供核准的政策決策表

以下每項均為 R/D，沒有預選核准。影響數量來自目前資料；替代方案是可明確命名的另一研究任務，不能事後挑有利分數的政策。

| ID／決策 | 推薦選項 R | 替代選項 | 影響筆數／指標影響 |
| --- | --- | --- | --- |
| P01 來源優先序 | 按明確 interpretation_basis 指定欄位，不回退、不用多數決。CLSI_2022_pheno→clsi_2022_phenotype；source_report→source_phenotype；明確 legacy→reported_sir；未知 basis 未評 | 另開「原報告 phenotype 重現」任務，固定讀 source_phenotype；不能沿用 selected-source 指標名稱 | 全 91 列／90 單位均受來源規則約束。替代任務使 5 levofloxacin 從 I 變 S，並使 5 ertapenem 的來源目標從缺失變 S；至少 10 單位的目標意義改變 |
| P02 reported/selected 衝突 | 分類忠實讀 selected；衝突另評。本例分類可提議 S，reported S/R 標衝突，不覆寫原值 | 只在主分類暫時隔離有矛盾的單位，保留到專門 conflict stratum | 1 單位、2 列，其中 1 列矛盾。全部核實並核准後，主分類潛在分母 85；替代為 84。衝突偵測仍可保留該 positive |
| P03 衝突定義 | 三旗標分開：reported-vs-selected、within-reported、within-selected；主 positive 為任一明確 true；充分可觀察才可標 negative | 僅評 within-selected 作為另一個較窄任務；或另報包含歷史差異的 discrepancy 指標 | 推薦範圍 85 單位＝1 positive＋84 negative，5 unassessable。只看 selected 則本 Pilot 無 positive，recall=null；若納入歷史差異則增加 5 個陽性單位，已是不同任務 |
| P04 selected 缺失 | source=null/missing；主 S/I/R accuracy 排除，另評完整 Missing/Unknown Handling；unknown 本身不給完成 credit | 另報「含 unknown 的來源狀態分類」次指標，unknown 只代表 label matching | 5 列／5 單位。主分類潛在分母 85；若另訂 overall-state 任務可涵蓋 90，但不能混稱同一 accuracy。禁止用歷史 S 填補 |
| P05 levofloxacin 差異 | 主分類依 selected I，保留歷史 S 與 historical_difference；不納主要 conflict positive | 明確定義跨來源 discrepancy 偵測，將其列為陽性，但不改寫原值 | 5 列／5 單位；推薦不使它們變成主要衝突 FN。改採 discrepancy 任務會改變偵測陽性分布，必須重定 Gold／分母 |
| P06 來源歸因 | 正確版本＋同藥＋basis 指定欄位＋非空類別值支持聲明；另報引用 coverage | 僅作 pointer locatability 工程檢查，保持不同名稱 | 全 90 單位需保留來源；S/I/R attribution 潛在適用 85 單位，但真正分母是預測 links，現階段不能指定為 85/90/91。缺失 5 單位另走缺失任務 |
| P07 重複列 | 91 列全部保存；同 case/revision/drug 聚成 90 個評分單位，來源 links 一對多 | 另報 observation-level fidelity，只作輔助診斷，單獨分母 91 | 唯一差異單位是 conflict/amoxicillin_clavulanate。推薦避免該單位被雙重加權；替代指標不能取代 case-drug accuracy |
| P08 分母與失敗 | conditional accuracy＋prediction coverage＋strict task success 同報；壞輸出與無 Gold 分開 | 以 strict task success 為主要終點，conditional 仍作診斷 | 影響全部 eligible 單位；無 Gold 不進品質分母，invalid/failed 在已有 Gold 且任務可比時保留 strict 分母。禁止只排掉壞輸出後報高分 |
| P09 同源分組 | G01 五例全留 dev，同組配對描述，報 group=1 | 預先指定一個基礎 AST 的主分析，其他變體作 stress cases | 五例／90 單位均受影響；兩種方案都不能把 90 藥或五變體當獨立患者，不能在此證明泛化增益 |
| P10 資格與核實 | 逐任務 policy-approved＋source-verified＋label-adjudicated 才 eligible；身份/hash 鎖定 | 允許明確標示的 provisional 工程觀察報告，但不得命名正式 Gold accuracy | 全 90 草稿／360 labels；目前正式 eligible=0。可分批核實與發布，未完成的任務不隨其他任務升格 |

P01 的非 CLSI 映射是推薦協定，這五例未提供其他 basis 的驗證樣本。未知／混合 basis、selected 本身多類別、同藥部分列缺失等尚無本 Pilot 完整正反例，應保守 pending_review，不自行補一個答案。

## 3. 91 與 90 的無損處理

F：`data/handoff/cases/agent-ast-conflict.json` revision 4 的 amoxicillin_clavulanate 有兩筆：

| AST index | 完整 asset pointer | reported | selected CLSI | source_phenotype |
| ---: | --- | --- | --- | --- |
| 0 | `/3/case/ast_results/0` | S | Susceptible | Susceptible |
| 18 | `/3/case/ast_results/18` | R | Susceptible | Susceptible |

F：只有 reported_sir 不同，其他原始欄位相同。`backend/scripts/build_agent_cases.py:77` 明示複製、翻轉、append；不是第二種藥物，也無獨立採檢證據。dataset 的同一 case-drug 已連結兩個 observation IDs，source_rows 含兩個 selected field pointers；追加列有 authored_conflict_append 標記。

R：分類一藥算一次；若 P02 核准，selected S/S 的分類答案只提供一份成功 credit。偵測只算一個 positive，保留「跨欄位」與「同藥 reported」兩個旗標作診斷，不能把它當兩個獨立錯誤樣本。歸因可允許任一已核准 selected S link，但重複相同 link 不重複給分；不同合法 links 可作不同來源連結觀察，不增加獨立藥物樣本數。

R：不得刪列、覆寫、排序後遺失原 index、任取第一／最後一列，或用 S/R 多數決。原始事實、衝突類型、人工注入 provenance 與一對多 links 均需保留到報告。

## 4. 四項指標的核准契約

共同條件：身份對齊、可追溯來源、政策已批准、獨立核實與該任務 adjudicated。下列所有分母為零時 value=null 並列原因。C/D/M 是已合格 Gold 任務集合，不是原始檔行數。

| 指標 | 預測與 Gold | 分母／分子與邊界 |
| --- | --- | --- |
| AST Source Classification Accuracy | AST normalized assessment 對照已核准唯一 selected S/I/R | 潛在 C=85（P02 隔離時 84）；E 為 C 中合法類別輸出。conditional=正確數/E；coverage=E/C；strict=正確數/C。合法 unknown/conflicting 對已知 S/I/R 是未命中，留在 E；invalid/missing output 不冒充某個類別 |
| AST Conflict Detection | 明確 conflict prediction binding 對照獨立來源三旗標 Gold | 潛在 D=85＝1 positive＋84 negative；5 missing 排除。E_D 為明確合法預測；conditional=(TP+TN)/E_D，precision=TP/(TP+FP)，recall=TP/(TP+FN)。另報 E_D/D、正負 coverage、strict detection=TP/Gold positives in D。無 binding 協定時整項未評，不給假零分 |
| AST Source Attribution Accuracy | 實際 category_source_refs 對照聲明與允許 source relation | 分母為有合格 Gold 的可解析預測 links，分子為版本、藥物、selected field、值與聲明均相符的 links。合法格式但來源錯／不存在算錯；格式不可解析另記 invalid。空引用 accuracy=null，必要聲明 attribution coverage 可為 0，不能因此得滿分 |
| Missing/Unknown Handling | unknown/暫緩＋明確識別 selected 缺失＋null field binding，對照獨立 missing Gold | 潛在 M=5。分子為完整滿足核准處理條件者／M，另報 binding/output coverage。只有泛用 unknown 沒有完成證據，不自動算正確；若根本未建立 binding 協定則未評，而非將缺量測當模型失敗 |

Source Attribution 的可接受多來源應在看預測前核准。缺失聲明的 null 來源有不同語意，不混入「非空 S/I/R 類別歸因」。若要只評 unknown label matching，另命名 secondary metric，不稱完整缺失處理。

狀態區分：source missing 是輸入事實；missing_gold 是未有合格標註；not_evaluated 是不適用／執行失敗／缺 binding 或 scorer；invalid_output 是輸出格式或完整性不合法；alignment_error 阻擋不同版本混評。只有有合法預測與合格 Gold 的不相符才是實際 prediction error。invalid/failed 的工程計數與適用 strict 分母仍保留，防止選擇性刪除。

## 5. 哪些可經來源複核形成 A_source Gold？

| 範圍 | 可獨立核對的事實 V | 尚不能直接升格的部分 D/V |
| --- | --- | --- |
| 全 91 列 | 原值、basis、index、pointer、資產/hash；可由另一人直接讀取交接 JSON 逐欄複核 | 程式 extraction 與 hash 相符並不等於獨立人工 verified；原 CSV 個案無鍵，不保證原檢驗真值 |
| 84 個無主要衝突的已知類別單位（含 levofloxacin 5） | selected 非空且唯一，reported 與 selected 相符 | 來源優先序／歷史差異處理須批准；逐任務 provenance、reviewer、adjudication 未完成 |
| conflict 藥物 1 單位／2 列 | selected S/S、reported S/R、人工注入可核對；可建立來源矛盾 Gold | selected 分類 accepted_labels 及 conflict 正式定義待批准；沒有 Agent prediction binding |
| ertapenem 5 單位 | selected=null、reported=null、有 AST 列、歷史 S 均可核對；missing 事實可成為可靠來源標籤 | unknown 成功條件／理由／null binding 待批准；不能從缺失事實推導臨床可用性 |
| source attribution 的來源關係 | 版本、同藥、selected field、raw value可逐一核對；可審閱候選 allowed refs | 是否支持具體聲明、哪些 refs 可替代及必要引用集合仍需政策／獨立標註 |

所有 90 筆現在仍 pending_review；上述是「可核實的材料」，不是已核實的 Gold。某單位可先完成 missing-fact 核對，不代表 classification、attribution、conflict、missing-handling 四任務一起核准。臨床 breakpoint、藥物適當性與安全性不屬本次 A_source。

## 6. 現有 Evaluator／Schema 缺口（原始碼確認）

依據：`backend/app/evaluation/evaluator.py:111–141`、`schemas.py:54–88`、`alignment.py:5`、`metrics.py:31–85`；AST 原契約 `backend/app/agents/contracts_led.py:32`。

| 項目 | 現況 F | 最小需要／不需要的改動 R |
| --- | --- | --- |
| 分類 prediction | ASTItem 有 assessment、reason、category_source_refs；已有 Gold accuracy 比對 accepted_labels | 不需新 Agent Schema；先批准與核實 Gold。85 的主 S/I/R scope、缺失排除、coverage/strict 報表仍需明確 eligibility，不能僅填 unknown labels |
| 分類與來源 proxy | ast_source_consistency 對跨欄位衝突會暫緩、對選定缺失的 unknown 可給 proxy 相符；Gold accuracy 是另一條分支 | 保留 proxy 名稱與歷史語意；新的正式任務 eligibility 不可偷偷改寫 proxy。P02 核准後，Gold 分類可獨立接受 S，不需改 Agent 判決 |
| Conflict | 目前只是未評估 placeholder；有 draft task key 也可能顯示 binding 不可用 | 需要獨立 prediction binding、任務 scope、Gold eligibility、純 scorer。不能把 source_conflict_present 輸入旗標當 Agent 預測 |
| Attribution | 原輸出已有 category_source_refs，現有 citation metric 只處理 evidence_refs/quotes | 新增 AST 專用 refs adapter＋scorer；保留 raw dot path，嚴格轉成 snapshot JSON pointer。讀不到原輸出的內容不得從 category_sources/source_validation 等系統判決補成模型成功 |
| Missing handling | assessment=unknown 存在，reason 是自由文字；沒有已定義的 missing-source prediction/binding | 先定義離線 binding；不可用 keyword contains 或泛用 unknown 當完整成功。无需先改 Prompt/Agent |
| Gold 格式 | generic Label 支援 Boolean label、accepted_labels、source_rows；case_drug payload 為彈性 dict，四個 draft task keys 可載入 | 既有 Gold envelope 足夠存草稿；應補任務層驗證／allowed refs／配對來源資訊，不急著更換所有 record types |
| Gold 衝突 provenance | 現有各任務 source_rows 主要列 selected pointers；reported 值可追到 observation sidecar | 未來核准版 conflict Gold 要顯式綁 paired reported/selected paths、原值與所有列；不能只列 selected S/S 便聲稱證明 reported S/R |
| Release eligibility | 檢查 adjudicated、policy 非空與人員欄位，但不完整聯動 payload.verification_status；policy_version 不代表已登錄批准；source_rows 非空不等於已核對其正確性 | 加入 task-specific、versioned release validator／eligibility gate；確認 verified/review/policy registry、pointer/value/hash 一致。當前草稿驗證器已強制 labels=null/draft，但不能替代未來 release gate |
| 身份／分組 | align() 檢查 case/revision/snapshot/group；Manifest 支援 drug universe；沒有完整政策批准登錄或 source-release manifest 契約 | 以額外 release sidecar 固定政策/來源 hash與資格，不改原 Run；維持 exact hash，不靜默套當前 Case defaults |

建議 prediction binding 使用**新的離線 sidecar**，不寫回 Run，也不把它混成 Gold label。最少包含：binding_version、task、run_content_sha256、case/revision/snapshot hash、node_id、drug_code、normalized_output_sha256、原文／欄位 locator、prediction value（含 abstain）、reference paths、binding method、審閱人員與狀態。只擷取既有輸出真的表達的內容；人工 binding 需與來源 Gold 判讀分離、盲於評分結果。沒有表達該判斷時記 absent/unassessable，不能由 Gold 推導模型本意。

現有 GoldRecord 的 record_type 不含 AST prediction binding；推薦 sidecar 獨立 Schema/Loader，避免將 binding 假裝成 case_drug Gold。Classification／Attribution 可先從已有結構化欄位作 deterministic binding；Conflict／完整 Missing handling 需另行可審查的 binding 協定。

## 7. 最小後續實作順序與驗證條件（本輪未執行）

| 次序 | 最小工作範圍 | 完成與驗證條件 |
| --- | --- | --- |
| 1 | 研究者核准 P01–P10，建立具批准紀錄的政策/release manifest；安排獨立來源複核 | 每決策有版本、選項、理由、批准者、日期；每個正式標籤有 source pointers/hash、annotator/reviewer。未完成者保持 draft；不能批次升格全部 360 labels |
| 2 | 新增 release/task eligibility validator；保留既有格式與歷史 proxy | 測試拒絕未批准 policy、provisional+adjudicated 矛盾、錯版本/hash、錯藥pointer、來源值不符、缺 reviewer；允許合法分批 release，列清 Gold coverage |
| 3 | 最先做主分類 scope/coverage/strict 報告 | 已核准資料下確認85/84的條件、5 missing 排除、unknown 對已知類別為未命中；重複列只算一藥；零分母=null；保持原 source-consistency proxy 結果不變 |
| 4 | 新增離線 binding sidecar Schema/Loader；先用既有 assessment/category_source_refs | 同 Run ID 不同內容拒絕、node/drug/輸出 hash固定、原始字串與順序保留、合法錯 pointer計錯、格式壞值列invalid；不 import API、Provider 或重新生成 |
| 5 | 加入 AST attribution scorer，再加 conflict/missing scorer | 以明示 synthetic 工程 fixtures 手算驗證 link accuracy、coverage、TP/FP/FN、abstention與strict；泛用unknown不自動成功；沒有 binding 時 N/A，人工注入 positive單列 |
| 6 | 對保存 Run 做唯讀回歸與草稿保護測試 | Evaluation＋dataset tests；全部 provisional 指標仍缺 Gold或未評；原 Run/Review/病例/文件 hashes相同；新 scorer需可重現 JSON/CSV與完整分母。現有 88 passed 僅是前輪基準，本輪沒有重跑 |

上述會涉及未來 evaluation eligibility、sidecar adapter 與新 scorer，是需另行授權實作的工作。批准前不啟用新正式評分政策；不需要先改 Agent、Prompt、RAG、Clinical Rules、DB 或現有 benchmark.py。

## 8. 研究者核准紀錄模板與停止點

每個 P01–P10 填：`decision_id / selected_option / approved_policy_version / rationale / approver / approved_at / effective_dataset_release / unresolved_items`。目前所有項目均為 **pending approval**，欄位沒有代填研究者姓名或批准日期。

需要分清：批准政策只決定如何評，不證明來源已複核；來源已複核也不自動提供 Agent prediction binding；Schema 可載入不代表 scorer 已具備或標籤已合格。目前可做來源與工程檢查，四項正式 AST 指標仍需上述對應條件。本文交付後停止，不建立 verified Gold、Clinical Gold、不呼叫真實 LLM。
