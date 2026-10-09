# Agent-led 驗證紀錄（持續更新）

## 2026-10-08：1.4.0 本機驗證

後端331、前端47、build與diff check通過；Sol/high來源／補正邊界審查及修正複查完成。已實作逐聲明核對與有證據的待審閱選項；Review API不允許直接提升第二層。服務已載入1.4.0，舊v10匯出完全一致。本輪沒有新live結果。完整紀錄見 [1.4.0驗證報告](AGENT_LED_140_VALIDATION.md)。

## 2026-10-08 最新

已依直接授權完成v10 live：1.3.6／6calls／208秒／188841tokens，0候選、18待確認，16筆AST來源確認。clinical與audit皆漏選引文；26段Evidence引文存在，但Sol/high指出語意問題。保存run及API匯出一致。後續1.3.7本機修正已312後端／46前端／build通過，尚未live；授權已用完。詳見 [v10 驗證報告](AGENT_LED_V10_VALIDATION.md)。以下為歷史。

## 最新：1.3.6 本機驗證完成

後端308／前端45／build及diff check通過；Sol/high最後小範圍複查無阻擋。來源與聲明分開核對、風險引用不能借作治療聲明支持，來源不足的avoid亦降待確認。服務已載入1.3.6，重啟前後v9匯出完全一致。v9離線重驗兩項avoid均uncertain，但不等於新版live完成。上一筆授權已用完，本輪未外送模型。詳細結果與未完成範圍見 [1.3.6 驗證報告](AGENT_LED_136_VALIDATION.md)；以下為歷史。

## 最新：v9完成後依額度暫停（五小時剩4%）

2026-10-07 本次直接明確同意已使用於一次v9 live，沒有第二次外送。run `66e190b6-7feb-456d-9b1f-7cdba2fd64f8`，agent-complete revision4／18AST／gpt-4.1-mini／1.3.4，六次呼叫、無格式錯誤、約163秒、172153tokens（prompt158467／completion13686）。0可供審閱、16待確認、2不建議。`data/local/agent_cases/live-complete-v9-source-options.json`及`live-complete-v9-export.json`已保存且API匯出一致。無執行中的live或測試，session64327/58533已結束。

進步：synthesis引用識別碼錯誤為0；ertapenem選定CLSI缺值時模型保持unknown。AST仍18unknown，其中17筆實際有正確CLSI來源，但同時列了同藥同類別原始報告refs，1.3.4 guard誤把額外比較来源當invalid；clinical仍18unknown。獨立audit竟18supported，不能據此宣稱語意正確；兩個avoid亦需來源核對。

本機新1.3.5已修AST來源比較：確定S/I/R必須有有效selected_basis且所有已引類別一致，可保留同類別比較來源；缺selected來源／CLSI缺值／其他藥／相反類別仍不通過。合法conflicting仍保留。新增四個回歸，完整後端292passed（4既有warnings），diff check通過。本輪無前端變更，沿用上一輪43tests/build成功；1.3.5尚未live。Sol/high已受託小範圍AST修正及v9 avoid來源審查，額度達門檻已通知停止，只保存當下觀察；恢復時先讀AGENT_LED_V9_REVIEW.md，缺報告或未完成須補驗，不假設已通過。

五小時已用96%（剩4%），每週已用15%（剩85%），依使用者要求停止。backend session82216/PID22812仍載入1.3.4（尚未重啟載入1.3.5），frontend33116沿用。恢復先查額度→讀Sol/high交接→完成1.3.5來源修正複查→在無進行中分析時重啟自己的backend→再取得新的具體一次授權才可live。不可重用v9授權。不要把舊v9當1.3.5驗證。

後續仍須核對audit18supported與兩項avoid的實際來源、逐藥風險證據涵蓋、正常事實誤列issues與重複摘要、未測AST選項、八情境／配對比較、候選至人工審閱及瀏覽器QA。未完成臨床驗收，禁止強行出藥。以下保留較早進度，以上方為準。

## 最新：v8一次live已完成，1.3.4已通過本機測試

