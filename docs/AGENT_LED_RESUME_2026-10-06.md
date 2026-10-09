# 2026-10-06 暫停與續作

## 最新續作結果（取代下方舊續作順序）

**最新為1.3.2／v7 live後暫停：五小時96%（剩4%）、每週46%。** 一次新授權已用於 `91ddb348-f6a6-4576-9926-989df2447128`，1.3.1 live 7calls、342秒、0候選／18待確認。Clinical兩次string_type；8個audit=supported有4個明確原文錯配，詳見 `AGENT_LED_V7_CITATION_REVIEW.md`。不可當臨床驗收。

修正：wire Risk只保留必填risk_details；AST需本藥選定類別來源，raw數值不能補CLSI空值；來源描述明示缺失。UI覆蓋數正名準備＋呼叫狀態／版本衝突；最後新增pending草稿折疊與未核對不代表缺資料。後端276passed；前端35passed/build在最後UI變更之前，恢復必須補跑。Sol/high快速複查無阻擋；醫師UI回饋已收，報告由physician_ui保存。

v7匯出已核對case與170證據快照一致；無候選故未提交人工接受/修改。沒有新live授權剩餘。backend session50174 PID11208、frontend session33116 本輪啟動仍開著；backend未載入最後AST修正，下輪只重啟自己服務。未改寫舊run，套件source metadata尚未重建/升級。完整下一步見 TODO 頂端。下方皆歷史。

**最新暫停：1.3.1，五小時 used 96%／剩 4%，每週 used 30%。** 已收完測試：後端 265 passed、前端 31 passed、build 成功。新增逐藥檢索／送入／未送入來源表及零結果、失敗、預算不足分組；Agent 收到缺額資訊；新版 partial output 公開顯示相容性已修。尚待這次小幅修改的 Sol/high 追加審查及 UI QA。沒有新增外送；上一個一次 live 授權問題仍待回覆。恢復先看額度，完整待辦見 TODO 頂端。下方 1.3 為前一輪完成紀錄。

2026-10-06 15:30 左右 heartbeat 續作：已完成 `agent-led-1.3` 分項風險、caution 條件放行、病例／文件獨立來源核對、排除理由及逐項風險複核。後端 **264 passed**、前端 **30 passed**、build 通過，Sol/high 複查完成。

八個情境為 revision 3（新用藥史完整性 metadata、其餘現行欄位保留），四個過敏配對已匯入 revision 1；論文已匯入為 UK 成人觀察性背景研究，doc_id `doc_eb8313e05c138e10cb0e`。本機 Ollama 47 片段索引成功、無警告；臨床正確性仍未驗收。

本次未新增模型外送，正詢問 `agent-complete` revision 3、18 AST、WHO／DailyMed 的一次 live 同意。收到前不可執行。下一步為 live 引用及候選→審閱→匯出；其他情境、多模式配對比較、WHO 566 族群語意、醫師完整 UI QA 尚待完成。沒有重啟使用者後端，無本輪 live 程序。最新完整狀態以 TODO 及 VALIDATION 的 1.3 段落為準。

---

以下為上一輪額度暫停紀錄，已由上述進度取代：

本輪再次達五小時已用 95%／剩 5%，每週已用 15%，依使用者門檻暫停。完整最新待辦見 `AGENT_LED_IMPROVEMENT_TODO.md`。

- 已完成選段引文、部分引用保留、過敏來源／確認狀態／前端補充 revision、文件研究類型／設計、四個過敏配對檔案、逐藥檢索分組及指引選項獨立查詢。
- 最終後端 237、前端 28 測試通過，build 通過。Sol/high 審查與修正複查完成；無新 PR。
- 本輪明確同意的一次 live 已用於 `live-complete-v6-spans.json`，run `7e9c0465-a5bb-4192-be67-52eec706b60d`：引文抄写核對失敗為 0，但整合輸入過長、無候選。
- 已在 `agent-led-1.2` 精簡整合輸入，保留專責評估與來源 ID、audit 獨立讀原文；18 藥長引文回歸通過，尚未再次 live。下一次外送需新的明確同意。
- 分項風險／caution、逐項聲明對照、排除理由複核、全部病例 live 及 UI 審閱匯出仍待完成；論文未自動匯入，配對病例在 `data/local/allergy_pairs` 尚未匯入病例庫。
- 未重啟使用者後端，程式更新需重啟生效；本輪無未結束 live 程序。

---

以下保留前次暫停歷史。

使用者門檻：五小時已用95%（剩5%）、每週已用33%；依要求暫停，未完成全部計畫。

## 本輪完成

