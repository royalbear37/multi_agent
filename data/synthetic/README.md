# Synthetic fixtures

These fixtures are fictional software test inputs. They are not clinical
guidelines and must not be used for patient care. Each file is accepted by the
canonical case schema; `expected` describes software behavior only.

`case-15-integrated-complete` and `case-16-integrated-followup` are complete
interaction fixtures: renal data, medication context, rapid identification,
population resistance context, AST records, and a pinned synthetic evidence
policy are all present. The current demo rules do not implement drug-drug or
medication reconciliation logic, so the medication fields are carried as
context only and must not be read as an interaction result.

## 完整展示操作

從專案根目錄執行 `powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1 -Synthetic`，另開前端，選以下病例的最近執行紀錄。資料保存在 `data/runtime/handoff-demo/`，不需要私人 CSV、WHO、API key 或 Ollama，不修改一般研究資料庫：

| 病例 | 可觀察結果 |
| --- | --- |
| case-15-integrated-complete | 腎功能、背景、快速鑑定、2 筆 AST、展示證據均齊全，無缺漏與錯誤 |
| case-16-integrated-followup | 不同觀測時間／用藥背景的完整示範，同樣可進人工審閱；是獨立病例 ID，不是自動串接前案的追蹤功能 |

rule-only 可列出 A/B 展示候選；新版 multi-agent mock 會完成六次角色呼叫，但保留兩藥為待確認，不捏造文件支持。這是預期的軟體測試行為，不是藥效比較。需要展示規則避免限制可用 case-04 或 case-05 執行 rule-only。
