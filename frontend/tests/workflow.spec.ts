import { expect, test } from "@playwright/test";

test("v2 independent agents are persisted and visible in the workflow", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("目前病例").selectOption("case-01-complete");
  await page.getByLabel("比較模式").selectOption("multi-agent-v2");
  await page.getByLabel("模型執行方式").selectOption("mock");
  const response = page.waitForResponse(r => r.url().endsWith("/api/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  const run = await (await response).json();
  expect(run.mode).toBe("multi-agent-v2");
  expect(run.output).not.toBeNull();
  const agents = run.nodes.filter((n: any) => n.agent_id);
  expect(agents).toHaveLength(5);
  expect(agents.every((n: any) => n.attempts.length === 1)).toBeTruthy();
  await page.getByRole("button", { name: "查看證據與流程" }).click();
  const synthesis = page.locator("details.node").filter({ hasText: "結果整合 Agent" });
  await synthesis.locator("summary").first().click();
  await expect(synthesis.getByText(/模型：synthetic-agent-mock-v2/)).toBeVisible();
  await synthesis.getByText("Agent 輸入", { exact: true }).click();
  await expect(synthesis.getByText(/clinical_assessment/).first()).toBeVisible();
  const trace = await page.request.get(`/api/runs/${run.run_id}/trace`);
  expect((await trace.json()).nodes.filter((n: any) => n.agent_id)).toHaveLength(5);
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
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  await expect(page.locator(".candidate")).toHaveCount(0);
  await expect(page.getByText("沒有族群相符且已標示的參考片段，請確認文件範圍後重新分析")).toBeVisible();
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
  await expect(
    page.getByRole("button", { name: "執行分析", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  await expect(page.getByText("可供審閱的藥敏選項")).toBeVisible();
  await expect(
    page.getByText("ceftriaxone", { exact: false }).first(),
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
  await step.getByText("詳細資料（原始 JSON）", { exact: true }).click();
  await expect(step.locator("pre")).toBeVisible();
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
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  await expect(
    page.getByText("沒有可發布候選。請查看安全閘門、資料缺漏或模型設定。"),
  ).toBeVisible();
  await page.getByRole("button", { name: "前往人工審閱" }).click();
  await page.getByLabel("審閱理由").fill("不應解除資料缺漏限制");
  await page.getByRole("button", { name: "送出審閱" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
});

test("explicit mock multi-agent and four mode benchmark", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("目前病例").selectOption("case-01-complete");
  await page.getByLabel("比較模式").selectOption("multi-agent");
  await page.getByLabel("模型執行方式").selectOption("mock");
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  await expect(page.getByText("可供審閱的藥敏選項")).toBeVisible();
  await expect(page.locator(".candidate")).not.toHaveCount(0);
  await expect(page.locator(".runbanner")).toContainText("MOCK 模擬");
  await page.getByRole("button", { name: "06研究與設定" }).click();
  await page.getByLabel("Benchmark 模型").selectOption("mock");
  await page.getByRole("button", { name: "執行四模式比較" }).click();
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
