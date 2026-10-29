# Pilot A_source 盤點與 AST Conflict Evaluation Policy

日期：2026-10-26。政策版本：`ast-source-policy-0.1-draft`。本文件核對交接資產中的來源事實，並提出待審閱的評估政策；尚未建立或核准正式 Gold。範圍僅限五個 Pilot 的最新 revision，未修改任何資料／程式、未執行模型或大型測試。

## 1. 資料身份與盤點單位

資料位於 `data/handoff/cases/<case_id>.json`，每檔是 revision history array；以最高 revision 的 `case` 讀取，不將歷史版本混入樣本數。

| case_id | revision | source_case_group（外部研究分組） | AST 列 | 不重複藥物 |
| --- | ---: | --- | ---: | ---: |
| agent-complete | 4 | G01-provisional | 18 | 18 |
| agent-ast-conflict | 4 | G01-provisional | 19 | 18 |
| agent-allergy | 4 | G01-provisional | 18 | 18 |
| agent-renal | 4 | G01-provisional | 18 | 18 |
| agent-evidence-mismatch | 4 | G01-provisional | 18 | 18 |
| 合計 | — | 1 個同源群組 | **91** | **90 個 case×drug** |

`source_case_group` 並非病例 JSON 既存欄位；延用設計文件／MVP 的外部分組提案。`G01-provisional` 是衍生與防洩漏群組，不代表患者 ID。五例皆具有來源檔 hash `76099ebbe1aca384dd4a83cd9e9cdbed1b21bf86294b1a54485cc1e66e453fe5`、`source_record_id=null`。Builder 明確 deepcopy 同一 base；前 18 列 AST 的四個核對欄位一致，conflict 例額外追加一列。

依據：`backend/scripts/build_agent_cases.py:73–80` 的 deepcopy／翻轉 reported_sir／追加列；`docs/EVALUATION_DESIGN.md` §1、§4.1、§6.2–6.5；`docs/OFFLINE_EVALUATOR_MVP.md` §3.3、§5。交接包無原始 CSV 個案鍵，因此不能獨立核實原檢驗真值，也不能將五例當作五位獨立病人。

## 2. 實際 AST 欄位比較

以下 index 為各病例 `case.ast_results` 的 **0-based 原始順序**，不可排序後拿新 index 回填來源。全部 **91/91** 列 `interpretation_basis="CLSI_2022_pheno"`，選定欄位為 `clsi_2022_phenotype`。

| index／適用病例 | drug_code | reported_sir | source_phenotype | clsi_2022_phenotype | 判定 |
| --- | --- | --- | --- | --- | --- |
| 0／全部 | amoxicillin_clavulanate | S | Susceptible | Susceptible | 一致；conflict 例另有 index 18 |
| 1／全部 | amikacin | S | Susceptible | Susceptible | 一致 |
| 2／全部 | ampicillin | S | Susceptible | Susceptible | 一致 |
| 3／全部 | aztreonam | S | Susceptible | Susceptible | 一致 |
| 4／全部 | cefazolin | S | Susceptible | Susceptible | 一致 |
| 5／全部 | ciprofloxacin | S | Susceptible | Susceptible | 一致 |
| 6／全部 | ceftriaxone | S | Susceptible | Susceptible | 一致 |
| 7／全部 | ertapenem | null | Susceptible | null | 選定來源缺失，禁止回退 source_phenotype |
| 8／全部 | cefepime | S | Susceptible | Susceptible | 一致 |
| 9／全部 | gentamicin | S | Susceptible | Susceptible | 一致 |
| 10／全部 | imipenem | S | Susceptible | Susceptible | 一致 |
| 11／全部 | levofloxacin | I | Susceptible | Intermediate | reported 與選定來源一致；歷史 phenotype 不同 |
| 12／全部 | meropenem | S | Susceptible | Susceptible | 一致 |
| 13／全部 | nitrofurantoin | S | Susceptible | Susceptible | 一致 |
| 14／全部 | ampicillin_sulbactam | S | Susceptible | Susceptible | 一致 |
| 15／全部 | trimethoprim_sulfamethoxazole | S | Susceptible | Susceptible | 一致 |
| 16／全部 | tetracycline | R | Resistant | Resistant | 一致 |
| 17／全部 | piperacillin_tazobactam | S | Susceptible | Susceptible | 一致 |
| 18／僅 agent-ast-conflict | amoxicillin_clavulanate | R | Susceptible | Susceptible | 人工追加：reported 與選定來源矛盾 |

列級互斥分類：**80 列三欄非空且一致、5 列歷史 phenotype 差異、5 列選定來源缺失、1 列 reported／selected 矛盾＝91 列**。前兩類共 85 列 reported 與 selected 的非空類別相符；但歷史差異需保留其來源資訊。

