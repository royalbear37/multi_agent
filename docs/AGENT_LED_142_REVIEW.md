# Agent-led 1.4.2 輸出預算唯讀審查

範圍：僅核對 `runtime_v2.AgentProvider.complete`、`runtime_led.Provider.complete`、`agent_led.execute` 的輸出長度、會計資訊與時間／呼叫邊界，以及直接相關的 legacy V2、前端版本顯示與新增回歸。沒有執行 live、外部模型或其他模式的完整工作流。父任務回報 339 項後端、50 項前端測試與 build 通過；本報告不將測試通過視為真實模型可完成全角色的證明。

## 已核對的行為

- `AgentProvider.complete` 依角色的 `output_tokens_setting`、`max_output_tokens`、`output_token_ceiling` 計算 `max_tokens`，回傳 `finish_reason`、實際 `output_token_limit` 與 provider usage。1.4.2 對 synthesis 預設 16,000 tokens、audit 24,000，兩者上限 24,000；其他 agent 預設 6,000、上限 8,000。Legacy V2 Agent 沒有這些新屬性，仍使用 `LLM_V2_MAX_OUTPUT_TOKENS`、預設 2,000、上限 8,000。新增測試直接檢查送出的 payload 與 clamp。
- `finish_reason=length` 時，provider 不解析或發布可能不完整的 JSON；`runtime_led` 保留原回覆的 usage/finish reason，workflow 在驗證前將其記進 attempt，轉成 `AGENT_OUTPUT_TRUNCATED`。該 `ProviderError` 預設不可重試，所以同一角色不會以相同額度再花一次模型呼叫。若 synthesis 因此失敗，後續 audit 沒有聲明可查時標 `not_applicable`，候選維持空；新增回歸覆蓋五次呼叫、一次截斷 attempt 與不發布局部 JSON。
- 1.4.2 已列入 `public_agent_nodes` 白名單，前端分層表涵蓋 1.4.0–1.4.2，並以中文說明截斷是未完成 JSON、需重新分析，不能解讀成藥品不適用。保存的舊 run 沒有 `finish_reason`，無法事後以此欄確認截斷。父任務所述 v12 synthesis 兩次用滿 6,000 tokens 且輸出 `None`，與截斷相符，但因歷史資料未存 finish reason，只能作強推論，不能改寫為已證實。

## 預算邊界與下一步

全程預設 deadline 仍是 480 秒、最多八次模型呼叫。前四角色各最多 60 秒，synthesis、audit 各最多 180 秒，但每次實際 timeout 是 `min(角色上限, deadline 剩餘時間)`。光六角色上限相加為 **600 秒**，還未計檢索；例如前四角色合計 240 秒、synthesis 180 秒後，audit 最多剩 60 秒。這是安全地拒絕逾時輸出，**不是**超過八次呼叫或發布未核對候選的繞過；但新的 24,000-token audit 預算並未獲得對應的 180 秒保留時間，可能仍因總 deadline 而無法完成。若要提高完整工作流成功率，下一步宜以離線時序或後續明確授權的 live 驗證各階段實耗，再決定是否替 audit 預留時間、調整全程 deadline 或縮減上游輸入／輸出；不能單憑增加 `max_tokens` 推論已解決。

此輪未逐項重審 1.4.0 的來源語意、病人風險或所有舊模式端對端行為，也未核對任何新 live 結果。就所讀截斷／會計路徑，未見阻擋性資料放行問題。
