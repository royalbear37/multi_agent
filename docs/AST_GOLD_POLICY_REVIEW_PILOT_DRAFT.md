# AST Gold Policy Review：Pilot Draft 補充審查

日期：2026-10-27。既有 `AST_GOLD_POLICY_REVIEW.md`（2026-10-26）完整保留；本文件與其合讀，補齊四項獨立指標與本次 provisional 建檔決定。政策仍為 `ast-source-policy-0.1-draft`，沒有人工批准或正式 Gold release。本輪建草稿的授權不等於核准評分政策。

## 1. 已確認事實（Phase A）

五例均 revision 4、history array index 3，分組為外部暫定 G01-provisional。共 91 observation／90 case×drug；manifest 的五個資產 hash 與 revision 均核對一致。

| case_id | revision | observations | case×drug |
| --- | ---: | ---: | ---: |
| agent-complete | 4 | 18 | 18 |
| agent-ast-conflict | 4 | 19 | 18 |
| agent-allergy | 4 | 18 | 18 |
| agent-renal | 4 | 18 | 18 |
| agent-evidence-mismatch | 4 | 18 | 18 |

差異全部來自 `data/handoff/cases/agent-ast-conflict.json`：

- case_id=agent-ast-conflict、revision=4、drug_code=amoxicillin_clavulanate。
- 原 AST index 0、18；來源 pointer 分別為 `/3/case/ast_results/0`、`/3/case/ast_results/18`。
- 四個欄位路徑為上述 pointer 加 `/reported_sir`、`/source_phenotype`、`/clsi_2022_phenotype`、`/interpretation_basis`。
- 只有 reported_sir 不同（S/R）；selected 是 Susceptible/Susceptible，historical 亦相同。`backend/scripts/build_agent_cases.py:77` 明確複製、翻轉 reported、追加列，沒有第二次獨立檢驗的證據。
- observation 保留兩列；case-drug 草稿保留兩個 observation IDs 與所有 source_rows，不任選或覆寫原列。

其餘已核對：80 列三欄一致；5 列 levofloxacin 是歷史 Susceptible、selected Intermediate、reported I；5 列 ertapenem 是 selected=null、reported=null、歷史 Susceptible；1 列追加 reported/selected 矛盾。全 91 列 interpretation_basis 為 CLSI_2022_pheno。

## 2. 推薦來源政策與保留狀態

| 概念 | 觀察值與推薦用途 |
| --- | --- |
| Selected Source Category | interpretation_basis 指定欄位的類別；CLSI_2022_pheno→clsi_2022_phenotype，source_report→source_phenotype，明確 legacy→reported_sir；未知 basis 不猜 |
| Reported Category | reported_sir 原值；不以它覆寫明確選定的另一來源 |
| Historical Source Category | 在本 Pilot 選定 CLSI 的前提下，另保留 source_phenotype；不假設有可證實的時間序或臨床差異成因 |
| Source Conflict | 分開標 reported-vs-selected、within-reported、within-selected；有已知矛盾才標 observed_conflict |
| Missing Selected Source | 選定欄位 null 記 missing，selected_source_category 保留 null，不回退歷史 S，不直接填 unknown Gold |

本次的 category normalization 僅把 S/Susceptible 等明確字串對應成 susceptible/intermediate/resistant；這是來源觀察，不是 accepted_labels。所有四任務的 label/accepted_labels 均為 null，review_status=draft；所有 observation verification_status=provisional、case-drug payload.review_status=pending_review。

推薦 conflict 藥物的分類任務忠實回答 selected S，並另外識別 reported S/R；正式接受 susceptible 的 Gold 仍待人工裁決。levofloxacin 建議分類 I 並保留 historical_difference。任何 selected 本身多類別、未知 basis、來源混合或部分缺失仍須獨立政策，不套多數決。

## 3. 四項獨立評估契約（推薦，尚未批准）

