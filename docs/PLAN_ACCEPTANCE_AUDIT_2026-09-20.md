# 依《計畫資訊參考》之專案驗收盤點

盤點日期：2026-09-20。基準：使用者提供的《計畫資訊參考.pdf》，共 13 頁。範圍：此工作目錄的程式、設定、測試、文件，以及前次已保存的 live／前端測試紀錄。此次只盤點，不修改系統功能、不重跑付費模型。CSV 規則重寫待辦依使用者要求暫緩。

## 判讀原則

**本期驗收的是研究原型，不是可正式執行醫囑的產品。** PDF 第 2、6、7、11 頁明確容許 demo、synthetic case、測試文件與研究報告；正式院端串接、正式臨床試驗、醫囑介入、正式資安驗證、商用部署與維運不屬本期必要驗收。

四種主標記互斥，每列按其列名限定範圍判定：
- **完全未做**：本工作目錄未找到該交付物或能力的實作／成果。不能據此認定合作單位在別處也沒做。
- **已做但不完整**：已有對應能力，但要求中的處理、驗證或交付文件缺一部分。
- **僅 demo**：主要以合成內容、固定展示條件或樣例完成，可支持原型展示，不能宣稱真實臨床能力。
- **功能完整**：限定的原型工程功能已實作，有相應測試或實際紀錄，不代表整個模組或臨床適用性完整。

「僅 demo」不自動等於驗收失敗；「功能完整」也不代表整體計畫已驗收。以下列出功能狀態及對本期交付的影響，不任意計算完成百分比。

## A. 完全未做／未找到成果

| ID | PDF 要求與位置 | 狀態 | 查核結果與本期影響 |
|---|---|---|---|
| A1 | 國際論文初稿或投稿資料 1 篇；p4 Table 3、p10 Table 9、p11、p13 | 完全未做 | 搜尋專案未找到論文初稿、投稿資料或成稿。屬明確交付物；不是現在必須到期，但目前尚無可驗收成果。 |
| A2 | 期中、期末報告書；p11 交付條款 | 完全未做 | 有 README、技術筆記、測試與修正紀錄，未找到依計畫編製的期中／期末報告書。不能把開發筆記直接算正式報告。 |
| A3 | 指引檢索後的重排序；p10 Table 9 第 3 項 | 完全未做 | 有關鍵字／向量相似度排序，未找到獨立的檢索後 reranker。若以廣義排序解釋此要求可再議，不能宣稱已做獨立重排序模組。 |
| A4 | 管制抗生素的政策檢查；p3 Table 2 安全閘門 | 完全未做 | 未找到管制清單、放行條件、限制理由或審核流程。既有同名過敏及來源藥敏排除不是管制抗生素檢查。 |
| A5 | 合作醫院醫師／藥師確認用藥品項與院內政策；p6、p8 Table 7 | 完全未做 | 本目錄未見合作醫院确认清單、政策簽核或具名專家確認紀錄；CSV 字典與 LLM 模擬醫師回饋都不能替代。不是要求即時院端串接。 |

## B. 已做但不完整

