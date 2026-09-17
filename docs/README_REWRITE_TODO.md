# README 改寫接續事項

狀態：**已完成（2026-09-16）**。使用者繼續後，已把所有現有功能教學整合到根目錄 [README](../README.md)，共 15 個章節。已檢查相對連結、目錄錨點、腳本路徑、程式碼區塊配對及 diff 空白格式；按鈕名稱與功能已對照程式。此次僅文件修改，不重啟服務或呼叫模型。

以下保留先前額度不足時的交接紀錄，**不是仍未完成的待辦**。

先前更新：2026-09-16。使用者要求改善 README，並把所有功能教學直接寫進 README。使用者另要求額度剩 5% 時暫停並記錄待辦；當時查詢剩 6%，先保存交接。

## 現況

- 已讀取 README、setup/run/seed/prepare_demo 腳本、App.tsx 的功能與按鈕，以及 USER_GUIDE_ZH_TW、WORKFLOW_AND_BENCHMARK、DATA_AND_RULES。
- 完整改寫補丁因同一次 patch 對 README 同時 Delete/Add 被拒絕，原 README 未修改，沒有需要恢復的半成品。
- 其他先前程式修改均保留；本次不需重跑應用測試或重啟使用者服務。

## 下一次直接完成

1. 使用 apply_patch 的 Update File 改寫 README，避免在同一次 patch 對同一路徑 Delete/Add。
2. 章節順序：目錄 → 首次安裝 → 建立 .env／Git 忽略 → OpenAI＋Ollama → 前後端啟停 → 離線 demo → 病例 CRUD／版本 → 分析／狀態 → 證據／trace → 審閱 → 文件與 WHO → benchmark → 匯出備份 → 開發 API／測試 → 排錯 → 限制。
3. 所有操作直接放 README，不只連結到其他教學。requirements 保留 backend，根目錄 setup 已統一安裝前後端。
4. 最後檢查相對連結、目錄錨點、Bash/POSIX 路徑、按鈕文案與 git diff；只改文件，不動 .env 或啟停服務。

## 已確認的重點

- setup 建立 .venv，但不建立 .env；只在檔案不存在時使用 `cp`，避免覆蓋 key。禁止讀出使用者 key。
- 一般 `backend/scripts/run.sh` 讀 .env；`scripts/demo.sh` 明確用 lexical/mock，二擇一啟動。前端另開終端機跑 `scripts/frontend.sh`；首頁 5173，API docs 8000/docs，8000/ 404 正常。
- OpenAI 用 LLM_PROVIDER/live、LLM_BASE_URL、LLM_MODEL、LLM_API_KEY；既有 gpt-4.1-mini 範例與官方來源在 USER_GUIDE。Ollama 負責 embedding，不是回答模型；模型 embeddinggemma、11434、EMBEDDING_TIMEOUT=120。可明確改 lexical。
- 病例 UI 可 JSON 檔案／文字匯入，canonical／alternate，編輯建立 revision、取消、歷史。同 case_id 不代表新病例。以 case-15/16 示範成功，故障案例保留。
- 四模式與 provider 是兩個選擇；mock 不會自動解決 embedding 失敗。multi-agent 是確定性多節點＋一次主要生成。
- 審閱者固定 demo-user，可切醫師／藥師／研究角色。接受、修改、拒絕皆需理由；修改 JSON 再驗證。歷史獨立保存，不改原 run trace。
- 文件單檔 20 MiB，PDF/UTF-8 MD/TXT。WHO 取消 synthetic、選 reference，再重建／檢索；目前病例工作流只查 synthetic。
- indexed 是解析成功，不等於向量完成；同 hash 上傳不更新 metadata。自訂 synthetic 文件可用 doc_id 加進病例 policy_refs；UI 上傳沒有 policy tag 欄位。
- WHO 本機先前匯入 697 頁、1442 chunks，6 頁空文字警告；Git clone 不帶 runtime 原檔。未完整人工檢查表格與相關性。
- Benchmark UI 跑全部已保存病例×四模式，不是只跑目前病例；16 例即64筆結果。live 可能多次付費，API 可指定小批 case_ids/modes。
- run 匯出 JSON；benchmark 匯出逐例與摘要。審閱需 UI/API 另外取，run 匯出不等於整庫備份。無 UI CSV／一鍵整庫匯出。
- 備份前停止後端，保存整個 runtime（含 documents），自訂 DB 時文件在 DB 同層。
- 8000 占埠先確認 PID/命令，不能直接引用舊聊天 PID。健康檢查 /api/health。
- 歷史驗證：81 backend、4 component、4 E2E、build 通過；coverage 86%。不能宣稱這次文件修改重新跑過或真實模型已測通。
