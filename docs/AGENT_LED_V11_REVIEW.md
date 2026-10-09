# v11 唯讀引用語意審查（2026-10-08）

審查對象：`data/local/agent_cases/v11-evidence-checkpoint.json`、`live-complete-v11-layered.json`、`v11-source-layer-checks.json`，同一 run `fbb4bb56-96e7-4ce9-889e-b952e0cae688`、病例版本 4、workflow `agent-led-1.4.0`。只核對保存的引用文字能否支持模型對「45 歲女性、穩定下泌尿道感染、尿液 E. coli」的感染與族群判斷；沒有呼叫外部模型、啟動新 run、修改程式，也不以本文件提供治療建議。

## 執行與邊界

- `evidence_agent` 完成 18 藥、88 段引用；`v11-source-layer-checks.json` 回報 88 段都能在對應快照找到（`bad_quote_count=0`），且匯出與保存的 run 一致。這只證明引用字面存在，不證明藥品、感染部位、族群或限制條件相符。
- `case_agent`、`ast_agent`、`evidence_agent` 有回覆；`clinical_agent` 和 `synthesis_agent` 在呼叫前因 `AGENT_INPUT_TOO_LARGE` 失敗。`evidence_audit` 是 `not_applicable`，原因是沒有整合聲明可複核，**不能計為獨立引用複核通過**。實際 3 次模型呼叫、61,227 tokens、約 119 秒；最終 `partial / needs_confirmation`，0 候選、0 `review_option`、18 `pending`，全數保留待確認。`v11-source-layer-checks.json` 的 18 列 `checks` 均為空，與 audit 未執行一致。
- 88 段引用中沒有 WHO PDF p566，保存的證據快照也沒有 p566；本次不能據此評斷 p566 的語意。WHO 原 PDF（`who`）與 `WHO AWaRe lower UTI chapter` 是同一原始文件及其節錄，不能當作兩份獨立證據。原 PDF 的文件級 `population=all` 也不能取代每頁的成人／兒童欄位判讀。

## 18 項證據 Agent 輸出逐項核對

下表的「核對」只針對**本次實際選取的引用**，不推論其他未選片段、未完成的臨床風險評估或藥品最終適用性。`supported`、`unsupported` 是模型保存的原狀態。