衝突計數必須指名定義：

- reported 與 selected 的非空跨欄位矛盾：**1 列**（conflict index 18）。
- 同藥 reported 同時 S/R：**1 個 case×drug**，涉及 conflict 的 index 0、18 **兩列**。
- 同藥 selected 多類別矛盾：**0 個 case×drug**；該藥 selected 是 S/S。
- 非空歷史 phenotype 與 selected 不同：**5 列 levofloxacin**，屬不同來源／依據的差異，不能自動當失敗或臨床衝突。
- 若僅以「任兩個非空欄位類別不同」粗算，為 **6 列**；此數不等於主要衝突偵測 Gold 的陽性數。
- ertapenem 的 5 列為「有 AST 列但選定類別缺失」，不是未測、不是 R，也不是已確認臨床不可用。

## 3. 評估政策：類別與衝突分開

### 3.1 共通來源規則

只將 `S/Susceptible → susceptible`、`I/Intermediate → intermediate`、`R/Resistant → resistant` 作字串對應，保留 raw value。依據映射：CLSI_2022_pheno 選 clsi_2022_phenotype；source_report 選 source_phenotype；明確 legacy 選 reported_sir。未知／缺失 basis 不默認 legacy。五 Pilot 實際僅涵蓋第一種。

不從 MIC/raw_measurement、resistance_context、Mock、Audit 或 validator 推導答案；不把同一藥的重複列多算一次分類正確。

### 3.2 任務 A：selected_source_classification

單位為 case×revision×drug；目標是忠實讀取指定來源，與處方安全性分開。

| 資料情況 | 可核實事實／提議政策 | 正式評分資格 |
| --- | --- | --- |
| 選定來源非空且無矛盾 | 記實際 S/I/R；核准政策後以單一對應 label 評分 | A_source 標註完成且 adjudicated |
| levofloxacin 歷史 S、selected I、reported I | 保留歷史差異；建議分類目標為 intermediate，不採多數決 | 先由政策審閱者核准來源優先序 |
| ertapenem selected=null、reported=null、歷史 S | availability=present，selected_category=null；建議系統分類目標 unknown，禁止回退歷史 S | 缺失到 unknown 的映射需核准；缺失本身可直接核實 |
| conflict amoxicillin_clavulanate selected S/S、reported S/R | 保存 selected 事實為 susceptible；**目前 accepted_labels=null，draft** | 待裁決：是否在「選定來源讀取」任務接受 susceptible 並另外標衝突；未核准前 missing_gold |
| selected 本身有多類別、混合 basis、部分列缺失／未知值 | 不自行決定 conflicting/unknown 或挑某列 | 本 Pilot 未出現；未定政策時保持未評估 |

建議將「來源讀取的 susceptible」與「需處理衝突」同時保存；但本輪不把這項建議升格為已裁決 Gold，也不改 MVP 現有衝突暫緩規則。不得僅因 reported R 就把此藥分類 Gold 設 resistant。

Gold 已有合格答案後，accuracy 為命中 accepted_labels 的 case×drug 數／可評 case×drug 數。合法 unknown 對已知類別是 evaluated 下的未命中，另記 abstention；Gold 缺席是 missing_gold。沒有可評單位時 value=null，不能填 0。

### 3.3 任務 B：source_conflict_detection

預先固定三種可直接從來源核對的旗標：`reported_vs_selected_conflict`、`within_reported_conflict`、`within_selected_conflict`。非空已識別類別才互相比較；歷史 phenotype 差異另記 `historical_vs_selected_difference`，不直接列入主要 conflict positive。

主要偵測任務建議定義：前三種旗標任一 true 為 positive；全部可充分觀察且均 false 才為 negative。選定來源缺失時，若沒有明確已知矛盾，保持 unassessable，不能把「沒有看到衝突」當完整 negative。

在此**待核准定義**下，90 個 case×drug 為：1 positive（conflict/amoxicillin_clavulanate）、84 negative、5 unassessable（ertapenem）。這是機械來源盤點，不是已產出的正式 Gold labels。

偵測評估使用獨立來源旗標與 Agent 的明確 prediction binding 對照；accuracy=(TP+TN)/可評單位，detection recall=TP/(TP+FN)，另報 precision、FP 與 abstention。分母為 0 均為 null。任務 A 輸出 unknown 或 conflicting，不能自動推論任務 B 已成功。

現行 Run 沒有對應上述旗標的結構化 prediction，MVP 因此仍 not_evaluated；下一階段可先規劃人工可審查的 binding，不能拿 Audit verdict、自由文字關鍵字或來源旗標本身充當 Agent 的預測。

## 4. 可追溯的 Gold Schema 提案

