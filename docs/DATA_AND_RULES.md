# 資料字典、展示規則與待確認事項

研究展示用／僅 synthetic 資料／非臨床使用。

## 病例版本 1.0

| 群組 | 意義與邊界 |
| --- | --- |
| case_id / schema_version / is_synthetic | 原型識別碼、交換格式版本、必須為 true；不收真實病人身分 |
| source / created_at / provenance | 來源、含時區 ISO 8601、匯入與 adapter 版本 |
| demographics | 年齡、生理性別、體重與單位；未提供用 null |
| encounter | 感染部位、嚴重程度、情境、觀測時間 |
| renal | creatinine 與單位、egfr 與單位／計算方法、透析與採樣時間；不自動套用公式 |
| allergies | known_none、known_present、unknown；unknown 不是無過敏 |
| medications | 藥品代碼、狀態、時間；不是新處方 |
| microbiology | 菌種、檢體、報告狀態與採樣時間 |
| ast_results | drug_code、mic、comparator、unit、reported_sir、方法、標準及版本、來源 |
| rapid_identification | 方法、結果、時間、來源；不直接推定敏感 |
| resistance_context_ref / policy_refs | 版本化背景與文件參照；不是個別病例的確定判斷 |

精確型別、列舉、欄位限制以產生的 JSON Schema 為準。null 表示缺少值；空 AST 陣列表示沒有可用報告；unknown 是已知狀態不明。not_applicable 是規則適用性結果，不等於 unknown。未提供資料不補值、不假定通過。

匯入保留 raw_payload、正規化病例與 warnings。結構錯誤以 HTTP 422 指出欄位；合法但不完整資料保留並由適用規則限制輸出。病例編輯建立 revision，舊 run 與 review 保留其原快照。

`data/synthetic/` 保存可重現病例及獨立預期軟體行為。第二種 alternate 格式由 adapter 轉換為相同 Case；不支援的欄位不猜測。

## 展示規則

`configs/demo/` 僅含 DEMO_ORGANISM_* 與 DEMO_DRUG_* 虛構代碼及虛構展示條件，不對應真實藥品或正式 breakpoint。

每條規則有 ID、版本、demo_only 狀態、scope、required_fields、受限制 condition、severity、action、reason、source_ref。規則引擎只解讀允許的運算，不使用 eval。結果分 matched、not_matched、not_applicable、unknown/error；未命中不代表安全。

來源 reported_sir 與系統展示規則判讀分開。缺少 AST 標準／版本、MIC 單位／比較符號，不能視為重新驗證成功。候選只限此次病例確定性允許集合；模型不得新增藥品、解除規則或生成給藥方案。

## 日後接入正式資料

1. 由臨床負責人確認適用族群、感染情境、藥品、正式標準、授權與版本。
2. 另建正式設定與 adapter，補上正式標準對照及獨立測試；不要把展示 JSON 改名冒充正式規則。
3. 正式資料不屬於本期可用範圍；現有匯入仍只接受 synthetic。

## 待主管／臨床確認

- 支援感染情境、族群與排除條件。
- 藥品與菌種清單、AST 標準名稱與版本、正式規則授權來源。
- 腎功能方法、單位與取樣時效；過敏與禁忌的權威判定方式。
- 院內政策、抗藥性背景與更新／衝突處理負責人。
- WHO／其他文件的適用版本與可用引用標準。
- 專家答案、人工標註、臨床適當性與驗證計畫負責人。