一次授權已使用於v8 `eff53f5a-b59d-4f56-929b-d6deca1eb52e`（1.3.3／revision4／18AST／6calls／216.9秒／168463tokens），無schema錯誤但0候選／18待確認。run/trace/export API已核對並保存；不能把此run當作修正後1.3.4的live驗證。詳見`AGENT_LED_V8_VALIDATION.md`及`AGENT_LED_V8_CITATION_REVIEW.md`。

1.3.4已修可選AST/evidence來源、錯誤來源診斷、逐聲明引用最低檢查、ASTunknown節點狀態與未核對摘要隔離。後端288、前端43、build及diff check通過，Sol/high審查與三項修正複查完成。backend session82216/PID22812已載入1.3.4，frontend33116沿用，無未完成live/測試。

待續：新一次直接授權後才能驗證1.3.4（同agent-complete revision4／18AST／WHO/DailyMed／gpt-4.1-mini）。目前授權已消耗，不自動重跑。引用語意錯配、正常事實誤列issues、角色重複摘要、未測AST選項、逐藥風險證據涵蓋、八情境/配對比較、候選到審閱、瀏覽器驗收仍未完成。不要把零候選改成強制出藥；不可用mock聲稱live成功。

以下為歷史紀錄，先前「授權未使用／等待回覆／run執行中」已由本節取代。

## 2026-10-07／1.3.3 追加驗證（最新）

本機後端281、前端41測試通過，build及diff check成功；Sol/high審查與修正複查完成。WHO完整PDF與節錄用原始檔hash及逐行重抽取比對（限定bullet/標點空白正規化）連結同源，原文與舊run未改，v7整份export比對相同。新輸入及引用畫面呈現同源，不以片段數計支持強度；不同ID仍不證明來源獨立。這是來源與軟體驗證，並非臨床语意確認。

新backend71396/PID3640已載入1.3.3；本輪沒有新的付費live，仍等使用者直接回覆先前一次外送問題。瀏覽器工具不可用，UI回歸為測試與build，未宣稱醫師實際操作驗收。以下保留先前測試/執行歷史。

2026-10-06。軟體流程執行與臨床正確性分開記錄；尚未取得專家確認。

## 2026-10-07 較早本機續驗

後端 **278 passed**、前端 **38 passed**、build成功、diff --check通過。最後pending草稿與新增醫師可讀提示皆已包含前端測試；Sol/high來源升級審查的人工source覆寫/並行revision風險已修並複查。7個基礎情境revision4、4個過敏配對revision2，rapid-only維持revision3；逐一比對AST/臨床值未變，v7完整export仍相同。

醫師瀏覽器復驗因CUA無可用browser未完成，不能用component測試替代；見PHYSICIAN_UI_RECHECK_2026-10-07.md。本輪沒有新live，正等待revision4一次直接人工外送同意；排程重播不當作新增授權。上次臨床/AST契約修正與引用語意仍待live，不宣稱完整臨床驗收。

## 最新：v7 live與1.3.2修正

使用者明確授權一次執行，1.3.1 run `91ddb348-f6a6-4576-9926-989df2447128`：7calls，341901ms，178108 tokens，0候選／18待確認。整合輸入89386字元，先前長度失敗未重現。Clinical兩次舊文字欄填物件，均schema失敗；其他5個模型步驟完成。Sol/high逐筆引用複查發現8個supported中有4個明確原文錯配；見 `AGENT_LED_V7_CITATION_REVIEW.md`，不把model supported當人工認可。已核對export API保留病例revision3與170證據快照，保存 `live-complete-v7-export.json`。

1.3.2修正wire臨床契約重複欄位、AST類別來源檢核、缺失CLSI的source文字、準備片段與模型呼叫分離、版本衝突提示。後端276passed，Sol/high快速複查無阻擋。前端35passed/build通過之後，另按醫師UI回饋折疊pending草稿並說明Agent未核對不等於缺資料；**最後UI變更尚未補跑測試/build**。因五小時剩4%暫停。無第二次live；候選到接受／修改仍未驗收。

## 最新：agent-led-1.3.1

