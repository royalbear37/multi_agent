import { render, screen, fireEvent } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import {
  BenchmarkOverview,
  SettingsOverview,
  WorkflowStep,
  executionLabel,
  localTime,
} from "./Insights";

test("v2 trace shows independent agent messages and model attempts", () => {
  render(<WorkflowStep index={7} run={{}} node={{
    node_id: "ast_agent", agent_id: "ast_agent", status: "completed", model: "test-ast-model",
    is_mock: true, depends_on: ["case_agent"], elapsed_ms: 12, usage: { total_tokens: 42 },
    input: { case_assessment: { findings: [] } }, output: { reviewed_drugs: ["TEST"] },
    attempts: [{ attempt: 1, status: "completed" }],
  }} />);
  fireEvent.click(screen.getByText(/藥敏分析 Agent/));
  expect(screen.getByText(/模型：test-ast-model/)).toBeVisible();
  expect(screen.getByText(/Token：42/)).toBeVisible();
  expect(screen.getByText(/接收上游：病例整理 Agent/)).toBeVisible();
  fireEvent.click(screen.getByText("Agent 輸入"));
  expect(screen.getAllByText(/case_assessment/)[0]).toBeVisible();
  expect(screen.getByText("模型呼叫與重試紀錄")).toBeVisible();
});

test("withheld agent content stays hidden in the readable trace", () => {
  render(<WorkflowStep index={8} run={{}} node={{
    node_id: "synthesis_agent", agent_id: "synthesis_agent", status: "failed",
    content_withheld: true, input: null, output: null, errors: [{ code: "AGENT_SCHEMA_INVALID" }],
  }} />);
  fireEvent.click(screen.getByText(/結果整合 Agent/));
  expect(screen.getByText(/中間內容已隔離/)).toBeVisible();
  expect(screen.queryByText("Agent 輸入")).toBeNull();
});

test("single mode history distinguishes runs, N/A and no LLM", () => {
  const onOpen = vi.fn();
  render(
    <BenchmarkOverview
      onOpenRun={onOpen}
      benchmark={{
        benchmark_id: "old",
        created_at: "2026-09-15T08:37:01Z",
        cases: ["case-a"],
        modes: ["rule-only"],
        provider_kind: "live",
        results: [
          {
            run_id: "run-a",
            case_id: "case-a",
            mode: "rule-only",
            status: "awaiting_review",
            gate_status: "needs_confirmation",
          },
        ],
        summary: {
          total_cases: 1,
          completion: { value: 0, numerator: 0, denominator: 1 },
          safety_withholding: { value: 1, numerator: 1, denominator: 1 },
          schema_validity: { value: 1, numerator: 1, denominator: 1 },
          citation_support_conclusion: {
            value: null,
            denominator: 0,
            status: "not_evaluated",
          },
        },
      }}
    />,
  );
  expect(
    screen.getByRole("heading", { name: /規則執行（不使用 LLM）/ }),
  ).toBeVisible();
  expect(
    screen.getByText(/1 個不同病例 × 1 種模式 · 1 筆執行結果/),
  ).toBeVisible();
  expect(screen.getByText(/並非完整四模式比較/)).toBeVisible();
  expect(screen.getAllByText("0.0%（0／1）")[0]).toBeVisible();
  expect(
    screen.getByText("詳細摘要資料（原始 JSON）").closest("details"),
  ).not.toHaveAttribute("open");
  fireEvent.click(screen.getByText(/逐次執行結果/));
  fireEvent.click(screen.getByRole("button", { name: "查看分析" }));
  expect(onOpen).toHaveBeenCalledWith(
    expect.objectContaining({ run_id: "run-a" }),
  );
});

test("step completion does not imply safety approval and JSON is optional", () => {
  render(
    <WorkflowStep
      index={5}
      run={{}}
      node={{
        node_id: "safety_gate",
        status: "completed",
        output: {
          gate_status: "needs_confirmation",
          limitations: ["過敏狀態未知"],
        },
      }}
    />,
  );
  fireEvent.click(screen.getByText(/安全條件檢查/));
  expect(screen.getByText("需補資料或確認")).toBeVisible();
  expect(screen.getByText("過敏狀態未知")).toBeVisible();
  expect(
    screen.getByText("詳細資料（原始 JSON）").closest("details"),
  ).not.toHaveAttribute("open");
});

test("configuration presence and demo index do not claim service health or WHO coverage", () => {
  render(
    <SettingsOverview
      rules={{ version: "demo-v1" }}
      config={{
        provider: { configured: true, kind: "live", model: "test-model" },
        rag: {
          retrieval_mode: "embedding",
          index: { chunks: 8, embedded_chunks: 8, missing_chunks: 0 },
        },
        reference_status: "已匯入 1 份正式參考文件",
      }}
    />,
  );
  expect(
    screen.getByText(/設定已填齊，連線與輸出仍須實際執行驗證/),
  ).toBeVisible();
  expect(screen.getByText(/此數字對應 WHO/)).toBeVisible();
  expect(screen.getByText(/匯入文件不代表已完成向量索引/)).toBeVisible();
  expect(executionLabel({ provider_kind: "live" })).toBe("選用已設定模型");
  expect(localTime(undefined)).toBe("時間未記錄");
});
