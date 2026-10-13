import { useEffect, useState } from "react";
import { EvidenceCoverage } from './AgentLed';
import { EvidenceLibrary } from './EvidenceLibrary';
import { api, pretty } from "./api";
import type { components } from "./api.generated";
import { ReviewEditor, reviewOutput } from "./ReviewEditor";
import { PhysicianReview, physicianDecisionNames } from './PhysicianReview';
import { CaseContext, CandidateEvidence } from './ClinicalContext';
import {AllergyEditor, allergyStatuses} from './AllergyContext';
import {
  BenchmarkOverview,
  DrugOverview,
  DemoSourceResult,
  evidenceOrigin,
  SettingsOverview,
  WorkflowStep,
  RunIssues,
  RunProvenance,
  TechnicalDetails,
  executionLabel,
  localTime,
  modeNames,
  statusNames,
  withheldSummary,
  RetrievalWarnings,
  sourceExclusionReason,
} from "./Insights";
type CaseRecord = components["schemas"]["CaseRecord"];

const sections = [
  "病例工作台",
  "分析結果",
  "證據與流程",
  "人工審閱",
  "文件資料庫",
  "研究與設定",
];
const modes = ["rule-only", "rag-only", "single-agent", "multi-agent"];
const names: Record<string, string> = {
  completed: "已完成",
  awaiting_review: "待人工審閱",
  ready_for_review: "可送審閱",
  needs_confirmation: "需要確認",
  blocked: "已阻擋",
  not_configured: "尚未設定",
  failed: "失敗",
  partial: "部分完成",
  skipped: "已略過",
  pending: "等待中",
  running: "執行中",
};
export function Status({ value }: { value: string }) {
  return (
    <span className={"badge " + value}>
      {statusNames[value] || names[value] || value}
    </span>
  );
}
function Json({ value }: { value: unknown }) {
  return <pre>{pretty(value)}</pre>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

export default function App() {
  const [agentTarget,setAgentTarget]=useState<string|null>(null);
  function openAgent(id:string) { setSection(2); setAgentTarget(id); }
  const [section, setSection] = useState(0),
    [cases, setCases] = useState<CaseRecord[]>([]),
    [selected, setSelected] = useState<CaseRecord | null>(null);
  const [config, setConfig] = useState<any>(null),
    [run, setRun] = useState<any>(null),
    [runs, setRuns] = useState<any[]>([]),
    [reviews, setReviews] = useState<any[]>([]);
  useEffect(()=>{
    if(section!==2 || !agentTarget) return;
    const target=document.getElementById(`agent-step-${agentTarget}`) as HTMLDetailsElement|null;
    if(target) { target.open=true; target.scrollIntoView?.({block:'center'}); target.querySelector('summary')?.focus(); }
    setAgentTarget(null);
  },[section,agentTarget]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [mode, setMode] = useState("rule-only"),
    [provider, setProvider] = useState("unconfigured");
  const [payload, setPayload] = useState(""),
    [format, setFormat] = useState("canonical"),
    [editing, setEditing] = useState(false),
    [history, setHistory] = useState<any[]>([]);
  const [reason, setReason] = useState(""),
    [action, setAction] = useState(""),
    [proposed, setProposed] = useState(reviewOutput(null)),
    [role, setRole] = useState("physician");
  const [documents, setDocuments] = useState<any[]>([]),
    [query, setQuery] = useState("urinary tract infection"),
    [search, setSearch] = useState<any>(null),
    [documentScope, setDocumentScope] = useState<"synthetic" | "reference">(
      "reference",
    );
  const [docFile, setDocFile] = useState<File | null>(null),
    [docTitle, setDocTitle] = useState(""),
    [docVersion, setDocVersion] = useState("1"),
    [docPopulation, setDocPopulation] = useState("unspecified"),
    [docKind, setDocKind] = useState('reference'),
    [studyDesign, setStudyDesign] = useState('not_recorded'),
    [docSource, setDocSource] = useState(''),
    [docRegion, setDocRegion] = useState(''),
    [synthetic, setSynthetic] = useState(false);
  const [benchmark, setBenchmark] = useState<any>(null),
    [benchmarks, setBenchmarks] = useState<any[]>([]),
    [rules, setRules] = useState<any>(null);
  const [benchmarkProvider, setBenchmarkProvider] = useState("unconfigured");
  const [benchmarkCaseIds, setBenchmarkCaseIds] = useState<string[]>([]);
  const [benchmarkModes, setBenchmarkModes] = useState<string[]>(modes);
  async function work(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    const [cs, cf, ds, bs, rs] = await Promise.all([
      api("/cases"),
      api("/config"),
      api("/documents"),
      api("/benchmarks"),
      api("/rules"),
    ]);
    setCases(cs);
    setConfig(cf);
    setDocuments(ds);
    setBenchmarks(bs);
    setBenchmark((current: any) => current ?? bs[0] ?? null);
    setRules(rs);
  }
  useEffect(() => {
    void work(refresh);
  }, []);
  async function chooseCase(id: string) {
    const [detail, rs, revs] = await Promise.all([
      api("/cases/" + encodeURIComponent(id)),
      api("/runs?case_id=" + encodeURIComponent(id)),
      api("/cases/" + encodeURIComponent(id) + "/revisions"),
    ]);
    setSelected(detail);
    setRuns(rs);
    setHistory(revs);
    setRun(null);
    setReviews([]);
    setSection(0);
    setEditing(false);
  }
  async function chooseRun(value: any) {
    const detail = await api("/runs/" + value.run_id);
    setRun(detail);
    setAction('');
    setReason('');
    setProposed(reviewOutput(detail.output));
    setReviews(await api("/reviews?run_id=" + detail.run_id));
  }
  async function startRun() {
    if (!selected) return;
    await work(async () => {
      const value = await api("/runs", {
        case_id: selected.case_id,
        mode,
        provider_kind: provider,
        request_id: crypto.randomUUID(),
        previous_run_id: run?.run_id,
      });
      await chooseRun(value);
      setRuns(await api("/runs?case_id=" + selected.case_id));
      setSection(1);
    });
  }
  const c = selected?.case;
  const referencedDocuments = c?.evidence_scope === 'reference' && !c.policy_refs?.length
    ? documents.filter(d => d.is_synthetic === false)
    : (c?.policy_refs || [])
    .map((id: string) => documents.find((d: any) => d.doc_id === id))
    .filter(Boolean);
  const unverifiedPopulationDocuments =
    c?.evidence_scope === "reference"
      ? referencedDocuments.filter((d: any) =>
          ["unspecified", "mixed"].includes(
            d.metadata?.population || "unspecified",
          ),
        )
      : [];
  return (
    <div className="app">
      <aside>
        <div className="brand">
          <span className="brandmark">＋</span>
          <div>
            ABX <strong>研究工作台</strong>
            <small>多代理人決策 Prototype</small>
          </div>
        </div>
        <div className="navlabel">工作空間</div>
        <nav>
          {sections.map((s, i) => (
            <button
              key={s}
              className={section === i ? "active" : ""}
              onClick={() => setSection(i)}
            >
              <span>0{i + 1}</span>
              {s}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Status value="demo_only" />
          <p>
            病例區分來源藥敏與模擬臨床資訊。
            <br />
            來源敏感判讀不等於治療建議。
          </p>
          <label>
            審閱紀錄角色（展示）
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="physician">醫師</option>
              <option value="pharmacist">藥師</option>
              <option value="researcher">研究／管理人員</option>
            </select>
          </label>
          <small>
            只記錄審閱身分，不改變分析結果或權限；目前沒有正式登入。
          </small>
        </div>
      </aside>
      <main>
        <div className="disclaimer">
          研究展示用／病例標示來源與模擬欄位／非臨床使用
        </div>
        <header>
          <div>
            <div className="eyebrow">ANTIBIOTIC RESEARCH · LOCAL PROTOTYPE</div>
            <h1>{sections[section]}</h1>
            <p>可追溯的規則、文件證據與人工審閱</p>
          </div>
          <div className="connection">
            <span className={config ? "dot" : "dot offline"} />
            {config ? "本機服務已連線" : "等待本機服務"}
            <small>
              正式參考文件：
              {config?.reference_status || config?.who_status || "尚未匯入"}
            </small>
          </div>
        </header>
        {error && (
          <div className="alert error" role="alert">
            {error}
            <button onClick={() => void work(refresh)}>重新連線</button>
          </div>
        )}
        {notice && (
          <div className="alert success" role="status">
            {notice}
          </div>
        )}
        {busy && (
          <div role="status" className="loading">
            處理中，請稍候…
          </div>
        )}
        <div className="contextbar">
          <label>
            目前病例
            <select
              aria-label="目前病例"
              disabled={busy}
              value={selected?.case_id || ""}
              onChange={(e) => {
                if (e.target.value) void work(() => chooseCase(e.target.value));
              }}
            >
              <option value="">選擇研究病例</option>
              {cases.map((x) => (
                <option key={x.case_id} value={x.case_id}>
                  {x.case_id} · revision {x.revision}
                </option>
              ))}
            </select>
          </label>
          <button
            disabled={busy}
            onClick={() =>
              void work(async () => {
                const seeded = await api("/seed", {});
                await refresh();
                setNotice(seeded.message || "來源病例已備妥");
              })
            }
          >
            載入已準備的來源病例
          </button>
          <span className="muted">
            {cases.length} 個病例 ·{" "}
            {selected ? "版本 " + selected.revision : "尚未選取"}
          </span>
        </div>
        {section === 0 && (
          <>
            <div className="grid two">
              <section className="panel">
                <h2>病例摘要</h2>
                {c ? (
                  <>
                    <p className="notice">
                      {c.source || "研究病例"} ·{" "}
                      {c.is_synthetic ? "全部合成" : "含去識別來源資料"}
                    </p>
                    <CaseContext value={c} />
                    <button type="button" disabled={busy} onClick={()=>void work(async()=>{
                      const status=c.medications?.length?'reviewed_list':'reviewed_none';
                      await api('/cases/'+c.case_id+'/revisions',{payload:{...c,medication_history_status:status,
                        provenance:{...c.provenance,notes:[...(c.provenance?.notes || []),`使用者於 ${new Date().toISOString()} 確認目前用藥紀錄：${status}`]}}});
                      await chooseCase(c.case_id);
                      setNotice('用藥清單核對狀態已保存為新版本，請重新分析。');
                    })}>{c.medications?.length?'確認目前列出的用藥清單完整':'確認目前無用藥'}</button>
                    <AllergyEditor key={`${c.case_id}:${selected?.revision}:allergies`} value={c.allergies} busy={busy} onSave={async allergies=>{
                      await work(async()=>{
                        await api('/cases/' + c.case_id + '/revisions', {payload:{...c,allergies}});
                        await chooseCase(c.case_id);
                        setNotice('過敏資料已保存為新版本；請重新分析，舊分析與審閱紀錄維持原樣。');
                      });
                    }}/>
                    <p>
                      證據範圍：
                      {c.evidence_scope === "reference"
                        ? "WHO 等參考文件"
                        : "測試文件"}
                    </p>
                    <p>文件選擇：{c.policy_refs?.length ? `指定文件（${c.policy_refs.join('、')}）` : c.evidence_scope === 'reference' ? '文件庫全部參考文件；按病例相關性檢索' : '尚未指定測試文件'}</p>
                    <button type="button" disabled={busy} onClick={() => void work(async () => {
                      await api('/cases/' + c.case_id + '/revisions', {payload: {...c, evidence_scope:'reference', policy_refs:[]}});
                      await chooseCase(c.case_id);
                      setNotice('已改用文件庫全部參考文件；新上傳的參考文件也會納入搜尋，請重新分析。');
                    })}>使用文件庫全部參考文件</button>
                    <details><summary>改為指定參考文件</summary>
                      <form key={`${c.case_id}:${selected?.revision}`} onSubmit={event => {
                        event.preventDefault();
                        const refs = new FormData(event.currentTarget).getAll('policy_refs').map(String);
                        if (!refs.length) { setError('請至少選擇一份參考文件，或使用全部參考文件。'); return; }
                        void work(async () => {
                          await api('/cases/' + c.case_id + '/revisions', {payload:{...c, evidence_scope:'reference', policy_refs:refs}});
                          await chooseCase(c.case_id);
                          setNotice('指定文件已保存，請重新分析。');
                        });
                      }}>
                        {documents.filter(d => d.is_synthetic === false).map(d => <label className="check-label" key={d.doc_id}>
                          <input type="checkbox" name="policy_refs" value={d.doc_id} defaultChecked={c.policy_refs?.includes(d.doc_id)} />{d.title} · {d.document_version}
                        </label>)}
                        <button disabled={busy} type="submit">保存指定文件</button>
                      </form>
                    </details>
                    <div className="facts">
                      <div>
                        <small>病例 ID</small>
                        <strong>{c.case_id}</strong>
                      </div>
                      <div>
                        <small>過敏狀態</small>
                        <strong>{allergyStatuses[c.allergies?.status || 'unknown']}</strong>
                      </div>
                      <div>
                        <small>菌種</small>
                        <strong>{c.microbiology?.organism || "未知"}</strong>
                      </div>
                      <div>
                        <small>腎功能 eGFR</small>
                        <strong>
                          {c.renal?.egfr ?? "未知"} {c.renal?.unit}
                        </strong>
                      </div>
                    </div>
                    <h3>來源 AST 報告</h3>
                    <p className="muted">
                      來源 S/I/R
                      與系統規則判讀分別保留；此處不是系統重新驗證結果。
                    </p>
                    <div className="tablewrap">
                      <table>
                        <thead>
                          <tr>
                            <th>藥品代碼</th>
                            <th>原始測量</th>
                            <th>原始報告</th>
                            <th>CLSI 2022 衍生判讀</th>
                            <th>採用來源</th>
                          </tr>
                        </thead>
                        <tbody>
                          {c.ast_results?.map((a: any, i: number) => (
                            <tr key={i}>
                              <td>{a.drug_code}</td>
                              <td>
                                {a.interpretation_basis &&
                                a.interpretation_basis !== "legacy" ? (
                                  <>
                                    {a.raw_measurement?.AST_inequality}{" "}
                                    {a.raw_measurement?.AST_val1 || "未提供"}{" "}
                                    {a.raw_measurement?.AST_val2 &&
                                      `／${a.raw_measurement.AST_val2}`}
                                    <small>{a.method} · 原檔未提供單位</small>
                                  </>
                                ) : (
                                  <>
                                    {a.comparator ?? "?"} {a.mic ?? "未知"}{" "}
                                    {a.unit ?? "單位缺漏"}
                                  </>
                                )}
                              </td>
                              <td>
                                {a.source_phenotype ||
                                  a.reported_sir ||
                                  "未提供"}
                              </td>
                              <td>{a.clsi_2022_phenotype || "未提供"}</td>
                              <td>
                                {a.interpretation_basis === "CLSI_2022_pheno"
                                  ? "資料集衍生欄位（未重新計算）"
                                  : `${a.standard || "未知"} / ${a.standard_version || "未知"}`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <details>
                      <summary>全部病例資料與轉換警告</summary>
                      <Json value={selected} />
                    </details>
                    <button
                      disabled={busy}
                      onClick={() => {
                        setPayload(pretty(c));
                        setEditing(true);
                      }}
                    >
                      編輯並建立新版本
                    </button>
                    <details>
                      <summary>歷史版本（{history.length}）</summary>
                      <Json value={history} />
                    </details>
                  </>
                ) : (
                  <Empty>選擇病例，或先載入已準備的來源病例。</Empty>
                )}
              </section>
              <section className="panel">
                <h2>執行分析</h2>
                <p>分析完成後，結果仍需人工審閱；multi-agent 由各 Agent 評估與獨立引用複核。</p>
                <label>
                  比較模式
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    {modes.map((m) => (
                      <option key={m} value={m}>
                        {modeNames[m]}（{m}）
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  模型執行方式
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    <option value="unconfigured">未設定模型</option>
                    <option value="mock">明確啟用 mock（離線展示）</option>
                    <option value="live">
                      已設定模型（OpenAI／本機 Ollama）
                    </option>
                  </select>
                </label>
                {provider === "live" && (
                  <div className="alert">
                    執行時將傳送必要病例
                    欄位及檢索片段至已設定的外部模型，可能產生費用。
                  </div>
                )}
                {provider === "mock" && (
                  <div className="alert">
                    MOCK 模擬輸出，不能視為真實模型研究結果。
                  </div>
                )}
                {mode === "multi-agent" && <p>每病例通常有 5 次獨立模型呼叫；遇缺漏或失敗會提早停止。可在「證據與流程」查看各 Agent 的輸入、輸出與用量。</p>}
                {!!unverifiedPopulationDocuments.length && (
                  <div className="alert" role="alert">
                    此病例引用的文件{" "}
                    {unverifiedPopulationDocuments
                      .map((d: any) => d.title)
                      .join("、")}{" "}
                    尚未有可用的單一族群標示，相關片段可能被排除。若沒有其他適用證據，分析會暫緩；請到「文件資料庫」核對適用族群。
                  </div>
                )}
                <button
                  className="primary wide"
                  disabled={busy || !c}
                  onClick={() => void startRun()}
                >
                  執行分析
                </button>
                <h3>執行紀錄</h3>
                {runs.length ? (
                  runs.map((r) => (
                    <button
                      className="runrow"
                      key={r.run_id}
                      onClick={() =>
                        void work(async () => {
                          await chooseRun(r);
                          setSection(1);
                        })
                      }
                    >
                      <span>
                        {modeNames[r.display_mode || r.mode] || r.mode}{" "}
                        <small>{r.run_id.slice(0, 8)}</small>
                        <small className="block">
                          {localTime(r.created_at || r.nodes?.[0]?.started_at)}{" "}
                          · {executionLabel(r)}
                        </small>
                      </span>
                      <Status value={r.status} />
                    </button>
                  ))
                ) : (
                  <Empty>此病例尚無執行紀錄。</Empty>
                )}
              </section>
            </div>
            <section className="panel">
              <h2>{editing ? "建立病例新版本" : "匯入病例 JSON"}</h2>
              <label>
                格式
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                >
                  <option value="canonical">標準格式 canonical</option>
                  <option value="alternate">第二種格式 alternate</option>
                </select>
              </label>
              <input
                aria-label="選擇病例 JSON"
                type="file"
                accept=".json"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void work(async () => setPayload(await f.text()));
                }}
              />
              <textarea
                aria-label="病例 JSON"
                rows={7}
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                placeholder="貼上病例 JSON；請標示資料來源與模擬欄位"
              />
              <button
                disabled={busy || !payload}
                onClick={() =>
                  void work(async () => {
                    const value = await api(
                      editing
                        ? "/cases/" + selected!.case_id + "/revisions"
                        : "/cases/import",
                      { payload: JSON.parse(payload), format },
                    );
                    await refresh();
                    await chooseCase(value.case_id);
                    setPayload("");
                    setEditing(false);
                    setNotice("病例已保存。");
                  })
                }
              >
                {editing ? "保存新版本" : "驗證並匯入"}
              </button>
              {editing && (
                <button
                  onClick={() => {
                    setEditing(false);
                    setPayload("");
                  }}
                >
                  取消編輯
                </button>
              )}
            </section>
          </>
        )}
        {section === 1 &&
          (run ? (
            <>
              <div className="runbanner">
                <div>
                  <small>
                    {modeNames[run.display_mode || run.mode] || run.mode} · {executionLabel(run)} ·{" "}
                    {run.run_id}
                  </small>
                  <h2>
                    <Status value={run.gate_status} />
                    <Status value={run.status} />
                  </h2>
                </div>
                <a
                  className="button"
                  href={"/api/runs/" + run.run_id + "/export"}
                  download
                >
                  匯出 JSON
                </a>
              </div>
              <RunProvenance run={run}/>
              <details className="panel"><summary>分析時的病例摘要</summary><CaseContext value={run.case_snapshot} snapshot /></details>
              {run.decision_basis==='agent' && <><DrugOverview key={run.run_id} run={run} /><section className="panel"><RunIssues run={run} onOpenAgent={openAgent}/></section></>}
              {run.decision_basis!=='agent' && <div className="grid two">
                <section className="panel">
                  {run.decision_basis!=='agent' && <DrugOverview run={run} />}
                  <DemoSourceResult run={run} />
                  <h2>可供審閱的藥敏選項</h2>
                  {(run.output?.candidates || []).length ? (
                    run.output.candidates.map((x: any) => (
                      <article className="candidate" key={x.drug_code}>
                        <h3>
                          {x.drug_code} {run.decision_basis!=='agent' && <Status value="demo_only" />}
                        </h3>
                        <p><strong>模型理由（待核對）：</strong>{x.reason}</p>

                        <CandidateEvidence refs={x.evidence_refs} evidence={run.evidence_snapshots} audited={run.decision_basis==='agent' && x.verification_status==='complete'} />
                        <TechnicalDetails value={{rule_refs:x.rule_refs,evidence_refs:x.evidence_refs}} label={run.decision_basis==='agent' ? '技術資料：引用代碼（JSON）' : '技術資料：規則與引用代碼（JSON）'} />
                      </article>
                    ))
                  ) : (
                    <Empty>{withheldSummary(run)}</Empty>
                  )}
                </section>
                <section className="panel">
                  <h2>{run.decision_basis==='agent' ? '不建議與待確認事項' : '來源排除／待確認項目'}</h2>
                  {(run.safety_summary?.avoid ?? run.output?.avoid)?.map(
                    (x: any, i: number) => (
                      <article key={i}>
                        <h3>{x.drug_code}</h3>
                        <p>{run.decision_basis==='agent' ? x.exclusion_reasons?.join('；') || x.reason : sourceExclusionReason(run, x.drug_code, x.reason)}</p>
                      </article>
                    ),
                  )}
                  <RunIssues run={run} onOpenAgent={openAgent} />
                </section>
              </div>}
              {run.raw_baseline?.withheld && (
                <div className="alert">
                  研究基線原始輸出已隔離保存；此畫面僅呈現通過共用安全檢核的內容。
                </div>
              )}
              <button onClick={() => setSection(2)}>查看證據與流程</button>
              <button onClick={() => setSection(3)}>前往人工審閱</button>
            </>
          ) : (
            <Empty>先從病例工作台執行或選擇一筆分析。</Empty>
          ))}
        {section === 2 &&
          (run ? (
            <div className="evidence-workspace">
              <section className="panel">
                <h2>分析步驟與結果</h2>
                <RunProvenance run={run}/>
                {run.decision_basis!=='agent' && <DrugOverview run={run} />}
                <p>
                  展開步驟查看做了什麼與得到的結果；「步驟已執行」不代表資料或候選已通過檢核。
                </p>
                {run.nodes?.map((n: any, i: number) => (
                  <WorkflowStep key={i} node={n} index={i} run={run} />
                ))}
                <details>
                  <summary>{run.decision_basis==='agent' ? 'Agent 流程版本' : '規則命中與版本'}</summary>
                  <Json
                    value={{
                      versions: run.versions,
                      evaluations: run.rule_evaluations,
                    }}
                  />
                </details>
              </section>
              <section className="panel"><EvidenceCoverage run={run}/><details><summary>檢索查詢紀錄（{run.retrievals?.length || 0} 次）</summary><div className="tablewrap"><table><thead><tr><th>查詢</th><th>狀態</th><th>片段數</th></tr></thead><tbody>{run.retrievals?.map((r:any,i:number)=><tr key={i}><td>{r.query}</td><td>{r.status}</td><td>{r.count}</td></tr>)}</tbody></table></div></details></section>
              <EvidenceLibrary run={run}/>

            </div>
          ) : (
            <Empty>選擇執行紀錄後查看流程與引用。</Empty>
          ))}
        {section === 3 &&
          (run ? (
            <div className="review-workspace">
              <section className="panel">
                <h2>人工審閱</h2>
                <RunProvenance run={run}/>
                <p>分析：{run.run_id} · {modeNames[run.display_mode || run.mode] || run.mode} · {localTime(run.created_at || run.nodes?.[0]?.started_at)}</p>
                <details><summary>病例摘要</summary><CaseContext value={run.case_snapshot} snapshot /></details>
                {run.decision_basis==='agent' && <PhysicianReview key={run.run_id} run={run} role={role} busy={busy} onSave={async decisions=>{
                  setBusy(true);
                  try {
                    await api('/reviews',{run_id:run.run_id,action:'drug_review',reason:'逐藥醫師決策，理由與條件見各項紀錄',reviewer_id:'demo-user',role,drug_decisions:decisions});
                    setReviews(await api('/reviews?run_id='+run.run_id));
                    setNotice('逐藥決策已保存，原始系統警示與核對狀態保持不變。');
                  } finally {setBusy(false);}
                }}/>}
                <details open={run.decision_basis!=='agent'}><summary>{run.decision_basis==='agent'?'整份 AI 結果審閱（原有流程）':'整份結果審閱'}</summary>
                {run.decision_basis!=='agent' && <><h3>本次待審候選</h3>
                {run.output?.candidates?.length ? run.output.candidates.map((x: any) => <article key={x.drug_code}><h4>{x.drug_code}</h4><p><strong>模型理由（待核對）：</strong>{x.reason}</p><CandidateEvidence refs={x.evidence_refs} evidence={run.evidence_snapshots} /></article>) : <p>本次沒有可接受或修改的候選；可以拒絕並記錄原因。</p>}</>}
                <button onClick={() => setSection(1)}>回看病例情境與待確認事項</button>
                <RunIssues run={run} onOpenAgent={openAgent} />
                <p>審閱者 demo-user · {role} · 僅展示角色</p>
                <Status value={run.gate_status} />
                <label>
                  決定
                  <select
                    aria-label="決定"
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                  >
                    <option value="">請選擇審閱決定</option>
                    <option value="accept" disabled={run.gate_status !== 'ready_for_review' || !run.output?.candidates?.length}>接受</option>
                    <option value="modify" disabled={run.gate_status !== 'ready_for_review' || !run.output?.candidates?.length}>修改</option>
                    <option value="reject">拒絕</option>
                  </select>
                </label>
                {action === "modify" && (
                  <ReviewEditor
                    run={run}
                    value={proposed}
                    onChange={setProposed}
                  />
                )}
                <label>
                  審閱理由
                  <textarea
                    aria-label="審閱理由"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="請輸入可追溯的審閱理由"
                  />
                </label>
                <p className="muted">請先選擇決定並填寫審閱理由，才能送出。修改候選時，每項須有理由與必要引用。</p>
                <button
                  className="primary"
                  disabled={
                    busy ||
                    !action ||
                    (action !== 'reject' && (run.gate_status !== 'ready_for_review' || !run.output?.candidates?.length)) ||
                    !reason.trim() ||
                    (action === "modify" &&
                      proposed.candidates.some(
                        (x) =>
                          !x.reason.trim() ||
                          (!!run.evidence_snapshots?.length &&
                            !x.evidence_refs.length),
                      ))
                  }
                  onClick={() =>
                    void work(async () => {
                      await api("/reviews", {
                        run_id: run.run_id,
                        action,
                        reason,
                        reviewer_id: "demo-user",
                        role,
                        ...(action === "modify"
                          ? { proposed_output: proposed }
                          : {}),
                      });
                      setReviews(await api("/reviews?run_id=" + run.run_id));
                      setNotice("審閱已保存。");
                      setReason("");
                    })
                  }
                >
                  送出審閱
                </button>
                </details>
              </section>
              <section className="panel">
                <h2>已保存的審閱歷史</h2>
                <button
                  disabled={busy}
                  onClick={() =>
                    void work(async () =>
                      setReviews(await api("/reviews?run_id=" + run.run_id)),
                    )
                  }
                >
                  重新讀取審閱
                </button>
                {reviews.length ? (
                  reviews.map((r: any, i: number) => (
                    <article className="review" key={i}>
                      <strong>
                        {({accept:'接受',modify:'修改',reject:'拒絕',drug_review:'逐藥醫師決策'} as Record<string,string>)[r.action] || r.action} · {r.reviewer_id}
                      </strong>
                      <p>{r.reason}</p>
                      {r.drug_decisions?.map((d:any)=><div key={d.drug_code}><strong>{d.drug_code}：{physicianDecisionNames[d.decision] || d.decision}</strong><p>理由：{d.reason}</p>{d.conditions && <p>使用條件：{d.conditions}</p>}<p>{d.outside_analysis?'醫師自行新增；此名稱未對應本次藥品評估，請核對是否為既有藥品別名':`原系統狀態：${statusNames[d.system_assessment?.status] || d.system_assessment?.status}；警示與未完成項目仍保留。`}</p></div>)}
                      {r.action==='drug_review' && <a href={'/api/reviews/'+r.review_id+'/export'} download>匯出醫師決策與原始警示</a>}
                      <small>{localTime(r.created_at)}</small>
                      <details>
                        <summary>原始／修改內容</summary>
                        <Json value={r} />
                      </details>
                    </article>
                  ))
                ) : (
                  <Empty>尚未送出人工審閱。</Empty>
                )}
              </section>
            </div>
          ) : (
            <Empty>請先選擇要審閱的執行紀錄。</Empty>
          ))}
        {section === 4 && (
          <div className="grid two">
            <section className="panel">
              <h2>匯入文件</h2>
              <p>
                支援
                PDF、Markdown、文字。原始檔、版本與引用定位會保留；不自動轉成臨床規則。
              </p>
              <label>
                文件
                <input
                  type="file"
                  accept=".pdf,.md,.txt"
                  onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <label>
                標題
                <input
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                />
              </label>
              <label>
                版本
                <input
                  value={docVersion}
                  onChange={(e) => setDocVersion(e.target.value)}
                />
              </label>
              <label>
                適用族群
                <select
                  value={docPopulation}
                  onChange={(e) => setDocPopulation(e.target.value)}
                >
                  <option value="unspecified">尚未標示</option>
                  <option value="all">所有年齡</option>
                  <option value="adult">成人</option>
                  <option value="pediatric">兒童</option>
                  <option value="mixed">成人與兒童混合（待整理適用片段）</option>
                </select>
              </label>
              <label>證據類型<select value={docKind} onChange={e=>setDocKind(e.target.value)}>
                <option value="reference">一般參考文件（待分類）</option><option value="guideline">感染指引</option>
                <option value="drug_label">藥品標示</option><option value="research_article">研究文章（背景證據）</option>
              </select></label>
              {docKind==='research_article' && <label>研究設計<select value={studyDesign} onChange={e=>setStudyDesign(e.target.value)}>
                <option value="not_recorded">未提供</option><option value="observational">觀察性研究</option>
                <option value="randomized_trial">隨機試驗</option><option value="systematic_review">系統性回顧</option><option value="other">其他</option>
              </select></label>}
              <label>來源網址<input type="url" value={docSource} onChange={e=>setDocSource(e.target.value)}/></label>
              <label>適用地區<input value={docRegion} onChange={e=>setDocRegion(e.target.value)}/></label>
              {docKind==='research_article' && <p>本流程將研究文章用於背景；群體關聯不能直接推定個人風險、解除過敏標籤或支持本例選藥。</p>}
              <label className="check">
                <input
                  type="checkbox"
                  checked={synthetic}
                  onChange={(e) => setSynthetic(e.target.checked)}
                />
                虛構展示文件（正式文件請取消）
              </label>
              <p className="muted">
                來源病例依 evidence_scope 檢索參考文件；上傳 WHO
                時請取消合成文件勾選。
                適用族群須由上傳者核對。混合或未標示的內容可供搜尋，
                但須先整理成附來源與定位的單一族群文件，才能支持候選。
              </p>
              <button
                disabled={busy || !docFile || !docTitle || !docVersion}
                onClick={() =>
                  void work(async () => {
                    const f = new FormData();
                    f.append("file", docFile!);
                    f.append("title", docTitle);
                    f.append("version", docVersion);
                    f.append("is_synthetic", String(synthetic));
                    f.append("population", docPopulation);
                    f.append('document_kind',docKind);
                    f.append('study_design',docKind==='research_article'?studyDesign:'not_recorded');
                    f.append('source_url',docSource);
                    f.append('jurisdiction',docRegion);
                    const d = await api("/documents/import", f);
                    setDocuments(await api("/documents"));
                    setConfig(await api("/config"));
                    setNotice("文件處理狀態：" + d.processing_status);
                  })
                }
              >
                匯入並解析文件
              </button>
              <h3>文件版本（{documents.length}）</h3>
              <p className="muted">刪除文件會移除原檔與檢索索引，保留歷史分析的證據快照；病例引用不會自動切換到 WHO。</p>
              {documents.map((d: any) => (
                <details key={d.doc_id}>
                  <summary>
                    {d.title} · v{d.document_version}{" "}
                    <Status value={d.processing_status} />
                  </summary>
                  <p>{evidenceOrigin(d)} · 已解析 {d.chunk_count ?? 0} 個片段</p>
                  <p>證據類型：{({reference:'一般參考文件',guideline:'感染指引',drug_label:'藥品標示',research_article:'研究文章（背景證據）'} as Record<string,string>)[d.metadata?.document_kind || 'reference'] || '其他'} · 研究設計：{({observational:'觀察性研究',randomized_trial:'隨機試驗',systematic_review:'系統性回顧',other:'其他'} as Record<string,string>)[d.metadata?.study_design] || '未提供'}</p>
                  {d.metadata?.source_url && <p>來源：{d.metadata.source_url}</p>}
                  {d.metadata?.source_derivation && <p>節錄自：{d.metadata.source_derivation.original_title} · 版本 {d.metadata.source_derivation.original_version}。與全文屬同一原始文件，不能計為獨立證據。</p>}
                  {d.metadata?.jurisdiction && <p>適用地區：{d.metadata.jurisdiction}</p>}
                  <RetrievalWarnings warnings={d.processing_warnings} />
                  <h4>目前族群標示與依據</h4>
                  <p>{({all:'所有年齡',adult:'成人',pediatric:'兒童',mixed:'成人與兒童混合',unspecified:'尚未標示'} as Record<string,string>)[d.metadata?.population || 'unspecified']}{d.metadata?.population && d.metadata.population!=='unspecified' && !d.metadata?.population_history?.some((entry:any)=>entry.reason?.trim()) && '（標示依據未記錄；仍需核對原文適用範圍）'}</p>
                  {d.metadata?.population_history?.length ? d.metadata.population_history.map((entry: any, i: number) => <p key={i}>{localTime(entry.updated_at)} · 標示為 {({all:'所有年齡',adult:'成人',pediatric:'兒童',mixed:'混合',unspecified:'尚未標示'} as Record<string,string>)[entry.population] || entry.population} · 依據：{entry.reason || '未記錄'} · 操作者：{entry.updated_by || '未記錄'}</p>) : <p>未保存族群標示的變更紀錄或依據，請核對文件。</p>}
                  <TechnicalDetails value={d} label="技術資料：文件索引與中繼資料（JSON）" />
                  <form
                    key={d.metadata?.population_revision ?? 0}
                    onSubmit={(event) => {
                      event.preventDefault();
                      const form = new FormData(event.currentTarget);
                      void work(async () => {
                        await api("/documents/" + d.doc_id + "/population", {
                          population: String(form.get("population")),
                          reason: String(form.get("reason")),
                          expected_revision: d.metadata?.population_revision ?? 0,
                        });
                        setDocuments(await api("/documents"));
                        setNotice("族群標示已保存；請重新分析病例，舊執行紀錄維持原快照。");
                      });
                    }}
                  >
                    <label>
                      此文件適用族群
                      <select name="population" defaultValue={d.metadata?.population ?? "unspecified"}>
                        <option value="unspecified">尚未標示</option>
                        <option value="all">所有年齡</option>
                        <option value="adult">成人</option>
                        <option value="pediatric">兒童</option>
                        <option value="mixed">混合（待整理適用片段）</option>
                      </select>
                    </label>
                    <label>
                      本次變更的標示依據
                      <input name="reason" required maxLength={2000} placeholder="請填來源頁碼或適用範圍的核對依據" />
                    </label>
                    <button type="submit" disabled={busy}>儲存族群標示</button>
                  </form>
                  <a
                    href={"/api/documents/" + d.doc_id + "/source"}
                    target="_blank"
                    rel="noreferrer"
                  >
                    開啟原始文件
                  </a>
                  <button type="button" disabled={busy} onClick={() => {
                    if (!window.confirm(`確定刪除「${d.title}」（${d.document_version}）？\n原檔與檢索索引將刪除。歷史證據快照保留，但原始文件連結將失效。病例引用不會自動改成 WHO。`)) return;
                    void work(async () => {
                      const result = await api('/documents/' + encodeURIComponent(d.doc_id), undefined, 'DELETE');
                      setDocuments(current => current.filter(x => x.doc_id !== d.doc_id));
                      setSearch(null);
                      setNotice(result.message);
                      await refresh();
                    });
                  }}>刪除此文件</button>
                </details>
              ))}
            </section>
            <section className="panel">
              <h2>本地文件檢索</h2>
              <p>
                {config?.rag?.retrieval_method === "lexical"
                  ? "目前使用明確啟用的關鍵字檢索。"
                  : "將問題與文件片段轉為 embedding 向量，以語意相似度檢索。手動搜尋會建立缺少的向量；multi-agent 分析前請先重建向量索引，避免占用整合與複核時間。"}
              </p>
              <p className="muted">
                Embedding 模型：{config?.rag?.model || "尚未設定"}
              </p>
              <button
                disabled={busy}
                onClick={() =>
                  void work(async () => {
                    const path =
                      documentScope === "synthetic"
                        ? "/documents/reindex"
                        : "/documents/reindex?scope=" + documentScope;
                    const result = await api(path, {});
                    setNotice(
                      "向量索引：" +
                        result.status +
                        (result.warnings?.length
                          ? " · " + result.warnings.join("、")
                          : ""),
                    );
                    setConfig(await api("/config"));
                  })
                }
              >
                重建向量索引
              </button>
              <label>
                文件範圍
                <select
                  disabled={busy}
                  value={documentScope}
                  onChange={(e) => {
                    setDocumentScope(
                      e.target.value as "synthetic" | "reference",
                    );
                    setSearch(null);
                  }}
                >
                  <option value="synthetic">synthetic 測試文件</option>
                  <option value="reference">
                    reference 正式參考文件（例如 WHO）
                  </option>
                </select>
              </label>
              <p className="muted">
                這裡切換文件查詢範圍。病例分析使用該病例設定的證據範圍；來源病例使用
                reference。
              </p>
              <label>
                查詢
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <button
                disabled={busy || !query.trim()}
                onClick={() =>
                  void work(async () =>
                    setSearch(
                      await api(
                        "/documents/search?q=" +
                          encodeURIComponent(query) +
                          (documentScope === "synthetic"
                            ? ""
                            : "&scope=" + documentScope),
                      ),
                    ),
                  )
                }
              >
                檢索文件
              </button>
              {search ? (
                <>
                  <Status value={search.status} />
                  <p>檢索方式：{search.retrieval_method}</p>
                  <RetrievalWarnings warnings={search.warnings} />
                  {search.evidence?.map((e: any) => (
                    <article className="evidence" key={e.chunk_id}>
                      <strong>
                        {e.doc_id} · {e.chunk_id}
                      </strong>
                      <blockquote>{e.text}</blockquote>
                      {typeof e.score === "number" && (
                        <p>語意相似度：{e.score.toFixed(3)}（非可信度機率）</p>
                      )}
                      <p>
                        {e.location?.page
                          ? `PDF 第 ${e.location.page} 頁`
                          : "非 PDF 頁碼定位"}
                      </p>
                      <TechnicalDetails
                        value={e.location}
                        label="詳細引用位置"
                      />
                      <a
                        href={
                          "/api/documents/" +
                          e.doc_id +
                          "/source" +
                          (e.location?.page ? "#page=" + e.location.page : "")
                        }
                        target="_blank"
                        rel="noreferrer"
                      >
                        開啟原始文件
                      </a>
                    </article>
                  ))}
                </>
              ) : (
                <Empty>輸入查詢以查看實際文件片段。</Empty>
              )}
            </section>
          </div>
        )}
        {section === 5 && (
          <>
            <div className="grid two">
              <section className="panel">
                <SettingsOverview config={config} rules={rules} />
              </section>
              <section className="panel">
                <h2>四模式比較（Benchmark）</h2>
                <p>
                  已勾選 {benchmarkCaseIds.length} 個病例 × {benchmarkModes.length} 種模式，共 {benchmarkCaseIds.length * benchmarkModes.length} 筆結果。
                </p>
                <p className="muted">
                  獨立代理協作包含六個評估步驟，臨床及整合評估依藥物數量分批呼叫模型，必要時補答或補正引用。各模式的檢索與呼叫量不同；這是軟體流程比較。
                </p>
                <fieldset><legend>選擇比較病例</legend>{cases.map(c=><label className="check-label" key={c.case_id}><input type="checkbox" checked={benchmarkCaseIds.includes(c.case_id)} onChange={e=>setBenchmarkCaseIds(e.target.checked ? [...benchmarkCaseIds,c.case_id] : benchmarkCaseIds.filter(id=>id!==c.case_id))}/>{c.case_id}</label>)}</fieldset>
                <fieldset><legend>選擇比較模式</legend>{modes.map(m=><label className="check-label" key={m}><input type="checkbox" checked={benchmarkModes.includes(m)} onChange={e=>setBenchmarkModes(e.target.checked ? [...benchmarkModes,m] : benchmarkModes.filter(x=>x!==m))}/>{modeNames[m]}</label>)}</fieldset>
                <label>
                  Benchmark 模型
                  <select
                    aria-label="Benchmark 模型"
                    value={benchmarkProvider}
                    onChange={(e) => setBenchmarkProvider(e.target.value)}
                  >
                    <option value="unconfigured">未設定模型</option>
                    <option value="mock">Mock 離線測試</option>
                    <option value="live">外部模型（可能產生費用）</option>
                  </select>
                </label>
                {benchmarkProvider === "live" && (
                  <div className="alert">
                    將向已設定的模型傳送必要病例
                    欄位及片段。每個病例有三種模型模式，可能多次呼叫並產生費用。
                  </div>
                )}
                <button
                  className="primary"
                  disabled={busy || !benchmarkCaseIds.length || !benchmarkModes.length}
                  onClick={() =>
                    void work(async () => {
                      const b = await api("/benchmarks", {
                        case_ids: benchmarkCaseIds,
                        modes: benchmarkModes,
                        provider_kind: benchmarkProvider,
                        request_id: crypto.randomUUID(),
                      });
                      setBenchmark(b);
                      setBenchmarks(await api("/benchmarks"));
                    })
                  }
                >
                  執行所選比較
                </button>
                <h3>比較歷史（時間依本機時區）</h3>
                {benchmarks.map((b: any, i: number) => (
                  <button
                    className={
                      "runrow benchmark-history " +
                      (benchmark?.benchmark_id === b.benchmark_id
                        ? "selected"
                        : "")
                    }
                    aria-pressed={benchmark?.benchmark_id === b.benchmark_id}
                    disabled={busy}
                    key={b.benchmark_id}
                    onClick={() =>
                      void work(async () =>
                        setBenchmark(
                          await api("/benchmarks/" + b.benchmark_id),
                        ),
                      )
                    }
                  >
                    <span>
                      <strong>
                        {localTime(b.created_at)}
                        {i === 0 ? " · 最新" : ""}
                      </strong>
                      <small className="block">
                        {b.cases?.length ?? "?"} 個病例 ·{" "}
                        {b.modes?.length ?? "?"} 種模式 ·{" "}
                        {b.results?.length ?? b.summary?.total_cases ?? "?"}{" "}
                        筆結果 · {executionLabel(b)}
                      </small>
                      <small className="block">
                        {b.benchmark_id.slice(0, 8)} ·{" "}
                        {(b.modes || [])
                          .map((m: string) => modeNames[b.display_modes?.[m] || m] || m)
                          .join("／")}
                      </small>
                    </span>
                  </button>
                ))}
              </section>
            </div>
            {benchmark && (
              <section className="panel">
                <BenchmarkOverview
                  benchmark={benchmark}
                  onOpenRun={(r) =>
                    void work(async () => {
                      await chooseCase(r.case_id);
                      await chooseRun(r);
                      setSection(1);
                    })
                  }
                />
              </section>
            )}
          </>
        )}
        <footer>
          研究展示用／病例標示來源與模擬欄位／非臨床使用 ·
          不提供劑量、頻率、療程或正式醫囑
        </footer>
      </main>
    </div>
  );
}
