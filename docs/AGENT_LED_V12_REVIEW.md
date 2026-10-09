# v12 Clinical Agent 唯讀引用與事實來源審查

日期：2026-10-09。範圍：`data/local/agent_cases/live-complete-v12-context.json` 和 `v12-source-layer-checks.json` 中的 Clinical Agent 18 項逐藥輸出、78 段引文，以及其 `allergy`、`renal`、`interactions` 的病例事實引用。對照 v11 只有 Clinical 輸入過大失敗的狀態；不重做 v11 已完成的 WHO 下泌尿道 18 藥語意表，沒有呼叫外部模型或啟動新 run。本文件核對**被選取的文字對聲明是否貼切**，不是治療建議。

## 執行結果與實際改善

- run `6d05f0aa-5f57-43b9-a54d-e133e81b9657`、病例版本 4、workflow `agent-led-1.4.1`。Clinical 輸入約 155,015 字元，完成 18 列與 78 段引文；其中 12 列 `no_identified_risk`、2 列 `caution`（amikacin、gentamicin）、4 列 `unknown`（ampicillin、imipenem、levofloxacin、tetracycline）。這比 v11 在呼叫前 `AGENT_INPUT_TOO_LARGE` 的情況多了可追溯的分項回覆。
- 保存的 87 段 Evidence 引用與 78 段 Clinical 引用合計 165 段，`v12-source-layer-checks.json` 顯示全部可在快照字面找到、匯出與保存 run 相同。字面存在不保證引文支援相應風險面向。
- Clinical 的 18 列均從人工編製的病例事實取 `allergies.status=known_none`、`renal.egfr=92`、`renal.crcl=84.1` 與空的 `medications`；輸入另含 `medication_history_status=reviewed_none`。這使「目前清單無用藥」在本測試情境有來源，但所有交互作用分項的 `fact_refs` 只列 `medications`，沒有列實際確認清單完整性的 `medication_history_status`；空陣列本身不足以證明已核對無用藥。18 列腎功能分項也只列數值，沒有列 `renal.crcl_calculation_method` 或 `simulated_fields`：本例 CrCl 是由人工情境資料推算，**不是實測值**。數值可用來做此測試情境分析，但輸出不應讓它看似真實病人觀察。
- 驗證層已保守處理部分錯誤：ampicillin 的 interactions 含一個未在該藥 `quotes` 的 ampicillin-sulbactam ref，imipenem 的 allergy 含一個未在 `quotes` 的 WHO ref，兩項被降為 `unknown`；levofloxacin、tetracycline 的整體狀態與分項敘述不一致也被降為 `unknown`。這些降級沒有修正下表仍被接受的語意錯配。

## 逐藥 Clinical 引文核對