| ID | PDF 要求與位置 | 狀態 | 已有／缺口；本期驗收影響 | 證據 |
|---|---|---|---|---|
| B1 | 資料欄位盤點、hospital adapter prototype；p3、p5、p7、p11 | 已做但不完整 | 已有病例契約、兩種 JSON 格式及 CSV 轉換；但缺依 PDF 各資料源整理的完整欄位對應與輸入／輸出交付包。舊文件仍寫只支援 synthetic，與現況不符。無需正式 EHR API。 | `backend/app/schemas/case.py`、`backend/app/adapters/`、`contracts/`、`docs/DATA_AND_RULES.md` |
| B2 | AST/MIC/breakpoint 測試規則表及範例；p2、p4、p7–8 | 已做但不完整 | 有 S/I/R 來源篩選、版本化展示矩陣及測試；目前不以 MIC 數值和 breakpoint 閾值進行判讀，demo 矩陣也只核對既定 S 標籤。缺可讀規則表與邊界範例。真實 CLSI 引擎並非本期必需，但不能把現有矩陣算完整 MIC/breakpoint 測試。 | `backend/app/rules/engine.py`、`reported.py`、`configs/demo/rules.json` |
| B3 | 腎功能安全提示規則；p2–3、p8、p10 | 已做但不完整 | 有 eGFR、單位、透析等欄位，會檢查缺漏；未有依腎功能條件而觸發的具體藥品限制／提示規則。LLM 描述腎功能不等於確定性規則。 | `schemas/case.py`、`rules/reported.py`、`configs/demo/rules.json` |
| B4 | 過敏及禁忌條件；p2–3、p10 | 已做但不完整 | 同名藥品過敏能排除，過敏未知會提示；缺明確分類的禁忌測試表，亦未有類別／交叉反應規則。後兩者不能以同名比對冒稱完成。 | `rules/reported.py`、`workflow/safety.py` |
| B5 | RAG 證據鏈支持建議；p3、p5、p9–10 | 已做但不完整 | 文件與引用可追溯，但只檢查引用存在和範圍，未證明文字支持病例／藥物結論；模擬醫師發現 WHO 引用條件與既有候選情境可能不符。醒目提示尚未驗證不等於完成支持性驗證。 | `workflow/safety.py`、`workflow/v2.py`、`docs/PHYSICIAN_UI_REVIEW_2026-09-20.md` |
| B6 | 治療指引、院內政策、抗藥性背景的版本化內容；p3、p8、p10 | 已做但不完整 | 通用文件系統與 WHO 已有；未見經確認的院內政策及真實抗藥性背景內容包。synthetic policy 可供展示但不能當醫院正式政策。 | `rag/service.py`、`data/demo_documents/`、`configs/demo/resistance.json` |
| B7 | RAG 索引測試文件初版／測試報告；p3、p8、p11 | 已做但不完整 | 有解析、去重、版本、定位、向量與失敗分支單元測試及開發紀錄；缺對照查詢、預期片段、實測結果、品質缺口的集中驗收報告。WHO 表格及全文切段品質未完成系統性人工驗證。 | `backend/tests/test_rag.py`、`docs/RAG_AND_PROVIDERS.md` |
| B8 | 安全閘門、警示／阻擋紀錄；p3、p8–10 | 已做但不完整 | 有硬性規則、白名單、輸出格式及引用檢核，v2 待確認狀態可繼續；但此次全套測試 6 項失敗，寬鬆策略與舊驗收預期未統一，不能直接標全部通過。 | `workflow/safety.py`、`workflow/v2.py`、`tests/test_safety_regressions.py` |
| B9 | 候選／避免清單的解釋與品質；p1–2、p5–6 | 已做但不完整 | 已能輸出、展示與審閱；未選藥缺逐藥比較理由，引用適用性未驗證，模型仍可能把模擬情境写成事實。資料結構完成不等於建議品質完成。 | `frontend/src/Insights.tsx`、`ClinicalContext.tsx`、既有 live 紀錄 |
| B10 | 四架構差異化 benchmark 報告；p3、p8–10 | 已做但不完整 | 比較執行器、分母、N/A、逐模式統計與匯出存在；但缺固定研究設計、可信標註及結果討論的完整比較報告。引用支持性、適當性、專家一致率、臨床效用仍明列 not_evaluated。 | `workflow/benchmark.py`、`docs/WORKFLOW_AND_BENCHMARK.md` |
| B11 | 可用性與醫師／藥師審閱驗證；p6、p8 | 已做但不完整 | 有 UI 測試及 Sol/high 模擬醫師操作回饋；缺實際醫師／藥師審閱與驗證結果。模擬角色不是臨床專家。正式臨床試驗則不在本期必要範圍。 | `docs/PHYSICIAN_UI_REVIEW_2026-09-20.md`、前端測試 |
| B12 | 移轉文件與後續平台化／場域規劃；p4、p7–8、p12–13 | 已做但不完整 | 架構、API、啟動和操作說明存在；缺整合的場域延伸驗證方案、責任／輸入輸出交付清單，且多份舊文件與新版實作不一致。 | `README.md`、`docs/ARCHITECTURE.md`、`contracts/IMPLEMENTATION.md` |

## C. 目前僅 demo 功能

