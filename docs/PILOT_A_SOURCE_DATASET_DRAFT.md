# Pilot A_source Provisional Dataset：建置與驗收

日期：2026-10-27。狀態：**provisional／pending_review；verified Gold=0**。本輪完成來源盤點、四項任務的政策補充審查及可重現草稿，沒有人工政策批准或臨床標準答案。

## 1. 文件與交付位置

原 `docs/AST_GOLD_POLICY_REVIEW.md` 保留；Phase A 的四項指標、來源歸因／缺失處理補充位於 `docs/AST_GOLD_POLICY_REVIEW_PILOT_DRAFT.md`，兩份合讀。沒有覆寫前次政策結論，也沒有把本輪建立草稿的授權當作政策批准。

Dataset 目錄：`data/local/evaluation/pilot-a-source-v0.1-provisional/`。

| 檔案 | 數量／用途 |
| --- | --- |
| observations.jsonl | 91 列原 AST 的欄位副本、原 index、來源 pointers、機械觀察狀態與 extraction provenance |
| case_drug_drafts.jsonl | 90 筆 eval-gold-0.1/case_drug；保留所有 observation links，四任務 label 全 null/draft |
| manifest.json | 五病例的 revision、case snapshot hash、G01-provisional、完整 drug universe；符合原 Manifest schema |
| provenance.json | handoff manifest hash/version、五個 history asset hashes、原 CSV hash、snapshot hashes、原病例 provenance、extractor hash、三個 dataset 檔 hash |

這個 data/local 目錄受既有 Git ignore 保護；交接時須另外複製 dataset 與 provenance，或在相同來源資產及 extractor 版本上重建。來源 hash 不等於原始檢驗已由第三方核實。

新增工具：`backend/scripts/pilot_source_draft.py`；新增測試：`backend/tests/evaluation/test_pilot_source_draft.py`。Evaluator、Agent、Prompt、RAG、Clinical Rules 未修改。

## 2. 狀態與結果

| 來源觀察狀態 | 列數 |
| --- | ---: |
| 三欄一致／no_observed_conflict | 80 |
| 歷史 phenotype 差異（levofloxacin） | 5 |
| 選定來源缺失／unassessable（ertapenem） | 5 |
| reported/selected 矛盾（conflict index 18） | 1 |
| 合計 | 91 |

Case-drug 層為 84 no_observed_conflict、5 unassessable、1 observed_conflict，共 90；**這些是來源狀態，不是已核准 Gold labels**。全部 90 筆 payload.review_status=pending_review，四個 labels（selected_source_classification、source_conflict_detection、source_attribution、selected_source_missing_handling）皆為 draft、label=null、accepted_labels=null。所有 annotator_id=null、reviewer_ids=[]；未捏造人工複核。

amoxicillin_clavulanate 的重複來源完整保留：conflict case r4 `/3/case/ast_results/0` 與 `/3/case/ast_results/18`，同一草稿指向兩列。selected 觀察集合為 susceptible，reported S/R 矛盾另記，不任選某列、不覆寫來源。追加列 row_origin=authored_conflict_append。

`synthetic_fixture=false` 表示這是來源資產草稿，並非軟體 toy Gold；不表示病例為純真實觀察。人工注入部分由 row_origin／contains_authored_conflict 明示，所有來源仍待審查。`origin=independent_source` 表示標註資料讀自來源而非模型輸出，不能解讀為已有獨立人員核准。

## 3. 建置與驗證指令

在 `backend/` 內執行；build 拒絕任何已存在的目的目錄：

```powershell
./.venv/Scripts/python.exe -B -m scripts.pilot_source_draft build `
  ../data/local/evaluation/pilot-a-source-v0.1-provisional

./.venv/Scripts/python.exe -B -m scripts.pilot_source_draft validate `
  ../data/local/evaluation/pilot-a-source-v0.1-provisional
```

上述目錄現在已存在，後續重建必須指定新目錄。只執行 validate 不寫入資料。工具固定五例 revision 4、先核對 handoff manifest hash 與 revision，再逐列抽取；不啟動服務、不連模型、不寫 DB。重現性測試確認相同來源與工具生成的四個檔案 bytes 完全相同。

驗證器不呼叫 production AST validator，也不以 generator 的整份輸出作預期答案；它逐欄回到原 JSON pointer 核對，另檢查已盤點的數量、特殊 index、原始 hash、case-drug source links 與標註狀態。修改資料即使更新了檔案 hash，也仍需通過來源與狀態的語意核對。

