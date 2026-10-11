import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App, { Status } from "./App";
afterEach(() => vi.unstubAllGlobals());

test('reference selection resets between cases and saves library or pinned scope', async () => {
  const records: Record<string, any> = {
    a:{case_id:'a',revision:1,case:{case_id:'a',is_synthetic:true,evidence_scope:'reference',policy_refs:['who']}},
    b:{case_id:'b',revision:1,case:{case_id:'b',is_synthetic:true,evidence_scope:'reference',policy_refs:[]}},
  };
  const saved: any[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    let value: any = [];
    const revision = url.match(/^\/api\/cases\/([ab])\/revisions$/);
    if (revision && options?.method === 'POST') {
      const payload = JSON.parse(String(options.body)).payload;
      records[revision[1]] = {...records[revision[1]],revision:records[revision[1]].revision+1,case:payload};
      saved.push(payload);
      value = records[revision[1]];
    } else if (url === '/api/cases') value = Object.values(records);
    else if (url === '/api/config') value = {};
    else if (url === '/api/documents') value = [{doc_id:'who',title:'WHO book',document_version:'2022',is_synthetic:false,metadata:{population:'adult'}}];
    else if (/^\/api\/cases\/[ab]$/.test(url)) value = records[url.slice(-1)];
    return {ok:true,json:async () => value};
  }));
  render(<App />);
  await waitFor(() => expect(screen.getByLabelText('目前病例')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('目前病例'), {target:{value:'a'}});
  await screen.findByText('改為指定參考文件');
  expect(screen.queryByRole('checkbox', {name:/允許此病例的必要分析欄位與所選文件片段/})).toBeNull();
  expect(saved).toHaveLength(0);
  fireEvent.click(screen.getByText('改為指定參考文件'));
  expect(screen.getByLabelText(/WHO book/)).toBeChecked();
  fireEvent.change(screen.getByLabelText('目前病例'), {target:{value:'b'}});
  await waitFor(() => expect(screen.getByLabelText(/WHO book/)).not.toBeChecked());
  fireEvent.click(screen.getByLabelText(/WHO book/));
  fireEvent.click(screen.getByRole('button', {name:'保存指定文件'}));
  await screen.findByText('指定文件已保存，請重新分析。');
  expect(saved.at(-1)).toMatchObject({case_id:'b',evidence_scope:'reference',policy_refs:['who']});
  fireEvent.click(screen.getByRole('button', {name:'使用文件庫全部參考文件'}));
  await screen.findByText(/已改用文件庫全部參考文件/);
  expect(saved.at(-1)).toMatchObject({case_id:'b',evidence_scope:'reference',policy_refs:[]});
  expect(screen.getByLabelText(/WHO book/)).not.toBeChecked();
});

test('document delete requires confirmation and sends DELETE then refreshes', async () => {
  let deleted = false;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'DELETE') deleted = true;
    return {ok:true, json:async () => options?.method === 'DELETE' ? {deleted:true, message:'文件已刪除'} :
      url.endsWith('/config') ? {} : url.endsWith('/documents') && !deleted ? [{doc_id:'test_doc',title:'Wrong file',document_version:'1',metadata:{}}] : []};
  });
  vi.stubGlobal('fetch', fetcher);
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  render(<App />);
  await waitFor(() => expect(screen.getByText('載入已準備的來源病例')).toBeEnabled());
  fireEvent.click(screen.getByText('文件資料庫'));
  fireEvent.click(screen.getByText(/Wrong file/, {selector:'summary'}));
  fireEvent.click(screen.getByRole('button', {name:'刪除此文件'}));
  expect(deleted).toBe(false);
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole('button', {name:'刪除此文件'}));
  await screen.findByText('文件已刪除');
  expect(fetcher).toHaveBeenCalledWith('/api/documents/test_doc', expect.objectContaining({method:'DELETE'}));
  expect(screen.queryByRole('button', {name:'刪除此文件'})).toBeNull();
  confirm.mockRestore();
});
test("blocked state is visibly distinct", () => {
  render(<Status value="blocked" />);
  expect(screen.getByText("已阻擋")).toHaveClass("blocked");
});
test("backend failure is visible and retry is available", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "服務暫時無法使用" }),
    }),
  );
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "服務暫時無法使用",
  );
  expect(screen.getByText("重新連線")).toBeEnabled();
});
test("empty workspace can seed data and keeps model choice explicit", async () => {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      return {
        ok: true,
        json: async () =>
          url.endsWith("/config")
            ? { who_status: "尚未匯入", provider: { configured: false } }
            : url.endsWith("/seed")
              ? { imported: 14 }
              : [],
      };
    }),
  );
  render(<App />);
  await waitFor(() =>
    expect(screen.getByText("載入已準備的來源病例")).toBeEnabled(),
  );
  expect(
    screen.getByText("選擇病例，或先載入已準備的來源病例。"),
  ).toBeVisible();
  fireEvent.click(screen.getByText("載入已準備的來源病例"));
  await screen.findByText("來源病例已備妥");
  expect(calls).toContain("/api/seed");
  expect(screen.getByDisplayValue("未設定模型")).toBeVisible();
});

