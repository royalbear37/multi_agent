import { pretty } from "./api";

export function evidenceOrigin(e: any): string {
  if (e.is_synthetic === true) return "合成測試文件（僅供流程展示）";
  if (e.is_synthetic === false) return "真實參考文件（適用性仍需核對）";
  return "文件來源類型未記錄";
}

export function RetrievalWarnings({ warnings = [] }: { warnings?: string[] }) {
  const technical = warnings.filter(w => w === 'long_text_split' || /^page_\d+_blank$/.test(w));
  const important = warnings.filter(w => !technical.includes(w));
  const label = (w: string) => {
    if (w === 'long_text_split') return '長文字已正常切段供檢索，不是錯誤。';
    const page = w.match(/^page_(\d+)_(blank|requires_ocr)$/);
    if (page) return page[2] === 'blank' ? `第 ${page[1]} 頁為空白頁，已略過。` : `第 ${page[1]} 頁未擷取到文字（舊紀錄可能包含空白頁；有影像內容才需 OCR）。`;
    return errorNames[w] || w;
  };
  return <>
    {!!important.length && <ul>{important.map(w => <li key={w}>{label(w)}</li>)}</ul>}
    {!!technical.length && <details><summary>文件解析細節（{technical.length} 項，不代表本次分析失敗）</summary><ul>{technical.map(w => <li key={w}>{label(w)}</li>)}</ul></details>}
  </>;
}

export function sourceExclusionReason(run: any, code: string, reason: string) {
  const source = run.nodes?.find((n: any) => n.node_id === 'ast')?.output?.source_report ?? run.case_snapshot?.ast_results ?? [];
  const row = source.find((x: any) => x.drug_code === code);
  if (row?.interpretation_basis === 'CLSI_2022_pheno' && !row.clsi_2022_phenotype && reason.includes('來源判讀缺漏')) {
    return reason.replace('來源判讀缺漏或無法識別；未自行推算', `原始報告為 ${row.source_phenotype || '未提供'}；規則採用的 CLSI 2022 衍生判讀未提供，不等於抗藥`).replace('；來源結果不是 S，不自動列入敏感選項', '；本次未列入候選');
  }
  return reason;
}

export function drugDisposition(run: any) {
  const ast = run.nodes?.find((n: any) => n.node_id === "ast")?.output;
  const source = ast?.source_report ?? run.case_snapshot?.ast_results ?? [];
  const codes: string[] = [...new Set<string>(source.map((a: any) => a.drug_code))];
  const evaluations = ast?.system_evaluations ?? [];
  const excluded = new Set<string>([
    ...evaluations.filter((e: any) => e.eligible === false).map((e: any) => e.drug_code),
    ...(run.safety_summary?.avoid ?? []).map((e: any) => e.drug_code),
  ]);
  const selected = new Set<string>((run.output?.candidates ?? []).map((e: any) => e.drug_code));
  const rows = codes.map((code) => {
    const evaluation = evaluations.find((e: any) => e.drug_code === code);
    const avoid = (run.output?.avoid ?? run.safety_summary?.avoid ?? []).find((e: any) => e.drug_code === code);
    if (excluded.has(code)) return { code, group: "excluded", label: "規則排除", reason: sourceExclusionReason(run, code, avoid?.reason ?? evaluation?.reason ?? "命中規則限制") };
    if (selected.has(code)) return { code, group: "selected", label: "列入最終候選", reason: "本次輸出已列入，待人工審閱" };
    if (evaluation?.eligible === true) return { code, group: "unselected", label: run.output ? "通過規則，未選入" : "通過規則，候選未發布", reason: run.output ? "未提供逐藥未選原因；不代表不適用" : "整份分析結果未發布，並非此藥品被排除；請查看執行錯誤與限制。" };
    return { code, group: "unknown", label: "核對狀態未記錄", reason: "此紀錄不足以確認是否通過規則" };
  });
  return { sourceCount: source.length, rows };
}

