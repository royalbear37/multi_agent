import {useState} from 'react';
import {CandidateEvidence} from './ClinicalContext';
import {RiskDetails} from './AgentLed';

export const physicianDecisionNames:Record<string,string>={adopt:'採用',conditional:'有條件採用',decline:'不採用'};
const dimensions:Record<string,string>={infection:'感染適用性',ast:'藥敏',allergy:'過敏',renal:'腎功能',interactions:'交互作用'};
const systemNames:Record<string,string>={reviewable:'系統核對完成',pending:'系統尚待確認',avoid:'系統不建議',not_selected:'系統未選入'};
const astNames:Record<string,string>={susceptible:'敏感',intermediate:'中介',resistant:'抗藥',conflicting:'來源衝突',unknown:'未知'};
type Decision={drug_code:string;decision:string;reason:string;conditions:string};

export function PatientQuestions({run}:{run:any}) {
 const c=run.case_snapshot || {}, questions:string[]=[];
 if(!['known_none','known_present'].includes(c.allergies?.status)) questions.push('過敏史尚未確認');
 if(!['reviewed_none','reviewed_list'].includes(c.medication_history_status)) questions.push('目前用藥清單是否完整尚未確認');
 if(c.renal?.egfr==null && c.renal?.crcl==null && c.renal?.creatinine==null) questions.push('沒有可用腎功能測量');
 return <section><h3>病例資訊（共同核對一次）</h3>
  {c.allergies?.status==='known_none' && <p>病例已記錄無已知過敏；一般過敏警語不等於缺少過敏史，不需逐藥重填。</p>}
  {c.medication_history_status==='reviewed_none' && <p>病例已確認目前無用藥；文件中的交互作用警語不代表本例正在併用。</p>}
  {questions.length ? <ul>{questions.map(q=><li key={q}>{q}</li>)}</ul> : <p>上述共同病例資訊已有記錄。其他具體缺口與藥品限制列在各藥旁，供醫師判斷。</p>}
 </section>;
}

export function DrugCautions({row,run}:{row:any;run:any}) {
 const details=Object.entries(row.clinical?.risk_details || {}).filter(([,d]:[string,any])=>d.status!=='no_identified_risk' || !!d.next_action);
 const hasStructured=Object.keys(row.clinical?.risk_details || {}).length>0;
 const audit=row.audit;
 return <>
  {row.ast?.assessment==='conflicting' && <p>藥敏來源衝突，請核對原始報告。</p>}
  {row.ast?.assessment==='resistant' && <p>來源核對為抗藥，保留此警示供醫師判斷。</p>}
  {row.ast_available && (!row.ast?.assessment || row.ast.assessment==='unknown') && <p>藥敏判讀尚未核實；即使下方模型初評提到「敏感」，也不能當成已確認的藥敏結果。</p>}
  {!row.ast_available && <p>本例未測此藥 AST，不能稱為敏感。</p>}
  {details.map(([key,value])=>{const d=value as any;const knownNone=key==='allergy' && run.case_snapshot?.allergies?.status==='known_none';const repeatedHistoryQuestion=knownNone && d.status==='caution' && !d.missing_fields?.length && !d.validation_issues?.length && /^(?:請|再次)?(?:詢問|確認|補充|補齊)(?:病人|患者|病患|既往|完整|詳細|既有|的)*過敏(?:史|紀錄|狀態)[。？?！!\s]*$/.test(d.next_action || '');return <div key={key}>
   <strong>{dimensions[key]}：{d.status==='unknown'?'尚未確認':'注意／限制（AI初評）'}</strong>
   <p>{d.reason}</p>
   {d.next_action && !repeatedHistoryQuestion && <p>模型提醒：{d.next_action}</p>}
  </div>})}
  {!hasStructured && <><p>未提供結構化分項風險評估，不能由空白推定無風險。</p>{['allergy','renal','interactions'].map(key=>typeof row.clinical?.[key]==='string' && row.clinical[key] && <p key={key}>{dimensions[key]}（原始初評）：{row.clinical[key]}</p>)}{row.clinical?.reason && <p>{row.clinical.reason}</p>}</>}
  {hasStructured && !details.length && <p>本次初評未列額外注意事項；仍須參照獨立複核結果。</p>}
  {!audit && <p>尚未完成獨立引用複核。</p>}
  {audit?.reason && <p>獨立複核：{audit.reason}</p>}
  {audit?.provenance_issues?.map((issue:string,i:number)=><p key={i}>引用／來源待確認：{issue}</p>)}
  {audit?.claim_checks?.filter((c:any)=>c.verdict!=='supported' || c.validation_issues?.length).map((c:any,i:number)=><div key={i}><strong>{dimensions[c.dimension] || c.dimension}複核未完成或有疑義</strong><p>{c.reason}</p>{c.validation_issues?.map((s:string,j:number)=><p key={j}>{s}</p>)}</div>)}
  {row.status!=='reviewable' && <p>系統核對尚未完成；醫師決策不會將它改為已通過。</p>}
  {!!row.blockers?.length && <details><summary>系統證據核對缺口（{row.blockers.length}）</summary><ul>{Array.from(new Set<string>(row.blockers.map((b:any)=>`${dimensions[b.dimension] || '整體'}：${b.detail}`))).map(x=><li key={x}>{x}</li>)}</ul></details>}
 </>;
}

