# v8 live 與 1.3.4 修正驗證（2026-10-07）

## 實際 live 結果

使用者在完整範圍問題下直接同意後，只執行一次 live。最初命令遭自動核准審查拒絕、未啟動；重新取得具體同意後才成功執行。此次授權已用完，沒有第二次模型分析。

- Run：`eff53f5a-b59d-4f56-929b-d6deca1eb52e`
- 病例：`agent-complete` revision 4，18筆AST；WHO/DailyMed，未檢索論文背景。
- 執行版本：`agent-led-1.3.3`，模型`gpt-4.1-mini`。
- 六次模型呼叫，六個模型節點皆有格式有效輸出，無重試／schema errors。
- 約216.9秒，168463 tokens（prompt150274／completion18189）；38次本機檢索、170個引用快照。
- 結果：0可供審閱、18待確認。AST18項因來源識別碼錯誤降unknown；clinical18項仍unknown；synthesis18項引用識別碼無效。不是18項臨床不適用。
- 證據與臨床輸入各因長度限制省略15個片段；指引未測AST選項仍未成功展示。

臨床風險格式錯誤已在本次live消失，但來源選取及語意仍未驗收。Sol/high逐字查證：27個證據、80個臨床、13個複核quote可在快照找到；六項audit=supported仍有只引用風險警語、漏核對感染／AST的問題。詳見[來源審查](AGENT_LED_V8_CITATION_REVIEW.md)。case正常事實誤列issues及各角色重複摘要仍是待改善項目。

## API實際操作

1. 執行一次`backend/scripts/verify_agent_live.py --case agent-complete --out data/local/agent_cases/live-complete-v8-source-contract.json`，使用backend虛擬環境，live需直接授權。
2. GET `/api/runs/eff53f5a-b59d-4f56-929b-d6deca1eb52e`查看保存結果。
3. GET同run的`/trace`：八個節點（六個模型步驟＋呈現＋人工審閱）。
4. GET同run的`/export`，保存`data/local/agent_cases/live-complete-v8-export.json`，逐項比對API/run檔/匯出一致。
5. 無候選，未偽造接受／修改；完整候選→審閱仍未驗收。

## 後續本機修正 1.3.4（尚未再次live）

- AST輸入列出逐藥實際欄位ref、值、選定basis；wire schema提供可選來源。null選定欄不改用其他類別、不從MIC重算。動態選項不是臨床規則，也不猜修模型的錯誤選擇。
- evidence_refs／quote chunk IDs列出本次alias選項。整合錯誤引用保留診斷及原始model_reason，公開主要理由說明來源錯誤。
- audit收到逐聲明evidence_refs；無該聲明引文時不能僅憑風險片段標supported。這只是來源最低檢查，仍不能保證語意吻合。
- 藥敏unknown/conflicting節點顯示需確認；未知來源的正面原始理由保存在草稿，不當作有效結論。整合不接收泛用findings，AST降級時也不接收自由摘要。
- legacy/未指定basis強制核對reported_sir；原報告S不能繞過選定R。合法兩來源衝突仍可呈現。
- 舊v8等歷史原文不改，前端來源警語不再把舊未核對肯定句展開。

後端288 passed（4個既有deprecation warnings）、前端43 passed、build及diff check成功。Sol/high程式審查發現三項問題，已修正並複查無阻擋性問題。這些測試不替代新live或專家確認。

後端已重啟載入1.3.4（session82216/PID22812），前端沿用33116，Ollama768維正常。醫師CUA仍無browser，指定前端實際操作未驗收；見PHYSICIAN_UI_RECHECK_2026-10-07.md。沒有新GitHub PR；本次為工作目錄差異審查。
