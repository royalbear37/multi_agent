import { pretty } from "./api";

export const modeNames: Record<string, string> = {
  "rule-only": "規則判斷",
  "rag-only": "文件檢索＋模型",
  "single-agent": "單次模型整合",
  "multi-agent": "多節點工作流",
};
export const statusNames: Record<string, string> = {
  completed: "步驟已執行",
  awaiting_review: "等待人工處理",
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
  label = "詳細資料（原始 JSON）",
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
  "resistance_context_ref.unconfigured": "抗藥性背景來源未設定",
};
const errorNames: Record<string, string> = {
  NON_SYNTHETIC_INPUT:
    "來源病例尚未啟用外送；請使用本機模型，或確認資料可外送後更新病例設定",
  duplicate_candidate: "候選清單有重複藥物，請保留一筆",
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
  return (
    <div>
      <h3>需要補充或確認</h3>
      {items(run.missing_fields, fields)}
      <h3>限制與提醒</h3>
      {items(limitations)}
      {!!run.errors?.length && (
        <>
          <h3>執行／輸出檢核問題</h3>
          <ul className="readable-list">
            {run.errors.map((e: any, i: number) => (
              <li key={i}>
                {errorNames[e.code] || e.code || "未分類錯誤"}
                {items(e.validation_errors, errorNames)}
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
              {x.reason ||
                (x.status === "evaluated"
                  ? "歷史測試規則核對完成"
                  : "需要人工核對")}
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
          {items(o.warnings, errorNames)}
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
      result = <p>請展開詳細資料。</p>;
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
        <p className="muted">
          耗時{" "}
          {typeof n.elapsed_ms === "number"
            ? `${n.elapsed_ms.toFixed(0)} ms`
            : "未記錄"}{" "}
          · 規則引用 {n.rule_refs?.length ?? 0} · 文件引用{" "}
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
      {selectedModes.length !== 4 && (
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
