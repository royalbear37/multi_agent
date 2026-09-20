import { render, screen, fireEvent } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import {
  BenchmarkOverview,
  DrugOverview,
  DemoSourceResult,
  RetrievalWarnings,
  drugDisposition,
  evidenceOrigin,
  SettingsOverview,
  WorkflowStep,
  executionLabel,
  localTime,
  withheldSummary,
} from "./Insights";

test('blank pages and normal splitting stay in collapsed parsing details', () => {
  render(<RetrievalWarnings warnings={['long_text_split','page_2_blank','page_44_requires_ocr','embedding_failed']} />);
  expect(screen.getByText(/向量檢索失敗/)).toBeVisible();
  expect(screen.getByText(/第 44 頁未擷取到文字/)).toBeVisible();
  expect(screen.getByText('第 2 頁為空白頁，已略過。')).not.toBeVisible();
  fireEvent.click(screen.getByText(/文件解析細節/));
  expect(screen.getByText('第 2 頁為空白頁，已略過。')).toBeVisible();
  expect(screen.getByText(/長文字已正常切段/)).toBeVisible();
});

test.each(['rule-only', 'rag-only', 'single-agent', 'multi-agent'])('failed %s displays a source demo table', (mode) => {
  render(<DemoSourceResult run={{ mode, output: null, nodes: [{node_id:'ast', output: {
    source_report: [{drug_code:'test_a'}, {drug_code:'test_b'}],
    system_evaluations: [{drug_code:'test_a', eligible:true}, {drug_code:'test_b', eligible:false}],
  }}] }} />);
  expect(screen.getByText('來源藥敏整理結果（demo）')).toBeVisible();
  expect(screen.getByText('test_a')).toBeVisible();
  expect(screen.queryByText('test_b')).toBeNull();
  expect(screen.getByText(/這不是模型推薦/)).toBeVisible();
  expect(screen.getByRole('table', {name:'來源藥敏整理表'})).toBeVisible();
  expect(screen.queryByRole('list')).toBeNull();
});

test('expanded agent explains confirmation even without missing fields', () => {
  render(<WorkflowStep index={6} run={{}} node={{ node_id:'case_agent', agent_id:'case_agent', status:'needs_confirmation',
    output:{missing_fields:[], limitations:['既往病史未提供'], findings:[{statement:'來源判讀有衝突', evidence_refs:[]}]}
  }} />);
  fireEvent.click(screen.getByText(/07\s+病例整理 Agent/));
  expect(screen.getByText('既往病史未提供')).toBeVisible();
  expect(screen.getByText('來源判讀有衝突')).toBeVisible();
  expect(screen.getByText(/此 Agent 未列出具體缺漏欄位/)).toBeVisible();
});

test("drug accounting separates exclusions, selections and unexplained omissions", () => {
  const run = { mode: 'rag-only', nodes: [{ node_id: 'ast', output: {
    source_report: ['a', 'a', 'b', 'c', 'd'].map(drug_code => ({ drug_code })),
    system_evaluations: ['a', 'b', 'c'].map(drug_code => ({ drug_code, eligible: drug_code !== 'b' })),
  }}], output: { candidates: [{ drug_code: 'a' }] }, evidence_snapshots: [{ doc_id: 'fixture', is_synthetic: true }] };
  const summary = drugDisposition(run);
  expect(summary.sourceCount).toBe(5);
  expect(summary.rows.map(r => r.group)).toEqual(['selected', 'excluded', 'unselected', 'unknown']);
  render(<DrugOverview run={run} />);
  expect(screen.getByText(/來源 5 筆藥敏／4 項藥品/)).toBeVisible();
  expect(screen.getByText(/合成測試文件/)).toBeVisible();
  expect(evidenceOrigin({})).toBe('文件來源類型未記錄');
  expect(evidenceOrigin({ is_synthetic: false })).toContain('真實參考文件');
  expect(drugDisposition({ ...run, output: null }).rows[0].label).toBe('通過規則，候選未發布');
  expect(drugDisposition({ ...run, output: null }).rows[0].reason).toContain('整份分析結果未發布，並非此藥品被排除');
});

test("withheld summary explains the concrete preflight blocker", () => {
  expect(
    withheldSummary({ missing_fields: ["evidence.population_applicability"] }),
  ).toBe(
    "未產生候選：沒有族群相符且已標示的參考片段，請確認文件範圍後重新分析。前置安全檢查未通過，因此 Agent 尚未呼叫。",
  );
});

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
  fireEvent.click(screen.getByText("技術資料：Agent 輸入（JSON）"));
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
    screen.getByText("技術資料（原始 JSON，供除錯）").closest("details"),
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

import { CaseContext, CandidateEvidence } from './ClinicalContext';
import { RunIssues, sourceExclusionReason } from './Insights';

test('clinical snapshot identifies simulated assertions and readable evidence', () => {
  render(<CaseContext snapshot value={{encounter:{infection_site:'bloodstream infection',severity:'stable',context:'生命徵象未提供'},provenance:{simulated_fields:['encounter']}}} />);
  expect(screen.getByText(/模擬設定，非已確認/)).toBeVisible();
  expect(screen.getByText(/不能據此認定已確診感染/)).toBeVisible();
  render(<CandidateEvidence refs={['ref1']} evidence={[{chunk_id:'ref1',doc_id:'who',document_title:'WHO',document_version:'1',location:{page:332},text:'引用原文'}]} />);
  fireEvent.click(screen.getByText(/WHO · 第 332 頁/));
  expect(screen.getByText('引用原文')).toBeVisible();
  expect(screen.getByRole('link',{name:'下載原始文件'})).toHaveAttribute('download');
});

test('confirmation summary identifies the agent and actual missing facts', () => {
  render(<RunIssues run={{output:{limitations:[]},missing_fields:[],nodes:[{node_id:'clinical_agent',agent_id:'clinical_agent',status:'needs_confirmation',output:{limitations:['既往病史未知'],missing_fields:[]}}],errors:[{node_id:'clinical_agent',code:'AGENT_NEEDS_CONFIRMATION'}]}} />);
  expect(screen.getByText('既往病史未知')).toBeVisible();
  expect(screen.queryByText('沒有記錄')).toBeNull();
  expect(screen.queryByText('執行／輸出檢核問題')).toBeNull();
});

test('historical source S and missing derived label are explained without removing other exclusions', () => {
  const run = {case_snapshot:{ast_results:[{drug_code:'a',interpretation_basis:'CLSI_2022_pheno',source_phenotype:'Susceptible',clsi_2022_phenotype:null}]}};
  const reason = sourceExclusionReason(run,'a','來源判讀缺漏或無法識別；未自行推算；來源結果不是 S，不自動列入敏感選項；命中過敏');
  expect(reason).toContain('原始報告為 Susceptible');
  expect(reason).toContain('CLSI 2022 衍生判讀未提供');
  expect(reason).toContain('命中過敏');
  expect(reason).not.toContain('來源結果不是 S');
});

