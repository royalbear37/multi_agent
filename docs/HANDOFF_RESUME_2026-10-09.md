# 額度暫停與 GitHub 交接待辦

2026-10-09（Asia/Taipei）。五小時剩4%、每週剩69%，依使用者要求暫停。

已完成 DailyMed 交接缺口：20組公開 XML／MD 固定文件（約3.7MB）整理至 `data/public_references/dailymed`，manifest保留SPL版本、網址、原产品名稱及檔案SHA256。`.gitattributes` 停用資料包MD/XML換行轉換，保證Windows clone後位元組雜湊；未放寬data/local忽略。

新增 `backend/scripts/install_reference_bundle.py`，只處理公開標示，不呼叫LLM。`--verify-only`驗證20份通過；`backend/tests/test_reference_bundle.py`兩項測試通過（乾淨SQLite匯入20份、檔案變更拒絕）。git diff --check通過。README新增交接入口，詳細步驟在 `docs/GITHUB_HANDOFF.md`。沒有修改正在運行的文件庫、沒有commit/push或付費分析。

恢復後若使用者要正式push：

1. 檢查 Git remote／分支與提交清單，包含本輪公共資料包、安裝script、測試、`.gitattributes`及交接文件；不要強制加入data/local、CSV、.env、DB或不相關tmp圖片。
2. README既有模式摘要仍寫agent-led-1.0，宜在正式交接整理時更新到1.5.1及最新驗證連結；不影響這次資料包匯入。
3. DailyMed已可從Git取得；目前agent-complete病例、修訂／歷史run仍位於本機非Git資料，要重現需另確定授權交接範圍，不能當成已隨公開文件交付。
4. 1.5.1後端session35091／PID3884、前端5173；377後端／59前端及build為前輪驗證。本輪只增加兩個交接資料包測試，未重跑完整suite，無需把它聲稱成379項完整回歸。
5. 新一次付費live尚未授權／未執行，與GitHub交接是分開的操作。
