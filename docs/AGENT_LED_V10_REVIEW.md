# Agent-led v10 保存來源一致性審查

審查對象：[v10 保存 run](../data/local/agent_cases/live-complete-v10-audit-provenance.json)，run `bec1ebb1-1f48-4ea7-87ad-11b93e2f07e4`，版本 `agent-led-1.3.6`。本次只讀取 run 內的病例快照、AST、選中引文、來源 metadata、各 Agent 輸出及最終草稿；沒有再次執行 live、呼叫外部模型或查詢網路。這是**保存來源與聲明一致性**檢查，不是臨床適當性認證。

## 保存結果與守門效果

Run 保存 6 次模型呼叫、`errors=[]`。整合節點先產生 15 筆 `reviewable`、2 筆 `avoid`（levofloxacin、tetracycline）及 1 筆 `pending`（ertapenem）；最終輸出為 **0 candidates、0 avoid、18 pending**。18 筆最終 audit `verdict` 均為 `uncertain`，`quotes` 全為空，故沒有任何一筆可視為已獲獨立引文支持。證據節點仍有 16 筆 `supported`，但那只是較早階段的模型標籤，不等於最終 audit 通過。

新 AST 核對確實擋下部分舊問題。Levofloxacin 的原始 AST 選定 `CLSI_2022_pheno=Intermediate`，同筆另存 `source_phenotype=Susceptible`、`reported_sir=I`；audit 將三欄全列為 `category_source_refs` 後，`source_status=unconfirmed`，沒有把模型的「中介」說法放行。Ertapenem 的選定 CLSI 欄缺值，雖有原報告 `Susceptible` 與原始 `<=0.5` 字串，AST 輸出維持 `unknown`，audit 僅引用非選定的 `source_phenotype` 亦為 `unconfirmed`。Tetracycline 的選定 CLSI 與報告均為 `Resistant`，獨立 AST 來源為 `confirmed`；但文獻錨定不成立，整體 audit 仍 `uncertain`。18 筆 `claim_status` 都顯示 `consistent`，其中 levofloxacin、ertapenem 的來源仍未核對；`consistent` 只表示模型填寫的聲明類別與其 audit 類別相符，**不表示原始 AST 已確認或自由文字語意已由程式理解**。

## 仍保留在草稿／中間輸出的來源錯配

| 對象 | 保存引文與對照 | 結果 |
| --- | --- | --- |
| Levofloxacin | 草稿與 audit 聲稱「WHO 建議保留給無其他選擇者」。本聲明 `evidence_refs` 只有 `doc_d797ce24ae2a7c7f5d23_chunk_0015`、`_0060`（DailyMed levofloxacin）及三段 DailyMed ciprofloxacin，**沒有 WHO 來源**。`_0015` 的「無其他選項時保留」文字出自 DailyMed。 | 1.3.6 audit 的 WHO 來源身份檢核列出錯誤，且 AST 來源未確認；最終 pending。舊的 WHO 歸因錯誤仍存在於可閱讀的草稿文字。 |
| Tetracycline | 證據節點唯一選段是 WHO 成人下尿路感染 `doc_71edc13aec9a7ba7c621_chunk_0007`（PDF 297／印刷 281），該段**沒有 tetracycline 藥名**。整合另列 DailyMed tetracycline `doc_116bd6df43cda151daa9_chunk_0017`，其中 penicillin、抗凝血及腎毒性文字各有條件；它未支持草稿所稱本例「腎功能接近下限」。病例快照為 eGFR 92、計算 CrCl 84.1 mL/min。 | 證據節點標 `unsupported`，audit 藥名錨定失敗；雖 AST 抗藥來源確認，最終仍 pending，沒有發布成已確認的 avoid。 |
| Ertapenem | 證據節點稱本例為非複雜感染而「仍為有效選項」；唯一選段 `doc_395624bbf9c6b441592f_chunk_0005` 的 DailyMed 標題和內文只說 *complicated* UTI／pyelonephritis。病例快照記為 lower UTI、stable。 | 此選段不能單獨支持從複雜感染外推至本例。整合因引用識別碼無法核對改為技術性 pending，沒有將推論當作候選。 |
| Amoxicillin/clavulanate | 草稿稱 WHO AWaRe 將其列為「首選」。WHO 成人圖表 `doc_71edc13aec9a7ba7c621_chunk_0007`（PDF 297／印刷 281）及原始擷取 `doc_877abfd30f72ab114bcf_chunk_0600` 卻明說多藥按字母排序，除非另有註明，視為**同等治療選項**；`_0604` 是兒童圖表。 | 引文能證明「列為選項」，不能證明「首選」。最終因 audit 無選段而 pending。原始擷取與節錄屬同一 WHO artifact，不能當獨立雙重支持。 |
| Nitrofurantoin | 草稿稱本例 CrCl 84.1 mL/min「接近禁忌下限」。所列 DailyMed `doc_f594720a34acb4f779eb_chunk_0009` 寫的是 CrCl **under 60 mL/min**；WHO `doc_71edc13aec9a7ba7c621_chunk_0008` 支持 lower UTI preferred option，沒有「84.1 接近禁忌」說法。 | 「接近禁忌」是未由所列來源直接支持的病例推論；最終 pending。這裡不判斷醫療上是否應用藥。 |

另外，證據節點 `supported` 的 **amikacin、ampicillin、imipenem、ampicillin_sulbactam**，其選中 quotes 分別只有 WHO 成人／兒童下尿路感染段落 `doc_71edc13aec9a7ba7c621_chunk_0007` 或 `doc_877abfd30f72ab114bcf_chunk_0604`；這些選段均未出現各自藥名。Ampicillin、imipenem、ampicillin_sulbactam 的整合聲明仍將 WHO 說成列有該藥。這是較早證據節點的錯誤支持標籤；新 audit 沒有選段、均降 `uncertain`，最終沒有候選。

## 尚會誤讀的保存狀態與下一步

雖然 18 筆 audit 均無選段且整體為 `uncertain`，其中 **17 筆**的 `infection_match`、`population_match`、`drug_match` 仍各標 `supported`（ertapenem 為 `not_applicable`）。這些細項缺少本次 audit 的選中原文，不能拿來說明來源已支持感染、族群或藥品對應；顯示時應以整體未確認與「無引文」為準。18 筆 audit 的 `fact_refs`、`risk_checks` 亦全空，故本報告沒有將病人特定的腎功能、過敏、交互作用或風險敘述算成已獨立複核。

具體下一步：先以保存 run 做離線回歸，阻止證據節點把不含本藥的 WHO 選段標成逐藥 `supported`，並要求 WHO／DailyMed 歸因對應到本聲明實際選中的來源。再讓 audit 細項 `supported` 必須能指出本次選段與所核對的事實；若 `quotes=[]`，維持未確認的展示語意。對病例特定敘述應要求可核對的 `fact_refs`，並區分一般藥物警語與本例實際用藥史。這些是來源契約與標示工作，不應以程式硬編臨床斷點或自動把未知升為支持。

## 未核對範圍

本次對 18 筆 audit 的狀態／引文數量與證據節點的藥名錨定做全面計數，並逐字核對上表及四筆 WHO 錯配的保存原文。**未**逐條審定其餘候選草稿所有風險、劑量、交互作用和適用條件；未檢查 170 筆 evidence snapshot 的每一段、外部原始文件或來源 hash；未重跑模型、沒有新增 live，也未作臨床專家判定。