- 新流程獨立480秒預算／6000輸出tokens；重試保留後續角色呼叫額度。檢索計時與截斷揭露、按文件類型及藥名路由、平衡每藥片段。
- Sol/high審查三項問題均修正並加測試：缺漏未阻擋、不安全給藥文字、重試用盡audit額度。
- 修正WHO章節為實體頁294–307；視讀成人296–297、兒童298–299，DailyMed保留子標題。新文件`data/local/agent_references_v2`，已替換上轮套件文件，原WHO保留；全部2064片段已索引。
- 本機Ollama已用官方既有程式隱藏啟動。另啟動本輪backend session 88812(PID25416)、frontend session59238；仍開著，不是停止使用者原後端。
- 八病例補獨立CrCl欄位，保留計算方法/provenance；目前資料庫revision2，病例修訂範例仍在agent-renal-revision.json。
- 新增八情境建構、統計分母與原始AST保留測試。211 backend tests、26 frontend tests、build通過。最后 runtime_led outbound evidence metadata 精簡之後尚需targeted測試。
- README已更新；`AGENT_LED_DEMO.md`有準備命令、15步操作、八情境矩陣；`AGENT_LED_VALIDATION.md`列出實測與未完成項。
- 前端實際一病例×兩模式Mock比較成功：84571b94-9ffe-4eee-970e-1e4d7a9f4854。其餘UI流程仍待完整QA。

## Live重點與未完成

- 最新完成`live-complete-v4.json`：run73175f9c-e550-4e2e-a026-802f806e13b7，六步6calls、無errors、無候選。引用與風險不確定仍在，不能宣稱全部功能live驗收完成。
- `live-complete-v3` clinical格式失敗；新增安全validation_details及retry feedback。曾精簡掉case/clinical原始AST導致模型誤稱缺漏，已恢復完整原始AST。
- `live-interaction.json` run3c1aec92：辨識ciprofloxacin/tizanidine，同時誤泛化levofloxacin禁忌；需要改善不能當臨床正確。
- `live-evidence-mismatch.json` run70121f79：六步完成、無候選，但避免用藥文字含無來源推論。
- WHO真實566頁負向audit：前兩次錯誤支持；刪除先前reviewable狀態／過多病例背景後infection_match=unsupported，但population_match仍誤判supported。`verify_who_negative.py`目前判pass只驗感染，不可說族群通過。AuditItem新增infection/population/drug_match，任一不支持則不能支持。
- runtime_led最近新增短引用E1映射、保留映射及wire input hash；最末精簡重複metadata，未改原文。
- 最後啟動`live-complete-v5.json` session66047，遇quota門檻已Ctrl+C，程序確認exit1停止。資料庫可能保留running checkpoint、輸出檔可能未建立；續作先確認此中斷run，勿誤當完成或重複付費呼叫。其他服務未停止。

## 續作順序

1. 查額度與最後v5程序/結果；不要終止其他python或使用者後端。
2. 跑最后runtime_led targeted測試，檢查retry feedback input_hash是否記錄實際每次輸入；schema細節不得洩漏原始無效內容。
3. 真實模型引用可靠性仍差：查latest clinical/evidence input及validation_details，減少不相關上下文，保持原文與條件，不能降級真實引用要求只為產生建議。
4. Audit人口適用性及感染雙重負向測試、未測AST實際live選項尚未通過；完整案例還沒完成有效候選→人工接受/修改→匯出。
5. 多份引用有一個錯即清空整組，需檢視是否應保存可驗證原文但仍標不確定（不能拿部分引文冒充整體支持）。藥名別名/重複藥、未測AST被誤稱敏感與專責重複文字仍需review。
6. RAG snapshot的lazy index只存temporary：本輪預先建立索引繞過，但新匯入文件在snapshot索引會丟失，應修持續快取/準備階段；未知警告不得淹没UI。
7. 八情境預期矩陣有建構測試，尚非8場live臨床評估；用實際情境驗收並標明專家未確認。
8. 前端完整QA：逐藥表、6agent內容、引用、病例版本、接受/修改/拒絕、匯出；加Benchmark勾選component測試。IAB demoTab目前指向localhost5173，新UI但backend需重啟讀最後變更。
9. 同步更新DEMO/VALIDATION，不宣稱已完成。最後fulltests/build/diffcheck；清理自己生成tmp/who*.png及tsbuildinfo（確認不是原有改动）；保留run.ps1、USER_GUIDE、兩份9/22稿的既有修改。

來源資料、XML、manifest、病例、live輸出均在gitignored data/local；不要加到公開repo。無PR建立或外部發文。