export function DrugOverview({ run }: { run: any }) {
  const { sourceCount, rows } = drugDisposition(run);
  const count = (group: string) => rows.filter((r) => r.group === group).length;
  const docs = (run.evidence_snapshots ?? []).filter((e: any, i: number, all: any[]) => all.findIndex((x) => x.doc_id === e.doc_id && x.document_version === e.document_version) === i);
  return <section className="panel">
    <h2>藥品數量與去向</h2>
    <p>來源 {sourceCount} 筆藥敏／{rows.length} 項藥品；規則排除 {count("excluded")} 項；{run.mode === "rule-only" ? "規則" : "模型"}選入 {count("selected")} 項；{run.output ? "其餘通過規則但未選入" : "通過規則但候選未發布"} {count("unselected")} 項；核對狀態未記錄 {count("unknown")} 項。</p>
    <p>來源筆數不是建議用藥數。通過規則僅表示符合目前來源判讀條件，不等於已取得臨床證據支持。</p>
    {!!count('unselected') && run.output && <p>本次未保存這些藥品與候選之間的逐藥比較或排序理由；不能據此認定未選藥品較差或不適用。</p>}
    {run.mode === "rag-only" && <p>此模式的藥敏核對由程式規則執行；生成模型收到病例摘要、測試藥品名稱與文件片段，未收到完整逐筆 AST。</p>}
    <details><summary>查看每項藥品去向</summary>
      <table><thead><tr><th>藥品</th><th>狀態</th><th>說明</th></tr></thead><tbody>
        {rows.map((r) => <tr key={r.code}><td>{r.code}</td><td>{r.label}</td><td>{r.reason}</td></tr>)}
      </tbody></table>
    </details>
    <h3>本次證據來源</h3>
    {docs.length ? <ul>{docs.map((e: any) => <li key={`${e.doc_id}:${e.document_version}`}>{e.document_title || e.title || e.doc_id}：{evidenceOrigin(e)}</li>)}</ul> : <p>沒有可用文件證據。</p>}
  </section>;
}

export function DemoSourceResult({ run }: { run: any }) {
  if (run.output?.candidates?.length) return null;
  const ast = run.nodes?.find((n: any) => n.node_id === 'ast')?.output;
  if (!ast?.system_evaluations?.length) return null;
  const { rows } = drugDisposition(run);
  const sourceOptions = rows.filter(r => r.group === 'unselected');
  return <section className="panel" aria-label="來源藥敏 demo 整理結果">
    <h2>來源藥敏整理結果（demo）</h2>
    <p>本次沒有可發布的最終候選，以下先顯示本機規則整理的來源資料。這不是模型推薦，也尚未完成逐藥證據核對。</p>
    <p>來源共 {rows.length} 項藥品；{sourceOptions.length} 項通過來源判讀規則；{rows.filter(r => r.group === 'excluded').length} 項被規則排除。</p>
    {sourceOptions.length ? <div className="tablewrap"><table aria-label="來源藥敏整理表">
      <thead><tr><th>藥品</th><th>來源規則核對</th><th>證據與適用性</th></tr></thead>
      <tbody>{sourceOptions.map(r => <tr key={r.code}><td>{r.code}</td><td>通過</td><td>尚待確認</td></tr>)}</tbody>
    </table></div> : <p>目前沒有通過來源判讀規則的項目。</p>}
    <p>每項排除原因、未知狀態及文件類型請見「藥品數量與去向」。本整理不開放當作模型候選接受審閱。</p>
  </section>;
}

