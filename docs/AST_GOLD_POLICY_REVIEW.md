# A_source Gold Policy Review

日期：2026-10-26。審查對象：`AST_SOURCE_GOLD_POLICY.md`／`ast-source-policy-0.1-draft`。本文件是唯讀核對結果及**待人工核准的建議**，不構成政策批准、獨立標註或正式 Gold release。未變更任何程式、病例或既有 Gold，也未執行模型／大型測試。

## 1. 已確認的資料事實與單位

五例 `agent-complete`、`agent-ast-conflict`、`agent-allergy`、`agent-renal`、`agent-evidence-mismatch` 都是 revision 4，位於各 history array 的 index 3。五檔 SHA-256 皆符合 `data/handoff/manifest.json` 的 path/hash/revision。共 91 列 AST、90 個 `(case_id, revision, drug_code)`，全部 interpretation_basis 為 CLSI_2022_pheno。

唯一重複藥品為 agent-ast-conflict 的 amoxicillin_clavulanate：

| 項目 | 原列 | 追加列 |
| --- | --- | --- |
| 檔案 | `data/handoff/cases/agent-ast-conflict.json` | 同左 |
| 完整 JSON pointer | `/3/case/ast_results/0` | `/3/case/ast_results/18` |
| case snapshot pointer | `/ast_results/0` | `/ast_results/18` |
| reported_sir | S | R |
| source_phenotype | Susceptible | Susceptible |
| clsi_2022_phenotype | Susceptible | Susceptible |
| interpretation_basis | CLSI_2022_pheno | CLSI_2022_pheno |

兩列所有其他欄位相同，包含 raw_measurement、method、standard/version、source；沒有不同採檢時間或新檢驗的證據。`backend/scripts/build_agent_cases.py:77` 明確 deepcopy 原列、翻轉 reported_sir 後 append，且記入 simulated_fields。故為**人工注入的不同 reported 判讀記錄**，不能當成獨立檢驗或完全相同的重複資料。

保留 91 列原始 observation；建立評估視圖時，該 case×drug 只形成一個單位，連到 index 0、18 兩列。這是評估單位的 grouping，不刪除或改寫原列；禁止 last-write-wins、S/R 多數決或只保留任一列。91 與 90 的差異可完全由此解釋，未發現其他重複藥物。

列級盤點互斥合計：80 列三類別欄位一致、5 列 levofloxacin 歷史 phenotype 差異、5 列 ertapenem 選定來源缺失、1 列 reported/selected 矛盾。同藥 reported S/R 衝突則是 **1 個單位、涉及 2 列**。不將列數、藥物數及獨立病例數互換。

## 2. 推薦政策裁決表

| 問題 | 推薦規則 | 核准前狀態／理由 |
| --- | --- | --- |
| interpretation_basis | 明確 CLSI_2022_pheno 選 clsi_2022_phenotype；source_report 選 source_phenotype；明確 legacy 選 reported_sir。保留原值，只做 S/I/R 名稱正規化；不回退其他欄、不重算 breakpoint | Pilot 只驗證第一種；其他模式需獨立來源例證。未知 basis 不猜測 |
| reported 與 selected 衝突 | **分類回答指定來源是什麼，偵測回答是否存在資料矛盾。** selected 全為 S 時，建議來源分類 Gold 接受 susceptible，另外標 reported conflict=true | 本例仍為 draft/missing_gold；此建議須人工核准，不能自行升格。MVP 原有暫緩規則保持原樣 |
| selected 缺失 | 資料層記 selected_category=null、selected_source_status=missing、availability=present；輸出層可依核准規格期待 unknown；評估層主 S/I/R accuracy 不納入 | missing 是來源狀態，unknown 是預測類別，not_evaluated 是評估狀態，三者分開 |
| levofloxacin 歷史差異 | 保存 source_phenotype=Susceptible、selected=Intermediate、reported=I；建議分類接受 intermediate，另記 historical_vs_selected_difference=true | 不把歷史欄當錯誤資料，不因 S/I 不同直接列主要 conflict positive；其差異的臨床成因未核實 |
| 尚未獨立核實標籤 | provisional 只供盤點，不能進正式 Gold 分母；獨立核對來源與政策後才 verified。資料核實、政策核准、Gold 裁決分別記錄 | Schema 的 review_status 仍沿用 draft/in_review/adjudicated/rejected；不創造新的合法 enum |
| source_case_group | 五例固定同一 G01-provisional dev group，manifest 記 grouping_basis/sources；不得按 case ID 拆 train/test 或將 drugs 當獨立病人 | source_case_group 為外部研究分組，並非病人識別；不同臨床情境不使來源獨立 |
| Run／handoff 身份 | 先比對 asset hash，再抽取明確 revision；比較保存 Run.case_snapshot 的版本化 hash，不能以「最新版」替代 Run 所用版本 | 不同 hash 先拒絕對齊，待明確、可審查的轉換證明；禁止僅因同 ID/revision 就放行 |

