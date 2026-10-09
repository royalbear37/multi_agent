# Agent-led 1.3.3 v8：保存來源與引用審查

審查對象：run `eff53f5a-b59d-4f56-929b-d6deca1eb52e` 的資料庫 checkpoint 與[保存輸出](../data/local/agent_cases/live-complete-v8-source-contract.json)。這是合成病例 `agent-complete` 的**來源一致性**審查，不是臨床適當性認證，也未重新呼叫模型或外部資料。最終為 6 次模型呼叫、18 藥 `pending`、0 候選；因此下述來源錯配未形成可供審閱的候選。

## 可重現的主要落差

1. **選定 AST 依據缺失，模型文字仍推論敏感。** 病例快照中 `ertapenem` 的 `interpretation_basis=CLSI_2022_pheno`，`clsi_2022_phenotype`、`reported_sir`、`mic` 均為 `null`；獨立保留的 `source_phenotype=Susceptible` 與原始 `AST_val1<=0.5` 不能填補選定欄。AST Agent 的 `assessment` 被守門降為 `unknown`，但理由仍稱「原始 MIC 值低……通常對 ertapenem 敏感，適合用於治療」。Evidence、synthesis 與 audit 又分別稱「本例敏感」。18 筆 AST Agent 的 `category_source_refs` 全填來源描述字串，而非 `ast_results.N.clsi_2022_phenotype` 等欄位路徑；`category_sources=[]`、`source_validation=unconfirmed`，最後 18 筆評估均為 `unknown`。守門有擋住候選，公開文字仍須與降級結果一致。
2. **逐藥文件引用識別碼失效後，獨立 audit 只拿到風險片段，卻有 6 筆整體 `supported`。** Synthesis 的 18 筆 `evidence_refs` 全清空，保存輸出未保留模型原填識別碼；audit 輸入的逐藥聲明沒有指引／適應症引用。僅 6 藥的 `risk_claims` 帶入共 13 個藥品警語片段。Audit 對下表 6 筆給 `basis=mixed`、整體 `verdict=supported`，並將 `infection_match`、`population_match`、`drug_match` 均標 `supported`。然而所引片段只處理風險、禁忌或監測，無法單獨支持完整聲明中的感染用途或本例 AST 類別；`fact_refs` 也只列腎功能／過敏，未指向任何 `ast_results.N.*`。其餘 12 藥為 `uncertain`、沒有 audit 引文。這裡的 `supported` 是模型欄位值，**不是本審查認定整體聲明獲支持**。

| Audit 顯示 `supported` 的藥品 | 保存引文定位 | 原文能核對的範圍與不足 |
| --- | --- | --- |
| amikacin | DailyMed `doc_5232fea78033d27130fe_chunk_0014`–`0016`，`PRECAUTIONS / General` | 談腎毒性、監測及交互作用；未在這些選段核對本次下尿路感染適應症或個案 AST 類別。 |
| gentamicin | DailyMed `doc_b96a9a1d8f382e3d4e1d_chunk_0003`、`0004`、`0013`，`BOXED WARNINGS`／`PRECAUTIONS` | 談腎／耳毒性、監測及交互作用；不能單獨支持整體排除理由或本例敏感聲明。 |
| nitrofurantoin | DailyMed `doc_f594720a34acb4f779eb_chunk_0009`、`0019`，`CONTRAINDICATIONS`／`PRECAUTIONS` | 原文有腎功能限制及不良反應警語；本次 audit 未收到用來複核感染用途的選段，也未引用本藥 AST 欄位。 |
| trimethoprim_sulfamethoxazole | DailyMed `doc_9d36c7fdbb6fa587c1ce_chunk_0040`、`0041`，`PRECAUTIONS / Geriatric Use` | 談老年、腎功能不全與血鉀等風險；病例記錄為 45 歲，不能把此警語當成本次感染與個案敏感性的整體支持。 |
| tetracycline | DailyMed `doc_116bd6df43cda151daa9_chunk_0012`，`WARNINGS / Antianabolic Action` | 談腎功能不佳時的毒性；未支持聲明中的「本例抗藥」「無適應症」兩部分。 |
| piperacillin_tazobactam | DailyMed `doc_be834cece0eb8175714d_chunk_0016`、`0017`，`Nephrotoxicity in Critically Ill Patients`／`Electrolyte Effects` | 第一段明示 *critically ill patients*，病例快照為 stable lower UTI；可供核對特定風險警語，不能據此把本例族群／感染匹配標為已支持。 |