Gold Loader 只讀 `case_drug_drafts.jsonl`；observations 是獨立 sidecar，不能把它丟進 Gold Loader 當 GoldRecord。provisional/pending_review 放 payload，正式 schema 的 review_status 用 draft，因此不需要欄位命名或 Schema 修正。

品質驗證應先於 Evaluator。現有 Loader 不會自行把 payload.verification_status 與 adjudicated 做完整聯動驗證；本次 validator 強制草稿標籤為 null/draft，避免資料被不慎升格。未來 release eligibility 的狀態聯動屬後續提案，本輪不改現有評分語意。

## 4. 實際測試與整合結果

執行：

```powershell
./.venv/Scripts/python.exe -B -m pytest tests/evaluation -q --tb=short `
  --basetemp ../data/runtime/pilot-source-draft-20261027/pytest `
  --junitxml ../data/runtime/pilot-source-draft-20261027/evaluation-tests.xml
```

結果：**88 passed、0 failed、0 skipped，4.16 秒**，包含原有 67 個 Evaluation tests＋21 個新增資料測試。新增測試涵蓋數量、重複 observation 遺失、pointer、revision/group/hash、缺失回填、衝突被覆寫、未核准標籤升格、case-drug links、唯讀來源、拒絕覆寫、重現性與 loader/scorer eligibility。

實際保存 Mock Run 的 CLI 整合（沒有重新分析）：

```powershell
./.venv/Scripts/python.exe -B -m app.evaluation.cli `
  --runs ../data/runtime/evaluator-mvp-20261026/saved-run.json `
  --manifest ../data/local/evaluation/pilot-a-source-v0.1-provisional/manifest.json `
  --gold ../data/local/evaluation/pilot-a-source-v0.1-provisional/case_drug_drafts.jsonl `
  --out ../data/runtime/pilot-source-draft-20261027/evaluator-integration
```

exit 0、153 observations、沒有 invalid_output/alignment_error。該 Run 為 agent-complete r4，snapshot hash 與草稿 manifest 相同；18 個 ast_classification_accuracy 都是 **missing_gold、value=null**，conflict accuracy 也沒有值。其餘四例的 72 個草稿可載入，但沒有這次 Run 對應，CLI 記錄 unmatched Gold diagnostics，不把它們加入模型能力分母。

原 MVP 的 ast_source_consistency 仍可產生工程 proxy；那不等於本次 provisional 成為正式 Gold。Source Attribution 與完整 Missing/Unknown Handling scorer 仍未實作；conflict detection 尚缺 prediction binding，沒有為本任務補造預測或改核心評分。

只跑資料驗證與 Evaluation regression，沒有跑完整 Backend／前端測試。沒有 LLM API、Ollama、GPU、套件安裝或 Git Commit。

## 5. 保全紀錄

`data/runtime/pilot-source-draft-20261027/` 保存：

- `dataset-validation.json`：91/90、zero verified Gold、來源狀態計數與 loader 相容結果。
- `evaluation-tests.xml`：88 項測試結果。
- `evaluator-integration/report.json`、`observations.csv`：實際保存 Run 的離線整合報告。
- `preservation-before.json`、`preservation-after.json`：157 項開始時資產／table maps 比對相同。

保全涵蓋 backend/app（含整個既有 Evaluation 模組）、data/handoff、既有 docs 檔案 hash；另對 mock-check/prototype.db 與 documents/rag.sqlite3 使用唯讀 SQLite 比對所有資料表完整列的 hash。原病例、Run、Review、文件索引均不變。既有工作目錄中的三個測試修改屬前次 Baseline，本輪未修改。

## 6. 待人工裁決清單

1. 核准 basis 指定來源、reported 衝突不覆寫 selected、主分類 85 個潛在單位及 5 個缺失的獨立任務。
2. 核准 conflict 三旗標與 negative/unassessable 範圍，並指定 Agent prediction binding。
3. 核准 Source Attribution 的正確版本／同藥／selected field／支持聲明條件與多來源可接受集合。
4. 決定 Missing/Unknown Handling 是否要求明確缺失理由與 null source binding；不能讓 Mock 泛用 unknown 自動得分。
5. 指定獨立 reviewer、核實範圍、review status 流程、release 版本；G01 維持同組 dev，不能當獨立病人數。

目前可執行的是來源一致性、完整性、來源定位、Schema、身份/hash 與 provisional eligibility 的工程檢查。四項正式 Gold 指標均仍缺人工核實／核准或必要 binding/scorer，所有 90 筆草稿都不可進正式評分。下一步應先人工審閱政策與來源，再依任務逐筆裁決；本輪在 provisional dataset 與驗證完成後停止。
