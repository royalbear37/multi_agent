# GitHub 交接：文件與本機資料

DailyMed 原先位於被 Git 忽略的 `data/local/agent_references_v2`，直接 clone 不會取得。現在公開文件另整理到 `data/public_references/dailymed`：20 組原始 XML／檢索 Markdown，以及版本／來源／SHA256 清單。這個目錄可以正常提交，不需解除整個 `data/local` 的忽略規則。

## 接手者操作

1. 先照根目錄 README 的「接手者先照這裡做」安裝、執行 `check_handoff.py`。
2. 在專案根目錄驗證並匯入目前工作站的病例與文件：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 backend/scripts/install_handoff.py --verify-only
powershell -ExecutionPolicy Bypass -File scripts/handoff.ps1
```

3. 另開終端啟動 `scripts/frontend.ps1`。病例選 `agent-complete`，確認第4版／18筆 AST；文件庫應有24份文件。此啟動方式是 lexical＋mock，可立即操作，不需 CSV／Ollama／API key。
4. 要切到原本的向量與外部模型，停止 handoff 服務，依 README 設定自己的 `.env`、Ollama，再用一般後端啟動。選「參考文件」，按「重建向量索引」，確認沒有缺少片段後再執行 multi-agent。重建使用本機 Ollama，不會執行付費 LLM 分析。
5. 病例與95筆修訂已包含，來源 AST 保留，外送授權需重新確認。歷史分析與醫師決策沒有複製，接手者重新分析與審閱；完整差異見 [病例包](../data/handoff/README.md)。若只需要 DailyMed，可單獨使用 `install_reference_bundle.py`，不必重新下載。

既有 DB 若同一份文件標示不同，安裝會在任何資產匯入前停止，不覆寫標示。依錯誤在文件庫人工核對修改，或設定新的 `PROTOTYPE_DB_PATH` 再安裝；WHO 的舊 all／新 mixed 差異尤其需要注意。全新 clone 不會碰到此衝突。

## 提交範圍

- 包含：本輪程式、完整 Python 鎖定依賴、前端套件鎖定檔、WHO PDF、`data/public_references/dailymed` 全目錄、`data/handoff` 目前測試病例與參考資料、匯入與交接檢查腳本、歷史合成 fixture／文件／規則、相關測試及交接文件。
- 保持分開：`.env`、API key、`data/local`、來源 CSV、runtime SQLite、付費分析保存內容。若須移交病例或 DB，另行確認可分享範圍及傳送方式。
- 不要以 `git add -f data/local` 解決文件缺少；該目錄也有病例及分析內容。可先用 `git status --short` 核對提交清單。

## 可重現性界線

資料包固定公開標示版本與字面內容；不保證不同機器的 embedding、排序或模型輸出完全一致。來源 SHA256 不符會停止匯入，避免靜默換版本。Git 使用 `.gitattributes` 保留此資料包原始位元組，避免 Windows 換行轉換導致驗證失敗。

`imipenem.md` 對應的是 RECARBRIO 複方，已在清單列原產品名稱；不把它改寫成單方資料。1.5.1 來源範圍檢查會保留此限制。這次沒有重新下載新版本或執行付費分析。

## 不在 Git 的必要條件

| 要做的事 | 接手者還需準備 |
| --- | --- |
| 離線合成展示／自動測試 | Python、Node.js，首次安裝依賴的網路；資料已隨附 |
| WHO／DailyMed 檢索 | 將 Git 內公開資料匯入自己的 DB；向量模式另需 Ollama 模型及重建索引 |
| 真實藥名與目前模擬情境 | 已隨 Git 提供28病例／95修訂，執行 handoff 匯入即可；只有重新處理全資料集才需另取原 CSV |
| 重現原機歷史／審閱 | 另行移交獲准分享的 runtime DB 與同層 documents，服務停止時備份／還原 |
| 外部模型分析 | 自己的 `.env`、模型帳號／額度及病例外送授權 |

乾淨副本驗證結果見 [交接驗證](HANDOFF_VALIDATION.md)。歷史報告中的 `data/local/...` 路徑、PID、session 與索引數量是原工作站當時狀態，不是接手後會自動存在的資料。WHO 全書族群由原機的 all 改為 mixed，其餘文件保留原分類；這項安全修正可能改變檢核結果。模型服務、向量索引與歷史分析不可能只靠 clone 就逐位元相同，應以固定病例／文件及可執行流程驗收。