3. **Evidence Agent 仍有 v7 型態的藥名、感染及出處錯配。** 下列是已保存的 quote span；引號內文字都能在對應快照逐字找到，但「文字存在」不等於「支持所寫結論」。

| 模型聲明 | 引文與短摘 | 來源一致性結論 |
| --- | --- | --- |
| amikacin、ampicillin、imipenem、ampicillin_sulbactam 被列為 WHO 下尿路感染選項 | WHO 成人節錄 `doc_71edc13aec9a7ba7c621_chunk_0007`（PDF 297，印刷 281）及／或兒童全文 `doc_877abfd30f72ab114bcf_chunk_0604`（PDF 299，印刷 283）；選段列 *Amoxicillin+clavulanic acid* 等 | 所選片段沒有上述四個藥名，不能支持這四筆逐藥 `supported` 的 WHO 選項說法。 |
| ceftriaxone 用於本例下尿路感染 | WHO 全文 `doc_877abfd30f72ab114bcf_chunk_1028`，PDF 504、印刷 488，標題 `Upper urinary tract infection`、`Severe cases` | 這個 WHO 選段是上尿路／重症情境，與病例保存的 stable lower UTI 不符。另有 DailyMed 引文，須分別核對，不能讓前一引文蒙混通過。 |
| ertapenem 本例敏感且可考慮 | DailyMed `doc_395624bbf9c6b441592f_chunk_0005`，`Complicated Urinary Tract Infections Including Pyelonephritis` | 選段明示 *complicated* 感染條件；病例輸入未確立該條件，且選定 CLSI 類別缺失。 |
| piperacillin_tazobactam 是尿路感染選項 | DailyMed `doc_be834cece0eb8175714d_chunk_0005`，`Female Pelvic Infections`，提產後子宮內膜炎／骨盆腔炎 | 選段不是尿路感染。 |
| meropenem 適用於複雜感染 | DailyMed `doc_ce61df1efa1ab1de7c3a_chunk_0025`，`Geriatric Use` | 選段談老年族群，未核對該感染用途。 |
| ciprofloxacin、levofloxacin 的「WHO 指引建議保留」 | 分別引 DailyMed `doc_aed31a80506dead25b15_chunk_0014`／`0015`、`doc_d797ce24ae2a7c7f5d23_chunk_0015` | 保留使用的限制可能可從藥品標示核對，但這些引文不是 WHO；來源歸屬寫錯。 |

WHO 全文與 lower-UTI 節錄在新快照共享 `source_document_id=sha256:4960ecc4fa5bab8281feda656a0da3176dafa1fd21971d87e3b2092d7dac562f`，表示同一原始 artifact；不能把兩者重複計為獨立文件。Amoxicillin-clavulanate 同時有成人 PDF 297 與兒童 PDF 299 引文；成人情境應靠成人選段核對，兒童選段不能單獨代替。

## 保存與驗證界線

本次快照共有 170 個證據片段。Evidence Agent 27 條、Clinical Agent 80 條、Audit 13 條引用均有對應 `chunk_id`，其 `quote` 均為保存片段的逐字子串；audit 的 13 條也全在該節點實際輸入中。12 筆 `uncertain` audit 沒有文件引文，6 筆 `supported` 只引用風險／警語文件。Case、AST、Evidence 三角色的 findings 都重複患者摘要；Case Agent 更把已提供的感染部位、腎功能與無已知過敏列成 `issues`，其中包含「依標準劑量使用」等未由該角色來源核對的行動句。這是輸出用途混淆，不是病例缺資料。

結論僅限於**保存輸入、引文與聲明是否對得上**。Run 的 18 藥仍為 `pending`、0 候選；本報告不認定任何藥品對真實患者適用，也不以模型的 `supported` 取代具資格者審查。
