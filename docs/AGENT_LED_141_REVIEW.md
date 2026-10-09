# Agent-led 1.4.1 輸入脈絡唯讀審查

日期：2026-10-09。範圍：`backend/app/workflow/input_context.py`、`agent_led.py` 的證據選段與上下游資料、`runtime_led.py` 版本、`v2.py` 公開節點白名單、`frontend/src/AgentLed.tsx` 版本相容，及直接相關測試／v11 離線重播。沒有修改程式、呼叫外部模型或啟動新 live run。此審查針對先前 v11 的 Clinical／Synthesis 在 180,000 字元輸入檢查前失敗；不把離線 stub 視為真實臨床或引用 audit。

## 根因與 1.4.1 修正

- v11 保存的 `evidence_agent` 輸入為 175,014 字元，其中 `evidence` 物件約 150,994 字元，即使選取的原文受 65k 限制，儲存用中繼資料仍佔大量序列化空間；Clinical／Synthesis 當時的失敗節點輸入已隱藏，無法從保存檔精確拆分每一欄。1.4.1 的 `compact_sources()` 在送模型前保留原文、chunk/doc ID、版本、位置、族群、文件類型、研究設計、來源文件 ID、來源網址、地區，以及 `is_synthetic`／`external_model_allowed`，省去大型儲存細節；快照仍完整保存。`evidence_for()` 同時計算原文 65k 與壓縮後來源物件 120k 預算，最後還有原有 180k 整筆輸入上限。
- Synthesis 不再重送已選原文與每筆 specialist quote。`synthesis_assessments()` 將 specialist `quotes` 換成 `evidence_refs`，`evidence_for('synthesis_agent')` 只帶各有效角色輸出實際引用的 來源 metadata catalog。這能消除來源原文與專科回覆的重複序列化；catalog 仍有 `chunk_id`、`doc_id`、版本、位置、類型、族群及 `source_document_id`，但**沒有原文**。因此 Synthesis 不能自行重新讀全文，引用語意仍必須由後續獨立 audit 檢查。
- `assessment_source_refs()` 遞迴收集頂層、逐藥及 nested risk detail 的 `evidence_refs` 和 quote `chunk_id`。Audit 的輸入由 Synthesis 聲明與臨床風險聲明的 refs，回到 `evidence_snapshots` 取**原始原文**，並保留原病例事實與 AST 原始索引；`claim_checks.py` 仍要求感染、族群、藥品與五面向分項複核。未完成 audit 時不會因 catalog metadata 或 Specialist `supported` 直接升為候選／`review_option`。
- 1.4.1 已加入 `v2.py` 可公開的已完成 Agent 節點版本集合；前端 `AgentDrugTable` 同時辨識 1.4.0、1.4.1 分層欄位。舊 run 的版本顯示路徑仍保留。

## 離線核對結果與限制

`backend/tests/test_input_context.py` 三項測試覆蓋 metadata 壓縮不改原文／權限／位置、巢狀風險 refs 收集與完整 mock 流程。父任務回報 334 項後端、49 項前端及 build 通過。`data/local/agent_cases/v11-replay-141.json` 用 v11 保存的檢索與前三角色回覆、後三角色本地 MOCK 重播，外部呼叫 0，6 個 stub 呼叫無錯：Evidence 139,304、Clinical 155,042、Synthesis 72,076、Audit 24,175 字元，均低於 180k；原 AST 與送入的來源原文相同。Evidence 選取 73／86、Clinical 79／230，分別省略 13、151 個片段；選段 coverage、`omitted_refs` 與限制訊息仍保留。另依 1.4.1 選段排序及預算重建 v11 Evidence 輸入，88 段引用涉及的 63 個獨特 `chunk_id` **全部在 73 個選段內**，本次重播沒有遺失前三角色已引用來源。

**目前未見阻擋下一次已授權 live 驗證的程式缺陷。** 但這項結論限於 v11 保存資料的離線重播：Clinical、Synthesis、Audit 在重播中仍是 mock，未證明真實模型輸出大小或逐藥語意。Clinical 只收到 79／230 個檢索片段，省略的 151 個可能含有個別藥品的重要限制，不能把「未看到」解讀為「已排除」。若真實 Synthesis 或 Clinical 引用大量來源，Audit 仍會送完整原文且沒有另外的選段預算，可能再碰 180k 上限；那會安全地使 audit 失敗並保留待確認，但無法完成獨立複核。v12 應核對 audit 是否真正呼叫、每藥五面向及引用語意是否通過，特別是 v11 審查已發現的錯藥、成人／兒童及上／下泌尿道錯配。