逐藥檢索分組新增找到／送入／未送入片段與原文對照；零結果、失敗和時間不足保留，未送入片段不提供給模型冒充已讀。前端表格及新版局部結果顯示回歸通過。後端 **265 passed**、前端 **31 passed**、build 成功。新增修改尚待 Sol/high 追加複查及瀏覽器驗證；沒有新 live。五小時剩 4% 時依使用者門檻暫停。

## 最新：agent-led-1.3（取代下方歷史狀態）

- 後端 **264 passed**、前端 **30 passed**、正式 build 通過。API schema／前端型別已同步。Sol/high 唯讀複查通過；未建立 GitHub PR。
- 過敏、腎功能、交互作用分項保存狀態、病例欄位、文件引用、缺漏及下一步。一般 caution 須資料及來源完整、無阻擋問題，且經獨立 risk_checks 支持，才能附提醒供審閱；提醒在人工修改後仍保留。
- 獨立複核包含推薦、排除、未選與等待聲明；病例數值核對不再要求文件證明個人數值。無支持的排除降為待確認；沒有聲明則不呼叫模型，明示不算複核通過。正常六次模型呼叫與共用上限不變。
- 新增用藥史完整性狀態；舊病例為未知，空清單不等於確認無用藥。介面可確認目前清單並新增 revision。八個人工情境已依相符套件來源新增 revision 3，保留其他現行欄位與全部歷史。
- 補充回歸涵蓋：未確認空用藥史、全空腎功能物件、其他藥品過敏紀錄／整份清單冒充本藥事實、缺失病例欄位、分項複核缺漏與未支持、研究引文混用。
- `1.pdf` 已匯入為 UK 成人觀察性研究／背景證據，doc_id `doc_eb8313e05c138e10cb0e`；本機 Ollama 已完成 47 片段索引，warnings 為空，結果存於 `data/local/allergy_pairs/paper-index.json`。四個過敏配對病例已匯入 revision 1；尚未執行四模式 live 比較，索引不代表臨床驗證。
- 本次沒有新增模型外送。1.3 live 驗證已另行詢問一次授權；v6 的失敗記錄不能作為新版驗收。完整候選→人工審閱→匯出、八情境 live、WHO 566 族群語意與醫師完整 UI QA 仍待完成。

## 2026-10-06 引用與論文延伸功能更新

- 最終驗證：後端 **237 passed**、前端 **28 passed**、正式 build 通過；新功能測試與其他模式回歸皆包含在內。五小時額度剩 5% 時依使用者要求暫停。

- 新版 `agent-led-1.2`：模型選段落 ID、程式從來源快照還原引文，保存別名、段落位移及 wire input hash；未知 ID 不通過。仍保留獨立語意複核。
- 過敏來源／確認欄位、病例摘要及非 JSON 補充表單完成；確認／排除評估要求來源、內容、紀錄者與時間。API 測試確認新 revision 不改舊版本，模型不會移除原標籤。
- 文件匯入新增類型、研究設計、網址及地區；研究背景不能混入逐藥引用充當指引。關鍵字與向量查詢使用相同 metadata 序列化，避免關鍵字模式漏掉文件類型。
- 四個過敏配對病例與預期檢核已產生於 `data/local/allergy_pairs`；尚無四模式 live 比較或專家評分，未自動匯入 `1.pdf`。
- Sol/high 唯讀審查指出研究引用混用及同藥嚴重過敏與無風險結論矛盾；已修正並加入回歸。追加 severity 大小寫及中文值處理。
- v6 一次 live 已獲本輪明確外送同意並執行；`data/local/agent_cases/live-complete-v6-spans.json`，run `7e9c0465-a5bb-4192-be67-52eec706b60d`。專責輸出未出現原文核對失敗，證據 Agent 16 項 supported；但整合 `AGENT_INPUT_TOO_LARGE`，無候選，空聲明 audit 不算實質驗收。
- live 後已移除整合輸入重複引文，原文留在快照供 audit。18 藥長引文回歸通過；此修正尚未做第二次 live，不將 v6 當 1.2 最終驗收。
- 詳細已完成／待辦見 `AGENT_LED_IMPROVEMENT_TODO.md`。原先八情境、病例審閱匯出與完整 UI 驗收仍未全部完成。

## 已完成