建議增加 metadata `verification_status=provisional|verified|rejected`，只放在未來 Gold 的 provenance/payload，**本輪未改 Schema**。verified 應明定為「已核對指定交接資產」，不宣稱原始檢驗生物學真值；adjudicated 還要求政策版本、標註人員、獨立 reviewer 與裁決紀錄。先前模型／Mock／Audit 輸出均不能當 verifier。

## 3. 正式評分資格與分母

### 3.1 共同門檻

一個正式單位必須具備：case/revision/hash/group 對齊、完整原列 pointers、已核准政策版本、獨立來源核對及 adjudicated 的任務 Gold。這五例尚未建立這些正式標註，**目前正式 eligible Gold 分母是 0，分數應為 null**。下列 85/90 等數字均為完成上述門檻後的潛在分母，不是已發布 Gold 或本輪算出的 Agent accuracy。

正式分母排除：未裁決／provisional Gold、身份不符、未知 basis、無法恢復來源座標、任務答案不唯一且政策未決等。每項保留排除原因與 requested coverage；不能把排除後的較高分數當成全資料成績。原始 row schema 壞值記 invalid_input/source，並非 Agent prediction error。

### 3.2 AST Source Classification Accuracy：以 case×drug 評分

建議主指標只量測**已知 S/I/R 來源類別**，將缺失處理能力另報，避免 unknown 樣本增加主 accuracy。

令 C 為共同門檻通過、選定來源存在唯一已識別 S/I/R 的 case×drug 集合。reported 衝突不改變 selected 唯一性；若已批准「分類與衝突分開」，該單位可進 C。反之，衝突政策未決則排除並列 missing_gold。

- Pilot 潛在 `|C|=85`：84 個無主要衝突的已知類別單位（含 5 個 levofloxacin）＋1 個 reported 衝突但 selected=S/S 的單位。
- 若只剩 conflict 分類政策未決且其餘均已 adjudicated，最多為 84，並明示排除 1；不能先假設全部已核准。
- 5 個 ertapenem 不進主 C；不把歷史 S 回填，也不以 unknown 當主分類正確。
- 令 E 為 C 中有完整合法 AST 類別輸出的單位，`Accuracy_conditional = 正確類別數 / |E|`；unknown/conflicting 是合法類別，在已知 S/I/R 任務中屬 prediction error，仍在 E 中，另報 abstention。
- 同時必報 `prediction_coverage=|E|/|C|`、invalid/missing/failed counts，以及 `strict_task_success=正確類別數/|C|`。invalid/missing 輸出不假裝為某個錯誤類別，但 strict success 不給成功 credit。
- 方法根本沒有可對應的 AST 輸出契約／adapter 時，整項 not_evaluated；不能以 0 取代尚未建立的可比性。

分母為零均為 null。主指標中的 `conditional` 與 `strict` 必須具名；不可只展示排掉壞輸出的 conditional 分數。