| 藥品 | 模型狀態 | 引用語意核對 |
| --- | --- | --- |
| amoxicillin_clavulanate | supported | WHO 成人下泌尿道頁 297／`chunk_0007` 與 DailyMed UTI／`chunk_0002` 有直接相關文字；同列 WHO p299／`chunk_0604` 是兒童體重帶，不能作成人支持或第二份獨立證據。 |
| amikacin | supported | 選取 WHO 成人 p297 與兒童 p299 的下泌尿道通用文字及其他藥物表，**沒有選到 amikacin 的本例下泌尿道適用敘述**；`supported` 缺逐藥支持。 |
| ampicillin | supported | 與 amikacin 相同的 WHO p297／p299 通用及他藥片段，沒有 ampicillin 的逐藥適用敘述；`supported` 缺支持。 |
| aztreonam | supported | DailyMed／`chunk_0002` 明列成人／兒童、E. coli、複雜與非複雜 UTI（含 cystitis），感染／菌種文字相關；其餘標題與其他器官片段不增加支持。這仍不是本例風險評估或治療優先順序。 |
| cefazolin | supported | DailyMed／`chunk_0002` 有 E. coli UTI，但段落前提是「serious infections」；本例標示穩定下泌尿道感染，嚴重度前提未由所選引用解決。其餘腎功能、其他器官片段不能補足此差距。 |
| ciprofloxacin | supported | DailyMed／`chunk_0015` 直接涉及成年女性 E. coli 非複雜膀胱炎，但同段明言應保留給沒有其他選項的患者；本病例還有其他 AST 結果，模型不能只取適應症而略過此條件。兒童 UTI 與呼吸道引文不能支持本例。 |
| ceftriaxone | supported | WHO p503–504／`chunk_1027`、`chunk_1028` 是**上泌尿道感染**，其中 ceftriaxone 位於嚴重病例；本例是穩定**下**泌尿道感染。所選 DailyMed／`chunk_0008` 未引到 UTI 適應症段落，`chunk_0007` 是其他細菌列表；本次引用不足以支持本例。 |
| ertapenem | supported | DailyMed／`chunk_0005` 只明列 **complicated UTI／pyelonephritis** 的 E. coli；保存病例是穩定下泌尿道情境，未從所選引文建立複雜感染條件。肺炎、骨盆及皮膚引文不適用此感染。 |
| cefepime | supported | DailyMed／`chunk_0004` 明列非複雜／複雜 UTI 與 E. coli，屬相關適應症文字；兒科、發熱性嗜中性球低下及皮膚片段不能獨立支持本例。標示存在不等於已完成個人風險或優先順序判斷。 |
| gentamicin | supported | DailyMed／`chunk_0006` 明言初次非複雜 UTI 原則上不適用，例外需致病菌敏感且**沒有**較低毒性藥物可用；本例的其他 AST 項尚在表中，模型沒有證明例外條件。所選引文反而構成應核對的限制，不能無條件標 `supported`。 |
| imipenem | supported | 五段 WHO 下泌尿道通用／他藥引文沒有點名 imipenem，也沒有其本例適用條件；`supported` 無逐藥文字依據。 |
| levofloxacin | supported | DailyMed／`chunk_0015` 明列成年 E. coli 非複雜 UTI，但同段設「沒有其他治療選項」保留條件；病例的 CLSI 2022 判讀為 `Intermediate`、報告 `I`，不能把來源 `Susceptible` 字樣或藥品標示直接當作本例敏感與可用。肺炎／瘟疫／複雜 UTI 引文不能解除條件。 |
| meropenem | supported | 六段 DailyMed 引文談皮膚、腹腔、兒科腦膜炎、腎功能與老人，**沒有 UTI 適應症片段**；E. coli 出現在其他器官不能轉成下泌尿道支持。 |
| nitrofurantoin | supported | WHO 成人下泌尿道 p297／`chunk_0008`、原 PDF `chunk_0601` 明列本感染情境，且對成人頁可定位；另引兒童 p298／`chunk_0009` 屬無關族群。文字支持不等於已完成個人風險核對。 |
| ampicillin_sulbactam | supported | 同 amikacin／ampicillin，WHO 成人 p297、兒童 p299 片段列的是 amoxicillin-clavulanate、nitrofurantoin、TMP 等，沒有 ampicillin-sulbactam 的本例逐藥敘述；不能混同藥名。 |
| trimethoprim_sulfamethoxazole | supported | WHO p306–307 表 23.5 的成人欄／`chunk_0027`、`chunk_0028` 直接涉及下泌尿道；同頁兒童欄和原 PDF 重複片段不可當額外獨立支持。原文還提示多地抗藥性高，需保留該限制。 |
| tetracycline | unsupported | 病例 AST 報告為 `R`，但模型所選 WHO p297／p299 引文只是其他藥與通用下泌尿道敘述；「表內沒列」本身不足以證明 tetracycline 對所有情境不適用。最終待確認是審慎的。 |
| piperacillin_tazobactam | supported | DailyMed 所選四段為女性骨盆感染、皮膚感染、肺炎與給藥段落，沒有本例 UTI 適應症；E. coli 出現在骨盆感染也不能轉作膀胱感染支持。 |

## 審查結論

證據 Agent 的 17 個 `supported` 中，多筆由**同章節但錯藥**、**兒童頁套成人**、**上泌尿道或複雜感染套穩定下泌尿道**、或**其他器官適應症套 UTI**而來。最明確的逐藥錯配是 amikacin、ampicillin、imipenem、ampicillin_sulbactam、meropenem、piperacillin_tazobactam；ceftriaxone、ertapenem 另有感染部位／複雜程度不符，gentamicin、ciprofloxacin、levofloxacin 的原文限制不可省略。WHO p566 沒有在本次引用或快照中，不能稱其已被核對。

最終分層將 18 藥全留在 `pending`，沒有發布候選，與 clinical／synthesis 呼叫前失敗、audit 未執行的事實一致；這是本次輸出邊界正確保守，**不是**前述錯配已經獨立審核或修復。後續若要評估模型語意品質，須在另一次有完整 clinical、synthesis 與 evidence_audit 回覆的授權 run 中，逐項核對聲明及引用；本輪唯一 live 已完成，不據此要求或啟動重跑。
