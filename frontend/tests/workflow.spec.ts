import { expect, test } from "@playwright/test";
test("reference document upload and search remain separate from synthetic", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /05.*文件/ }).click();
  await page
    .getByLabel("文件", { exact: true })
    .setInputFiles({
      name: "reference-test.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "REFERENCE_SEARCH_ONLY_2026 source inspection fixture",
      ),
    });
  await page.getByLabel("標題", { exact: true }).fill("Reference test fixture");
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
test("seed → analysis → evidence/trace → review → reread persists", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "載入展示資料" }).click();
  await expect(
    page.getByText("展示病例與文件已初始化；既有資料已保留。"),
  ).toBeVisible();
  const selector = page.getByLabel("目前病例");
  const first = "case-01-complete";
  await selector.selectOption(first);
  await expect(
    page.getByRole("button", { name: "執行分析", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "執行分析", exact: true }).click();
  await expect(page.getByText("可供審閱的展示候選")).toBeVisible();
  await expect(
    page.getByText("DEMO_DRUG_A", { exact: false }).first(),
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
  await page.getByLabel("審閱理由").fill("E2E synthetic 人工審閱測試");
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
  await expect(page.getByText("可供審閱的展示候選")).toBeVisible();
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
  await page.getByRole("button", { name: "查看分析", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "分析結果", exact: true })).toBeVisible();
  await expect(page.getByLabel("目前病例")).toHaveValue("case-01-complete");
});

test("benchmark history distinguishes a one-mode record from four modes", async ({ page }) => {
  const one = await page.request.post("/api/benchmarks", { data: { case_ids: ["case-01-complete"], modes: ["rule-only"], provider_kind: "unconfigured" } });
  expect(one.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: "06研究與設定" }).click();
  await expect(page.locator(".benchmark-history").first()).toContainText("1 種模式");
  await expect(page.locator(".benchmark-history").first()).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/並非完整四模式比較/)).toBeVisible();
  await page.locator(".benchmark-history").filter({ hasText: "4 種模式" }).first().click();
  await expect(page.getByText(/並非完整四模式比較/)).not.toBeVisible();
  await expect(page.getByRole("heading", { name: /Benchmark 結果/ })).toContainText("MOCK");
});
