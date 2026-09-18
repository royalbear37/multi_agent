import { useEffect, useState } from "react";
import { api, pretty } from "./api";
import type { components } from "./api.generated";
import { ReviewEditor, reviewOutput } from "./ReviewEditor";
import {
  BenchmarkOverview,
  SettingsOverview,
  WorkflowStep,
  RunIssues,
  TechnicalDetails,
  executionLabel,
  localTime,
  modeNames,
  statusNames,
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
const modes = ["rule-only", "rag-only", "single-agent", "multi-agent", "multi-agent-v2"];
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
  const [section, setSection] = useState(0),
    [cases, setCases] = useState<CaseRecord[]>([]),
    [selected, setSelected] = useState<CaseRecord | null>(null);
  const [config, setConfig] = useState<any>(null),
    [run, setRun] = useState<any>(null),
    [runs, setRuns] = useState<any[]>([]),
    [reviews, setReviews] = useState<any[]>([]);
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
    [action, setAction] = useState("accept"),
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
    [synthetic, setSynthetic] = useState(true);
  const [benchmark, setBenchmark] = useState<any>(null),
    [benchmarks, setBenchmarks] = useState<any[]>([]),
    [rules, setRules] = useState<any>(null);
  const [benchmarkProvider, setBenchmarkProvider] = useState("unconfigured");
  const [includeV2, setIncludeV2] = useState(false);
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
                    <p>{c.encounter?.context}</p>
                    {!!c.provenance?.simulated_fields?.length && (
                      <p>
                        模擬欄位：{c.provenance.simulated_fields.join("、")}
                        。菌種與藥敏來源請見下表。
                      </p>
                    )}
                    <p>
                      證據範圍：
                      {c.evidence_scope === "reference"
                        ? "WHO 等參考文件"
                        : "測試文件"}
                    </p>
                    {!c.is_synthetic && (
                      <label className="check-label">
                        <input
                          type="checkbox"
                          checked={c.external_model_allowed ?? false}
                          disabled={busy}
                          onChange={(e) => {
                            const allowed = e.target.checked;
                            void work(async () => {
                              await api("/cases/" + c.case_id + "/revisions", {
                                payload: {
                                  ...c,
                                  external_model_allowed: allowed,
                                },
                              });
                              await chooseCase(c.case_id);
                            });
                          }}
                        />
                        允許此病例的必要分析欄位送至外部模型（請先確認來源資料使用條款允許；本機
                        Ollama 不需開啟）
                      </label>
                    )}
                    <div className="facts">
                      <div>
                        <small>病例 ID</small>
                        <strong>{c.case_id}</strong>
                      </div>
                      <div>
                        <small>過敏狀態</small>
                        <strong>{c.allergies?.status || "unknown"}</strong>
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
                <p>規則限制通過後，結果仍需人工審閱。</p>
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
                {mode === "multi-agent-v2" && <p>v2 每病例通常有 5 次獨立模型呼叫；遇缺漏或失敗會提早停止。可在「證據與流程」查看各 Agent 的輸入、輸出與用量。</p>}
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
                        {modeNames[r.mode] || r.mode}{" "}
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
                    {modeNames[run.mode] || run.mode} · {executionLabel(run)} ·{" "}
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
              <div className="grid two">
                <section className="panel">
                  <h2>可供審閱的藥敏選項</h2>
                  {run.output?.candidates?.length ? (
                    run.output.candidates.map((x: any) => (
                      <article className="candidate" key={x.drug_code}>
                        <h3>
                          {x.drug_code} <Status value="demo_only" />
                        </h3>
                        <p>{x.reason}</p>
                        <small>
                          規則：{x.rule_refs?.join(", ")}
                          <br />
                          引用：{x.evidence_refs?.join(", ")}
                        </small>
                      </article>
                    ))
                  ) : (
                    <Empty>
                      沒有可發布候選。請查看安全閘門、資料缺漏或模型設定。
                    </Empty>
                  )}
                </section>
                <section className="panel">
                  <h2>來源排除／待確認項目</h2>
                  {(run.safety_summary?.avoid ?? run.output?.avoid)?.map(
                    (x: any, i: number) => (
                      <article key={i}>
                        <h3>{x.drug_code}</h3>
                        <p>{x.reason}</p>
                      </article>
                    ),
                  )}
                  <RunIssues run={run} />
                </section>
              </div>
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
            <div className="grid two">
              <section className="panel">
                <h2>分析步驟與結果</h2>
                <p>
                  展開步驟查看做了什麼與得到的結果；「步驟已執行」不代表資料或候選已通過檢核。
                </p>
                {run.nodes?.map((n: any, i: number) => (
                  <WorkflowStep key={i} node={n} index={i} run={run} />
                ))}
                <details>
                  <summary>規則命中與版本</summary>
                  <Json
                    value={{
                      versions: run.versions,
                      evaluations: run.rule_evaluations,
                    }}
                  />
                </details>
              </section>
              <section className="panel">
                <h2>本次使用的文件片段</h2>
                <p className="muted">
                  保留分析當時的版本與內容，供回頭核對依據。
                </p>
                {run.evidence_snapshots?.length ? (
                  run.evidence_snapshots.map((e: any, i: number) => (
                    <article className="evidence" key={i}>
                      <h3>{e.document_title || e.title || e.doc_id}</h3>
                      <small>
                        {e.chunk_id} · v{e.document_version}
                      </small>
                      <blockquote>{e.text}</blockquote>
                      <Json value={e.location} />
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
                  ))
                ) : (
                  <Empty>此執行沒有可用文件證據。</Empty>
                )}
              </section>
            </div>
          ) : (
            <Empty>選擇執行紀錄後查看流程與引用。</Empty>
          ))}
        {section === 3 &&
          (run ? (
            <div className="grid two">
              <section className="panel">
                <h2>人工審閱</h2>
                <p>審閱者 demo-user · {role} · 僅展示角色</p>
                <Status value={run.gate_status} />
                <label>
                  決定
                  <select
                    aria-label="決定"
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                  >
                    <option value="accept">接受</option>
                    <option value="modify">修改</option>
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
                <button
                  className="primary"
                  disabled={
                    busy ||
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
                        {r.action} · {r.reviewer_id}
                      </strong>
                      <p>{r.reason}</p>
                      <small>{r.created_at}</small>
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
              {documents.map((d: any) => (
                <details key={d.doc_id}>
                  <summary>
                    {d.title} · v{d.document_version}{" "}
                    <Status value={d.processing_status} />
                  </summary>
                  <Json value={d} />
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
                      標示依據
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
                </details>
              ))}
            </section>
            <section className="panel">
              <h2>本地文件檢索</h2>
              <p>
                {config?.rag?.retrieval_method === "lexical"
                  ? "目前使用明確啟用的關鍵字檢索。"
                  : "將問題與文件片段轉為 embedding 向量，以語意相似度檢索。首次搜尋會建立缺少的向量。"}
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
                  <Json value={search.warnings} />
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
                <label><input type="checkbox" checked={includeV2} onChange={e => setIncludeV2(e.target.checked)} /> 加入獨立代理協作 v2（增加模型呼叫）</label>
                <p>
                  對全部已保存的 {cases.length} 個病例各執行四種模式，共{" "}
                  {cases.length * 4} 筆結果。不是只比較上方選取的病例。
                </p>
                <p className="muted">
                  規則判斷／文件檢索＋模型／單次模型整合／多節點工作流。後者是多節點整理加一次主要模型生成。這是軟體流程比較，臨床適當性尚未評估。
                </p>
                <label>
                  Benchmark 模型
                  <select
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
                  disabled={busy || !cases.length}
                  onClick={() =>
                    void work(async () => {
                      const b = await api("/benchmarks", {
                        case_ids: cases.map((c) => c.case_id),
                        modes: includeV2 ? modes : modes.filter(m => m !== "multi-agent-v2"),
                        provider_kind: benchmarkProvider,
                        request_id: crypto.randomUUID(),
                      });
                      setBenchmark(b);
                      setBenchmarks(await api("/benchmarks"));
                    })
                  }
                >
                  {includeV2 ? "執行五模式比較（含 v2）" : "執行四模式比較"}
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
                          .map((m: string) => modeNames[m] || m)
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
