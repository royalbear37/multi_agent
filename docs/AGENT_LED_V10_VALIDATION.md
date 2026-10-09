# v10 live 與 1.3.7 本機修正（2026-10-08）

## 實際執行

使用者直接回覆「同意執行」後，依前一則完整問題範圍執行一次付費 live；該次授權已使用完。不是由 heartbeat 重播取得新授權。

| 項目 | 結果 |
| --- | --- |
| Run | `bec1ebb1-1f48-4ea7-87ad-11b93e2f07e4` |
| 病例 | agent-complete revision 4，18 筆 AST |
| 流程／模型 | agent-led-1.3.6／gpt-4.1-mini |
| 呼叫／時間 | 6 次、約 208 秒，沒有格式錯誤或重試 |
| Token | 188841（prompt 175080／completion 13761） |
| 最終 | 0 可供審閱、0 不建議、18 待確認 |
| AST | 15 susceptible、1 resistant、2 unknown |
| Clinical | 18 unknown；每藥 quotes 均為空 |
| Audit | 18 uncertain；每藥 quotes 均為空 |

保存：`data/local/agent_cases/live-complete-v10-audit-provenance.json`；API 匯出 `live-complete-v10-export.json` 與 run 完全一致。全部 26 段 Evidence Agent 引文均存在於該次 Agent 輸入；檢查保存於 `v10-citation-existence.json`。引文存在不代表語意支持。

## 原因與限制

1. AST 來源修正實際生效：16 筆取得一致類別。ertapenem 選定 CLSI 缺值、levofloxacin 原始／CLSI 衝突，仍不能認定來源一致；audit 對這兩筆的錯誤來源選擇也未放行。
2. 臨床 Agent 的 54 個風險分項全缺可核對引文，18 個交互作用分項沒有病例欄位引用。病例實際已提供 reviewed_none 與空用藥清單；不能把它描述為病例一律缺資料。
3. Audit 同樣未選取引文。17 筆感染／族群／藥品細項仍自稱 supported，但最終 verdict 全 uncertain，不能當作已核對。
4. Sol/high 的保存來源審查仍發現語意錯配：部分 WHO 選段未含本藥、把同等選項說成首選、複雜 UTI 外推本例、腎功能數值與標示門檻敘述不符。詳見 [審查報告](AGENT_LED_V10_REVIEW.md)。最終未發布這些草稿為候選或已確認排除。
5. 六次成功回覆、mock 測試或來源存在檢查都不等於臨床適用性已確認；八情境、論文過敏配對、候選到人工審閱及瀏覽器醫師驗收仍未完成。

## 1.3.7 本機修正

- Wire schema 明示要求逐藥 quotes、fact_refs、evidence_refs、missing_fields、next_action；也涵蓋 CaseReport 根層 missing_fields。保留空陣列以允許未知；不自動替模型補引文，舊 run 的 canonical 契約不變。
- 提示明確指出引文在每個 `drugs[i].quotes`，同藥三個風險分項共享該陣列，避免「top-level」位置含糊。
- 明確區分一般藥品標示警語與病人實際併用藥；已確認無用藥時引用 medications 與 medication_history_status，不虛構暴露。
- 來源診斷區分「完全沒有選取引文」與「選段不含本藥」。前端對零引文的 audit 明示細項不是已通過文件核對；舊 run 也能看到提示。
- 完整後端 **312 passed**（4 既有 warnings），前端 **46 passed**、build 成功。無新臨床篩選規則。

1.3.7 尚未 live。Wire 必填與提示改善不能保證下一次模型完整引用，也沒有解决全部語意問題。新一次付費驗證須新授權；不得重用 v10 授權。恢復時先看最新待辦／服務版本，再決定下一個具體修正。