沿用 MVP 的 `eval-gold-0.1`／`case_drug`，每個 case×drug 一筆（規劃 **90 筆**）；保留 91 列來源觀察，不將它們當 91 個獨立分類樣本。以下為欄位規格，沒有建立 JSON/JSONL Gold 檔或虛構 reviewer。

```text
schema_version: eval-gold-0.1
record_type: case_drug
record_id: 穩定的 case/revision/drug/version 識別
case_id / revision / case_snapshot_sha256
source_case_group: G01-provisional
drug_code
synthetic_fixture: false（正式來源標註；人工注入列另在 payload 明示）
labels:
  selected_source_classification:
    accepted_labels: null，待政策核准與獨立審閱後填入
    ground_truth_tier: A_source
    review_status: draft
    policy_version: ast-source-policy-0.1-draft
    source_rows: 每列的原 index、selected field JSON pointer、raw value
    annotation_provenance: 見下
  source_conflict_detection:
    label: null，待核准任務定義與審閱後填 Boolean
    ground_truth_tier: A_source
    review_status: draft
    policy_version / source_rows / annotation_provenance
payload:
  source_asset_path / source_asset_sha256 / history_array_index
  canonicalization: json-sorted-utf8-v1
  grouping_basis / grouping_sources / source_dataset_sha256
  observations: 每列 index、drug_code、interpretation_basis、四欄原值
                JSON pointers、selected_field、normalized_category
                row_origin: source_preserved | authored_conflict_append
                row_origin_basis: builder 路徑與行號
  source_flags: 三種 conflict、historical_difference、selected_missing
  availability / selected_category / conflict_observability
  adjudication_question / decision_rationale
annotation_provenance:
  source_assets（含 history hash 與 JSON pointer）
  annotation_guideline_version
  origin: independent_source
  annotator_id: null
  qualification_role: null
  reviewer_ids: []
```

`synthetic_fixture=false` 不宣稱病例為真實完整臨床紀錄：此旗標只避免將軟體 toy fixture 當正式標註；conflict index 18 必須明示人工注入，研究時另外分層。真實 AST 與人工臨床情境仍依原病例 provenance 保存。未有 annotator/reviewer，不得填 adjudicated。

來源 pointer 有兩種座標：history asset 的 `/<history_array_index>/case/ast_results/<index>/<field>` 與 case snapshot 的 `/ast_results/<index>/<field>`；兩者均記錄，不混用。raw selected=null 與未完成的 label=null 使用不同欄位與 review_status 區分。

## 5. 身份固定與可驗證邊界

以下 snapshot hash 僅對 handoff 最新 `case` 原物件作 json-sorted-utf8-v1：key 排序、UTF-8、compact separators、不補 defaults、不改陣列／文字／日期。不能直接拿它對齊補齊 null/default 後的 DB／Run snapshot；下一階段須保存明確的正規化契約或分別鎖定兩個 snapshot，禁止默默放寬 hash。

| case_id | handoff case snapshot SHA-256 |
| --- | --- |
| agent-complete | da43f1f666d26fb1933e9b87c0ca72f60d143556862dde2a8405c1b9c795ed26 |
| agent-ast-conflict | 609ad9eb50640845de74ce72dc2ba0972f57c8021fe16892430661f347406787 |
| agent-allergy | 0b16c150d10544686a2291f98399c0c66c08c41614d5957c928a9dd84ef7a2f0 |
| agent-renal | 813121d9d603773c0b8126ba54d2816376b16fdf418dbf7a184d455dae1f50de |
| agent-evidence-mismatch | cb1341829dd59360399696a88989e7bac22d69a6f35961744642d8fff9e7ce05 |

可直接核實：revision、91 列四欄原值、91 列相同 basis、選定來源缺失、非空欄位差異、重複藥列、builder 的人工追加、同源來源 hash。來源事實可由獨立 extraction＋人員複核建立 A_source，無須用模型判斷。

仍需人工確認／裁決：來源優先序的正式評估政策、歷史差異是否按來源任務排除、缺失到 unknown 的映射、conflict 藥物的 accepted_labels、偵測 negative 的可觀察性條件、實際標註與 reviewer 身分、輸出 prediction binding，以及 Run/handoff 身份正規化方法。臨床 breakpoint、療效與用藥安全性不在 A_source 可核實範圍，仍需適當醫療專家與獨立證據。

## 6. 下一階段建檔順序

先核准上述兩個任務政策與 hash 對齊方式，再建立五病例 manifest、91 列可追溯 observation 和 90 筆 case_drug 草稿。由獨立人員複核來源與爭議項，完成者才升為 adjudicated；未裁決者保留 missing_gold，缺 prediction binding 的偵測維持 not_evaluated。五變體均留在同一 dev group，不拆成獨立 train/test，也不使用 Mock／Agent Audit 作標準答案。