| ID | PDF 要求與位置 | 狀態 | 實際能力／本期判讀 | 證據 |
|---|---|---|---|---|
| C1 | 完整病例情境展示；p2、p4、p6 | 僅 demo | 來源 CSV 提供菌種／藥敏，年齡、感染情境、腎功能、過敏等是補寫模擬欄位；有 16 份 synthetic fixtures。足以支撐模擬流程，不能當完整真實病歷。 | `adapters/microbiology.py`、`data/synthetic/` |
| C2 | 抗藥性背景整理；p1、p3、p5–6 | 僅 demo | 讀取固定 synthetic resistance records，可展示背景與保守限制；沒有公開抗藥統計、院內 antibiogram 或趨勢計算。可展示節點，不算完成真實趨勢分析。 | `configs/demo/resistance.json`、`workflow/engine.py` |
| C3 | MALDI-TOF／快速鑑定介面與早期訊號；p5–7 | 僅 demo | 有方法、結果、時間、來源欄位，能轉換／顯示既有資料；沒有儀器資料處理或風險模型。PDF 要求預留介面，故此 demo 能支持本期介面展示。 | `schemas/case.py:112`、`adapters/case_adapter.py`、`workflow/engine.py` |
| C4 | 合成規則与警示範例；p2–4、p8 | 僅 demo | DEMO_DRUG／DEMO_ORGANISM 與合成背景限制可測警示／阻擋。是软件情境規則，不能當臨床正式規則；本期允許測試規則。 | `configs/demo/rules.json`、`backend/tests/test_workflow.py` |
| C5 | 醫師／藥師角色與作業者；p3、p6、p8 | 僅 demo | 能選 physician/pharmacist 等角色並保存 reviewer_id；目前 demo-user 與角色不是登入驗證。可示範回饋流程，不代表有正式身份或權限治理。 | `frontend/src/App.tsx`、`backend/app/main.py` |
| C6 | mock 模型流程示範；p2–4 原型／synthetic 驗證 | 僅 demo | 固定模板支援離線走完流程並明確標 mock；不能當真實 LLM 效果比較。另有 live provider，不能因此說整個系統都只是假回覆。 | `providers/service.py`、`agents/runtime_v2.py` |

## D. 功能完整（限定原型工程範圍）

| ID | PDF 要求與位置 | 狀態 | 可驗收的具體範圍及邊界 | 證據 |
|---|---|---|---|---|
| D1 | 病例匯入、結構化保存及版本；p1–3、p7 | 功能完整 | CSV／canonical／alternate 轉換、schema 驗證、缺漏警告、新 revision、原 payload 與既有分析快照保存。有工程測試；不含正式院端 API。 | `adapters/`、`schemas/case.py`、`repositories/sqlite.py`、`tests/test_backend_contract.py` |
| D2 | 任務工作流編排；p3、p6、p11 | 功能完整 | 原八節點工作流存在；v2 另有五個獨立模型角色及依賴、輸入輸出契約、錯誤與呼叫紀錄。可供 prototype V1 展示；不保證每個臨床子模組完整。 | `workflow/engine.py`、`workflow/v2.py`、`agents/contracts_v2.py`、`tests/test_agents_v2.py` |
| D3 | 文件匯入與版本化索引機制；p3、p8、p10 | 功能完整 | PDF／MD／TXT、hash 去重、版本、片段定位、關鍵字及 Ollama 向量索引、重建與錯誤處理已實作。此列不包含表格/OCR品質及引文語意正確性。 | `rag/service.py`、`tests/test_rag.py` |
| D4 | 引用快照與原文追溯；p3、p9–10 | 功能完整 | 分析保存引用原文、頁碼／位置、版本；前端可展開、開原件或下載。文件刪除後保留快照，但原檔連結不再可用。此列只驗收可追溯性。 | `repositories/sqlite.py`、`frontend/src/ClinicalContext.tsx`、`tests/test_document_delete.py` |
| D5 | 接受／修改／拒絕與理由記錄；p3、p8–10 | 功能完整 | 回饋表單、保存與重新讀取、原始／修改內容；修改仍受本次允許集合與引用邊界檢查。接受是人工送出，非自動醫囑。角色身份驗證另列 C5。 | `main.py` reviews API、`ReviewEditor.tsx`、`tests/test_acceptance.py` |
| D6 | 執行／規則／證據／版本的作業紀錄；p3、p6、p8、p13 | 功能完整 | 有 run ID、病例版本、規則快照、節點狀態、耗時、可得用量、錯誤及 JSON 匯出；不聲稱正式不可竄改稽核或完整授權追溯。 | `repositories/sqlite.py`、`workflow/engine.py`、`workflow/v2.py` |
| D7 | 四模式比較工具；p3、p9–10 | 功能完整 | rule-only、rag-only、single-agent、multi-agent 可批次執行與分組，v2 可追加；設定固定、mock/live 區分、分子分母與 N/A、保存匯出。研究報告／有效性另列 B10。 | `agents/runners.py`、`workflow/benchmark.py`、`tests/test_acceptance.py` |
| D8 | 原型不自動開藥的操作邊界；p1–2、p5、p11 | 功能完整 | 沒有處方送出／醫囑介接，候選要人工審閱，有禁止方案欄位與文字檢查。這是原型操作邊界，不等同證明所有自由文字臨床安全。 | `workflow/safety.py`、`main.py`、`frontend/src/App.tsx` |

