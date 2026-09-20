# 工作流、審閱與研究比較

研究展示用／僅 synthetic 資料／非臨床使用。

## 執行狀態

pending / running / completed / skipped / blocked / not_configured / failed 是節點狀態；awaiting_review 表示等待使用者，partial 表示必要模型尚未完成。服務重啟後中斷執行標為 failed / INTERRUPTED。completed 的節點不表示整體完成臨床審核。

安全閘門 ready_for_review 只代表可送展示審閱；needs_confirmation 需要補資料；blocked 禁止候選發布。缺少資料或模型不影響病例整理、來源 AST 與可用 trace 查閱。

每次重跑建立新 run_id，保留 previous_run_id。request_id 用於防止同一請求重複執行。API 的同步回應可能需要等待；UI 執行期間停用重複按鈕。持久化保留病例版本、規則命中、引用快照、節點耗時與錯誤，不保存模型隱藏推理。

人工審閱的接受、修改、拒絕皆保存 reviewer_id、展示角色、時間與理由。修改候選仍受原 run 的安全限制，不能解除硬性阻擋或加入未允許藥品。病例新版本不繼承舊審閱。

## 模式

| 模式 | 生成與資料範圍 | 無模型 |
| --- | --- | --- |
| rule-only | 確定性展示規則＋模板化候選；證據仍保留定位 | 可執行 |
| rag-only | 病例摘要與檢索證據；原始基線只見全域虛構藥品詞彙，不見規則候選集合 | not_configured／partial |
| single-agent | 病例摘要、來源 AST／證據的一次主要生成；不見規則候選集合 | not_configured／partial |
| multi-agent | 前置規則與檢索後，五 Agent 依序核對病例、AST、證據、臨床限制與整合；通常五次模型呼叫 | 前置通過後 not_configured／partial |

四種模式共用最終輸出檢核。raw baseline 與可發布內容分開，UI 不把隔離內容當成正常建議。模型呼叫次數不是工作流是否正確的替代指標。正式報告比較前應核對 run 記錄的資訊範圍、模型、版本與配置。

2026-09-20：舊的一次生成 multi-agent 已移除，multi-agent-v2 改名為 multi-agent。歷史 run 不改寫；舊的一次生成紀錄顯示「舊版多節點工作流（歷史）」。跨日期研究比較須依 workflow 版本區分，不可把兩代 multi-agent 視為相同實驗條件。

Demo 逐項移除無法核對的藥品、引用及候選／排除矛盾，保留其餘有效候選；不補造引用。模型沒有任何有效候選時不發布候選結果，標為需確認。人工審閱仍執行嚴格檢核。

## 指標解讀

- 完成率：符合完成定義的 run / 全部 run；另外列 blocked、failed、partial／not_configured 分布。
- 安全阻擋召回率：正確阻擋 / 標註預期應阻擋；不必要阻擋率：被阻擋但預期可完成 / 標註預期可完成。
- 缺漏 precision / recall：命中標註缺漏 / 預測缺漏，以及命中標註缺漏 / 標註缺漏。只有存在標註時計算。
- 引用有效率：可定位到此次 evidence snapshot 的引用 / 實際輸出引用；不代表引文支持結論。
- Schema 合格與白名單違規依實際生成及確定性驗證紀錄計算；未生成不可當成成功。
- 耗時為測得 wall time；token 只有供應商提供才保存；成本未設定為 null。

輸出保留分子與分母；零分母為 null（N/A），不填 0 或 100%。規則測試只有獨立預期存在且病例內容仍與 seed 相同才評分。Benchmark 開始時固定病例、規則及每個病例的檢索結果，避免模式之間因版本更新漂移。mock／live 分开，synthetic 規則驗收不可推論 multi-agent 在真實臨床較佳。Mock 只從提供詞彙選第一個代碼，是管線測試模板，不是模型品質基線。

引文支持性、臨床建議適當性、專家一致率與臨床可用性為 not_evaluated。逐案例與摘要 JSON 可從研究頁匯出。