| 藥品／最終 Clinical 狀態 | 選取引文與病例事實的核對 |
| --- | --- |
| amoxicillin_clavulanate／`no_identified_risk` | 本藥 DailyMed 過敏禁忌、嚴重腎功能不全及 probenecid 交互作用片段，與三分項相關。另引口服避孕藥片段；目前用藥清單經確認為空，該片段只是一般風險背景。 |
| amikacin／`caution` | 本藥標示的氨基糖苷交叉過敏、腎／耳毒性與監測片段有關；但把**體外混合失活**概括成病人體內與 β-lactam「拮抗」須保留原文限定，且同列另引體外協同作用片段，不能當單一無條件交互作用結論。 |
| ampicillin／`unknown` | 過敏禁忌引文相關。腎功能 `chunk_0015` 是 Drug Interactions、`chunk_0012` 是病人衛教，均未支持「正常腎功能無需調整」；交互作用另引用 ampicillin-sulbactam 的未選段，被程式降級。 |
| aztreonam／`no_identified_risk` | 過敏禁忌相關；腎功能引文為老年用藥與肝／腎受損需監測，不能直接證成個人「無需調整」。交互作用 refs `chunk_0006`、`0007`、`0011` 分別為過敏禁忌／警告、致癌生殖研究，不支持下一步所寫的 aminoglycoside 監測。 |
| cefazolin／`no_identified_risk` | 過敏與 probenecid 片段對題；腎功能主要引低尿量／腎損傷及老年段落，屬間接背景，不能替代針對本例 CrCl 的來源推論。 |
| ciprofloxacin／`no_identified_risk` | 過敏、腎排除與 QT／CYP 交互作用引文對應三面向；這個狀態**只**表示模型在所列過敏／腎／目前用藥三面向未辨識風險，不解除 Evidence 階段「無其他選項才保留使用」的限制。 |
| ceftriaxone／`no_identified_risk` | 過敏、腎／肝受損與 chloramphenicol 體外拮抗來源可定位；額外尿路沉積症段落偏兒科，不能從「本例腎功能數值高」推成所有腎／泌尿風險均不存在。 |
| ertapenem／`no_identified_risk` | 過敏禁忌與 probenecid 交互作用引文相關；腎功能 `chunk_0023` 為老年用藥、`chunk_0025` 為**肝**功能受損，未直接支持本例腎功能「無需調整」。 |
| cefepime／`no_identified_risk` | 過敏禁忌、CrCl 閾值、aminoglycoside／強利尿劑交互作用引文與各面向相符；沒有目前合併用藥須由病例完整性狀態支撐。 |
| gentamicin／`caution` | 本藥交叉過敏、boxed 腎／耳毒性、其他腎毒性藥物與強利尿劑的原文風險有保留；`chunk_0013` 也明說體外混合失活在正常腎功能、不同途徑給藥病人未被證實，解釋時不能省略。 |
| imipenem／`unknown` | **嚴重來源錯配。** 腎功能所引 WHO `doc_877abfd30f72ab114bcf_chunk_1285` 實為 **plazomicin** 劑量表；「DailyMed imipenem」`doc_2dab15a0a139f788d037_chunk_0028/0030/0031` 實述 **RECARBRIO（imipenem/cilastatin/relebactam）** 的機轉／體外微生物互動，不能無條件當單一 imipenem 的過敏、腎功能或交互作用依據。allergy 另有未選 WHO ref 已被降級，但 renal 與 interactions 仍顯 `no_identified_risk`。 |
| levofloxacin／`unknown` | 本藥過敏、CrCl <50 腎功能閾值、theophylline 警示引文存在；整體「輕度受損需調整」與分項「目前正常無需調整」不一致，程式已降級。另有 AST `I`，不能由 Clinical 風險分項推出本例藥敏。 |
| meropenem／`no_identified_risk` | 過敏禁忌可定位。交互作用 `doc_ce61df1efa1ab1de7c3a_chunk_0028` 談**體外與 aminoglycosides 協同／微生物活性**，沒有 valproic acid；下一步「避免與 valproic acid 合用」可能是別處資訊，但**非這段引用支持**。腎功能主要引老年人段落，對本例數值僅間接。 |
| nitrofurantoin／`no_identified_risk` | 引文中的腎功能禁忌門檻可與本例 CrCl 比對；`chunk_0014` 雖開頭為腹瀉衛教，同一完整引文後段明載含 magnesium trisilicate 制酸劑降低吸收，故不應僅憑前段把此交互作用誤判成無引文。 |
| ampicillin_sulbactam／`no_identified_risk` | 過敏禁忌對題；腎功能唯一 ref `doc_02b50f9b6472281fa8f0_chunk_0020` 是 **Drug Interactions**（probenecid、allopurinol、aminoglycoside 體外失活），不是本例腎功能「無需調整」的依據。交互作用面向引用同段則相關。 |
| trimethoprim_sulfamethoxazole／`no_identified_risk` | 過敏禁忌與藥物交互作用片段相關；腎功能引文主要談老年／腎功能受損與高鉀風險，不能把「目前 CrCl 高」擴張為所有風險已排除；仍需保留原標示條件。 |
| tetracycline／`unknown` | 過敏、腎功能警告、與 penicillin／抗凝血藥交互作用片段對題。整體「不建議」理由含病例 AST 抗藥，與三個 Clinical 風險分項皆 `no_identified_risk` 不一致，程式保守降級；AST 判斷應由 AST Agent 承擔。 |
| piperacillin_tazobactam／`no_identified_risk` | 本藥過敏、CrCl 閾值、與 aminoglycoside 體外失活的標示引文直接對題；尚未核對感染適用性與其他臨床面向。 |

## 最終邊界

Synthesis 的兩次呼叫都達 `completion_tokens=6000`，沒有可用 JSON，節點以 `AGENT_SCHEMA_INVALID` 失敗；Audit 因沒有整合聲明標為 `not_applicable`，**沒有獨立複核**。最終 0 candidate、0 `review_option`、18 pending，符合本次未完成流程，不表示 Clinical 來源錯配已被 audit 排除。此次最有價值的改善是 Clinical 不再因輸入長度未呼叫，並且部分缺引用／內部矛盾確實降級；仍需修正逐藥來源與風險面向的語意對應，尤其 imipenem 錯藥、腎功能引用交互作用／肝功能段落，以及 meropenem／aztreonam 交互作用與實際所選段落不符。
