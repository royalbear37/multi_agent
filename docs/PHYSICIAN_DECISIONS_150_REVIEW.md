# 逐藥醫師決策 1.5.0 唯讀審查

審查範圍：`/api/reviews` 的 `drug_review` 分支、`physician_review.py`、review 儲存與匯出，以及 `PhysicianReview`／`App` 的輸入和歷史展示。只讀本機程式與回歸，未修改程式、未執行 live 或外部模型。父任務回報新增後端測試與 55 項前端測試通過；本報告不把測試視為臨床或真實身分驗證。

## 已確認的邊界

- API 只接受本 run `drug_assessments` 中的藥品，每次請求的藥碼不可重複；空決策清單、不適用的 role、空白決策理由、新增藥、`conditional` 的空白條件，以及 `adopt`／`conditional` 未明示 `acknowledged_warnings=true` 都被拒絕。`decline` 不必勾採用警示；前端只提交已選決策，未選藥品不會自動變成不採用。ReviewBody 對 `accept`／`modify` 舊動作仍走既有驗證，且非 `drug_review` 不能附逐藥決策。
- 醫師可對系統 `pending` 或 `avoid` 留下人工決策，但新 review 的 `new_output=None`，每筆決策保存完整 `system_assessment`，另存 run 的 `case_revision`／`case_snapshot`／版本及原輸出。儲存只新增 reviews 紀錄；原 run、候選邊界和原 run 匯出不改。review 匯出由 review ID 讀回保存紀錄。人工 `adopt` 不會變成 AI `reviewable`。
- `PatientQuestions` 對病例明示 `allergies.status=known_none` 和 `medication_history_status=reviewed_none` 不重問；缺少／未知狀態仍列為待確認。病例 schema 禁止 `known_none` 同時有過敏項目，故此特例不會由有效病例中的相反明細掩蓋。

## 原發現與修正狀態

以下兩項是初次審查發現，現已修正。`frontend/src/PhysicianReview.tsx:23-43` 的逐藥主欄直接顯示 `audit.reason`、`provenance_issues` 及非 supported／有 validation issues 的分項複核，舊 run 缺少結構化 `risk_details` 時會列出原 `allergy`／`renal`／`interactions` 字串並提醒不能由空白推定無風險；`PhysicianReview.tsx:53` 也顯示 `row.reason`。對應前端回歸見 `frontend/src/PhysicianReview.test.tsx:51-55`。下述文字保留原始重現情境，以供追溯，非目前未修缺口。

1. **新的非感染 audit 警示未在逐藥決策頁顯示。** `frontend/src/PhysicianReview.tsx:23-55` 的 `DrugCautions` 只列臨床 `risk_details`、部分 AST 與 `row.blockers`；同頁「引用與完整初評」（第 53 行）只列 `evidence.reason` 和 `RiskDetails`，沒有 `audit.reason`、`provenance_issues` 或 `claim_checks[*].validation_issues`。例如感染分項獲支持、過敏或腎功能分項因來源不符為 `uncertain`，而臨床分項沒有 `unknown`／缺欄、audit 有選段時，`classify_options`（`backend/app/workflow/claim_checks.py:68-94`）的 blockers 未必列出該非感染錯誤。醫師頁只看到系統尚待確認，卻可勾選「已閱讀系統警示」採用。完整警示仍存於 review 的 `system_assessment`，但決策當下未清楚呈現。建議在該藥決策區直接列出 audit 整體未通過原因與每個分項的未核對訊息，對所選藥品保持可見。
2. **舊 Agent run 的風險字串會被誤稱無額外注意事項。** `frontend/src/PhysicianReview.tsx:23-34` 的 `DrugCautions` 只從 `clinical.risk_details` 建清單；舊 run 若只有 `clinical.allergy`／`renal`／`interactions` 字串，`details.length=0` 就顯示「本次初評未列額外注意事項」，即使舊字串含警示。後端允許這些既有 `decision_basis='agent'` run 建立逐藥決策。雖然旁邊折疊的 `RiskDetails` 可讀舊字串，決策主欄的肯定句仍會誤導。建議顯示 legacy 字串，或明示「未提供結構化分項；請核對完整原評估」，並加舊 run UI 測試。

## 追溯資料與未核對範圍

`ReviewBody.reviewer_id` 的純空白缺口亦已修正：`backend/app/main.py:73-79` 與 `reason` 共用去空白／空值驗證；`backend/tests/test_physician_review.py:45-46` 覆蓋 `reviewer_id='   '` 收到 422。Role 仍是請求者提供的展示欄位；API 限制允許值及逐藥動作，但目前沒有驗證真人醫師／藥師身分，前端也標為「展示角色」，不能將保存紀錄稱為已認證臨床簽核。

本輪未測多使用者同時提交、跨 review 的後續修訂／覆蓋規則、真實授權與權限服務，也未全面重審舊 `accept`／`modify` 的所有輸出模式。沒有新增 live。上述發現屬資料呈現與追溯缺口，不表示 AI 的 `pending`／`avoid` 已被 API 自動升級。
