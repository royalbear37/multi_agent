# Agent-led 1.3.1 live run：引用與來源基礎審查

審查對象：[保存的 run](../data/local/agent_cases/live-complete-v7-risk-details.json)，`91ddb348-f6a6-4576-9926-989df2447128`。這是合成病例、單次 live 模型輸出的來源核對，不是臨床適當性認證。此 run 共 7 次模型呼叫；clinical Agent 兩次輸出契約驗證失敗，最終 **0 個候選、18 個 pending**。下表的 `supported` 是模型複核欄位值，不代表本次審查接受該結論。

病例來源記錄為 45 歲女性、穩定的下尿路感染情境；有排尿疼痛和頻尿，無發燒、側腰痛、肋脊角壓痛，病史記錄無導尿管、阻塞或近期泌尿道處置。這些是病例輸入，不等同獨立診斷為「非複雜性」感染。

| 藥品 | 模型標為 `supported` 的引文 | 本次逐字核對 |
| --- | --- | --- |
| amoxicillin_clavulanate | `doc_71edc13aec9a7ba7c621_chunk_0007`，WHO 成人下尿路感染圖表；`doc_6a7f507935c3e7ab519d_chunk_0002`，DailyMed 尿路感染適應症；另引 WHO 第 291 印刷頁的表格註記 | 前兩段直接提到相應感染與藥品。複核理由額外說「腎功能正常，適合使用」；這是病例／臨床風險判斷，不能由適應症引用單獨證成。 |
| amikacin | `doc_877abfd30f72ab114bcf_chunk_0604`，WHO PDF 第 299 頁（印刷第 283 頁）；`doc_5232fea78033d27130fe_chunk_0015`，DailyMed 腎功能監測段 | 選中的 WHO 片段列兒童 amoxicillin-clavulanate、nitrofurantoin 等內容，**沒有 amikacin 的該感染建議**；藥品標示片段談腎毒性監測，未給出尿路感染適應症。兩段不能支撐複核理由中的「WHO 及藥品標示支持 amikacin 用於尿路感染」。 |
| ampicillin | `doc_71edc13aec9a7ba7c621_chunk_0028`，WHO PDF 第 307 頁（印刷第 291 頁）；`doc_6c687dc322f9778e445f_chunk_0015`，DailyMed 交互作用段 | 選中的 WHO 片段是 TMP-SMX／trimethoprim 表格及 amoxicillin-clavulanate 註記，**沒有 ampicillin 的下尿路感染選項**；藥品標示片段是交互作用，未支持該感染適應症或一般過敏結論。 |
| aztreonam | `doc_e1ab20e851d11e00c428_chunk_0002`，DailyMed 適應症 | 原文確有 *complicated and uncomplicated* 尿路感染及 *E. coli*；此部分有直接來源。複核還說患者「臨床狀況穩定，適合使用」，但其 `fact_refs` 僅有菌種及 AST 判讀，沒有 `encounter.severity` 或相關病史；適應症引文也不等於個案適合使用。 |
| cefazolin | `doc_a687927b263311da5576_chunk_0002`，DailyMed 適應症 | 原文有 *Urinary Tract Infections: Due to E. coli*，感染／藥品文字可對上。複核把「腎功能正常，適合使用」併入 `supported`，但本 run 的 clinical Agent 未產出有效風險評估；證據審查不應代替該結論。 |
| ciprofloxacin | `doc_71edc13aec9a7ba7c621_chunk_0007`，WHO 成人圖表；`doc_aed31a80506dead25b15_chunk_0015`，DailyMed 急性膀胱炎段 | 選中的 WHO 片段沒有 ciprofloxacin。DailyMed 段有成人女性、*E. coli* 急性非複雜性膀胱炎適應症，但同段明寫應保留給沒有其他治療選項的患者；複核只說「評估風險後使用」，未保留這個重要條件。 |
| ceftriaxone | `doc_eb62ef54251289f72401_chunk_0008`，DailyMed 適應症 | 本次**選中的 quote span** 只涵蓋一般原則、下呼吸道感染及中耳炎，截止於中耳炎病原列舉；其中未出現尿路感染適應症。完整文件其他位置可能有相關內容，但這段引用不能支持複核理由所寫的「標示支持尿路感染」。 |
| ertapenem | `doc_395624bbf9c6b441592f_chunk_0005`，DailyMed「複雜性尿路感染，包括腎盂腎炎」 | 原文明確限定 *complicated urinary tract infections including pyelonephritis*。病例記錄為穩定下尿路情境且未記錄常見複雜化線索；這段不能單獨證成本病例感染條件吻合。複核卻給 `infection_match=supported`。此外，AST 與整合／複核文字用「MIC 低、無抗藥紀錄，推測敏感」作理由；病例中 `mic`、`reported_sir`、`clsi_2022_phenotype` 均為 `null`，只有原始 `<=0.5` 與獨立的 `source_phenotype=Susceptible`。不能從原始數值自行推導判讀，也不能把來源標籤與 CLSI 欄混成同一依據。 |

## 可檢驗的來源契約改進

1. **AST 類別與量測分開引用。** 為逐藥 AST 輸出加入 `category_source_ref`（只能指向實際非空的 `reported_sir`、`source_phenotype` 或 `clsi_2022_phenotype`）、`measurement_ref`、`basis_description`。若聲明某藥「敏感」，必須明示使用哪個來源類別；原始 `AST_val1` 僅能作原始量測展示，不能單獨作類別判讀依據。本例可表述為「來源 `source_phenotype` 標為 Susceptible；CLSI 2022 判讀欄未提供」，而非「MIC 低故推測敏感」。另須修正病例產生器 [build_agent_cases.py](../backend/scripts/build_agent_cases.py) 及一般 CSV 轉換器 [microbiology.py](../backend/app/adapters/microbiology.py)：兩處都固定填入 `interpretation_basis='CLSI_2022_pheno'` 與相同來源說明，即使該列的 CLSI 欄是空值。這是資料來源一致性檢查，不計算 MIC 斷點。
2. **每個 `supported` 聲明對應特定原文片段與條件。** 複核輸出可拆成 `drug_mention`、`infection_condition`、`population_condition`、`material_qualifier` 的來源選段與病例條件，並要求每項聲明指向實際選中的 quote span。藥名只在鄰近片段、只引用副作用段、或引用 *complicated* 條件卻未說明病例適用時，標為 `uncertain`，留給人工核對。這保留模型判斷感染語意，但使漏讀條件可見。
3. **病例事實不要混入文件支持結論。** 複核中的「穩定」「腎功能正常」「適合使用」應分列病例欄位、來源值及風險 Agent 結果；文件適應症只能支持其明示的感染、病原與族群。對於 `clinical_agent` 失敗的 run，複核不能以 `supported` 代替臨床風險核對。既有最終 gate 擋住了候選，應維持。
4. **縮小複核負荷並保留反例。** 此次獨立複核一次處理 18 個藥品／多種聲明。可以按少量藥品或聲明分批，讓每項 `supported` 都帶條件原文與可能不符之處；無法完成時保持 `uncertain`。不要把短引文存在或模型自報 `supported` 當成機械式適用性證明。

本審查只指出保存 run 的引文與輸出之間的可見落差。原始文件及病例仍須由具資格者核對；此報告沒有評定藥品對真實患者的適當性。