export function PhysicianReview({run,role,busy,onSave}:{run:any;role:string;busy:boolean;onSave:(decisions:any[])=>Promise<void>}) {
 const [draft,setDraft]=useState<Record<string,Decision>>({}),[ack,setAck]=useState(false),[error,setError]=useState('');
 const rows=run.drug_assessments || [], chosen=Object.values(draft).filter(x=>x.decision);
 const adopting=chosen.some(x=>x.decision!=='decline');
 const permitted=['physician','doctor','pharmacist'].includes(role);
 const valid=chosen.length>0 && chosen.every(x=>x.reason.trim() && (x.decision!=='conditional' || x.conditions.trim())) && (!adopting || ack);
 function update(code:string,change:Partial<Decision>) {setDraft(d=>({...d,[code]:{...(d[code] || {drug_code:code,decision:'',reason:'',conditions:''}),...change}}));setAck(false);}
 return <section aria-label="逐藥醫師決策"><h3>逐藥醫師決策</h3>
  <p>可先審閱有風險或尚待確認的藥品，不必等所有 AI 核對完成。只記錄你有決定的項目；每項留下理由，有條件採用另填使用條件。原始警示與系統狀態會保留。</p>
  <PatientQuestions run={run}/>
  <div className="tablewrap"><table><thead><tr><th>藥品／系統狀態</th><th>用藥注意與限制</th><th>醫師決定</th></tr></thead><tbody>
   {rows.map((r:any)=>{const d=draft[r.drug_code];return <tr key={r.drug_code}>
    <td><strong>{r.drug_code}</strong><p>{systemNames[r.status] || r.status}</p>{r.reason && <p>{r.reason}</p>}<p>AI 藥敏核對：{astNames[r.ast?.assessment] || '未完成'}</p>
     <details><summary>引用與完整初評</summary><p><strong>原始模型初評（須與藥敏及獨立複核分開核對）：</strong>{r.evidence?.reason || '文件適用性未完成'}</p><CandidateEvidence refs={r.evidence?.quotes?.map((q:any)=>q.chunk_id) || []} evidence={run.evidence_snapshots}/><RiskDetails risk={r.clinical} run={run}/></details></td>
    <td><DrugCautions row={r} run={run}/></td>
    <td><label>決定<select aria-label={`${r.drug_code} 醫師決定`} value={d?.decision || ''} onChange={e=>update(r.drug_code,{decision:e.target.value})}>
     <option value="">未決定</option>{Object.entries(physicianDecisionNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}
    </select></label>{d?.decision && <><label>理由<textarea aria-label={`${r.drug_code} 決策理由`} value={d.reason} onChange={e=>update(r.drug_code,{reason:e.target.value})}/></label>
     {d.decision==='conditional' && <label>使用條件<textarea aria-label={`${r.drug_code} 使用條件`} placeholder="例如需先核對或處理的併用藥限制" value={d.conditions} onChange={e=>update(r.drug_code,{conditions:e.target.value})}/></label>}</>}</td>
   </tr>})}
  </tbody></table></div>
  {!rows.length && <p>本次沒有可供逐藥審閱的評估。</p>}
  {adopting && <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>已閱讀所選藥品的系統警示與未完成項目；保留上述限制並記錄我的決策。</label>}
  {!permitted && <p>請使用醫師或藥師角色記錄逐藥決策。</p>}
  <p>本次選擇 {chosen.length} 項；未選項目維持未決定。</p>
  {error && <p role="alert">{error}</p>}
  <button disabled={busy || !valid || !permitted} onClick={async()=>{setError('');try{await onSave(chosen.map(d=>({...d,conditions:d.decision==='conditional'?d.conditions:'',acknowledged_warnings:d.decision!=='decline' && ack})));setDraft({});setAck(false);}catch(e){setError(String(e));}}}>保存逐藥決策</button>
 </section>;
}
