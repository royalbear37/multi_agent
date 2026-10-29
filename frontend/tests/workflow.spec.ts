import { expect, test } from "@playwright/test";

function expectPendingMock(run: any) {
  expect(run.provider_kind).toBe("mock");
  expect(run.is_mock).toBe(true);
  expect(run.versions.workflow).toBe("agent-led-1.6.0");
  expect(run.status).toBe("partial");
  expect(run.gate_status).toBe("needs_confirmation");
  expect(run.errors).toEqual([]);
  const agents = run.nodes.filter((n: any) => n.agent_id);
  expect(agents.map((n: any) => n.agent_id)).toEqual([
    "case_agent", "ast_agent", "evidence_agent", "clinical_agent", "synthesis_agent", "evidence_audit",
  ]);
  expect(run.agent_execution.calls).toBe(6);
  expect(agents.every((n: any) => n.attempts.length === 1 && n.attempts[0].status === "completed")).toBeTruthy();
  expect(agents.map((n: any) => n.status)).toEqual(["completed", ...Array(5).fill("needs_confirmation")]);
  const drugs = [...new Set(run.case_snapshot.ast_results.map((a: any) => a.drug_code))];
  expect(drugs.length).toBeGreaterThan(0);
  expect(run.output.candidates).toEqual([]);
  expect(run.output.pending.map((d: any) => d.drug_code)).toEqual(drugs);
  expect(run.drug_assessments.every((d: any) => d.status === "pending")).toBeTruthy();
  expect(run.physician_candidates.map((d: any) => d.drug_code)).toEqual(drugs);
  expect(run.physician_candidates.every((d: any) => d.verification_status === "incomplete")).toBeTruthy();
}

