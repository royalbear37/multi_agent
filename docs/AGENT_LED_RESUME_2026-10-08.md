# 2026-10-08 額度暫停交接

## 最新：2026-10-09 v12已完成，1.4.2已通過本機驗證

v12=6d05f0aa-5f57-43b9-a54d-e133e81b9657，1.4.1／病例4／18AST；6calls/215587tokens/277.7秒。Clinical已完成，Synthesis兩次各用滿6000輸出token而無完整JSON；Audit未執行，18pending/0候選。165引文字面存在，但Sol/high仍發現逐藥語意錯配。一次授權已使用，無新的付費run。

1.4.2已提高整合/複核輸出預算至16000/24000，保存截斷原因並避免同預算重試；339後端/51前端/build/diff check及Sol/high審查完成，醫師誤導文案修正與複驗完成。後端session41976/PID21044載入1.4.2，v12不變；新版尚未live。

使用者新增關注：已known_none的病例不應每藥重問過敏。需優先分開一般標示提醒/病例缺漏/引用缺口，空白不能自動當無過敏；此最新改善尚未實作。完整結果、時間預算風險與下一步見 [v12驗證與1.4.2交接](AGENT_LED_V12_VALIDATION.md)。以下為歷史。

## 最新：2026-10-09，1.4.1本機驗證完成，v12待具體外送同意

334後端／49前端／build／diff check通過；v11離線重播Clinical155042、Synthesis72076字元，原AST與選段原文保留。Sol/high小範圍審查未見阻擋。後端session16533／PID27200已載入1.4.1，舊v11匯出不變。

使用者「同意執行付費分析」後，自動核准審查仍拒絕執行v12，要求明確連結資料與目的地；拒絕發生在程序啟動前，未呼叫模型。已發具體一次外送確認問題等待回覆，不重复提問。詳見 [1.4.1驗證及恢復步驟](AGENT_LED_141_VALIDATION.md)。以下為歷史。

## 最新狀態：v11已完成，1.4.1修正中，依額度暫停

2026-10-08：直接「同意」的一次授權已用於v11，run fbb4bb56-96e7-4ce9-889e-b952e0cae688，1.4.0／agent-complete revision4／18AST／gpt-4.1-mini。3calls、61227tokens、119.2秒；Clinical及Synthesis因輸入超限未呼叫，Audit未執行。0候選、0review_options、18pending。88段引文字面全存在，但Sol/high發現錯藥／感染情境／族群錯配；不能當獨立複核已通過。

已寫1.4.1來源metadata精簡、整合引用目錄縮小、選段包含metadata大小預算及前後端版本相容修正；只有新增3項後端測試通過，完整測試/build/修正審查/新live均未完成。五小時剩0%、每週剩39%，依門檻暫停。服務仍1.4.0；沒有執行中模型或測試。本次授權用完，先完成本機修正驗證再請新一次live授權。

詳見 [v11結果與完整交接待辦](AGENT_LED_V11_VALIDATION.md)、[Sol/high引用審查](AGENT_LED_V11_REVIEW.md)。以下為歷史進度。

## 2026-10-08 本轮接續完成

八病例API契約檢查通過，來源與版本保留，記錄在 `data/local/agent_cases/readiness-140.json`。醫師Sol/high已實際驗證歷史run前端，找到的版本／模型不清與待確認來源不清兩項已修復並複驗。前端48測試及build通過；後端程式本輪未改，沿用331通過結果。Sol/high程式審查的空導覽問題也已結案。

DEMO：打開歷史分析後先核對「分析當時病例」版本／模型；待確認表格按來源Agent區分，中文顯示片段省略，按「查看此步驟」或「查看錯誤步驟」可直接展開對應Agent。未保存的歷史欄位顯示未記錄。

前端5173 session6730；8000既有服務health與1.4.0契約正常。新版付費live仍未執行；先前的具體一次外送確認仍待直接回覆，不重複提問。收到同意後只執行一次agent-complete第4版／18AST／WHO與DailyMed／外部gpt-4.1-mini驗證，逐項核對來源及層級，保存新結果；舊v10不能當作新版驗收。詳見 [驗證報告](AGENT_LED_140_VALIDATION.md)、[醫師操作複驗](PHYSICIAN_UI_140_RECHECK.md)。下方舊狀態僅供歷史追溯。

