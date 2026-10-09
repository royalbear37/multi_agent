# Agent-led 改版進度與續作待辦

2026-10-05 因使用者設定的額度門檻暫停：五小時額度已用 96%（剩 4%）；每週已用 18%。尚未完成整份計畫，不能宣稱 live 驗收完成。

## 已實作及驗證

- 新增 `contracts_led.py`、`runtime_led.py`、`workflow/agent_led.py`；multi-agent 預設走新流程，不呼叫 RuleEngine。五角色六次呼叫，最後獨立引用複核；逐藥結果、可定位原文、資料缺漏與部分失敗保留。
- 人工審閱改依已複核藥品與引用邊界；歷史 v2 保留舊解讀。`test_agents_v2.py` 明確以 fixture 測歷史實作，現行 public dispatch 由 `test_agent_led.py` 覆蓋，包含禁止 RuleEngine、偽造引用、未知藥、衝突、未測 AST 及部分失敗。
- 文件服務新增 SQLite 全語料快照、多查詢與相鄰片段；benchmark 的新模式改使用固定語料，不再將每次查詢替換成第一次結果。
- 前端新增 Agent 逐藥決策表、各角色專屬報告與缺漏表；benchmark 可勾病例與模式；更新 review 選項及 API 型別。
- 後端完整測試 **198 passed**；前端 **26 passed**；`npm run build` 通過；`git diff --check` 無格式錯誤。
- 新增三支準備程式：`build_agent_cases.py`、`prepare_agent_references.py`、`install_agent_package.py`。
- 病例在 `data/local/agent_cases/`（gitignored）：八情境及一個腎功能修訂；源自 CSV 的 AST 不覆寫，臨床補寫有 provenance。來源 CSV 4,960,599 列，E. coli 尿液來源統計 51 藥，本例 18 筆 AST。統計依 culture-organism-drug 去重，列出缺漏、衝突和分母。
- 22 份參考／負向測試文件已匯入目前 main.repo 使用的本機資料庫。公開來源及 SPL 版本在 `data/local/agent_references/manifest.json`；八病例及文件 ID 在 `data/local/agent_cases/installed.json`。下載器篩掉局部劑型，針劑藥指定 INJECTION。
- WHO PDF 第 297 頁（印刷頁 281）已用 Poppler 渲染人工視讀，確認為成人 lower UTI 治療頁。暫存 `tmp/who-297.png`；完整下泌尿道章節文字抽取仍須再檢查成人／兒童圖示在抽取時遺失的問題。

## 暫停時的 live 驗證

- 已開始的 run：`91d18a40-971e-45d6-bdef-b21c3cdcb564`，病例 `agent-complete`，外部 `gpt-4.1-mini`。
- 暫停前保存的節點：case_agent 需確認、ast_agent 完成、evidence_agent 需確認。當時尚在逐藥風險文件檢索階段。
- 收尾時程序已自行結束，exit 0；run 最終為 `partial / needs_confirmation`。共 4 次模型呼叫、3 個步驟完成；clinical_agent、synthesis_agent、evidence_audit 均記錄 `AGENT_BUDGET_EXCEEDED`。18 項藥品全部待確認，沒有發布候選。不能當作 live 驗收成功。
- 完整輸出已保存 `data/local/agent_cases/live-complete.json` 及 SQLite；沒有停止使用者的後端，也沒有仍在運作的這次驗證程序。

## 下一步（依序）

1. 先讀完整 git diff 作工程審查。特別檢查新流程的藥名正規化、未測 AST 身份、局部失敗隔離、支援條件和案例資料欄位是否完備。現在是第一輪實作，還需要審查。
2. 修正/確認檢索預算：目前每藥最多兩階段查詢、前 30 藥及 65,000 字證據上限。超量、截斷、索引失敗需明確記錄；不要在長時間 lazy indexing 後把全部剩餘 Agent 都耗到逾時。可先 reindex reference，再開始限定 live 測試。
3. 引用複核需測真實 WHO 第 566 頁失配，不僅 stub 回傳 unsupported；確認原文與頁碼、族群、適用感染及藥名一致。WHO 抽取頁碼 293–306 的章節邊界和成人/兒童標題需人工檢查並保存導入說明。DailyMed 節錄的劑型與子章節標題也要逐件抽查。
4. 確認完整病例的「需確認」是哪個欄位。只補人工情境允許的值，不修改來源 AST、不隱藏不確定性；必要時擴充 renal 的不同測量型別，而非將 eGFR 冒充 CrCl。
5. 重跑限定 `agent-complete`、`agent-interaction`、`agent-evidence-mismatch` 的 live 驗證，逐藥核對真實引用並保存結果。原本的 live 已發生部分付費呼叫；重跑需記錄新的 run ID。
6. 補八病例逐一預期結果對照與自動驗收（目前已有情境檔，但沒有涵蓋八情境內容的完整驗收矩陣）；測來源 AST 一致性、抗藥統計分母及重複/缺漏資料邊界。
7. 瀏覽器實測新增表格可讀性、全部 Agent 展開、無候選時保留報告、病例修訂、文件查詢、接受/修改/拒絕、匯出與勾選 benchmark。確認主 App 的舊候選/避免標題及摘要沒有留下誤稱規則排除的文字。
8. benchmark 目前排除了新模式的規則分母，但仍需補檢索量和引用複核結果彙總、混合版本比較標識及病例模式勾選 UI 測試。
9. 更新正式 DEMO 操作稿、README、來源與版本清單、測試報告；目前舊 2026-09-22 操作稿描述的是舊流程，不能照用。
10. 最後跑全套測試/build、檢查 Git diff；清理本次 `tmp/who-297.png` 和 build 產生的 `frontend/tsconfig.tsbuildinfo` 差異（確認原有內容後處理），不要撤銷既有 `backend/scripts/run.ps1`、`docs/USER_GUIDE_ZH_TW.md` 及兩份舊操作稿的未提交修改。

## 續作命令

於專案根目錄：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/verify_agent_live.py --case agent-complete --out data/local/agent_cases/live-complete.json
```

其他測試：backend 目錄執行 `.\.venv\Scripts\python.exe -m pytest -q`；frontend 目錄執行 `npm test`、`npm run build`。本機 Windows 沙箱內 esbuild 讀取父目錄會失敗；已用受核准的沙箱外 npm 指令驗證。

額度恢复後仍遵守使用者偏好：五小時剩 5% 或每週剩 3% 即暫停並更新本檔。若需要 subagent，使用者預設 Luna/high，PR 審查偏好 Sol/high；此輪未啟動 subagent。
