# Agent-led v9 來源抽查交接

審查對象：[v9 保存輸出](../data/local/agent_cases/live-complete-v9-source-options.json)，run `66e190b6-7feb-456d-9b1f-7cdba2fd64f8`；1.3.5 的 `ast_sources.py` 與新增 AST 回歸。這是合成病例的**保存來源一致性**抽查，不是臨床適當性認證，未執行新 live、網路或外部模型呼叫。因使用額度停止門檻，本報告只涵蓋下述已完成核對；其餘 16 筆 pending 與 18 筆 audit 的全面來源核對尚未做。

## AST 來源守門

1.3.5 對確定的 `susceptible`／`intermediate`／`resistant`，同時要求至少一個選定 `interpretation_basis` 的非空類別來源（`primary_states == {asserted}`），且所引用的所有有效類別一致（`states == {asserted}`）。`legacy` 或未記錄 basis 仍選 `reported_sir`；只有同值的原報告比較欄不能取代選定欄。缺選定欄、僅原報告欄或相反類別會降為 `unknown`。`conflicting` 仍可比較兩個不同類別，不會被誤當成確定 S/I/R。新增測試覆蓋同值比較可保留、缺選定、僅原報告與相反類別降級。就這約 30 行及已讀案例，未發現新的確定 S/I/R 繞過；未做所有多筆同藥 AST 組合的窮舉測試。

## v9 最終 `avoid` 的來源問題

保存 run 為 6 次呼叫、0 候選、16 `pending`、2 `avoid`。以下兩筆 `avoid` 的 audit 均標 `supported`，但各自 `ast.assessment=unknown`、`clinical.status=unknown`；因此 `supported` 不能被解讀為本審查認定整項排除理由已獲來源核對。

| 藥品 | 保存引用與可核對內容 | 尚未獲來源支持的聲明 |
| --- | --- | --- |
| levofloxacin | `doc_d797ce24ae2a7c7f5d23_chunk_0015`，DailyMed `1.12 Uncomplicated Urinary Tract Infections`。原文提成人、*E. coli* 與「無其他治療選項時保留使用」；audit quote 是快照逐字子串。 | Synthesis/audit 稱「WHO 及藥品說明書」建議保留，但唯一 audit 引用是 **DailyMed，不是 WHO**。又稱本例 AST「中介」及「有其他敏感藥物可用」；audit `fact_refs` 只有 `allergies.status`、`renal.egfr`，沒有本藥或其他藥的 `ast_results.N.*`。AST 守門已將本藥降為 unknown。 |
| tetracycline | `doc_71edc13aec9a7ba7c621_chunk_0007`，WHO AWaRe lower UTI 成人圖表，PDF 297／印刷 281。原文列其他下尿路感染用藥；audit quote 是快照逐字子串。 | 選段**沒有 tetracycline 藥名**，也沒有 penicillin 交互作用或腎毒性文字，不能支持整項 `avoid` 理由。Synthesis/audit 稱本例抗藥，audit `fact_refs` 同樣只列過敏／腎功能，未核對本藥 AST；AST 守門已降 unknown。 |

兩筆 audit 均回報 `basis=mixed`、`infection_match=population_match=drug_match=supported`，但上述引用與病例欄位不足以解釋這些支持標籤。它們沒有形成候選，然而最終 `avoid` 仍可能被閱讀成已確認的排除理由；需將其視為待審查的模型判斷。

## 未完成範圍

未逐項核對其餘 16 筆 `pending` 的引文、audit 判斷、臨床風險或整合理由；也未全面核對 parent 所述 18 筆 audit `supported`。未重跑 1.3.5 全套測試；parent 已回報後端 292 passed。本報告僅保存已完成抽查，不外推到整個 run 的來源正確性。
