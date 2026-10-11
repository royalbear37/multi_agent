import {useRef, useState} from 'react';
import {CandidateEvidence} from './ClinicalContext';
import {RiskDetails} from './AgentLed';
import {physicianCandidates, riskNextAction} from './physicianCandidates';

export const physicianDecisionNames:Record<string,string>={adopt:'採用',conditional:'有條件採用',decline:'不採用'};
const dimensions:Record<string,string>={infection:'感染適用性',ast:'藥敏',allergy:'過敏',renal:'腎功能',interactions:'交互作用'};
const systemNames:Record<string,string>={reviewable:'系統核對完成',pending:'系統尚待確認',avoid:'系統不建議',not_selected:'系統未選入'};
const astNames:Record<string,string>={susceptible:'敏感',intermediate:'中介',resistant:'抗藥',conflicting:'來源衝突',unknown:'未知'};
type Decision={id:number;selection:string;drug_code:string;decision:string;reason:string;conditions:string};
const emptyDecision=(id:number):Decision=>({id,selection:"",drug_code:"",decision:"",reason:"",conditions:""});
const drugIdentity=(s:string)=>s.trim().toLowerCase().replace(/[\s_+/／＋–—-]+/g,"_");

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
   {riskNextAction(run,key,d) && !repeatedHistoryQuestion && <p>模型提醒：{riskNextAction(run,key,d)}</p>}
  </div>})}
  {!hasStructured && <><p>未提供結構化分項風險評估，不能由空白推定無風險。</p>{['allergy','renal','interactions'].map(key=>typeof row.clinical?.[key]==='string' && row.clinical[key] && <p key={key}>{dimensions[key]}（原始初評）：{row.clinical[key]}</p>)}{row.clinical?.reason && <p>{row.clinical.reason}</p>}</>}
  {hasStructured && !details.length && <p>本次初評未列額外注意事項；仍須參照獨立複核結果。</p>}
  {!audit && <p>尚未完成獨立引用複核。</p>}
  {audit?.reason && <p>獨立複核：{audit.reason}</p>}
  {audit?.ast_check_validation && <>
   {(audit.ast_check_validation.source_status || audit.ast_check_validation.status)!=='confirmed' && <p>獨立複核：藥敏來源尚未確認，不能將模型的敏感判讀當成已確認結果。</p>}
   {audit.ast_check_validation.claim_status && audit.ast_check_validation.claim_status!=='consistent' && <p>獨立複核：藥敏聲明與來源尚未一致。</p>}
  </>}
  {audit?.risk_checks?.filter((c:any)=>c.verdict!=='supported').map((c:any,i:number)=><p key={i}>{dimensions[c.dimension] || c.dimension}獨立複核未支持或尚待確認：{c.reason}</p>)}
  {audit?.provenance_issues?.map((issue:string,i:number)=><p key={i}>引用／來源待確認：{issue}</p>)}
  {audit?.claim_checks?.filter((c:any)=>c.verdict!=='supported' || c.validation_issues?.length).map((c:any,i:number)=><div key={i}><strong>{dimensions[c.dimension] || c.dimension}複核未完成或有疑義</strong><p>{c.reason}</p>{c.validation_issues?.map((s:string,j:number)=><p key={j}>{s}</p>)}</div>)}
  {row.status!=='reviewable' && <p>系統核對尚未完成；醫師決策不會將它改為已通過。</p>}
  {!!row.blockers?.length && <details><summary>系統證據核對缺口（{row.blockers.length}）</summary><ul>{Array.from(new Set<string>(row.blockers.map((b:any)=>`${dimensions[b.dimension] || '整體'}：${b.detail}`))).map(x=><li key={x}>{x}</li>)}</ul></details>}
 </>;
}

