# v12 驗證與1.4.2修正（2026-10-09）

## 最新：2026-10-09，1.5.0 逐藥醫師決策

已實作採用／有條件採用／不採用、逐藥理由及使用條件、警示確認、保存及匯出；未選藥品不須逐一決定。一般用藥警語與病例缺漏分開，已明示無已知過敏不再逐藥重問；空白仍是未知。人工決策不會改寫 AI 分層或原始分析。

後端完整 348 通過，最終 API 9 項複驗通過；前端 58 通過、build／diff check 通過，Sol/high 三項審查發現已修正結案。服務已載入1.5.0（session40394／PID30404），舊 v12 匯出不變。醫師前端 QA 見最新報告；本輪未新增付費 live。

操作稿、測試及後續界線見 [1.5.0 驗證與逐步 DEMO](PHYSICIAN_DECISIONS_150_VALIDATION.md)。後续待辦：取得新一次具體授權後驗證1.4.2輸出預算及1.5.0提示；核對原 WHO／DailyMed 語意錯配，不將人工決策當成 AI 複核已通過。以下狀態為歷史。

## v12實際結果

使用者直接同意具體確認卡的一次授權已用完：agent-complete第4版、18AST、WHO/DailyMed、外部gpt-4.1-mini。run `6d05f0aa-5f57-43b9-a54d-e133e81b9657`，版本1.4.1；6次呼叫（前四角色各1次、整合2次），215587 tokens，277.7秒。0完整候選、0review_options、18pending。

輸入大小修正生效：Clinical完成18藥，78段引文；Evidence87段。165/165原文存在，API export與保存JSON相同，但字面存在不等於語意支持。Synthesis兩次皆completion_tokens=6000而output=None，最終AGENT_SCHEMA_INVALID；Audit因無整合聲明未執行。歷史run未保存finish_reason，因此「輸出截斷」是依兩次額度用滿與未形成JSON的強推論，不偽稱API明確記錄length。

保存檔：data/local/agent_cases/live-complete-v12-context.json、live-complete-v12-export.json、v12-source-layer-checks.json。check_v12.py為唯讀檢查。

## 審查與限制

Sol/high完成 [Clinical逐藥語意審查](AGENT_LED_V12_REVIEW.md)：imipenem引用plazomicin劑量表與RECARBRIO複方；另有腎功能引交互作用/肝功能、交互作用聲明不在所選原文等錯配。獨立audit未完成，不能把Clinical no_identified_risk當最終排除風險。需在下次完整流程逐项重核；不強制候選。

[醫師前端驗收](PHYSICIAN_UI_V12_RECHECK.md)確認18pending、Clinical已執行、Synthesis失敗、Audit未執行、接受/修改禁用。醫師發現的兩項誤導已修：0第二層選項不再宣稱感染已支持，風險逐列明示臨床初評、尚未完整核對及片段省略。瀏覽器複驗通過。相同省略原因可再按來源/查詢整合，仍是待辦。

## 1.4.2本機修正已完成

- Synthesis獨立setting `LLM_AGENT_SYNTHESIS_MAX_OUTPUT_TOKENS`，預設16000；Audit預設24000；兩者硬上限24000。明確設定較小值仍尊重，不靜默覆寫。其他角色維持6000，legacy V2硬上限仍8000。
- 新run保存finish_reason、output_token_limit及usage；length明確成AGENT_OUTPUT_TRUNCATED，保留使用量，不當格式可補正而重試相同預算，不解析/發布部分JSON。
- 兩個長輸出角色每次逾時上限180秒；仍受全程480秒、最多8次呼叫限制。沒有保證audit能取得完整180秒，可能因前序用時而剩餘不足；見 [Sol/high修正審查](AGENT_LED_142_REVIEW.md)。不能以本機通過保證下一次live成功。
- 新舊版本前端相容、截斷中文提示、0選項與風險初評說明已更新。
- 完整後端339通過（4既有warnings）、前端51通過、build及diff check通過。5項新增後端測試覆蓋角色預算、明確設定/硬上限、legacy保持、length使用量保存及不重試。

自有後端重啟為session41976/PID21044，contracts1.4.2；Ollama embeddinggemma 768維檢查正常；v12匯出與保存檔未改動。前端5173 session6730。1.4.2尚未live，沒有新的付費呼叫授權，無執行中模型。

## 使用者最新過敏提醒問題

本例原始資料是 allergies.status=known_none、items=[]，不是空白。v12 amikacin與gentamicin的allergy初評caution，missing_fields=[]，但next_action仍要求「詢問過敏史」；這是一般標示警語轉成重複待辦，不能據此宣称病歷缺過敏資料。imipenem的unknown則涉及缺少已核對引文，與病歷有無填過敏不同。

後續優先：將病例資料缺漏、一般標示注意、模型引用未確認分開；已明示無已知過敏者不逐藥重問，只有具體矛盾/新缺口需確認；真正空白/unknown集中問一次，不把空白自動改為無過敏。這項最新改善尚未實作。FHIR資料語意亦區分未記錄/未詢問/無已知過敏：https://hl7.org/fhir/R5/allergyintolerance.html

## 後續待辦與DEMO

1. 先處理上述過敏重複待辦及來源/查詢省略提示整理，保留真實未知與文件核對需求。
2. 檢查整體480秒的時間分配能否涵蓋新輸出預算；不得藉增加token宣稱引用語意正確。
3. 再取得新一次明確授權後才執行v13（1.4.2或後續版本），不得重用v12同意。準備好後明列病例/18AST/WHO+DailyMed/外部gpt-4.1-mini/一次付費，說明輸出上限已提高。
4. 真實Audit容量、五分項核對、錯藥/複方/UTI/族群與風險引文，及正確層級仍待新live驗證。mock不能代替。
5. 現在DEMO選歷史v12，確認版本1.4.1/病例4；展示Clinical18藥已執行與來源，標為初評；展開Synthesis錯誤與Audit未執行，不能示範接受不存在候選。新版輸出預算的實際成功尚無run可展示。