共同資格：身份/hash/group 對齊、來源可定位、政策已批准、獨立來源核對完成、該任務標籤 adjudicated。**本次 90 筆都不符合最後兩項，正式 Gold 分母目前為 0，分數為 null。** 下述數量是未來潛在範圍。

### 3.1 AST Source Classification Accuracy

- 單位：case×revision×drug，一藥一單位，保留所有 observation。
- 預測：AST Agent 的 normalized assessment，與正式原始模型輸出分開命名。
- Gold：已核准來源政策下唯一 selected S/I/R；reported conflict 不改寫 selected。potential C=85（含 conflict 1，須批准分開任務政策）；若該政策仍未決，其餘全部裁決後最多 84。
- 分母：C 中有合法類別輸出的 E；分子：預測等於已核准 selected category 的單位數。另必報 E/C coverage，以及同分子/C 的 strict_task_success。
- 排除：5 個 selected missing、未裁決 Gold、identity mismatch、未知/混合 basis 等。合法 unknown 對已知 S/I/R 是 prediction error／abstention，不能當正確。
- 不確定：Gold 未決為 missing_gold；輸出缺列或非法 enum 為 invalid_output，排除 conditional E 但保留在適用 strict C 分母；方法無對應輸出則 not_evaluated。零分母為 null。

### 3.2 AST Conflict Detection

- 單位：case×revision×drug，必要時另報各衝突旗標。
- 預測：可審查的明確 conflict Boolean／旗標 binding；不能以 assessment=conflicting、unknown 或 Audit verdict 代替。
- Gold：獨立核對的三旗標任一 true 為 positive；資訊充分且全 false 才是 negative。歷史 phenotype 差異不自動列 positive。
- 分母：Gold 可判定的 D 潛在為 85＝1 positive＋84 negative，排除 5 個 selected missing 的 unassessable。conditional accuracy=(TP+TN)/有明確 prediction 的 E_D；precision=TP/(TP+FP)、conditional recall=TP/(TP+FN)。
- 另外必報 binding coverage E_D/D、正負類各自 coverage、strict detection=TP/D 中 Gold positive 數。合法拒答不偽裝成 negative；未回答 positive 沒有偵測成功，但另記 abstention，不改寫其輸出。
- 不確定：現有 Run 無上述 binding，整項 not_evaluated；不得因未建立量測契約就報 0%。分母為零為 null。唯一 positive 為人工注入，必須單獨標示，不能推論一般偵錯能力。

### 3.3 AST Source Attribution Accuracy

- 單位：一個具體類別聲明→來源欄位 link，以 `(case, revision, drug, claim, source_pointer)` 去重；不是 91 列或 90 藥的固定分母。
- 預測：AST Agent 對該類別聲明實際輸出的 category_source_refs；只評保存輸出中的 links，不把原始輸入欄位算成已引用。
- Gold：獨立審閱的 allowed source-pointer 集合／來源關係。正確 link 必須是正確版本、同藥、basis 指定欄位、非空合法來源值，而且值支持該聲明；純「pointer 存在」只算 locatability。
- 分母：有完整來源關係 Gold、可解析的預測 links；分子：符合上述條件的 links。已可解析但不存在、指錯藥、錯欄位或值不支持聲明者算錯誤，不當 missing_gold。
- 排除：未裁決來源關係、沒有可綁定的具體聲明、來源缺失任務未定、無法解讀格式的輸出；各自報 reason，非法格式另列 invalid rate。
- 空引用：accuracy=null，若有必須引用的 eligible 聲明，另報 required-attribution coverage=有完整有效來源的聲明數/全部必要聲明數，空引用得 coverage 0；避免不引用者拿高分。
- 多來源：conflict index 0、18 的 selected 值皆 S，若政策批准可接受任一支持該 selected 聲明的 link；必須保留人工注入標記。reported R 不是 selected S 聲明的可接受來源。對「來源缺失」的引用則需另訂任務，不混入非空類別歸因指標。
- 不確定：本次沒有正式 allowed-link Gold，也未建立 scorer。現有機械 locatability 不能冒充本指標。

