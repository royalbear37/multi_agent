# 對照需求 MD 的實作核對

日期：2026-09-15。依本次 pull 後的程式與測試核對；`antibiotic_prototype_codex_prompt.md` 是需求基準，不是本次重建指令。狀態：implemented＝工程功能存在；demo_only＝僅展示實作；not_configured＝需外部設定；deferred＝尚未完成或本期排除。

## 主要結論

已有可運作的 prototype，不需要重建。最影響操作的問題是 embedding 預設依賴 Ollama，以及正式文件匯入後原本完全被搜尋排除。本次補參考文件搜尋範圍、完整病例及離線預先執行教學。**尚未成為「輸入真實病人＋WHO 即能產生正式抗生素建議」的系統。**

## 逐項核對

| MD 章節 | 狀態 | 程式證據／仍缺內容 |
| --- | --- | --- |
| 1–4 架構、資料邊界 | implemented / demo_only | React/Vite、FastAPI、本機 SQLite；僅 synthetic 病例、DEMO 藥物，不產生醫囑。SQLite 使用 stdlib 與追蹤 SQL migration，非 SQLAlchemy/Alembic |
| 5 資料契約 | implemented | `schemas/case.py`、adapter、JSON Schema/OpenAPI、revision、原 payload；第二格式有轉換與測試 |
| 6 案例與文件 | demo_only | 原有 14 病例多為缺漏／失敗分支；本次補 2 個有完整背景、快速鑑定及 AST 的成功案例，保留故障測試 |
| 7 八節點工作流 | implemented / demo_only | `workflow/engine.py` 八節點、trace、狀態、錯誤、人工審閱；目前依序執行，沒有節點平行排程 |
| 7 非同步執行 | deferred（部分） | `POST /api/runs` 在同一請求內完成工作，GET 狀態與重啟中斷恢复已存在；不是非同步任務佇列，長時間全文 embedding／benchmark 可能等待很久 |
| 8 規則與候選 | demo_only | 版本化 JSON、受限 operator、AST 展示矩陣、安全閘門、候選引用白名單、生成後驗證存在；不是正式 MIC breakpoint 引擎 |
| 8 腎功能與用藥互動 | deferred（部分） | 腎功能目前重點是必要資料存在；沒有正式調整、透析規則、藥物交互作用引擎。`medications` 已保存，但未參與藥物交互作用推導 |
| 9 真實 provider | implemented / not_configured | OpenAI-compatible Chat Completions、timeout/retry、脫敏與輸出驗證；已 fake HTTP 測試，未真實連線。沒有 Responses adapter 或 reasoning effort 設定 |
| 9 可選 live smoke 命令 | deferred | 目前可透過 UI 明確選 live 做單病例測試；未有獨立專用 CLI smoke-test 命令 |
| 10 RAG | implemented | PDF/MD/TXT、原檔、hash 去重、位置、FTS/lexical、Ollama embedding、SQLite 向量快取、版本指紋與重建；本次加正式參考文件搜尋／索引範圍 |
| 10 WHO | implemented（文件匯入／查閱） | 本次真實附件保存並解析；仍不參與 DEMO 候選推導。正式文件政策映射與臨床規則未做 |
| 10 OCR／表格 | deferred | 無完整 OCR／表格結構還原；空文字／疑似表格採啟發式警告，可能漏檢。尚未逐頁驗證 WHO 全書切段品質 |
| 10 檢索品質 | deferred | embedding failure、排序與索引邏輯有測試；無人工標註的 WHO 查詢集、recall@k 或真實模型品質驗證；未設定相關性最低門檻，top-k 不代表支持結論 |
| 11 保存／審閱 | implemented | cases/revisions/runs/nodes/rules/evidence/reviews/audit/benchmarks 持久化；重跑歷史、引用快照、角色展示、JSON 匯出與審閱重新驗證 |
| 12 UI/API | implemented（主要功能） | 六區、匯入、執行、引用、trace、審閱、設定與 benchmark。多個回應仍為寬鬆 dict／手寫前端型別，尚未所有輸出共用嚴格 schema |
| 13 四模式 benchmark | implemented / demo_only | 有四 runner，依模式控制輸入可見性；multi-agent 是確定性多節點＋一次主要生成，不是多個 LLM 互相討論。無模型回報未設定，mock 明確標記 |
| 13 指標／研究解讀 | implemented（部分） | 分母、N/A、缺漏、引用、schema、阻擋等已計算；臨床適當性／專家一致率未評估。摘要缺耗時分布／token 統計（逐 run 有欄位），成本未設定；不可據 mock 排名得出模型優劣 |
| 14–16 測試 | implemented（離線） | 後端、前端、E2E 測試存在；本次執行結果另外記錄，不沿用舊 coverage 宣稱 |
| 17 交付文件 | implemented（主要） | README、架構、資料／規則、workflow/benchmark、RAG/provider；本次補集中操作教學及此逐項核對 |

## 仍要注意的實作差距

1. `rule-only` 也會執行檢索節點作為 trace，因此預設 embedding 故障會看到 retrieval 問題，即使規則輸出不要求文件。離線展示明確用 lexical 可避免環境依賴造成的混淆。
2. 過敏／抗藥展示規則採全體硬性阻擋，不能期待它自動挑另一種真實藥物。完整成功案例與預期阻擋案例用途不同。
3. `who_status` 原本為固定文字；本次改顯示實際「正式參考文件」數量，並不宣稱任意文件都是 WHO。以文件庫的 hash、來源、狀態、片段與實際檢索為準。
4. 文件來源 hash 不等於文件發布者身分驗證；本次年份取自附件版權頁，版本尾碼 user-supplied 表示使用者提供的檔案。
5. 不會把「沒有 API」「沒有正式規則」移除成假成功；mock 和 DEMO 保留明確標記。成功表示軟體流程可供人工審閱。

## 建議後續優先順序

1. 設定 OpenAI 與 Ollama，先單病例 live smoke，再用人工查詢集驗證 WHO 檢索與引用。
2. 確認感染情境、族群、真實藥物對應、AST 標準與版本、規則来源及審核人，才接正式候選流程。
3. 補用藥互動／腎功能規則與專家標註測試；完成表格與頁碼品質核對。
4. 再做非同步進度、批次索引體驗、嚴格共用輸出 schema 與更完整 benchmark 摘要。

本次可操作步驟見 [使用教學](USER_GUIDE_ZH_TW.md)。