export function PhysicianReview({run,role,busy,onSave}:{run:any;role:string;busy:boolean;onSave:(decisions:any[])=>Promise<void>}) {
 const [draft,setDraft]=useState<Decision[]>([emptyDecision(0)]),[ack,setAck]=useState(false),[error,setError]=useState('');
 const nextId=useRef(1);
 const candidates=physicianCandidates(run), candidateCodes=new Set(candidates.map((r:any)=>r.drug_code));
 const rows=run.drug_assessments || [], excluded=rows.filter((r:any)=>!candidateCodes.has(r.drug_code));
 const resolve=(code:string)=>rows.find((r:any)=>drugIdentity(r.drug_code)===drugIdentity(code));
 const chosen=draft.filter(d=>d.selection || d.drug_code.trim() || d.decision);
 const duplicate=new Set(chosen.map(d=>drugIdentity(d.drug_code))).size!==chosen.length;
 const adopting=chosen.some(x=>['adopt','conditional'].includes(x.decision));
 const permitted=['physician','doctor','pharmacist'].includes(role);
 const valid=chosen.length>0 && !duplicate && chosen.every(x=>x.drug_code.trim() && x.decision && x.reason.trim() && (x.decision!=='conditional' || x.conditions.trim())) && (!adopting || ack);
 function update(id:number,change:Partial<Decision>) {setDraft(ds=>ds.map(d=>d.id===id?{...d,...change}:d));setAck(false);setError('');}
 return <section aria-label="逐藥醫師決策" className="drug-picker"><h3>選擇要記錄的藥品</h3>
  <p className="muted">先增加一項藥品，再記錄決定。未選藥品不必逐一處理。</p>
  <details className="context-fold"><summary>共同病例資訊</summary><PatientQuestions run={run}/></details>
  {draft.map((d,index)=>{const row=resolve(d.drug_code), custom=d.selection==='__custom__';return <fieldset key={d.id} disabled={busy} className="drug-choice">
   <legend>藥品 {index+1}</legend>
   <div className="selection-line"><label>增加藥物<select aria-label={`藥品 ${index+1}`} value={d.selection} onChange={e=>update(d.id,{selection:e.target.value,drug_code:e.target.value==='__custom__'?'':e.target.value,decision:'',reason:'',conditions:''})}>
    <option value="">請選擇藥品</option>
    <optgroup label="候選藥品">{candidates.map((r:any)=><option key={r.drug_code} value={r.drug_code} disabled={draft.some(other=>other.id!==d.id && drugIdentity(other.drug_code)===drugIdentity(r.drug_code))}>{r.drug_code}</option>)}</optgroup>
    {!!excluded.length && <optgroup label="系統不建議（保留警示）">{excluded.map((r:any)=><option key={r.drug_code} value={r.drug_code} disabled={draft.some(other=>other.id!==d.id && drugIdentity(other.drug_code)===drugIdentity(r.drug_code))}>{r.drug_code}</option>)}</optgroup>}
    <option value="__custom__">其他藥品（自行輸入）</option>
   </select></label><button type="button" aria-label={`移除藥品 ${index+1}`} onClick={()=>{setDraft(ds=>ds.length===1?[emptyDecision(nextId.current++)]:ds.filter(x=>x.id!==d.id));setAck(false);}}>移除</button></div>
   {custom && <label>其他藥品名稱<input aria-label={`其他藥品名稱 ${index+1}`} maxLength={200} value={d.drug_code} onChange={e=>update(d.id,{drug_code:e.target.value})} placeholder="輸入藥品名稱"/></label>}
   {!!d.selection && <>
    {row ? <div className="selected-assessment"><div className="status-line"><span className="status">{candidateCodes.has(row.drug_code)?'醫師候選':'系統不建議'}</span><span>{systemNames[row.status] || row.status}</span><span>AST：{astNames[row.ast?.assessment] || '未完成／未測'}</span></div>
      {row.reason && <p><strong>整合判斷{row.status==='reviewable'?'':'（尚待核對）'}：</strong>{row.reason}</p>}
      {row.ast?.assessment==='conflicting' && <p className="selection-warning">藥敏來源衝突，請核對原始報告。</p>}
      {!candidateCodes.has(row.drug_code) && <p className="selection-warning">{run.physician_excluded?.find((r:any)=>r.drug_code===row.drug_code)?.exclusion_reasons?.join('；') || row.reason || '系統不建議，採用時請說明判斷依據。'}</p>}
      <details><summary>用藥注意與未完成核對</summary><DrugCautions row={row} run={run}/></details>
      <details><summary>引用與完整初評</summary><p><strong>原始模型初評（須與藥敏及獨立複核分開核對）：</strong>{row.evidence?.reason || '文件適用性未完成'}</p><CandidateEvidence refs={row.evidence?.quotes?.map((q:any)=>q.chunk_id) || []} evidence={run.evidence_snapshots}/><RiskDetails risk={row.clinical} run={run}/></details>
     </div> : <p className="selection-warning">醫師自行新增：此名稱未對應本次藥品評估，請核對是否為既有藥品別名，並另行確認藥敏、風險與引用。</p>}
    <div className="decision-fields"><label>決定<select aria-label={`${d.drug_code} 醫師決定`} value={d.decision} onChange={e=>update(d.id,{decision:e.target.value})}><option value="">請選擇</option>{Object.entries(physicianDecisionNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
    <label>決策理由<textarea aria-label={`${d.drug_code} 決策理由`} maxLength={4000} value={d.reason} onChange={e=>update(d.id,{reason:e.target.value})}/></label></div>
    {d.decision==='conditional' && <label>使用條件<textarea aria-label={`${d.drug_code} 使用條件`} maxLength={4000} value={d.conditions} placeholder="需先核對或處理的限制" onChange={e=>update(d.id,{conditions:e.target.value})}/></label>}
   </>}
  </fieldset>})}
  <button type="button" disabled={busy || draft.length>=100} onClick={()=>setDraft(ds=>[...ds,emptyDecision(nextId.current++)])}>＋ 繼續添加藥品</button>
  {duplicate && <p role="alert">藥品重複，請移除或改選。</p>}
  {adopting && <label className="check-label"><input type="checkbox" disabled={busy} checked={ack} onChange={e=>setAck(e.target.checked)}/>已閱讀所選藥品的警示與未完成項目；自行新增的藥品由我另行核對。</label>}
  {!permitted && <p>請使用醫師或藥師角色記錄逐藥決策。</p>}
  <p className="muted">本次填寫 {chosen.length} 項；其他藥品維持未決定。</p>
  {error && <p role="alert">{error}</p>}
  <button className="primary" disabled={busy || !valid || !permitted} onClick={async()=>{setError('');try{await onSave(chosen.map(d=>({drug_code:resolve(d.drug_code)?.drug_code || d.drug_code.trim(),decision:d.decision,reason:d.reason.trim(),conditions:d.decision==='conditional'?d.conditions.trim():'',acknowledged_warnings:d.decision!=='decline' && ack,outside_analysis:!resolve(d.drug_code)})));setDraft([emptyDecision(nextId.current++)]);setAck(false);}catch(e){setError(String(e));}}}>保存逐藥決策</button>
 </section>;
}
