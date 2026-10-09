# Agent-led 1.5.1 唯讀差異審查

範圍：`source_scope.py` 的必要來源範圍檢核及其在 evidence、clinical、audit 的接點；`time_budget.py` 與 agent 呼叫／檢索流程。僅讀本機程式與已保存資料，未執行 live、外部模型或更改程式。本審查不把字詞匹配視為臨床適用性證明。

## 原發現與複驗

以下兩項初查發現已由主線修正；本機使用原反例重新呼叫函式，兩個非劑量腎句、前置／括號羅馬字互動藥名、以及跨藥引文拼接主題均已產生問題清單。原重現情境保留供追溯，並非目前未修缺口。

1. **腎功能「無需調整劑量」初版可由非劑量敘述通過。** 初版 `backend/app/workflow/source_scope.py:78-85` 的 direct 分支 `no.{0,35}(adjust|alteration|modification)` 不要求調整對象是 dose/dosage。以正確 `MEROPENEM INJECTION` 標示、選段「No alteration in renal laboratory parameters was observed after meropenem administration.」及聲明「No renal dose adjustment」呼叫函式，初版結果為空；「No adjustment in renal function was observed ...」亦然。主線已要求同片語出現劑量指涉，兩個原反例現可攔截。此守門仍只判必要來源線索，不自動判定臨床正確性。
2. **前置羅馬字互動藥名未核對。** 初版 `backend/app/workflow/source_scope.py:90-94` 只擷取中文「與／和／併用／合用／使用／服用」之後的拉丁字藥名。若聲明為「valproic acid 與 meropenem 併用應避免」或「丙戊酸（valproic acid）與 meropenem 併用應避免」，引文只有「Meropenem has drug interaction warnings with probenecid.」，初版函式回傳空問題清單。主線已補前置／括號句型，原反例現可攔截。

原先另有一個非阻擋性誤降級：`dosage alteration/modifications is/are not required`。`source_scope.py:81` 已補 `alterations?`／`modifications?` 正向句型；本機重播兩句 `Meropenem dosage alteration is not required ...`、`Meropenem dosage modifications are not required ...` 都不再回報缺劑量依據，且 `backend/tests/test_source_scope.py:64-65` 覆蓋。

## 已確認與限制

- 原始產品 heading 優先於上傳短標題；本機 v12 所見單藥標示維持可辨識，而 `RECARBRIO` 複方 heading 供單成分 `imipenem` 時會報錯。`source_scope_issues` 現只在本藥錨定選段尋找風險主題；不同藥一般段落與本藥感染段落拼成腎風險的原反例已被攔。錯藥 `Table 47.2 Plazomicin suggested doses` 也獨立報錯。
- 新來源檢核接入 `risk_details.py:49-51`、`claim_checks.py:40-41`、`audit_sources.py:40-44` 及 `agent_led.py:141-145,232-235`，結果以 unknown／uncertain 降級，未發現其直接提升為 supported 的路徑。離線 v12 重播記錄了原始檔 hash、`source_unchanged=true`、`model_calls=0`；該重播只是既有來源必要條件檢核，並非對 54 個分項的獨立臨床核證。
- `TimeBudget` 以總期限扣除尾端角色保留時間；預設 780 秒、六角色最大呼叫共 600 秒，`agent_led.py:409-425` 對逾時模型回覆拒收，補正前亦檢查尾端角色及呼叫名額。同步檢索的初版軟預算已補合作式截止：`agent_led.py:284-295` 傳入扣除當前及後續角色保留時間的絕對 deadline；`service.py:299-333,894-946` 對單次請求複製 service/provider、在 deadline 下不做冷索引、縮小 Ollama timeout，並在逾時時丟棄結果。`backend/tests/test_agent_retrieval_budget.py:6-37` 覆蓋冷索引、其他模式保留 lazy indexing、共享 provider timeout 未被改動與晚到結果不採用。此仍非任意阻塞 OS／自訂 provider 的強制中止保證；超時檢索可能耗用牆鐘時間，但不會把晚到證據冒充按時檢索成功。

未全面核對全部 v12 選段的臨床含義、所有文件格式與實際服務延遲；也未重跑完整測試。父任務回報 source／time／retrieval 相關 29 項測試通過；最後版本的完整測試仍以父任務結果為準。本輪小範圍複查未見新增阻擋性問題。