test("multi-agent independent agents are persisted and visible in the workflow", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("目前病例").selectOption("case-01-complete");
  await page.getByLabel("比較模式").selectOption("multi-agent");
  await page.getByLabel("模型執行方式").selectOption("mock");
  const response = page.waitForResponse(r => r.url().endsWith("/api/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  const run = await (await response).json();
  expect(run.mode).toBe("multi-agent");
  expect(run.output).not.toBeNull();
  expectPendingMock(run);
  await expect(page.getByRole("heading", { name: "逐藥分析總覽", exact: true })).toBeVisible();
  await expect(page.locator(".analysis-counts")).toContainText("0 項 AI 完整核對");
  await page.getByRole("button", { name: "查看證據與流程" }).click();
  const synthesis = page.locator("#agent-step-synthesis_agent");
  await synthesis.locator("summary").first().click();
  await expect(synthesis.getByText(/模型：synthetic-agent-mock-v2/)).toBeVisible();
  await synthesis.getByText("查看判斷理由與來源", { exact: true }).click();
  await expect(synthesis.getByText("MOCK：僅驗證流程", { exact: true })).toBeVisible();
  const trace = await page.request.get(`/api/runs/${run.run_id}/trace`);
  expect(trace.ok()).toBeTruthy();
  const nodes = (await trace.json()).nodes;
  expect(nodes.filter((n: any) => n.agent_id)).toHaveLength(6);
  const synthesisInput = nodes.find((n: any) => n.node_id === "synthesis_agent").input;
  expect(Object.keys(synthesisInput.assessments)).toEqual(["case_agent", "ast_agent", "evidence_agent", "clinical_agent"]);
  expect(synthesisInput.assessments.clinical_agent.drugs[0].status).toBe("unknown");
  const auditInput = nodes.find((n: any) => n.node_id === "evidence_audit").input;
  expect(auditInput.assessments).toEqual({});
  expect(auditInput.claims[0].claims).toHaveLength(5);
  const saved = await page.request.get(`/api/runs/${run.run_id}`);
  expect(saved.ok()).toBeTruthy();
  expectPendingMock(await saved.json());
});

test.beforeAll(async ({ request }) => {
  const doc = await request.post("/api/documents/import", {
    multipart: {
      file: {
        name: "reference-fixture.md",
        mimeType: "text/markdown",
        buffer: Buffer.from(
          "# REFERENCE TEST FIXTURE\nurinary tract infection ESCHERICHIA COLI ceftriaxone. Software retrieval test only; not a treatment guideline.",
        ),
      },
      title: "Workflow reference fixture",
      version: "e2e-reference-v1",
      is_synthetic: "false",
      population: "all",
    },
  });
  expect(doc.ok()).toBeTruthy();
  const source = await doc.json();
  for (const [id, status] of [
    ["case-01-complete", "known_none"],
    ["case-03-allergy-unknown", "unknown"],
  ]) {
    const imported = await request.post("/api/cases/import", {
      data: {
        payload: {
          case_id: id,
          created_at: "2026-09-17T00:00:00Z",
          is_synthetic: true,
          evidence_scope: "reference",
          source:
            "Independently authored software fixture; real names, entirely synthetic observations",
          demographics: { age: 55, sex: "female" },
          microbiology: {
            organism: "ESCHERICHIA COLI",
            specimen: "URINE",
            report_status: "final",
          },
          encounter: {
            infection_site: "urinary tract infection",
            severity: "stable",
          },
          renal: { egfr: 90, unit: "mL/min/1.73m2" },
          allergies: { status, items: [] },
          ast_results: [
            {
              drug_code: "ceftriaxone",
              reported_sir: "S",
              interpretation_basis: "source_report",
              source_phenotype: "Susceptible",
              source: "synthetic test",
            },
          ],
          policy_refs: [source.doc_id],
        },
      },
    });
    expect(imported.ok()).toBeTruthy();
  }
});

test("reference document upload and search remain separate from synthetic", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /05.*文件/ }).click();
  await page.getByLabel("文件", { exact: true }).setInputFiles({
    name: "reference-test.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("REFERENCE_SEARCH_ONLY_2026 source inspection fixture"),
  });
  await page.getByLabel("標題", { exact: true }).fill("Reference test fixture");
  await page.getByRole("combobox", { name: "適用族群", exact: true }).selectOption("adult");
  await page.getByLabel("虛構展示文件（正式文件請取消）").uncheck();
  await page.getByRole("button", { name: "匯入並解析文件" }).click();
  await expect(page.getByText("文件處理狀態：indexed")).toBeVisible();
  await page.getByLabel("文件範圍").selectOption("reference");
  await page
    .getByLabel("查詢", { exact: true })
    .fill("REFERENCE_SEARCH_ONLY_2026");
  await page.getByRole("button", { name: "檢索文件", exact: true }).click();
  await expect(page.locator(".evidence")).toHaveCount(1);
  await expect(page.locator(".evidence a")).toHaveAttribute(
    "href",
    /\/api\/documents\/doc_.*\/source/,
  );
  await page.getByLabel("文件範圍").selectOption("synthetic");
  await expect(page.locator(".evidence")).toHaveCount(0);
  await page.getByRole("button", { name: "檢索文件", exact: true }).click();
  await expect(page.locator(".evidence")).toHaveCount(0);
});

test("existing reference scope can be annotated with a reason and reloaded", async ({ page }) => {
  const uploaded = await page.request.post("/api/documents/import", { multipart: {
    file: { name: "annotation.txt", mimeType: "text/plain", buffer: Buffer.from("Annotation roundtrip fixture") },
    title: "Annotation fixture", version: "v1", is_synthetic: "false",
  } });
  expect(uploaded.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: /05.*文件/ }).click();
  const record = page.locator("details").filter({
    has: page.locator("summary", { hasText: "Annotation fixture" }),
  });
  await record.locator("summary").first().click();
  await record.getByLabel("此文件適用族群").selectOption("mixed");
  await record.getByLabel("標示依據").fill("E2E fixture scope correction");
  await record.getByRole("button", { name: "儲存族群標示" }).click();
  await expect(page.getByText(/族群標示已保存/)).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /05.*文件/ }).click();
  await record.locator("summary").first().click();
  await expect(record.getByLabel("此文件適用族群")).toHaveValue("mixed");
  await expect(record.locator("pre")).toContainText("E2E fixture scope correction");
});