### 3.3 選定來源缺失：獨立次要任務

建立 `selected_source_missing_handling` 次要任務，潛在 5 個 ertapenem 單位。來源 null 可由資產核實；在缺失→unknown 規格已核准且該任務 Gold 已完成時，合法 unknown 得分、S/I/R 為無來源支持的分類錯誤。無藥列是 invalid/missing output，不等於 unknown。

如另報含 unknown 的 overall source-state accuracy，必須以不同名稱、完整說明政策後才可能使用 90 個單位；不能與主 S/I/R accuracy 混報。缺失資料本身不等於缺 Gold：來源 missing 可以有完整、可靠的「缺失處理」Gold。

### 3.4 Conflict Detection Evaluation

來源端獨立標註三旗標：reported_vs_selected_conflict、within_reported_conflict、within_selected_conflict。任一已知 true 即 positive；全部所需非空類別、basis 與列集合充分可觀察且均 false 才是 negative。歷史 phenotype 差異另保存，不納入主要陽性定義。

- 共同門檻通過後的潛在 D 為 **85 單位＝1 positive＋84 negative**；5 個 ertapenem 為 unassessable，排除主要 conflict 分母但保留 coverage。
- conflict 的 index 0/18 合為一個 positive，不計兩次。levofloxacin 5 個單位是 negative（對本任務定義），不是衝突漏檢的 5 個 FN。
- 必須有事前指定、人工可審查或結構化的 Agent Boolean prediction binding。只輸出 unknown／conflicting 不足以證明偵測了哪一種衝突；現有 Run 缺這種 binding，**目前偵測能力為 not_evaluated，不能報 0% 或 100%**。
- 令 E_D 為 D 中有合法 Boolean prediction 的集合：`Accuracy_conditional=(TP+TN)/|E_D|`、`Precision=TP/(TP+FP)`、`Recall_conditional=TP/(TP+FN)`。TP/FP/TN/FN 僅由 E_D 的明確對照形成。
- 必報 `binding_coverage=|E_D|/|D|`、positive/negative 各自 coverage，以及 abstention/invalid/missing counts。已具備適用 binding 協定的實驗另報 `StrictDetection=TP/Gold positives in D`、`StrictTaskSuccess=(TP+TN)/|D|`：未回答的 positive 未偵測成功，但另記為 abstention，不偷改原 confusion label。
- 已確認沒有 positive 時 recall=null；沒有 affirmative prediction 時 precision=null；均不填滿分。只有一個且人工注入的 positive，不能支持穩健泛化或統計顯著性。

### 3.5 狀態與計分裁決表

| 情況 | 資料／評估狀態 | 分母與結果 |
| --- | --- | --- |
| 完整 Gold；正確合法分類 | evaluated | 進 E，正確數＋1 |
| 完整 Gold；合法但錯的分類 | evaluated prediction error | 進 E，正確數不增加；unknown 亦按目標任務判斷 |
| 來源 selected=null | source missing | 不進主 C；可進有核准 Gold 的次要缺失任務 |
| Gold 未有／未裁決 | missing_gold | 不進 C/D，列入 requested 的 Gold coverage 缺口 |
| 輸出缺藥列、重複或非法 enum | invalid_output | 不進 conditional 的 E/E_D；保留在已合格 C/D 的 strict 成功率分母 |
| 執行失敗、沒有語意輸出 | not_evaluated:execution_failed | 保留工程失敗；有任務 Gold 時保留在適用 strict 分母，不能當安全拒答 |
| 無 adapter／無可審查 prediction binding | not_evaluated | 不算語意 accuracy；先報測量能力缺口，不能偽造布林預測 |
| revision/hash/group 不符 | alignment_error／invalid_input | 阻擋該筆評分，不是 prediction error |
| C/D/E 等指定分母為零 | not_evaluated，value=null | 同時保存 numerator/denominator/reason |

## 4. Run、handoff 與 hash 的實際對齊