### 3.4 Missing / Unknown Handling

- 單位：selected 缺失的 case×revision×drug，潛在 5 個 ertapenem；資料狀態是 missing，並非已核准 unknown 標籤。
- 預測：unknown/暫緩類別，加上可審查的「選定來源缺失」識別及其 null 欄位來源 binding。
- Gold：獨立核對 selected=null、availability=present，並經批准的缺失處理要求；不從歷史 S 或 MIC 補值。
- 分母：已完成該任務 Gold 的 missing 單位 M；分子：明確識別缺失、正確保留 unknown/暫緩且來源 binding 正確的單位數。條件缺一不算完成；若尚無可比 binding 協定則整項 not_evaluated。
- 排除：未知 basis、格式壞值、未裁決政策、未對齊版本；這些不自動當 selected=null。合法但無依據的 S/I/R 為 prediction error；壞輸出另記 invalid，不偽裝成 unknown。
- **Mock 泛用 unknown 本身不取得完成 credit，更不進主 S/I/R accuracy 的正確數。** 若日後只量測 unknown label accuracy，需另命名且明示不衡量缺失辨識能力。

## 4. 版本、來源與草稿相容性

來源鏈：handoff manifest blob hash → case history asset hash → 指定 revision=4、history index=3 → case canonical snapshot hash → observation pointer → case-drug 所有 source_rows。source_file_hash 明確表示原始 CSV hash，另用 source_asset_sha256 表示交接病例檔；不可混用。

正式評估另需 Run blob/content hash、case_id、case_revision、case_snapshot hash。現有保存 Run `51905060-412e-4e04-99f3-c9a1bbbbc596` 的 agent-complete snapshot 與 handoff r4 相同；其他四例未因此獲得 Run 驗收。不同 hash 直接阻擋，若需正規化須另審查 before/after 差異與 transformation version，不能只比 ID。

Gold Loader 相容方式：90 筆採 eval-gold-0.1/case_drug；verified/provisional 放 payload，標籤狀態用既有 draft，沒有新增或改動 enum。91 列 observation 是獨立來源 sidecar，使用專用品質 validator，不冒充 GoldRecord；這是 record type／格式分工，不是缺少臨床評分功能。

相容性與未完成事項分開：

| 類別 | 結論 |
| --- | --- |
| 欄位／格式 | 90 筆可由原 Gold Loader 直接讀取；manifest 使用既有 schema，無需修正 Evaluator |
| 政策未裁決 | 四任務所有 labels 保留 null/draft，case-drug 全部 pending_review；Loader 接受不代表 scoring eligible |
| Evaluator 功能缺口 | conflict prediction binding/scorer、AST 專屬 attribution、完整 missing-handling scorer 尚未具備；現有 source-consistency 是工程 proxy，不能冒充正式 Gold 指標 |
| 安全限制 | 現有 conflict metric 看到 draft label key 時可能回 not_evaluated:structured_prediction_binding_not_available；並不代表 Gold 已裁決 |

## 5. 待人工裁決與停止點

研究者需批准：來源優先序、分類與衝突分離、主 S/I/R 分母及缺失次要任務、歷史 phenotype 差異處理、attribution allowed links／多來源、missing-handling binding、conditional/strict 報告方式、source verification 的範圍與獨立 reviewer。G01 五變體固定 dev group，不能當五位獨立病人或拆 train/test。

本次只核對交接資產與 builder；沒有原始 CSV 個案鍵或原始實驗室報告的獨立驗證，不宣稱臨床真值。後續可先人工審閱 provisional，再逐任務裁決；未裁決者不得升為 verified/adjudicated。資料位置、建置指令、實測數字及保全結果見 `PILOT_A_SOURCE_DATASET_DRAFT.md`。本輪不展開 Retrieval Gold 或模型實驗。