## PDF 明確交付時點的整體判定

| 計畫日期 | 明確交付物 | 現況 |
|---|---|---|
| 115/08/31 | 資料欄位盤點、RAG 索引測試文件初版 | 部分完成：契約與測試存在，集中盤點／索引測試文件需整理，舊文件需核對。 |
| 115/09/30 | Multi-agent workflow prototype V1 ＋期中報告書 | 原型編排可展示；期中報告未找到，故此組交付不能判全部完成。 |
| 115/11/23 | 原型展示版 1 套＋期末報告書 | 展示系統已存在；安全測試預期、MIC/breakpoint 範例、證據品質與部分內容能力不完整；期末報告未找到。 |
| 115/12/31 | 國際論文初稿／投稿資料 | 尚未找到。 |

日期取自 PDF；若實際簽約較晚，細部時程需依文件條款和實際契約確認。本盤點不據此判定已逾期或違約。

## 此次新驗證與已知問題

完整執行 `backend/.venv/Scripts/python.exe -m pytest -q`：**176 passed、6 failed、4 warnings**。

六項失敗均位於 `test_safety_regressions.py`：
- 三項測未知藥品、偽造文件引用、偽造規則引用時，舊測試要求整份 blocked／output=None；現在 demo normalizer 會移除無效項目，整份仍可能 ready_for_review。
- 三項測 rag-only、single-agent、multi-agent 的候選／避免重疊；舊測試要求整份拒絕，現在移除重疊候選而保留其餘輸出。

**這是安全契約與寬鬆實作／測試未同步的明確缺口，不等於已證明無效藥品或偽造引用被發布。** 須先決定可驗收策略，再檢查空候選狀態與測試；不能只刪測試或改成通過。本輪遵照暫緩指示，不做修正。

前端 25 項通過及 build 通過為前一輪驗證紀錄，本次未重跑；Sol/high 模擬醫師測試報告僅為介面可用性證據。沒有新付費 live 呼叫。

## 明確不列為本期缺失的項目

依 PDF p7、p11：正式 EHR/LIS/HIS/藥歷/儀器即時 API、正式院端部署與維運、商用整合、正式資安驗證、IRB 後的真實醫院 silent-mode／臨床試驗、實際醫囑介入均非本期必要驗收。FHIR 可作後续延伸，不因未實作正式 FHIR 串接而直接判本期不合格。

## 結論

目前是**可運作且具版本與審閱機制的研究原型**，不是只有 UI 模型圖；但**功能展示版、驗證品質及正式交付文件三者尚未全部齊備**。最需要在驗收說明中明列的差距是 MIC/breakpoint 測試規則、腎功能／禁忌／管制條件、真實抗藥背景與政策內容、引用支持性、安全策略測試一致性、比較／索引測試報告及論文／期中期末報告。舊 CSV 規則重寫只是一個待辦，不會自動補齊上述計畫交付物。