1. 鎖定 `data/handoff/manifest.json` 的版本及自身 hash；其 cases[] 指向的是**整個 history 檔的 SHA-256**。先驗證 blob hash，再按 revision=4 選 `/3/case`，不憑 array index 猜 revision。
2. 分別保存 history asset hash、revision、原始 case canonical hash、91 列 pointers；source CSV hash 只標來源資產，不能替代 case hash。
3. 保存 Run blob/content hash及 `run_id, case_id, case_revision`。Run.case_snapshot 通常不帶 revision，使用外層 case_revision 並核對 case_id；不能用當前 DB current_revision 代替。
4. 使用同一 `json-sorted-utf8-v1` 算 snapshot hash：不補 defaults、不改文字、日期或 AST 順序；manifest 與 Gold 的 case_snapshot_sha256 都要鎖定**被評 Run 的精確 snapshot**。來源檔 hash 另列 provenance，不能混成同一 hash 欄。
5. 本輪實際核對 `data/runtime/evaluator-mvp-20261026/saved-run.json`：Run `51905060-412e-4e04-99f3-c9a1bbbbc596`、agent-complete、revision 4，其 case hash 為 `da43f1f666d26fb1933e9b87c0ca72f60d143556862dde2a8405c1b9c795ed26`，**與 handoff `/3/case` 完全相同，AST array 也完全相同**。此前政策對 defaults 差異的提醒是一般風險，本例未發生。
6. 對未來不同 hash 的輸入，不放寬成 ID/revision 相同即通過。若確有必要正規化，另建立版本化 transformation manifest，保存 before/after hash、逐欄差異與來源 row-index 映射；經獨立核准後才能產生對應 Run 的 Gold。缺證據則 alignment_error。

## 5. 分組與來源核實邊界

五例沿用 G01-provisional，並記 builder derivation 與來源檔證據；provisional 名稱不能省略其尚待正式 release 固定的狀態。採 group split，全組留在 dev。90 個 case×drug 可作功能覆蓋描述，但不能當 90 個獨立樣本；同一藥在五變體中的相同 AST 不提供五份獨立原始來源。統計同時報 group=1、cases=5、case×drug=90、rows=91，不在單一 group 上宣稱跨患者信賴區間。

可核實的是「交接資產中記錄了什麼」與 builder 如何注入矛盾。原始 CSV 個案識別鍵已移除，未有原始檢驗／實驗室報告的獨立核實，不能稱這些 phenotype 是已驗證臨床真值。A_source verified 應附限定語與 source level，臨床適當性須另走專家 Gold。

## 6. 仍須人工確認與建草稿的完成條件

本輪推薦清單，均尚未批准：

1. 核准 basis 優先序、reported 衝突不覆寫 selected 的分類目標，以及 duplicate rows 的一藥一單位規則。
2. 核准主 accuracy 只含已知 S/I/R，5 個缺失另評；核准 levofloxacin intermediate 與保留歷史差異的規則。
3. 核准 conflict 三旗標、negative 的可觀察性、conditional／strict 分母與 unknown/invalid/failed 的處理；確認人工注入樣本須獨立分層。
4. 指定 Gold producer 與獨立 reviewer、source verification 範圍、審查紀錄及 release 版本；沒有身份與紀錄就不填 verified/adjudicated。
5. 鎖定五例 manifest、history/case hashes、G01 分組與 drug universe；目前只核實一筆 Run 的精確 snapshot 對齊，不假設其他四例已有 Run。
6. 規劃未來偵測 prediction binding 與審查方法；這是日後啟用偵測 scorer 的前提，**不阻止先建立來源旗標草稿**。

完成政策範圍與資產身份固定後，可另行授權建立 91 列來源 observation＋90 筆 case_drug **draft**；草稿可保留未裁決欄位，但未驗證標籤不得進正式分母。正式 Gold release 則須再完成獨立逐筆複核、裁決、版本固定與資格驗證。此文件不替代任何一項人工核准，本輪未開始產生 Gold。