export const modeNames: Record<string, string> = {
  "rule-only": "規則判斷",
  "rag-only": "文件檢索＋模型",
  "single-agent": "單次模型整合",
  "multi-agent": "多節點工作流",
  "multi-agent-v2": "獨立代理協作 v2（研究）",
};
export const statusNames: Record<string, string> = {
  completed: "步驟已執行",
  awaiting_review: "分析已完成，待人工審閱",
  ready_for_review: "可送審閱",
  needs_confirmation: "需補資料或確認",
  blocked: "已阻擋",
  not_configured: "尚未設定",
  failed: "失敗",
  partial: "部分完成",
  skipped: "已略過",
  pending: "等待中",
  running: "執行中",
  demo_only: "展示用途",
  ok: "查詢成功",
  no_results: "沒有符合的片段",
  no_documents: "此範圍沒有文件",
  indexed: "文件已解析",
  indexed_with_warnings: "已解析，部分內容需檢查",
  conflict: "文件版本衝突",
};
export function localTime(value: unknown): string {
  if (typeof value !== "string" || !Number.isFinite(Date.parse(value)))
    return "時間未記錄";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
export function executionLabel(value: any): string {
  if (
    value.mode === "rule-only" ||
    (value.modes?.length === 1 && value.modes[0] === "rule-only")
  )
    return "規則執行（不使用 LLM）";
  if (value.is_mock || value.provider_kind === "mock") return "MOCK 模擬";
  if (value.provider_kind === "live") return "選用已設定模型";
  if (value.provider_kind === "unconfigured") return "未啟用生成模型";
  return "模型方式未記錄";
}
export function TechnicalDetails({
  value,
  label = "技術資料（原始 JSON，供除錯）",
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <details className="technical">
      <summary>{label}</summary>
      <pre>{pretty(value)}</pre>
    </details>
  );
}
const fields: Record<string, string> = {
  "microbiology.organism": "菌種",
  "encounter.infection_site": "感染部位",
  "allergies.status": "過敏狀態",
  "renal.egfr": "腎功能 eGFR",
  policy_refs: "適用政策文件",
  ast_results: "藥敏報告",
  "ast_results.unverified_or_conflicting": "藥敏結果未通過展示規則核對",
  "ast_results[].standard_or_version": "藥敏標準或版本",
  "ast_results[].unit_or_comparator": "MIC 單位或比較符號",
  "ast_results.no_approved_drug": "沒有通過來源藥敏與限制檢查的選項",
  "evidence.version_conflict": "引用文件版本衝突",
  "demographics.age_for_evidence": "請補上病例年齡，以核對參考文件適用族群",
  "evidence.population_applicability": "沒有族群相符且已標示的參考片段，請確認文件範圍後重新分析",
  "resistance_context_ref.unconfigured": "抗藥性背景來源未設定",
};
const errorNames: Record<string, string> = {
  PREFLIGHT_WITHHELD: "前置資料或證據檢查未通過，未呼叫 Agent",
  AGENT_INPUT_INVALID: "Agent 輸入資料不符合契約",
  AGENT_SCHEMA_INVALID: "Agent 輸出格式、藥品或引用檢查未通過",
  AGENT_NEEDS_CONFIRMATION: "Agent 發現尚待確認的事項，請檢查資料後重新分析",
  AGENT_NO_SUPPORTED_CANDIDATES: "各 Agent 的結果尚未形成有依據的共同候選",
  AGENT_BUDGET_EXCEEDED: "已達本次呼叫次數或時間上限",
  AGENT_INPUT_TOO_LARGE: "Agent 輸入超過大小上限，未發送模型",
  AGENT_EXECUTION_FAILED: "Agent 執行失敗，後續步驟已停止",
  V2_FINAL_VALIDATION_FAILED: "整合結果未通過最終安全檢查",
  NON_SYNTHETIC_INPUT:
    "來源病例尚未啟用外送；請使用本機模型，或確認資料可外送後更新病例設定",
  NON_SYNTHETIC_EVIDENCE: "參考文件片段尚未允許外送；請確認病例的資料與文件片段外送設定，或使用本機模型",
  duplicate_candidate: "候選清單有重複藥物，請保留一筆",
  duplicate_avoid: "避免清單有重複藥物，請保留一筆",
  candidate_avoid_overlap: "同一藥物同時出現在候選與避免清單",
  CANDIDATE_AVOID_OVERLAP: "同一藥物同時出現在候選與避免清單",
  UNALLOWED_DRUG: "模型輸出包含允許清單以外的藥品代碼",
  drug_not_allowed: "候選藥品未符合此病例的允許清單",
  OUTPUT_CONTENT_FORBIDDEN: "模型輸出包含目前不允許的內容，需檢查原始錯誤",
  OUTPUT_SCHEMA_INVALID: "模型輸出未通過格式、藥品或引用檢核",
  evidence_ref_required: "候選缺少必要文件引用",
  MODEL_NOT_CONFIGURED: "生成模型尚未設定",
  EVIDENCE_SEARCH_FAILED: "文件檢索失敗",
  embedding_failed: "向量檢索失敗",
  embedding_unavailable: "無法取得 embedding 向量，請檢查 Ollama 與模型",
};

export function withheldSummary(run: any): string {
  const missing = Array.isArray(run?.missing_fields) ? run.missing_fields : [];
  if (missing.length) {
    const detail = missing
      .map((value: unknown) => fields[String(value)] || String(value))
      .join("；");
    return `未產生候選：${detail}。前置安全檢查未通過，因此 Agent 尚未呼叫。`;
  }
  const errors = Array.isArray(run?.errors) ? run.errors : [];
  const firstCode = errors.map((value: any) => value?.code).find(Boolean);
  if (firstCode) {
    return `未產生候選：${errorNames[String(firstCode)] || String(firstCode)}。`;
  }
  return "沒有可發布候選。請查看安全閘門、資料缺漏或模型設定。";
}
function items(values: any[] | undefined, labels: Record<string, string> = {}) {
  return values?.length ? (
    <ul className="readable-list">
      {values.map((v, i) => (
        <li key={i}>{labels[String(v)] || String(v)}</li>
      ))}
    </ul>
  ) : (
    <p className="muted">沒有記錄</p>
  );
}
export function RunIssues({ run }: { run: any }) {
  const limitations =
    run.safety_summary?.limitations ?? run.output?.limitations ?? [];
  const confirmations = (run.nodes ?? []).filter((n: any) => n.agent_id && n.status === 'needs_confirmation');
  const errors = (run.errors ?? []).filter((e: any) => e.code !== 'AGENT_NEEDS_CONFIRMATION' || !confirmations.some((n: any) => n.node_id === e.node_id));
  return (
    <div>
      {run.nodes?.some((n: any) => n.agent_id && n.status === "needs_confirmation") && <p>{run.output ? "寬鬆 demo：Agent 的待確認事項已保留為限制，本次候選僅供展示與人工核對。" : "Agent 有待確認事項，請查看本次錯誤與限制。"} 額外病史或影像未知不需要補造資料。</p>}
      <h3>需要補充或確認</h3>
      {!!run.missing_fields?.length && items(run.missing_fields, fields)}
      {confirmations.map((n: any) => <section key={n.node_id}>
        <h4>{steps[n.node_id]?.[0] || n.node_id}</h4>
        {n.content_withheld ? <p>此步驟未通過檢核，內容未公開；請在「證據與流程」查看錯誤原因。</p> : <>
          {!!n.output?.missing_fields?.length && items(n.output.missing_fields, fields)}
          {!!n.output?.limitations?.length && items(n.output.limitations)}
          {!n.output?.missing_fields?.length && !n.output?.limitations?.length && <p>此 Agent 標示需確認，但未提供具體事項；請核對其發現，勿視為已確認。</p>}
        </>}
      </section>)}
      {!run.missing_fields?.length && !confirmations.length && <p>本次未列出待補欄位或 Agent 待確認事項。</p>}
      <h3>限制與提醒</h3>
      {limitations.length ? items(limitations) : <p>未列出額外限制；Agent 待確認事項請見上方。</p>}
      {!!errors.length && (
        <>
          <h3>執行／輸出檢核問題</h3>
          <ul className="readable-list">
            {errors.map((e: any, i: number) => (
              <li key={i}>
                {errorNames[e.code] || e.code || "未分類錯誤"}
                {!!e.validation_errors?.length && items(e.validation_errors, errorNames)}
              </li>
            ))}
          </ul>
        </>
      )}
      <TechnicalDetails
        value={{
          missing_fields: run.missing_fields,
          limitations,
          errors: run.errors,
        }}
      />
    </div>
  );
}
const steps: Record<string, [string, string]> = {
  case_agent: ["病例整理 Agent", "獨立整理病例資訊與缺漏，提供後續 Agent 使用。"],
  ast_agent: ["藥敏分析 Agent", "依病例整理結果核對來源藥敏；保留原報告的判讀依據。"],
  evidence_agent: ["證據核對 Agent", "核對檢索片段與病例的適用性，列出支持依據及待確認問題。"],
  clinical_agent: ["臨床背景 Agent", "核對已提供的過敏、腎功能與用藥背景，整理限制與不確定事項。"],
  synthesis_agent: ["結果整合 Agent", "接收四個 Agent 的結構化結果，整合後送交確定性安全檢查。"],
  case_completeness: [
    "病例整理與缺漏檢查",
    "整理菌種、感染部位、腎功能與過敏資料，檢查分析所需欄位。",
  ],
  ast: [
    "藥敏資料核對",
    "保留原始報告與指定來源判讀，核對衝突、最終報告及同名過敏；不重新計算 MIC 界值。",
  ],
  resistance_context: [
    "抗藥性背景整理",
    "讀取病例指定的抗藥性背景，供解釋參考；群體統計不代表個別病人的藥敏結果。",
  ],
  rapid_identification: [
    "快速菌種鑑定資料",
    "整理病例中的快速鑑定結果與來源，沒有直接連線到檢驗儀器。",
  ],
  evidence_retrieval: [
    "文件證據檢索",
    "依菌種、感染部位與政策範圍搜尋病例指定的文件，保存本次引用片段。",
  ],
  safety_gate: [
    "安全條件檢查",
    "綜合缺漏、規則與文件證據，判斷是否可提供候選供人工審閱。",
  ],
  candidate_presentation: [
    "候選結果整理與檢核",
    "依分析模式整理候選，再檢查輸出格式、允許藥品及引用；未通過時保留原因。",
  ],
  human_review: [
    "等待人工審閱",
    "由使用者接受、修改或拒絕並記錄理由。這是執行當下的快照，後續決定請看人工審閱頁。",
  ],
};
export function WorkflowStep({
  node: n,
  index,
  run,
}: {
  node: any;
  index: number;
  run: any;
}) {
  const o = n.output || {},
    [title, description] = steps[n.node_id] || [
      n.node_id || "未知步驟",
      "此步驟尚無摘要說明，請查看詳細資料。",
    ];
  let result;
  switch (n.node_id) {
    case "case_completeness":
      result = (
        <>
          <p>
            感染部位：{o.summary?.infection_site || "未提供"} · 菌種：
            {o.summary?.organism || "未提供"}
          </p>
          <p>來源藥敏：{o.summary?.ast_count ?? "未記錄"} 筆</p>
          <h4>缺漏或待確認項目</h4>
          {o.missing_fields?.length ? (
            items(o.missing_fields, fields)
          ) : (
            <p>此步驟未列出缺漏；仍需通過後續檢核。</p>
          )}
        </>
      );
      break;
    case "ast":
      result = (
        <>
          <p>
            來源報告 {o.source_report?.length ?? 0} 筆；已處理{" "}
            {o.system_evaluations?.filter((x: any) => x.status === "evaluated")
              .length ?? 0}{" "}
            筆。
          </p>
          {o.system_evaluations?.map((x: any, i: number) => (
            <p key={i}>
              {x.drug_code}：來源 {x.source_reported_sir || "未提供"} →{" "}
              {sourceExclusionReason(run, x.drug_code, x.reason ||
                (x.status === "evaluated"
                  ? "歷史測試規則核對完成"
                  : "需要人工核對"))}
            </p>
          ))}
          {items(o.warnings)}
        </>
      );
      break;
    case "resistance_context":
      result = (
        <>
          <p>
            找到 {Object.keys(o.records || {}).length} 筆背景紀錄；
            {n.status === "skipped"
              ? "此病例未指定背景來源。"
              : "請依來源適用範圍解讀。"}
          </p>
          {items(Object.keys(o.records || {}))}
        </>
      );
      break;
    case "rapid_identification":
      result =
        n.status === "skipped" ? (
          <p>{o.reason || "未提供快速鑑定資料。"}</p>
        ) : (
          <>
            <p>方法：{o.method || "未記錄"}</p>
            <p>結果：{o.result || "未記錄"}</p>
            <p>觀察時間：{localTime(o.observed_at)}</p>
          </>
        );
      break;
    case "evidence_retrieval":
      result = (
        <>
          <p>
            取得 {o.count ?? 0} 個片段；
            {statusNames[o.status] || o.status || "狀態未記錄"}。
          </p>
          <p>
            檢索方式：
            {o.retrieval_method === "lexical"
              ? "關鍵字"
              : o.retrieval_method === "ollama_embeddings"
                ? "語意向量"
                : "未記錄"}
            。取得片段不代表內容已支持結論。
          </p>
          <RetrievalWarnings warnings={o.warnings} />
          {o.population_filter && (
            <p>
              族群篩選：標示相符 {o.population_filter.matched ?? 0} 個、
              不符 {o.population_filter.mismatched ?? 0} 個、
              尚待確認 {o.population_filter.unverified ?? 0} 個。
              標示相符仍需核對片段是否支持結論。
            </p>
          )}
        </>
      );
      break;
    case "safety_gate":
      result = (
        <>
          <p className="step-outcome">
            {statusNames[o.gate_status] || "檢查結果未記錄"}
          </p>
          {items(o.limitations)}
        </>
      );
      break;
    case "candidate_presentation":
      result = (
        <>
          <p className="step-outcome">
            {o.published === true
              ? "已提供展示候選，仍需人工審閱。"
              : "尚未提供候選，請查看安全條件與錯誤原因。"}
          </p>
          <p>
            {executionLabel(run)} · 輸出檢核：
            {o.schema_valid === true
              ? "通過（不代表臨床正確）"
              : o.attempted
                ? "未通過或未取得有效輸出"
                : "未執行"}
          </p>
          {items(run.errors?.map((e: any) => errorNames[e.code] || e.code))}
        </>
      );
      break;
    case "human_review":
      result = (
        <p>
          執行時狀態：{statusNames[n.status] || n.status}
          。請到「人工審閱」頁查看目前已保存的決定。
        </p>
      );
      break;
    default:
      result = n.agent_id ? <p>以下是此 Agent 的回覆摘要；引用上游內容不代表另有獨立臨床驗證。</p> : <p>請展開詳細資料。</p>;
  }
  return (
    <details className="node">
      <summary>
        <span>
          {String(index + 1).padStart(2, "0")}　{title}
        </span>
        <span className={"badge " + n.status}>
          {statusNames[n.status] || n.status}
        </span>
      </summary>
      <div className="step-body">
        <p className="muted">{description}</p>
        {result}
        {!!n.demo_adjustments?.length && <p>Demo 容錯已套用：格式已整理，無法核對的項目或說明已省略；未補造藥敏或引用。</p>}
        {n.agent_id && (
          <section aria-label="Agent 執行紀錄">
            <p>模型：{n.model || "未呼叫"} · {n.is_mock ? "MOCK 訊息測試" : "模型執行"}</p>
            <p>呼叫 {n.attempts?.length ?? 0} 次 · Token：{n.usage?.total_tokens ?? "未提供"}</p>
            <p>接收上游：{n.depends_on?.map((id: string) => steps[id]?.[0] || id).join("、") || "原始病例"}</p>
            {!!n.validation_issues?.length && <TechnicalDetails value={n.validation_issues} label="格式檢核原因" />}
            {n.content_withheld ? <p>本次未通過完整檢核，中間內容已隔離；可查看狀態與錯誤。</p> : <>
              <h4>缺少的資料</h4>
              {o.missing_fields?.length ? items(o.missing_fields, fields) : <p>此 Agent 未列出具體缺漏欄位；「需確認」也可能是資料衝突或分析限制。</p>}
              <h4>需要確認的事項與限制（Agent 回覆）</h4>
              {o.limitations?.length ? items(o.limitations) : <p>未提供具體限制說明。</p>}
              <h4>核對發現（Agent 回覆，待人工確認）</h4>
              {o.findings?.length ? <ul>{o.findings.map((f: any, i: number) => <li key={i}>{f.statement}
                {!!f.evidence_refs?.length && <small>　引用：{f.evidence_refs.join('、')}</small>}
              </li>)}</ul> : <p>未提供核對發現。</p>}
              {!!o.support?.length && <><h4>逐藥證據支持</h4><ul>{o.support.map((s: any) => <li key={s.drug_code}><strong>{s.drug_code}</strong>：{s.explanation}<br /><small>引用：{s.evidence_refs?.join('、')}</small></li>)}</ul></>}
              <TechnicalDetails value={n.input} label="技術資料：Agent 輸入（JSON）" />
              <TechnicalDetails value={n.output} label="技術資料：Agent 輸出（JSON）" />
            </>}
            <TechnicalDetails value={n.attempts} label="模型呼叫與重試紀錄" />
            {!!n.errors?.length && <p>錯誤：{n.errors.map((e: any) => errorNames[e.code] || e.code).join("、")}</p>}
            {n.skip_reason && <p>未執行原因：{errorNames[n.skip_reason] || n.skip_reason}</p>}
          </section>
        )}
        <p className="muted">
          耗時{" "}
          {typeof n.elapsed_ms === "number"
            ? `${n.elapsed_ms.toFixed(0)} ms`
            : "未記錄"}{" "}
          · 規則引用 {n.rule_refs?.length ?? 0} · 文件片段引用{" "}
          {n.evidence_refs?.length ?? 0}
        </p>
        <TechnicalDetails value={n} />
      </div>
    </details>
  );
}
export function SettingsOverview({
  config,
  rules,
}: {
  config: any;
  rules: any;
}) {
  if (!config) return <p>尚未取得設定，請確認後端連線。</p>;
  const p = config.provider || {},
    rag = config.rag || {};
  return (
    <>
      <h2>模型與文件檢索設定</h2>
      <p>這裡顯示後端目前讀到的設定；實際執行方式由分析或比較時的選項決定。</p>
      <div className="setting-card">
        <h3>生成模型 · 整理分析說明</h3>
        <p>
          {p.kind === "mock" || p.is_mock
            ? "目前預設為模擬輸出"
            : p.configured
              ? "設定已填齊，連線與輸出仍須實際執行驗證"
              : "尚未啟用或設定未齊全"}
        </p>
        <p>模型名稱：{p.model || "未提供"}</p>
        <small>設定存在不代表 API 已連線成功。規則模式不需要生成模型。</small>
      </div>
      <div className="setting-card">
        <h3>文件檢索 · 找出參考片段</h3>
        <p>
          {rag.retrieval_mode === "lexical" ||
          rag.retrieval_method === "lexical"
            ? "關鍵字搜尋"
            : rag.retrieval_mode === "embedding" ||
                rag.retrieval_method === "ollama_embeddings"
              ? `語意向量搜尋 · ${rag.model || rag.embedding_model || "模型未記錄"}`
              : "檢索方式未記錄"}
        </p>
        {rag.index && (
          <p>
            參考文件向量：{rag.index.embedded_chunks ?? "—"}／
            {rag.index.chunks ?? "—"} 個片段（
            {rag.retrieval_method === "lexical"
              ? "關鍵字模式不需要向量"
              : `待建立 ${rag.index.missing_chunks ?? "—"} 個`}
            ）。此數字對應 WHO 等參考文件範圍。
          </p>
        )}
        <p>
          正式參考文件：
          {config.reference_status || config.who_status || "狀態未記錄"}
        </p>
        <small>
          來源病例使用參考文件，並保存引用快照。匯入文件不代表已完成向量索引。
        </small>
      </div>
      <div className="setting-card">
        <h3>病例規則</h3>
        <p>
          {rules?.config?.ast_mode === "reported_phenotype"
            ? "使用來源藥敏判讀、衝突與同名過敏檢查；不重新計算臨床界值。"
            : "歷史測試規則；尚未啟用正式臨床判讀。"}
        </p>
        <p>
          來源字典：{rules?.config?.organisms?.length ?? 0} 種菌種名稱、
          {rules?.config?.allowed_drugs?.length ?? 0}{" "}
          種測試藥品名稱。收錄不代表治療適用。
        </p>
        <small>規則版本：{rules?.version || "未記錄"}</small>
      </div>
      <p className="muted">API key 在後端 .env 設定；此頁不會呼叫付費模型。</p>
      <TechnicalDetails value={config} label="詳細設定資料（JSON）" />
      <TechnicalDetails value={rules} label="詳細規則與版本（JSON）" />
    </>
  );
}
type Metric = {
  value?: number | null;
  numerator?: number;
  denominator?: number;
  status?: string;
};
export function metricText(m?: Metric): string {
  if (!m || m.value == null || !m.denominator)
    return m?.status === "not_evaluated" ? "尚未評估" : "不適用／無可計算資料";
  return `${(m.value * 100).toFixed(1)}%（${m.numerator ?? "?"}／${m.denominator}）`;
}
const metrics: [string, string, string][] = [
  [
    "completion",
    "可供審閱輸出率",
    "安全狀態為可送審閱且有輸出的執行比例；不代表人工已核准。",
  ],
  [
    "safety_withholding",
    "輸出暫緩率",
    "需要補資料／確認或遭阻擋，尚未提供候選的比例。",
  ],
  [
    "blocked_ratio",
    "整體阻擋率",
    "包含安全規則阻擋與模型輸出檢核失敗；不全是正確安全攔截。",
  ],
  [
    "failed_ratio",
    "整體失敗狀態比例",
    "只計整體狀態 failed。模型錯誤可能列入 blocked，0% 不代表沒有錯誤。",
  ],
  [
    "not_configured_ratio",
    "部分完成／未設定比例",
    "整體狀態 partial 或 not_configured 的比例。",
  ],
  [
    "schema_validity",
    "輸出檢核通過率",
    "曾嘗試產生輸出的執行中，通過格式及相關檢核的比例；不代表內容正確。",
  ],
  [
    "whitelist_violation_rate",
    "白名單違規錯誤數／輸出嘗試數",
    "依錯誤紀錄計算，可能涉及藥品或引用；並非臨床錯誤率，多筆錯誤可能超過 100%。",
  ],
  [
    "rule_test_pass_rate",
    "標註規則符合率",
    "規則結果與測試預期相符的比例；需要適用的預期標註。",
  ],
  ["missing_precision", "缺漏提示精確率", "指出的缺漏中，符合測試標註的比例。"],
  ["missing_recall", "缺漏偵測召回率", "標註缺漏中，被系統找到的比例。"],
  [
    "expected_safety_block_recall",
    "預期阻擋召回率",
    "標註應阻擋的執行中，實際被阻擋的比例。",
  ],
  [
    "unnecessary_block_rate",
    "非預期阻擋率",
    "標註不應阻擋的執行中，卻遭阻擋的比例。",
  ],
  [
    "citation_id_validity",
    "引用編號可追溯率",
    "引用編號能在本次證據快照找到的比例。",
  ],
  [
    "citation_location_validity",
    "引用位置紀錄率",
    "可追溯引用中有位置資訊的比例；未核對頁碼內容是否正確。",
  ],
  [
    "citation_support_conclusion",
    "引用是否支持結論",
    "目前未進行內容支持性評估。",
  ],
  ["appropriateness", "臨床適當性", "目前未評估，不能由軟體流程通過率推定。"],
  ["expert_agreement", "專家一致率", "目前未評估，需獨立專家標註。"],
  ["clinical_utility", "臨床實用性", "目前未評估，需臨床使用者驗證。"],
];
export function BenchmarkOverview({
  benchmark: b,
  onOpenRun,
}: {
  benchmark: any;
  onOpenRun: (r: any) => void;
}) {
  const s = b.summary || {},
    results = b.results || [],
    byMode = s.by_mode || {};
  const caseCount = new Set(
    b.cases || results.map((r: any) => r.case_id).filter(Boolean),
  ).size;
  const selectedModes: string[] = b.modes || Object.keys(byMode);
  const errors = new Map<string, number>();
  for (const r of results)
    for (const e of r.errors || []) {
      const code = typeof e === "string" ? e : e.code || "UNKNOWN";
      errors.set(code, (errors.get(code) || 0) + 1);
    }
  return (
    <>
      <h2>Benchmark 結果 · {executionLabel(b)}</h2>
      <p>
        {localTime(b.created_at)}（本機時間） · {caseCount} 個不同病例 ×{" "}
        {selectedModes.length} 種模式 · {s.total_cases ?? results.length}{" "}
        筆執行結果
      </p>
      <p className="muted">記錄編號：{b.benchmark_id}</p>
      {selectedModes.length < 4 && (
        <div className="alert">
          這筆紀錄只包含 {selectedModes.length} 種模式，並非完整四模式比較。
        </div>
      )}
      <p>
        比較各模式能否產生可供審閱的輸出，以及缺漏、阻擋與引用情形。展示病例包含刻意設計的失敗情境，不能用總通過率判定哪個模式臨床較好。
      </p>
      <div className="metric-grid">
        {[metrics[0], metrics[1], metrics[2], metrics[5]].map(
          ([key, label, description]) => (
            <article className="metric-card" key={key}>
              <h3>{label}</h3>
              <strong>{metricText(s[key])}</strong>
              <p>{description}</p>
            </article>
          ),
        )}
      </div>
      <h3>按模式比較</h3>
      {!!Object.keys(s.by_agent || {}).length && <details>
        <summary>v2 各 Agent 用量與執行統計</summary>
        <p>MOCK 沒有真實 Token 用量；失敗呼叫可能沒有回傳用量，已知合計不代表完整帳單。</p>
        <div className="tablewrap"><table>
          <thead><tr><th>Agent</th><th>呼叫次數</th><th>失敗／略過</th><th>已知 Token</th><th>耗時</th></tr></thead>
          <tbody>{Object.entries(s.by_agent).map(([id, stat]: [string, any]) => <tr key={id}>
            <th>{steps[id]?.[0] || id}</th><td>{stat.calls}</td><td>{stat.failed}／{stat.skipped}</td>
            <td>{stat.known_total_tokens ?? "未提供"}{!stat.usage_complete && "（未完整）"}</td><td>{stat.elapsed_ms} ms</td>
          </tr>)}</tbody>
        </table></div>
      </details>}
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>模式</th>
              <th>執行筆數</th>
              <th>可供審閱輸出</th>
              <th>暫緩輸出</th>
              <th>整體阻擋</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(byMode).map(([mode, value]: [string, any]) => (
              <tr key={mode}>
                <th>
                  {modeNames[mode] || mode}
                  <small className="block">{mode}</small>
                </th>
                <td>{value.total_cases}</td>
                <td>{metricText(value.completion)}</td>
                <td>{metricText(value.safety_withholding)}</td>
                <td>{metricText(value.blocked_ratio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>執行與檢核問題</h3>
      {errors.size ? (
        <ul className="readable-list">
          {Array.from(errors).map(([code, count]) => (
            <li key={code}>
              {errorNames[code] || code}：{count} 筆錯誤{" "}
              <small>（{code}）</small>
            </li>
          ))}
        </ul>
      ) : (
        <p>這批結果沒有記錄錯誤；仍須查看暫緩原因與安全條件。</p>
      )}
      <details>
        <summary>所有指標與計算說明</summary>
        <p>比例後面的括號是分子／分母；沒有分母時顯示不適用，不當成 0 分。</p>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>指標</th>
                <th>結果</th>
                <th>如何解讀</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map(([key, label, description]) => (
                <tr key={key}>
                  <th>{label}</th>
                  <td>{metricText(s[key])}</td>
                  <td>{description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details>
        <summary>逐次執行結果（{results.length} 筆）</summary>
        <p>「等待人工處理」可能仍需補資料；請同時查看安全條件。</p>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>病例</th>
                <th>模式</th>
                <th>整體狀態</th>
                <th>安全條件</th>
                <th>耗時</th>
                <th>查看</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r: any, i: number) => (
                <tr key={r.run_id || i}>
                  <td>{r.case_id}</td>
                  <td>{modeNames[r.mode] || r.mode}</td>
                  <td>{statusNames[r.status] || r.status}</td>
                  <td>
                    {statusNames[r.gate_status] || r.gate_status || "未記錄"}
                  </td>
                  <td>
                    {typeof r.elapsed_ms === "number"
                      ? `${(r.elapsed_ms / 1000).toFixed(2)} 秒`
                      : "未記錄"}
                  </td>
                  <td>
                    <button onClick={() => onOpenRun(r)}>查看分析</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <TechnicalDetails value={s} label="詳細摘要資料（原始 JSON）" />
      <a
        className="button"
        href={"/api/benchmarks/" + b.benchmark_id + "/export"}
        download
      >
        匯出逐案例結果與摘要
      </a>
    </>
  );
}
