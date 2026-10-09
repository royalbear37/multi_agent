# v11 live 驗證與額度暫停（2026-10-08）

## 實際執行

使用者直接「同意」回覆一次明確授權，已使用完畢。執行 agent-complete 第4版、18筆AST、外部 gpt-4.1-mini；流程 agent-led-1.4.0。run `fbb4bb56-96e7-4ce9-889e-b952e0cae688`；3次模型呼叫、61227 tokens、119.2秒。腳本 `data/local/agent_cases/run_v11_once.py` 呼叫正式 start_run，固定 request_id；增加本次來源防護，WHO/DailyMed之外不外送。未改病例或文件库。

結果：0完整候選、0有證據待審閱選項、18其他待確認。Case/AST/Evidence已執行；Clinical與Synthesis因 AGENT_INPUT_TOO_LARGE 在呼叫前失敗；Audit沒有整合聲明而未執行。不是六次正常流程成功，也不是全部藥物不適用。

## 引用核對

Evidence Agent 選出88段引文，88/88在保存快照中存在；API export與保存run完全相同。Sol/high逐藥語意審查見 [V11審查](AGENT_LED_V11_REVIEW.md)：有錯藥、下/上UTI、複雜UTI及族群適用性錯配，不能把 supported 初評當已核對支持。例：ceftriaxone用WHO上UTI嚴重病例，病例卻為穩定下UTI；WHO p299為兒童頁。p566未出現在本次快照/引文。所有藥維持pending，獨立audit未完成。

保存：`data/local/agent_cases/live-complete-v11-layered.json`、`live-complete-v11-export.json`、`v11-source-layer-checks.json`。`v11-evidence-checkpoint.json`為中途快照，不能當最終结果。`check_v11.py`為唯讀來源/分層/匯出檢查。

## 已寫入但未完成驗證：1.4.1

輸入選段原先只計65k引文文字，完整來源metadata另計，Clinical 80段原始來源JSON約153837字元（尚未加facts/groups），造成180k總上限超限；Synthesis收到302段全檢索metadata，即使只需專責Agent引用的來源。

修正：新增 workflow/input_context.py，送模型前去除hash、重複location、儲存衍生資訊等metadata，保留原文、位置、族群、版本、來源識別與外送旗標，完整快照不變。選段仍依各組主要片段優先，保留65k文字上限並加120k序列化來源預算，省略仍入coverage。Synthesis目錄只含專責Agent實際引用（包括巢狀風險引用）的來源，不帶無關目錄。180k總輸入上限維持。

VERSION改agent-led-1.4.1；v2.py公開部分結果版本白名單、前端1.4.0/1.4.1分層判讀同步更新。新增3項test_input_context.py測試已通過；前端分層測試參數化兩版本但尚未執行。沒有新一次live，也未重啟服務載入1.4.1。

## 暫停與恢復待辦

五小時已用100%（剩0%）、每週已用61%（剩39%），依使用者門檻立即暫停。live session49941已完成；沒有執行中模型或測試。8000服務仍1.4.0，前端5173 session6730。

1. 額度回復後先檢查配額，再恢復。
2. 對保存v11資料做離線重播/重建，確認1.4.1下Clinical及Synthesis輸入實際低於180k，來源/coverage/病例事實不丟失；mock不可當live。
3. 完整後端、前端與build（先前331/48是1.4.0基線，不是此修正版結果）。
4. 交既有agent_led_review以Sol/high審查1.4.1來源瘦身、選段及版本相容修正。尚未派發此審查。
5. 檢查與重啟自己持有的後端使其載入新版本；不得任意停止未知8000程序。確認舊v11仍保持原貌。
6. 修正與審查完成後，再請求新一次明確live授權；本次同意已用於v11，不可重用。下一次预定v12，啟動前確認檔案不存在。
7. 新live完成五聲明獨立複核及來源逐項核對，尤其本次錯藥/錯UTI/兒童引用；醫師UI驗收新版分層，更新DEMO與待辦。

八情境契約已驗證但尚未八情境live；临床正確性未經專家認證。
