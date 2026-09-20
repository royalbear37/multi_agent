# 工作完成紀錄：2026-09-20

先前依五小時額度門檻暫停；額度恢復後完成剩餘工作。

## 修正與驗證
- 修正 v2 NON_SYNTHETIC_EVIDENCE：必要病例欄位及所選文件片段共用明確外送許可；本機模型不需外送許可。
- WHO 第 2、44、310、592、644、696 頁核對為空白並更新 metadata；片段、向量及歷史快照保留。
- 正常文字切段及空白頁提示預設折疊；需要 OCR 的頁面仍直接提醒。
- 一次授權 live 已完成並保存：b896b5b3-e0cc-4dd0-a0c2-dcb3d9514557。
- 病例 api-demo-source-ast-001，multi-agent-v2，gpt-4.1-mini，5 次呼叫，5 個 Agent 均執行，ready_for_review；前四個 needs_confirmation，整合 completed。
- 1 項 demo 候選 vancomycin，保留 6 項原規則排除。引用存在不等於已驗證臨床適用性，仍需人工核對。
- 額外 live 未執行；既有一次授權已消耗。

## Sol / high PR-style 審查
審查者 /root/review_rag_fix（gpt-5.6-sol，high）。因目錄無 git，採檔案層級 PR-style 審查，未建立 GitHub PR。

發現及修正：
1. 舊生成模式漏檢查文件片段外送許可：共用 provider 現在於投影及 HTTP 呼叫前逐片段檢查，補六種情境測試。
2. 合成病例隱藏外送控制：所有病例均顯示控制，UI 測試驗證合成病例可保存許可。
3. 真正 OCR 警告被折疊：只折疊 blank 與 long_text_split，測試驗證 requires_ocr 可見。

Sol / high 複核：三項均解決，無新增可處理問題。
最終驗證：backend 86 passed；frontend 21 passed；frontend production build passed。
已同步 MULTI_AGENT_V2.md 的 advisory 與警告說明。

## 使用
重啟後端、重新整理前端以載入修改。已保存的 live run 可供查看，歷史 run 保留原快照。
本次要求已完成，無剩餘程式待辦。
