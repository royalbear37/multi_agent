# v2 實作與接續待辦（2026-09-18）

## 本輪目標

建立安全、可選的獨立 Agent v2：各 Agent 有輸入／輸出 schema、個別模型呼叫、上游依賴與 trace；保留舊流程作為比較基準。

## 已完成

- [x] 五個獨立角色及 prompt：case、AST、evidence、clinical、synthesis。
- [x] 每角色的輸入／輸出契約，拒絕額外欄位、無效引用、未知藥品與不允許的方案文字。
- [x] 明確的上游輸出傳遞、每藥引用連結、整合候選取交集及排除；人工編輯保留相同邊界。
- [x] 規則／族群 preflight、最終安全 gate、必要 Agent 失敗或不確定時暫緩；無生成回退。
- [x] 獨立呼叫／重試、模型覆寫、輸出 token 上限、總呼叫次數及協調截止檢查。
- [x] Trace 記錄模型、prompt 版本、輸入輸出 hash、依賴 span、時間、錯誤、每次用量；未知費用不填 0。
- [x] 一般 run 的增量 checkpoint；公開 API／trace／export／benchmark 隔離未通過結果。
- [x] API 新模式、角色契約查詢、前端選項與 trace 展開、可選五模式比較、按 Agent 統計。
- [x] 原有四模式仍可執行；開發前已保存程式快照。

## 驗收狀態

- 已通過新增 22 項後端測試，包含獨立呼叫、結果傳遞、格式／引用錯誤、來源外送阻擋、逐次保存、重試、預算、截止時間、人工審閱邊界與族群檢查。
- 全套後端 146 項通過（原有 124 + v2 新增 22）；4 個既有套件棄用警告。
- 前端元件測試 10 項通過；TypeScript、Vite 正式建置通過；瀏覽器 E2E 8 項通過（含 v2 完整流程）。
- OpenAPI 與前端 API 型別已重新產生。Windows 前端測試需要沙箱外的套件目錄存取；測試使用獨立 runtime，不操作使用者資料庫。
- 全部驗證使用獨立編寫的合成資料及 mock／攔截 HTTP；尚未使用真实 CSV、WHO 全書或付費生成 API。

## 接續事項（不可當作已完成）

0. **Sol／High 程式審查尚未完成**：已依指定啟動 GPT-5.6 Sol／High reviewer，但服務回報「Selected model is at capacity」。沒有改用其他模型或宣稱審查通過。下一輪優先使用 Sol／High 審查新增的 contracts_v2.py、runtime_v2.py、workflow/v2.py，以及 engine.py/main.py 的整合、安全邊界與 trace 隔離；審查意見修正後才做後續 live 驗收。

1. 使用獨立合成病例與新 key 做少量 live 驗收，確認五個實際模型呼叫的格式、延遲、用量、prompt 品質；不要直接對整份 CSV 跑 benchmark。
2. 完成 WHO 適用片段整理、族群與引用支持的人工核對，再決定哪些病例可啟用 reference 工作流。CSV／WHO 已放在工作區 incoming_data，本輪未匯入。
3. 保留 HANDOFF_2026-09-17.md 所列原工作站 benchmark 診斷、檢索召回率評估、AST 方法／單位、交叉過敏／交互作用／腎功能等待辦；v2 架構完成不代表這些臨床／資料工作完成。
4. 若研究需要雙向交叉質疑或多輪辯論，需另訂回合數、停止條件及評估設計；本版為單輪有向協作、固定序列排程。
5. Benchmark 可再增加每次 Agent checkpoint、伺服器事件串流、取消執行，以及正式用量／費率帳務。當前 benchmark 完成單個 run 才保存，cost 為 null。
6. 個人工作台目前沒有新增使用者認證或診斷內容的角色權限；中間完整紀錄僅留本機資料庫，若要多人部署需先設計存取控制。
7. 尚未上傳 GitHub 或建立 PR。提交前排除 .env、incoming_data、來源 CSV、WHO PDF 及本機 runtime；既有 modified 程式在 multi_agent_download/multi_agent-main，github_latest 是比對副本。

## 用量收尾規則

使用者補充：節省 token，後續一般子代理使用 GPT-5.6 Luna／High，PR／程式審查使用 GPT-5.6 Sol／High。避免重複掃描、冗長回報與無關並行工作。

依使用者最新要求：五小時或每週用量任一剩餘接近 10% 時開始收尾，保存可驗證進度並更新本檔；此要求取代先前交接檔的 5% 門檻。不使用重置額度。記錄最後通過測試、未完成項目與下一個具體步驟，不把離線測試寫成 live 或臨床驗證。

本輪收尾檢查：五小時剩 14%、每週剩 53%；v2 實作及離線驗收完成，已開始收尾以保留餘額。Sol 審查因容量不足未完成，真實模型驗收尚未執行。

## GitHub 草稿 PR 交接

- 已在 multi_agent_pr 建立乾淨 worktree，分支 codex/multi-agent-v2；已成功 fetch origin main。
- 尚未將修改版程式複製進該 worktree，尚未 commit、push 或建立草稿 PR；GitHub 主分支未修改。
- 修改版仍在 multi_agent_download/multi_agent-main。github_latest/backend/.env.example 有使用者修改，請保留，不可直接提交或顯示其中可能的憑證。
- 下一步：核對遠端基準、只整理程式／測試／文件至 multi_agent_pr，排除資料集、PDF、.env、runtime、依賴與任何金鑰，再掃描待提交內容。
- Git 尚未取得 user.name/user.email，提交前需向使用者確認提交署名與電子郵件（可使用 GitHub noreply 位址）；GitHub 登入及推送權限尚未驗證。gh CLI 未安裝，可在推送後透過瀏覽器建立 draft PR，勿合併 main。
- 最新用量檢查：五小時剩 0%、每週剩 50%；依 10% 收尾要求暫停後續工作，未使用重置額度。
