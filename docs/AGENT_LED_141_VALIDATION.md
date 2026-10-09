# Agent-led 1.4.1 驗證與交接（2026-10-09）

## 最新：2026-10-09 v12已完成，1.4.2已通過本機驗證

v12=6d05f0aa-5f57-43b9-a54d-e133e81b9657，1.4.1／病例4／18AST；6calls/215587tokens/277.7秒。Clinical已完成，Synthesis兩次各用滿6000輸出token而無完整JSON；Audit未執行，18pending/0候選。165引文字面存在，但Sol/high仍發現逐藥語意錯配。一次授權已使用，無新的付費run。

1.4.2已提高整合/複核輸出預算至16000/24000，保存截斷原因並避免同預算重試；339後端/51前端/build/diff check及Sol/high審查完成，醫師誤導文案修正與複驗完成。後端session41976/PID21044載入1.4.2，v12不變；新版尚未live。

使用者新增關注：已known_none的病例不應每藥重問過敏。需優先分開一般標示提醒/病例缺漏/引用缺口，空白不能自動當無過敏；此最新改善尚未實作。完整結果、時間預算風險與下一步見 [v12驗證與1.4.2交接](AGENT_LED_V12_VALIDATION.md)。以下為歷史。

## 已完成

- 去除模型輸入的重複儲存metadata，保留原文、位置、族群、來源版本及外送旗標；完整證據快照保持原貌。
- 逐組主要片段優先，保留65k原文上限，加120k序列化來源預算，省略仍記錄coverage；180k整體輸入上限不變。
- 整合Agent只接收專責Agent實際引用的來源目錄，包含巢狀風險引用；獨立audit仍從原始快照取得聲明所需原文。
- 1.4.0/1.4.1前端分層相容，舊run不重算。

## 本機驗證

完整後端334通過（4個既有deprecation warnings）；前端49通過；build與git diff --check通過。新增3項後端測試包含大型metadata、來源權限/位置/族群保留，以及完整六角色流程。Sol/high審查見 [1.4.1審查](AGENT_LED_141_REVIEW.md)，本次範圍未見阻擋新live的問題。

以 `backend/scripts/replay_agent_context.py` 重播v11已保存檢索與前三角色回覆；去除AST結果上由程式追加的驗證欄位後重新檢查，後三角色使用MOCK。零外部呼叫、六次本機stub呼叫、無錯誤。保存 `data/local/agent_cases/v11-replay-141.json`。

| 角色 | 完整輸入字元 | 來源段數 |
|---|---:|---:|
| 病例 | 12340 | 0 |
| AST | 21668 | 0 |
| 證據 | 139304 | 73 |
| 臨床風險 | 155042 | 79 |
| 整合 | 72076 | 63 |
| 複核（MOCK聲明） | 24175 | 0 |

原始AST與選中的引文文字保持不變。證據Agent選段仍包含舊88引用所用的全部63個獨特來源。Clinical仍有151/230來源因預算省略，會如實列出。**MOCK audit沒有引用，無法證明新live產生大量引用時audit輸入也能低於180k；模型引用語意與分層仍須live驗證。**

## 服務與歷史

確認無running analysis後，停止本任務擁有的backend session45448；新session16533／PID27200，127.0.0.1:8000，contracts已為1.4.1。Ollama embeddinggemma 768維檢查通過。v11 API export與保存檔完全相同。前端沿用5173 session6730。

## v12 尚未執行

使用者說「同意執行付費分析」，但自動核准審查拒絕run_v12_once.py的命令：概括同意未明確連結特定病例/AST/文件片段與外部目的地。拒絕發生在啟動程序前，沒有v12模型呼叫、沒有新增v12run，也未消耗這次模型驗證。

已用非同步問題請求明確同意：agent-complete第4版必要欄位、18AST、WHO/DailyMed片段，送目前外部gpt-4.1-mini，一次付費1.4.1驗證並保存v12。此問題仍待回覆；不要重复詢問或繞過拒絕。

## 下一步

1. 取得上述問題直接回覆後，檢查輸出檔不存在與病例仍第4版，執行 `data/local/agent_cases/run_v12_once.py` 一次。固定request_id authorized-agent-led-141-v12-20261009，來源防護限定WHO/DailyMed，使用正式start_run；不修改病例及文件库。
2. 保存live-complete-v12-context.json；執行唯讀check_v12.py，產出匯出及source-layer-checks，確認原文存在、逐項引用語意、完整候選/第二層/待確認。
3. Sol/high核對實際v12，特別是v11錯藥/上下UTI/兒童引用、風險fact_refs與獨立audit；若有超限/缺引用，保留有效结果，不強制候選。
4. 醫師Agent透過前端檢視新版實際run；再更新DEMO與驗收報告。付費授權只限一次，不能自動重跑。