test("embedding index failure remains visible to the user", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/config")
          ? {
              rag: {
                retrieval_method: "ollama_embeddings",
                model: "embeddinggemma",
              },
            }
          : url.includes("/documents/reindex")
            ? { status: "failed", warnings: ["embedding_unavailable"] }
            : [],
    })),
  );
  render(<App />);
  await waitFor(() =>
    expect(screen.getByText("載入已準備的來源病例")).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: /05\s*文件資料庫/ }));
  expect(screen.getByText(/Embedding 模型：embeddinggemma/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "重建向量索引" }));
  expect(
    await screen.findByText("向量索引：failed · embedding_unavailable"),
  ).toBeVisible();
});

test('review identifies the run and requires an explicit decision before submission', async () => {
  const record = {case_id:'case-ui',revision:1,case:{case_id:'case-ui',is_synthetic:true,policy_refs:[]}};
  const run = {run_id:'run-ui',mode:'multi-agent',created_at:'2026-09-20T01:00:00Z',gate_status:'ready_for_review',status:'awaiting_review',case_snapshot:{encounter:{severity:'stable'},provenance:{simulated_fields:['encounter']}},output:{candidates:[{drug_code:'demo-drug',reason:'模型待核對說明',evidence_refs:[]}],limitations:[]},nodes:[]};
  vi.stubGlobal('fetch',vi.fn(async (url:string) => ({ok:true,json:async () =>
    url === '/api/cases' ? [record] : url === '/api/cases/case-ui' ? record :
    url === '/api/runs?case_id=case-ui' ? [run] : url === '/api/runs/run-ui' ? run :
    url === '/api/config' ? {} : []
  })));
  render(<App />);
  await waitFor(() => expect(screen.getByLabelText('目前病例')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('目前病例'),{target:{value:'case-ui'}});
  fireEvent.click(await screen.findByRole('button',{name:/run-ui/}));
  fireEvent.click(await screen.findByRole('button',{name:'前往人工審閱'}));
  expect(screen.getByText(/分析：run-ui/)).toBeVisible();
  expect(screen.getByRole('heading',{name:'demo-drug'})).toBeVisible();
  expect(screen.getByLabelText('決定')).toHaveValue('');
  fireEvent.change(screen.getByLabelText('審閱理由'),{target:{value:'已核對展示內容'}});
  expect(screen.getByRole('button',{name:'送出審閱'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('決定'),{target:{value:'reject'}});
  expect(screen.getByRole('button',{name:'送出審閱'})).toBeEnabled();
});

test('historical provenance and confirmation links use the run snapshot', async () => {
  const record={case_id:'case-ui',revision:4,case:{case_id:'case-ui',is_synthetic:true,policy_refs:[]}};
  const issue={agent_id:'evidence_agent',field:'evidence_context',impact:'省略 2 個片段',action:'核對引用快照'};
  const run={run_id:'run-old',case_id:'case-ui',case_revision:2,mode:'multi-agent',decision_basis:'agent',provider_kind:'live',model:'gpt-4.1-mini',status:'partial',gate_status:'needs_confirmation',confirmation_items:[issue,issue,{...issue,agent_id:'clinical_agent'}],nodes:[{node_id:'evidence_agent',agent_id:'evidence_agent',status:'needs_confirmation',output:{findings:['仍需核對感染情境']}}],errors:[]};
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url==='/api/cases'?[record]:url==='/api/cases/case-ui'?record:url==='/api/runs?case_id=case-ui'?[run]:url==='/api/runs/run-old'?run:url==='/api/config'?{}:[]})));
  render(<App/>);
  await waitFor(()=>expect(screen.getByLabelText('目前病例')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('目前病例'),{target:{value:'case-ui'}});
  fireEvent.click(await screen.findByRole('button',{name:/run-old/}));
  expect(await screen.findByText(/分析當時病例：case-ui · 病例版本 2 · 模型：gpt-4.1-mini/)).toBeVisible();
  fireEvent.click(screen.getByText(/系統證據核對缺口（3）/));
  expect(screen.getAllByText('文件片段未完整納入')).toHaveLength(2);
  expect(screen.getByText('相同記錄 2 筆')).toBeVisible();
  expect(screen.getByText('臨床風險 Agent')).toBeVisible();
  expect(screen.getAllByRole('button',{name:'查看此步驟'})).toHaveLength(1);
  fireEvent.click(screen.getAllByRole('button',{name:'查看此步驟'})[0]);
  expect(await screen.findByText('仍需核對感染情境')).toBeVisible();
  expect(document.getElementById('agent-step-evidence_agent')).toHaveAttribute('open');
});