- 不呼叫 RuleEngine 的 multi-agent 分析／審閱測試；有效引用、衝突、未知藥品、未測 AST、局部失敗、預算保留及不安全文字隔離。
- 完整後端 211 項、前端 26 項通過，正式 build 通過。最後另加 outbound evidence metadata 精簡，尚需補跑其 targeted 測試。
- Sol/high 唯讀審查三項 findings 已修正並有回歸測試。非 GitHub PR 審查，不表示已發布 PR。
- 八病例、一次腎功能修訂、來源 SHA 與統計檔已產生。CSV 4,960,599 列；E. coli 尿液統計含51個藥名；本例18筆AST。按 culture-organism-drug 去重；來源/CLSI不一致和缺漏不納入有效分母。
- WHO PDF 294–307頁為完整下泌尿道章節；296–297成人圖表、298–299兒童圖表，已依渲染圖確認族群。原先293頁屬前章、漏307頁的抽取已修正。藥品標示保留子章節與表格文字。
- 文件包包含20份DailyMed標示、WHO章節及無關文件負向控制；原WHO全文仍保留。參考文件向量2064/2064已完成。來源/SPL版本/原始XML雜湊見 `data/local/agent_references_v2/manifest.json`；XML與Markdown快照在同資料夾。
- 前端實測勾選一病例×兩模式，Mock比較產生兩筆；benchmark ID `84571b94-9ffe-4eee-970e-1e4d7a9f4854`。

## Live 記錄

模型沿用已設定的 gpt-4.1-mini。完整JSON保存在 `data/local/agent_cases/` 和資料庫，以下不把所有「無候選」都當成成功。

| 檔案／run | 觀察 |
|---|---|
| live-complete.json / 91d18a40 | 舊120秒預算導致後三步未完成，失敗 |
| live-complete-v2.json / a77f67a6 | 六步完成、7次呼叫，約189秒；部分引文無法核對，無可供審閱候選 |
| live-complete-v3.json / be97c694 | 7次呼叫；clinical_agent格式未通過；病例Agent因過度精簡輸入誤稱AST缺漏。已恢復其原始AST輸入，需以v4確認 |
| live-interaction.json / 3c1aec92 | 六步完成、7次呼叫，辨识ciprofloxacin/tizanidine風險；也出現對levofloxacin的禁忌泛化，不能認定整體臨床正確 |
| live-evidence-mismatch.json / 70121f79 | 六步、6次呼叫，無候選；無關文件未成為有效支持，但一些不建議理由仍是模型泛化 |
| live-who-566-negative.json | 真實WHO PDF566頁（印刷550）屬發燒性嗜中性球低下。前兩次語意誤判，不能以程式因引文／文字不符而降級冒充語意成功。縮小獨立輸入、去除先前支持標記後，最近一次 infection_match=unsupported；population_match仍不正確，族群維度未完成验收 |
| live-complete-v4.json / 73175f9c | 六步、6次呼叫全部完成，無errors；病例誤稱AST缺漏已修正。但仍有引文及風險未確認，沒有候選，不代表端到端審閱驗收成功 |
| live-complete-v5.json | 精簡outbound metadata後的驗證；因額度門檻中斷，須先查保存狀態，不可當完成 |

## 尚未完成／不可宣稱

- 目前完整病例尚未有一筆在最終版本完成「可供審閱→接受／修改→匯出」的 live 端到端驗收。
- 未測AST指引選項可由契約及程式處理，測試通過；目前live未穩定提出，仍須查檢索與提示。
- 八情境尚未全部做live專責檢核；不以Mock取代。
- 語意引用複核、同類藥交互作用泛化、過敏／腎功能判讀仍需專家核對。未做醫院串接、自動醫囑及正式臨床驗證。
- 前端逐藥表／全部Agent展開／接受修改拒絕／版本與匯出完整操作驗證尚待收尾。

官方來源：[WHO 2022書籍及更新說明](https://www.who.int/publications/i/item/9789240062382)、[DailyMed資料範圍](https://dailymed.nlm.nih.gov/dailymed/about-dailymed.cfm)。本次固定使用來源清單版本，不宣稱涵蓋所有最新指引；美國標示不是院內政策。