test("adult case with pediatric-only reference withholds output and explains why", async ({ page }) => {
  const response = await page.request.post("/api/documents/import", {
    multipart: {
      file: { name: "pediatric.txt", mimeType: "text/plain",
        buffer: Buffer.from("ESCHERICHIA COLI urinary tract infection pediatric fixture for children.") },
      title: "Pediatric-only fixture", version: "v1", is_synthetic: "false", population: "pediatric",
    },
  });
  expect(response.ok()).toBeTruthy();
  const doc = await response.json();
  const original = await (await page.request.get("/api/cases/case-01-complete")).json();
  const saved = await page.request.post("/api/cases/import", { data: {
    payload: { ...original.case, case_id: "case-population-mismatch", policy_refs: [doc.doc_id] },
  } });
  expect(saved.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByLabel("目前病例").selectOption("case-population-mismatch");
  await page.getByLabel("比較模式").selectOption("multi-agent");
  await page.getByLabel("模型執行方式").selectOption("mock");
  const multiResponse = page.waitForResponse(r => r.url().endsWith("/api/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  expectPendingMock(await (await multiResponse).json());
  await expect(page.locator(".candidate")).toHaveCount(0);
  // The baseline population gate and agent-led Audit are different paths.
  // Keep the multi-agent non-publication check, then verify the explicit gate.
  await page.getByRole("button", { name: "01病例工作台" }).click();
  await page.getByLabel("比較模式").selectOption("single-agent");
  const baselineResponse = page.waitForResponse(r => r.url().endsWith("/api/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  const baseline = await (await baselineResponse).json();
  expect(baseline.output).toBeNull();
  expect(baseline.gate_status).toBe("needs_confirmation");
  expect(baseline.nodes.find((n: any) => n.node_id === "evidence_retrieval").output.population_filter.mismatched).toBe(1);
  expect(baseline.nodes.find((n: any) => n.node_id === "candidate_presentation").status).toBe("skipped");
  await expect(page.getByText("沒有族群相符且已標示的參考片段，請確認文件範圍後重新分析", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "查看證據與流程" }).click();
  const retrieval = page.locator("details.node").nth(4);
  await retrieval.locator("summary").first().click();
  await expect(retrieval).toContainText("不符 1 個");
});
test("seed → analysis → evidence/trace → review → reread persists", async ({
  page,
}) => {
  await page.goto("/");
  const selector = page.getByLabel("目前病例");
  const first = "case-01-complete";
  await selector.selectOption(first);
  await page.getByLabel("比較模式").selectOption("rule-only");
  await expect(
    page.getByRole("button", { name: "執行分析", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  await expect(page.getByText("可供審閱的藥敏選項")).toBeVisible();
  await expect(
    page.locator(".candidate").getByRole("heading", { name: /^ceftriaxone/ }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/analysis-overview.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "查看證據與流程" }).click();
  await expect(page.getByText("分析步驟與結果", { exact: true })).toBeVisible();
  const step = page.locator("details.node").first();
  await step.locator("summary").first().click();
  await expect(step.getByText("來源藥敏：1 筆")).toBeVisible();
  await expect(step.locator("pre")).not.toBeVisible();
  await step.getByText("技術資料（原始 JSON，供除錯）", { exact: true }).click();
  await expect(step.locator("pre")).toBeVisible();
  const sourceGroup = page.locator(".source-group").filter({ hasText: "Workflow reference fixture" });
  await sourceGroup.locator("summary").first().click();
  await sourceGroup.locator(".source-excerpt summary").first().click();
  await expect(
    page.getByRole("link", { name: "開啟原始文件" }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "04人工審閱" }).click();
  await page.getByLabel("決定", { exact: true }).selectOption("modify");
  await page
    .getByLabel("藥物理由 1")
    .fill("已核對來源與參考片段，保留待審選項");
  await page.getByLabel("審閱理由").fill("E2E synthetic 人工審閱測試");
  await page.screenshot({
    path: "test-results/review-form.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "送出審閱" }).click();
  await expect(page.getByText("審閱已保存。")).toBeVisible();
  await page.getByRole("button", { name: "重新讀取審閱" }).click();
  await expect(
    page.getByText("E2E synthetic 人工審閱測試", { exact: true }).first(),
  ).toBeVisible();
  await page.reload();
  await selector.selectOption(first!);
  await page.locator(".runrow").first().click();
  await page.getByRole("button", { name: "04人工審閱" }).click();
  await expect(
    page.getByText("E2E synthetic 人工審閱測試", { exact: true }).first(),
  ).toBeVisible();
});

test("unknown allergy withholds output and cannot be accepted", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("目前病例").selectOption("case-03-allergy-unknown");
  await page.getByLabel("比較模式").selectOption("rule-only");
  const response = page.waitForResponse(r => r.url().endsWith("/api/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  const run = await (await response).json();
  await expect(
    page.getByText(/未產生候選：.*前置安全檢查未通過，因此 Agent 尚未呼叫。/),
  ).toBeVisible();
  await page.getByRole("button", { name: "前往人工審閱" }).click();
  await page.getByLabel("審閱理由").fill("不應解除資料缺漏限制");
  await expect(page.getByRole("option", { name: "接受", exact: true })).toHaveJSProperty("disabled", true);
  await expect(page.getByRole("option", { name: "修改", exact: true })).toHaveJSProperty("disabled", true);
  await expect(page.getByRole("button", { name: "送出審閱" })).toBeDisabled();
  const attemptedAccept = await page.request.post("/api/reviews", { data: {
    run_id: run.run_id, action: "accept", reason: "E2E must not bypass unknown allergy",
    reviewer_id: "demo-user", role: "physician",
  } });
  expect(attemptedAccept.status()).toBe(422);
  expect(await (await page.request.get(`/api/reviews?run_id=${run.run_id}`)).json()).toEqual([]);
});

test("explicit mock multi-agent and four mode benchmark", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("目前病例").selectOption("case-01-complete");
  await page.getByLabel("比較模式").selectOption("multi-agent");
  await page.getByLabel("模型執行方式").selectOption("mock");
  const response = page.waitForResponse(r => r.url().endsWith("/api/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  expectPendingMock(await (await response).json());
  await expect(page.getByRole("heading", { name: "逐藥分析總覽", exact: true })).toBeVisible();
  await expect(page.locator(".analysis-counts")).toContainText("0 項 AI 完整核對");
  await expect(page.locator(".runbanner")).toContainText("MOCK 模擬");
  await page.getByRole("button", { name: "06研究與設定" }).click();
  await page.getByRole("checkbox", { name: "case-01-complete", exact: true }).check();
  await page.getByLabel("Benchmark 模型").selectOption("mock");
  const benchmarkResponse = page.waitForResponse(r => r.url().endsWith("/api/benchmarks") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行所選比較", exact: true }).click();
  const benchmark = await (await benchmarkResponse).json();
  expect(benchmark.modes).toEqual(["rule-only", "rag-only", "single-agent", "multi-agent"]);
  expectPendingMock(benchmark.results.find((r: any) => r.mode === "multi-agent" && r.case_id === "case-01-complete"));
  await expect(
    page.getByRole("link", { name: "匯出逐案例結果與摘要" }),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByRole("heading", { name: /Benchmark 結果/ }),
  ).toContainText("MOCK");
  await expect(
    page.getByRole("heading", { name: "可供審閱輸出率" }),
  ).toBeVisible();
  await expect(page.locator(".benchmark-history").first()).toContainText(
    "4 種模式",
  );
  await page.screenshot({
    path: "test-results/benchmark-overview.png",
    fullPage: true,
  });
  await page.getByText(/逐次執行結果（/).click();
  await page
    .getByRole("button", { name: "查看分析", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "分析結果", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("目前病例")).toHaveValue("case-01-complete");
});

test("benchmark history distinguishes a one-mode record from four modes", async ({
  page,
}) => {
  const four = await page.request.post("/api/benchmarks", { data: {
    case_ids: ["case-01-complete"],
    modes: ["rule-only", "rag-only", "single-agent", "multi-agent"],
    provider_kind: "mock",
  } });
  expect(four.ok()).toBeTruthy();
  const one = await page.request.post("/api/benchmarks", {
    data: {
      case_ids: ["case-01-complete"],
      modes: ["rule-only"],
      provider_kind: "unconfigured",
    },
  });
  expect(one.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: "06研究與設定" }).click();
  await expect(page.locator(".benchmark-history").first()).toContainText(
    "1 種模式",
  );
  await expect(page.locator(".benchmark-history").first()).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByText(/並非完整四模式比較/)).toBeVisible();
  await page
    .locator(".benchmark-history")
    .filter({ hasText: "4 種模式" })
    .first()
    .click();
  await expect(page.getByText(/並非完整四模式比較/)).not.toBeVisible();
  await expect(
    page.getByRole("heading", { name: /Benchmark 結果/ }),
  ).toContainText("MOCK");
});
