# 暫停與續作待辦（2026-09-19）

## 2026-09-20 續作完成

- 額度恢复後已接續完成本文件列出的開發與驗證；下方保留原暫停紀錄供追溯。
- 已修正刪除按鈕測試的 summary 定位，更新 API 型別並完成前端建置。
- 指定文件表單以病例 ID／revision 重建，新增測試驗證切換病例不殘留勾選，以及保存指定文件／切回全庫。
- 刪除時暫存原檔位元組至 transaction commit；一般 commit 例外會回復原檔並 rollback metadata，新增測試通過。此補償不承諾斷電或程序強制終止的跨 SQLite／檔案系統原子性。
- 後端相關回歸 96 passed；前端 16 passed；`npm run generate:types`、`npm run build` 通過。
- 本機 lexical 檢索目前 api-demo-source-ast-001：scope=reference、policy_refs=[]、status=ok，取得 8 個片段，全部來自 who。這只是本機检索驗證，不代表已完成模型或臨床適用性驗證。
- 未刪除使用者現存文件，未呼叫外部模型。
- 使用者操作：重啟後端並重新整理前端；新分析採更新後文件範圍。歷史 run 不改寫。
- 目前此開發任務無未完成必要項目。額度暫停偏好仍維持有效。

## 暫停原因與使用者要求

- 使用者要求五小時剩餘 <=5% 或每週剩餘 <=3% 時停止工作並撰寫待辦。
- 最近檢查：五小時剩餘 3%（usedPercent=97）、每週剩餘 83%。已停止功能修改與測試。
- 後续若使用 subagent，使用者指定 Luna、high reasoning。本輪未使用 subagent。

## 目前任務

1. 文件資料庫／文件版本內加入「刪除此文件」按鈕，供刪除誤傳檔案。
2. 病例分析預設從文件庫全部真實參考文件搜尋，包含 WHO，不再固定測試文件；保留指定文件能力。
3. 解釋全庫檢索的限制：相關性、版本衝突、族群適用性；合成測試文件不混入 reference。

## 已完成程式與資料變更

- `backend/app/rag/service.py`：delete_document 刪除 embeddings、FTS、chunks、document 與原始檔；檢查 resolved 原檔路徑只在 originals 目錄；連線啟用 foreign_keys，避免刪除後並行 reindex 再插入孤立向量。
- `backend/app/main.py`：DELETE /api/documents/{doc_id}，CORS 允許 DELETE；404/422/409 處理。保留別的資料庫中 run 的證據快照，原檔連結會失效。
- `frontend/src/api.ts`：api 支援第三參數 DELETE。
- `frontend/src/App.tsx`：文件版本刪除按鈕、確認提示、刪除後更新列表並清除搜尋結果；沒有替使用者刪除任何現存文件。
- 病例工作台增加「使用文件庫全部參考文件」與「改為指定參考文件」表單，透過新 revision 保存。
- `backend/app/workflow/engine.py`：reference + policy_refs=[] 代表全參考庫，不再當缺漏。歷史 synthetic 空 policy 仍依原邏輯。
- `backend/app/adapters/microbiology.py`、`backend/scripts/import_microbiology.py`：--policy-ref 改為可選；未指定時新來源病例用 reference + 空 policy_refs。
- `backend/scripts/use_reference_library.py` 已建立且已執行：16 個本機 local-microbiology-csv 病例新增 revision，切換 reference + policy_refs=[]；15 個 prepared cases 亦更新。包含 api-demo-source-ast-001（revision 5）。來源 AST、外送許可與既有 run 未改寫。
- README 更新新匯入命令、文件刪除及全庫檢索說明。
- 已執行 generate_contracts.ps1，contracts/openapi.json 已有 DELETE endpoint；尚未重新生成 frontend/src/api.generated.ts。

## 驗證結果

- 後端：`tests/test_document_delete.py tests/test_rag.py tests/test_reported_cohort.py tests/test_agents_v2.py` 共 95 passed。
- 刪除測試涵蓋向量／FTS／原檔移除、保留其他文件、再上傳、越界路徑拒絕、API 404，以及 reference 全庫排除 synthetic／指定不存在文件不退回其他文件。
- 前端：14 passed、1 failed。失敗是新增 `App.test.tsx` 測試的文字查詢匹配 summary 與原始 JSON 兩個元素，不是已知功能故障。
- 最新功能變更後尚未 build；先前 agent 顯示修改有成功 build。

## 續作順序

1. 先查額度；仍達門檻時不要繼續。
2. 修 `frontend/src/App.test.tsx` 新增 delete test：`screen.getByText(/Wrong file/)` 改為只匹配 summary，例如 `{selector:'summary'}`。修好後重跑前端測試；必要時處理後續失敗。
3. 執行 `npm.cmd run generate:types` 更新 API types，再 `npm.cmd run build`。Windows esbuild 在沙箱中讀上層目錄 Access denied，先前以 require_escalated 成功；不得把本機 build 當成資料外送。
4. 補／檢查病例 UI 選全庫及指定文件的測試，確認多選表單切病例後 defaultChecked 不會殘留；必要時用病例 revision 作 form key。
5. 檢查刪除原檔與 SQLite commit 的故障一致性（目前 unlink 在 DB transaction commit 前；極少數 commit 失敗可能留下文件 metadata 但原檔已刪除）。考慮暫存 rename 與 rollback 恢復，或明確可恢復設計。
6. 確認新 UI 與 README 的所有敘述一致：synthetic 舊案例空 refs 仍不是 reference 全庫；reference 新案例可全庫。
7. 可做不外送病例的本機 WHO 檢索驗證；原 WHO metadata 為 population=all，status=indexed_with_warnings，是否真適用仍需核對。不要宣稱全庫搜尋保證 WHO 片段被採用或候選有支持。
8. 重啟後端／重新整理前端後，使用者需建立新分析才看到新證據來源；舊 run 仍引用原合成文件。
9. 最終向使用者說明已改內容、測試結果與全庫搜尋限制。此任務暫停時仍未驗證完成，不可宣稱全部完成。

## 先前 v2 狀態（避免重做）

- v2.4-demo 已可跑完來源病例配合合成測試文件；最後已成功 run `be52f63a-83d1-4230-881f-243b82aabb93`，其 policy_refs 為 api-demo-policy-v1，所以未引用 WHO。
- 病例整理、AST、證據、臨床 agent 的 needs_confirmation 在 demo 中為提醒，保留限制；逐藥 support 引用仍需存在。
- Agent 展開後已直接顯示缺漏、限制、findings、逐藥支持，不再只有 JSON。
- 模型整合失敗時會顯示明確標示的「來源藥敏整理結果（demo）」；不冒充模型推薦、不允許把此整理接受成模型候選。
- 曾由使用者明確同意一次外送 api-demo-source-ast-001 到 gpt-4.1-mini 的 live 驗證，該一次已用完。本次只做本機開發與測試，未再外送。