## 最新接續位置：1.4.0 已實作（取代下方暫停狀態）

使用者已要求實作分層計畫並回覆同意執行。軟體實作完成：wire schema驗證／逐藥部分保留補正／三面向檢索／五项分項複核／review_options與前端分層／審閱保護。後端331、前端47、build、diff check通過；Sol/high最後複查無已報問題的剩餘阻擋。backend session45448／PID30024載入1.4.0；舊12113服務本已停止，未殺其他程序。API health及contracts版本正常，v10export未變。無執行中模型／測試。

下一步：1.4.0一次新live的資料範圍仍需具體確認（agent-complete revision4、18AST、WHO/DailyMed、外部gpt-4.1-mini）；不要把計畫實作同意或heartbeat重播當新資料外送授權。預定v11輸出live-complete-v11-layered.json，啟動前確認不存在；v10授權已用完。詳見AGENT_LED_140_VALIDATION.md及AGENT_LED_140_REVIEW.md。八情境／論文配對／瀏覽器醫師QA仍待完成。以下為歷史。

五小時已用96%（剩4%），每週已用31%（剩69%）；依使用者門檻停止。無執行中的live／測試；v10 session53346已完成。不要在額度恢復前擴大工作。

## 已完成

- 使用者直接「同意執行」核准的一次live已用於v10，不能再次使用。run `bec1ebb1-1f48-4ea7-87ad-11b93e2f07e4`，agent-complete revision4／18AST／gpt-4.1-mini／1.3.6，6calls、208秒、188841tokens，無schema錯誤；0候選／0avoid／18pending。
- AST15敏感、1抗藥確認，2unknown。clinical及audit各18筆quotes空；clinical54分項缺引文、18交互作用缺fact_refs。Evidence26引用均存在於原輸入；語意不能據此確定。
- 保存live-complete-v10-audit-provenance.json、live-complete-v10-export.json（與API一致）、v10-citation-existence.json。Sol/high來源審查存AGENT_LED_V10_REVIEW.md；驗證報告AGENT_LED_V10_VALIDATION.md。
- 1.3.7改wire必填引用／風險欄位及CaseReport根層missing_fields；仍允許明確空陣列與未知，canonical舊run相容。不自動填引文。提示明確drugs[i].quotes位置及用藥已確認空清單的事實引用；區分一般標示警語与病人實際用藥。
- audit來源診斷區分完全未選引文與選錯藥。前端零引文時提示細項supported不是已通過文件核對。
- 後端312passed（4既有warnings）、前端46passed、build、diff check成功。Sol/high最後修正複查完成，未見阻擋；不代表下一次live一定成功。

## 服務／授權

backend session12113／PID19676仍載入1.3.6，**尚未重啟載入1.3.7**。frontend33116沿用；前端build成功，未完成瀏覽器醫師QA。

沒有新的live授權，也沒有新的確認問題待回覆；前一則1.3.6確認已由直接同意回覆且用於v10。Heartbeat重播「同意」不能當新授權。

## 恢復順序與待辦

1. 查額度；五小時剩≤5%或每週剩≤3%繼續暫停。
2. 確認沒有running run後，只重啟自己backend session12113載入1.3.7，核對health與舊v10export不變。
3. 針對1.3.7提出新一次明確授權：agent-complete revision4、18AST、WHO/DailyMed、外部gpt-4.1-mini、一次付費並保存。授權前不得live；預定v11輸出需確認不存在。
4. 驗證clinical／audit是否實際選引文、交互作用是否引用病例用藥狀態；明示必填schema仍依賴模型遵循，目前沒有強制wire JSON Schema驗證保證成功。
5. 續處理語意错配：4筆Evidence supported只選不含本藥WHO段落、同等選項誤稱首選、複雜UTI外推、腎功能門檻敘述不符。保留未知，不靠降低核對標準湊候選。
6. 正常事實誤列issues、重複摘要、未測AST指引選項、逐藥風險涵蓋、八情境與論文過敏配對、人工審閱／比較／匯出及瀏覽器醫師驗收未完成。
