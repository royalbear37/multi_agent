import { CandidateEvidence, EvidenceSourceNotice, evidenceLocation } from './ClinicalContext';
import { Fragment } from 'react';

const tierLabels:Record<string,string>={candidate:'完整核對候選',review_option:'有證據的待審閱選項',pending:'其他待確認',avoid:'不建議',not_selected:'未選入'};
const dimensions:Record<string,string>={infection:'感染適用性',ast:'藥敏',allergy:'過敏',renal:'腎功能',interactions:'交互作用'};
const blockerLabels:Record<string,string>={reported_avoid:'避用風險待釐清',model_output_incomplete:'模型回覆未完整',model_citation_missing:'模型漏選引用',retrieval_failed:'檢索未完成',retrieval_empty:'檢索未找到',input_omitted:'輸入片段被省略',case_data_missing:'病例缺資料',risk_unconfirmed:'風險尚未核對',citation_unsupported:'引用未支持',ast_unconfirmed:'藥敏尚未確認'};

const labels: Record<string,string> = {
  reviewable:'可供審閱', pending:'待確認', avoid:'不建議', not_selected:'未選入',
  supported:'有支持', unsupported:'未支持', uncertain:'待確認', unknown:'未知',
  susceptible:'敏感', intermediate:'中介', resistant:'抗藥', conflicting:'有衝突',
  no_identified_risk:'本次核對未發現風險', caution:'需注意',
  not_applicable:'不適用',
};
const titles: Record<string,string> = {
  case_agent:'病例整理 Agent', ast_agent:'藥敏與微生物 Agent', evidence_agent:'證據 Agent',
  clinical_agent:'臨床風險 Agent', synthesis_agent:'整合 Agent', evidence_audit:'引用獨立複核',
};
export function agentTitle(id:string) { return titles[id] || id || '未記錄來源 Agent'; }
export function AgentIssues({items=[],onOpenAgent,availableAgents=[]}:{items?:any[],onOpenAgent?:(id:string)=>void,availableAgents?:string[]}) {
  const grouped=new Map<string,{item:any,count:number}>();
  for (const item of items) {
    const key=JSON.stringify([item.agent_id,item.drug_code,item.field,item.impact,item.action,item.blocking]);
    const previous=grouped.get(key);
    if(previous) previous.count++; else grouped.set(key,{item,count:1});
  }
  const fieldNames:Record<string,string>={evidence_context:'文件片段未完整納入',allergy:'過敏',renal:'腎功能',interactions:'交互作用',drugs:'逐藥檢索範圍'};
  return items.length ? <table><thead><tr><th>來源步驟</th><th>需確認資料</th><th>影響</th><th>下一步</th></tr></thead><tbody>
    {[...grouped.values()].map(({item:x,count},i)=><tr key={i}><td>{agentTitle(x.agent_id)}{onOpenAgent && availableAgents.includes(x.agent_id) && <button onClick={()=>onOpenAgent(x.agent_id)}>查看此步驟</button>}{count>1 && <small>相同記錄 {count} 筆</small>}</td><td>{x.drug_code && `${x.drug_code} · `}{fieldNames[x.field] || factLabel(x.field || '未指定欄位')}</td><td>{x.impact}</td><td>{x.action}</td></tr>)}
  </tbody></table> : <p>此步驟未列出額外待確認事項。</p>;
}
function Quotes({quotes=[],run}:{quotes?:any[],run:any}) {
  return <>{quotes.map((q,i)=>{
    const source=run.evidence_snapshots?.find((e:any)=>e.chunk_id===q.chunk_id);
    return <details key={i}><summary>{source?.document_title || '引用原文'} · {evidenceLocation(source?.location)}</summary>
      <blockquote>{q.quote}</blockquote>{source?.source_url && <a href={source.source_url} target="_blank" rel="noreferrer">來源網站</a>}
      <EvidenceSourceNotice item={source} evidence={run.evidence_snapshots}/>
      <p>{source?.document_version} · {source?.jurisdiction || '適用地區未標示'}</p>
    </details>;
  })}</>;
}
const riskNames:Record<string,string>={allergy:'過敏',renal:'腎功能',interactions:'交互作用'};
function factLabel(path:string) {
  const labels:Record<string,string>={'allergies':'過敏紀錄','allergies.status':'過敏紀錄狀態',
    'renal':'腎功能資料','renal.egfr':'eGFR','renal.crcl':'CrCl','renal.creatinine':'肌酸酐',
    'medications':'完整用藥紀錄'};
  if (labels[path]) return labels[path];
  if(path.startsWith('allergies.items.')) return '個別過敏反應與確認紀錄';
  if(path.startsWith('medications.')) return '個別用藥與使用狀態';
  if(path.startsWith('ast_results.')) return `第 ${Number(path.split('.')[1])+1} 筆藥敏來源資料`;
  if(path==='medication_history_status') return '用藥清單完整性核對';
  return path;
}
function ASTSources({assessment}:{assessment:any}) {
  const fields:Record<string,string>={reported_sir:'報告類別',source_phenotype:'原始報告判讀',clsi_2022_phenotype:'CLSI 2022 衍生判讀'};
  return <>{assessment?.category_sources?.map((source:any,i:number)=><p key={i}>判讀來源：第 {Number(source.field.split('.')[1])+1} 筆 · {fields[source.field.split('.').at(-1)!] || '來源欄位'}：{source.value}</p>)}
    {assessment?.source_validation?.status==='unconfirmed' && <p>尚未核對選定來源的類別判讀；原始數值不能代替缺失判讀。</p>}</>;
}
export function RiskDetails({risk,run}:{risk:any;run:any}) {
  if (!risk?.risk_details) return <><p>過敏：{risk?.allergy || '未核對'}</p><p>腎功能：{risk?.renal || '未核對'}</p><p>交互作用：{risk?.interactions || '未核對'}</p><Quotes quotes={risk?.quotes} run={run}/></>;
  return <><p>以下為臨床 Agent 初評；是否通過完整核對，以獨立複核為準。</p>{Object.entries(risk.risk_details).map(([key,value])=>{
    const detail=value as any;
    return <details key={key}><summary>{riskNames[key] || key}初評：{labels[detail.status] || detail.status}</summary>
      <p>{detail.reason}</p><p>病例依據：{detail.fact_refs?.map(factLabel).join('、') || '未提供'}</p>
      {!!detail.missing_fields?.length && <p>缺少：{detail.missing_fields.map(factLabel).join('、')}</p>}
      {detail.next_action && <p>下一步：{detail.next_action}</p>}
      <Quotes quotes={risk.quotes?.filter((q:any)=>detail.evidence_refs?.includes(q.chunk_id))} run={run}/>
    </details>;
  })}</>;
}
function AuditDetails({audit,run}:{audit:any;run:any}) {
  return <><p>模型獨立複核回報：{labels[audit?.verdict] || '未核對'}；{audit?.reason}</p>
    {audit?.basis && <p>依據：{({document:'文件',case_fact:'病例事實',mixed:'病例事實與文件'} as Record<string,string>)[audit.basis]}</p>}
    {audit?.infection_match && <p>模型細項回報：感染：{labels[audit.infection_match]}；族群：{labels[audit.population_match]}；藥品：{labels[audit.drug_match]}</p>}
    {audit && audit.basis!=='case_fact' && !audit.quotes?.length && <p>本次複核沒有選取引文；上述模型細項不能視為已通過文件核對。</p>}
    {audit?.fact_match && audit.fact_match!=='not_applicable' && <p>病例事實核對：{labels[audit.fact_match]} · {audit.fact_refs?.map(factLabel).join('、')}</p>}
    {audit?.ast_check && <p>獨立藥敏來源核對：{(audit.ast_check_validation?.source_status || audit.ast_check_validation?.status)==='confirmed'?'來源欄位一致':'尚未通過來源核對'}；類別：{audit.ast_check.assessment==='untested'?'本例未測 AST':labels[audit.ast_check.assessment]}。這不代表藥品適用性已確認。</p>}
    {audit?.ast_check?.claim_assessment && audit.ast_check.claim_assessment!=='not_stated' && <p>複核辨識的原聲明判讀：{audit.ast_check.claim_assessment==='untested'?'本例未測 AST':labels[audit.ast_check.claim_assessment]}；與來源比對：{audit.ast_check_validation?.claim_status==='consistent'?'一致':'尚未一致'}。</p>}
    {audit?.provenance_issues?.map((issue:string,i:number)=><p key={i}>引用／來源待確認：{issue}</p>)}
    {audit?.risk_checks?.map((check:any)=><p key={check.dimension}>{riskNames[check.dimension]}聲明複核：{labels[check.verdict]} · {check.reason}</p>)}
    {!!audit?.claim_checks?.length && <table><thead><tr><th>分項聲明</th><th>獨立複核</th><th>依據／未完成原因</th></tr></thead><tbody>{audit.claim_checks.map((c:any,i:number)=><tr key={i}><td>{dimensions[c.dimension]}</td><td>{labels[c.verdict]}</td><td>{c.reason}{c.validation_issues?.map((s:string,j:number)=><p key={j}>{s}</p>)}<Quotes quotes={audit.quotes?.filter((q:any)=>c.evidence_refs?.includes(q.chunk_id))} run={run}/></td></tr>)}</tbody></table>}
    <Quotes quotes={audit?.quotes} run={run}/></>;
}
export function AgentDrugTable({run}:{run:any}) {
  const layered=['agent-led-1.4.0','agent-led-1.4.1','agent-led-1.4.2','agent-led-1.5.0','agent-led-1.5.1'].includes(run.versions?.workflow);
  const order=['candidate','review_option','pending','avoid','not_selected'];
  const rows=layered ? [...(run.drug_assessments || [])].sort((a:any,b:any)=>order.indexOf(a.result_tier)-order.indexOf(b.result_tier)) : run.drug_assessments || [];
  return <section className="panel" aria-label="Agent 逐藥決策">
    <h2>逐藥決策表</h2><p>Agent 主導判斷 · {rows.length} 項藥品 · {rows.filter((x:any)=>x.status==='reviewable').length} 項系統核對完成 · {rows.filter((x:any)=>x.status==='pending').length} 項待確認</p>
    {layered && <p>{rows.filter((x:any)=>x.result_tier==='review_option').length} 項有證據的待審閱選項（包含於待確認）。此層僅收錄感染適用性已獨立核對、仍有風險缺口的項目；不能直接接受為完成建議。</p>}
    {!!rows.length && !rows.some((x:any)=>x.status==='reviewable') && <p role="status">目前沒有完成系統核對的候選。仍可前往人工審閱逐藥記錄醫師決策，並保留待確認與不建議理由；此結果不等於所有藥品均不適用。</p>}
    <div className="tablewrap"><table><thead><tr><th>藥品／來源</th><th>原始 AST</th><th>藥敏評估</th><th>臨床風險</th><th>文件支持與複核</th><th>最終去向與理由</th></tr></thead><tbody>
      {rows.map((x:any,i:number)=><Fragment key={x.drug_code}>{layered && (i===0 || x.result_tier!==rows[i-1].result_tier) && <tr><th colSpan={6} scope="rowgroup">{tierLabels[x.result_tier] || '其他待確認'}</th></tr>}<tr>
        <td><span>{x.drug_code}</span><br/><strong>{layered ? tierLabels[x.result_tier] : labels[x.status] || x.status}</strong><br/>{x.ast_available?'本例有 AST':'指引選項；本例未測 AST'}</td>
        <td>{x.source_ast?.map((a:any,i:number)=><p key={i}>原始：{a.source_phenotype || a.reported_sir || '未知'}；CLSI 2022：{a.clsi_2022_phenotype || '未提供'}<br/>MIC：{a.mic == null ? '未提供（不自行換算）' : `${a.comparator || ''}${a.mic} ${a.unit || '單位未知'}`}</p>)}</td>
        <td>模型判讀：{labels[x.ast?.assessment] || '未測／未完成'}{x.ast?.source_validation?.status==='unconfirmed' && <p>{typeof x.ast.model_reason==='string'?x.ast.reason:'藥敏類別來源尚未通過核對，請核對來源或重新分析；不能以草稿推定敏感性。'}</p>}{x.status==='reviewable'?<p>{x.ast?.reason}</p>:<details><summary>藥敏模型草稿（不等於治療建議）</summary><p>{x.ast?.model_reason || x.ast?.reason}</p></details>}<ASTSources assessment={x.ast}/></td>
        <td>臨床初評：{labels[x.clinical?.status] || '未完成'}{x.status==='pending' && <p>尚未完成整體核對，不能解讀為已排除風險。{x.blockers?.some((b:any)=>b.kind==='input_omitted') && '部分來源片段未提供，請查看未完成項目。'}</p>}{x.clinical ? <RiskDetails risk={x.clinical} run={run}/> : <p>此 Agent 沒有可用評估；未核對不代表病例未提供資料。請查看病例摘要及執行錯誤。</p>}</td>
        <td><details open={x.status==='reviewable'}><summary>{x.status==='reviewable'?'查看文件支持與複核':'查看模型證據草稿（尚非建議）'}</summary><p>模型初評：{labels[x.evidence?.status] || '未完成'}</p><p>{x.evidence?.reason}</p><p>{x.evidence?.applicability}</p><Quotes quotes={x.evidence?.quotes} run={run}/><AuditDetails audit={x.audit} run={run}/></details></td>
        <td><strong>{labels[x.status] || x.status}</strong>{x.status==='pending' ? <><p>尚未通過完整核對，不能視為用藥建議。</p>{x.reference_validation?.status==='unconfirmed' && <p>{x.reason}</p>}<details><summary>整合草稿與限制（尚非建議）</summary><p>{x.model_reason || x.reason}</p></details></> : <p>{x.reason}</p>}{x.review_notes?.map((n:any,i:number)=><p key={i}>審閱注意事項（{riskNames[n.dimension]}）：{n.next_action}</p>)}{x.disagreements?.map((d:string,i:number)=><p key={i}>分歧：{d}</p>)}</td>
      </tr>{layered && !!x.blockers?.length && <tr><td colSpan={6}><details open={x.result_tier==='review_option'}><summary>{x.drug_code}：未完成項目</summary><table><thead><tr><th>類型</th><th>面向</th><th>原因</th></tr></thead><tbody>{x.blockers.map((b:any,j:number)=><tr key={j}><td>{blockerLabels[b.kind] || b.kind}</td><td>{dimensions[b.dimension] || '整體'}</td><td>{b.detail}</td></tr>)}</tbody></table></details></td></tr>}</Fragment>)}
    </tbody></table></div>
    {!rows.length && <p>尚無逐藥結果；請查看 Agent 執行紀錄。</p>}
    <EvidenceCoverage run={run}/>
    <details><summary>本次檢索紀錄（{run.retrievals?.length || 0} 次）</summary><table><thead><tr><th>查詢</th><th>狀態</th><th>片段數</th></tr></thead><tbody>{run.retrievals?.map((r:any,i:number)=><tr key={i}><td>{r.query}</td><td>{r.status}</td><td>{r.count}</td></tr>)}</tbody></table></details>
  </section>;
}
export function EvidenceCoverage({run}:{run:any}) {
  if (!run.evidence_coverage?.length) return null;
  const stages:Record<string,string>={infection:'感染情境',guideline_options:'指引選項',clinical:'藥品風險',background:'研究背景'};
  const statuses:Record<string,string>={ok:'檢索完成',no_results:'未找到片段',no_documents:'沒有可用文件',conflict:'文件版本衝突：請指定文件版本後重跑',failed:'檢索失敗',budget_exceeded:'未執行：時間已用盡',index_required:'未執行：向量索引尚未備妥',budget_reserved:'未執行：保留後續 Agent 時間',not_configured:'尚未設定'};
  const warnings:Record<string,string>={agent_index_not_ready:'請到文件資料庫重建向量索引後再分析；分析期間不臨時補建索引。',time_reserved_for_remaining_agents:'為整合及獨立複核保留時間；未完成的查詢不代表沒有證據。',document_version_conflict:'同名文件有多個版本；請在病例文件範圍指定版本後重跑。',no_documents_for_requested_genre:'沒有符合本次檢索用途的文件。',embedding_failed:'向量檢索失敗，請查看索引狀態。'};
  const execution=(node:any)=>!node?'未記錄呼叫狀態':node.is_mock?'Mock 流程，未呼叫外部模型':
    !node.attempts?.length?'未呼叫模型':node.attempts.some((a:any)=>a.response_id || a.usage || a.status==='completed')?'已收到模型回覆；不代表核對通過':'已嘗試呼叫；尚未確認收到回覆';
  return <details><summary>逐藥證據準備與呼叫情況</summary>
    <p>片段數表示輸入準備情況，不代表支持用藥、已送達模型或已完成核對。完整原文保留在快照；未納入的片段不在此 Agent 輸入內。</p>
    <div className="tablewrap"><table><thead><tr><th>Agent／用途</th><th>藥品</th><th>檢索狀態</th><th>找到</th><th>已準備</th><th>未納入</th><th>模型呼叫</th><th>來源片段</th></tr></thead><tbody>
      {run.evidence_coverage.map((g:any,i:number)=>{const notice=g.warnings || run.retrievals?.find((r:any)=>r.stage===g.stage && r.drug_code===g.drug_code)?.warnings || []; return <tr key={i}>
        <td>{titles[g.agent_id]}／{stages[g.stage] || g.stage}{g.dimension && `／${dimensions[g.dimension] || g.dimension}`}</td><td>{g.drug_code || '共同情境'}</td>
        <td>{statuses[g.retrieval_status] || g.retrieval_status}{notice.map((w:string,j:number)=><p key={j}>{warnings[w] || w}</p>)}</td><td>{g.retrieved_count}</td><td>{g.selected_count}</td><td>{g.omitted_refs?.length || 0}</td>
        <td>{execution(run.nodes?.find((n:any)=>n.node_id===g.agent_id))}</td>
        <td>{!!g.evidence_refs?.length && <details><summary>已準備片段</summary><CandidateEvidence refs={g.evidence_refs} evidence={run.evidence_snapshots}/></details>}
          {!!g.omitted_refs?.length && <details><summary>未納入片段（輸入長度限制）</summary><CandidateEvidence refs={g.omitted_refs} evidence={run.evidence_snapshots}/></details>}</td>
      </tr>})}
    </tbody></table></div>
  </details>;
}
export function AgentStep({node:n,index,run}:{node:any,index:number,run:any}) {
  const o=n.output;
  const pendingRows=(o?.drugs || []).filter((d:any)=>['uncertain','unknown','pending','caution','unsupported','conflicting'].includes(d.status || d.assessment || d.verdict));
  const snapshot=run.case_snapshot;
  const clinicalInput=snapshot ? [snapshot.allergies?.status && '過敏狀態',snapshot.renal?.crcl!=null && 'CrCl',snapshot.renal?.egfr!=null && 'eGFR',snapshot.medication_history_status && '用藥清單完整性'].filter(Boolean).join('、') : '';
  return <details className="node" id={`agent-step-${n.node_id}`}><summary>{String(index+1).padStart(2,'0')}　{titles[n.node_id] || n.node_id} · {n.status==='failed'?'執行失敗':n.status==='not_applicable'?'無可複核聲明，未執行':n.status==='needs_confirmation'?'需確認':'已執行'}</summary>
    <div className="step-body"><p>模型：{n.model || '未呼叫'} · 呼叫 {n.attempts?.length || 0} 次 · Token {n.usage?.total_tokens ?? '未提供'}</p>
      {n.is_mock && <p>MOCK 流程測試，未進行模型分析。</p>}
      {n.node_id==='clinical_agent' && n.status==='failed' && <p>本步驟沒有可用的風險結論，不能由其他 Agent 的肯定句取代。{clinicalInput && `病例快照已有 ${clinicalInput}；`}請先查看下方執行錯誤，不需因為「未核對」就重填已有資料。</p>}
      {o ? <><h4>此 Agent 的發現</h4>{o.findings?.map((x:string,i:number)=><p key={i}>{x}</p>)}
        {o.rapid_assessment && <p>快速鑑定：{o.rapid_assessment}</p>}{o.resistance_assessment && <p>抗藥背景：{o.resistance_assessment}</p>}
        {!!o.issues?.length ? <AgentIssues items={o.issues.map((x:any)=>({...x,agent_id:n.node_id}))}/> : pendingRows.length ? <p>模型未另列缺漏清單，但逐藥結果有 {pendingRows.length} 項需注意或尚未完成核對；請查看下方對應理由與來源，不能解讀為全部通過。</p> : <AgentIssues items={[]}/>}
        {n.node_id!=='case_agent' && <p>下方為此 Agent 的模型回報；最終是否可供審閱，以逐藥決策表為準。</p>}
        {o.drugs?.length>0 && <table><thead><tr><th>藥品</th><th>判斷</th><th>具體理由／引用</th></tr></thead><tbody>{o.drugs.map((x:any)=><tr key={x.drug_code}><td>{x.drug_code}</td><td>{labels[x.status || x.assessment || x.verdict]}</td><td>{x.reason}{x.applicability && <p>{x.applicability}</p>}{x.risk_details ? <RiskDetails risk={x} run={run}/> : <>{x.allergy && <p>過敏：{x.allergy}；腎功能：{x.renal}；交互作用：{x.interactions}</p>}<Quotes quotes={x.quotes} run={run}/></>}{x.evidence_refs?.length>0 && <CandidateEvidence refs={x.evidence_refs} evidence={run.evidence_snapshots}/>}</td></tr>)}</tbody></table>}
      </> : <p>{n.skip_reason==='no_claims'?'沒有可複核聲明；未呼叫模型，不算複核通過。':'此步驟沒有可用回覆；其他已完成步驟仍可查看。'}</p>}
      {n.errors?.map((e:any,i:number)=><p key={i}>{({AGENT_TIME_RESERVED:'本步驟剩餘時間不足，已保留後續 Agent 的時間；本步驟未完成。',AGENT_STAGE_TIMEOUT:'本步驟回覆超過分配時間，未納入判斷；其他有效結果保留。',AGENT_OUTPUT_TRUNCATED:'模型回覆達輸出長度上限，未完成 JSON；需調整輸出預算後重新分析，不能視為藥品不適用。',AGENT_PARTIAL_INVALID:'部分藥品的回覆未通過檢查，其他有效結果已保留。',CITATION_SELECTION_INVALID:'模型選擇的來源段落無法核對，需重新分析。',AGENT_INPUT_TOO_LARGE:'本步驟輸入超過長度上限，未完成評估；不代表藥品不適用。',AGENT_SCHEMA_INVALID:'回覆未通過格式或來源檢核，未完成評估。',AGENT_BUDGET_EXCEEDED:'執行時間或呼叫額度已用盡，未完成評估。'} as Record<string,string>)[e.code] || e.code}</p>)}
    </div></details>;
}
