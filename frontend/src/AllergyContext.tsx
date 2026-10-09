import {useState} from 'react';

export const allergyStatuses: Record<string,string> = {
  known_none:'已記錄無已知過敏', known_present:'有過敏標籤', unknown:'過敏資料未知',
};
const verificationLabels: Record<string,string> = {
  not_recorded:'未提供確認狀態', unverified:'尚未確認', confirmed:'已有確認紀錄',
  ruled_out:'已有臨床評估：不支持此過敏標籤', conflicting:'紀錄互相矛盾',
};

export function AllergyContext({value}:{value:any}) {
  return <section aria-label="過敏標籤與確認紀錄">
    <h4>過敏標籤與確認紀錄</h4>
    <p>{allergyStatuses[value?.status] || '過敏資料未知'}。病歷標籤與是否確認分別保留。</p>
    {!!value?.items?.length && <div className="tablewrap"><table><thead><tr>
      <th>藥品／原始反應</th><th>來源與發生時間</th><th>確認狀態與依據</th>
    </tr></thead><tbody>{value.items.map((item:any,index:number)=><tr key={index}>
      <td>{item.drug_code}<p>反應：{item.reaction || '未記載'}；嚴重程度：{item.severity || '未記載'}</p></td>
      <td>{item.label_source || '來源未記載'}<p>{item.occurred_at || '發生時間未記載'}</p></td>
      <td>{verificationLabels[item.verification_status] || verificationLabels.not_recorded}
        {item.verification_note && <p>{item.verification_note}</p>}
        {item.verification_source && <p>評估來源：{item.verification_source}</p>}
        {item.verified_by && <p>紀錄者：{item.verified_by} · {item.verified_at || '時間未記載'}</p>}
      </td>
    </tr>)}</tbody></table></div>}
  </section>;
}

export function AllergyEditor({value,busy,onSave}:{value:any;busy:boolean;onSave:(allergies:any)=>Promise<void>}) {
  const [items,setItems] = useState<any[]>(()=>(value?.items || []).map((item:any)=>({...item})));
  function update(index:number,key:string,next:string) {
    setItems(current=>current.map((item,i)=>i===index?{...item,[key]:next || null}:item));
  }
  return <details><summary>補充過敏紀錄（保存為新病例版本）</summary>
    <p>保留原始標籤；填寫既有評估的來源，不由模型解除標籤。保存後需重新分析，舊結果不變。</p>
    <form onSubmit={event=>{event.preventDefault(); void onSave({status:'known_present',items});}}>
      {items.map((item,index)=>{
        const traceRequired=['confirmed','ruled_out'].includes(item.verification_status);
        return <fieldset key={index}><legend>過敏紀錄 {index+1}</legend>
          <label>藥品代碼<input required value={item.drug_code || ''} onChange={e=>update(index,'drug_code',e.target.value)}/></label>
          <label>原始反應<input value={item.reaction || ''} onChange={e=>update(index,'reaction',e.target.value)}/></label>
          <label>嚴重程度<input value={item.severity || ''} onChange={e=>update(index,'severity',e.target.value)}/></label>
          <label>標籤來源<input value={item.label_source || ''} onChange={e=>update(index,'label_source',e.target.value)}/></label>
          <label>發生時間（可填約略日期）<input maxLength={200} value={item.occurred_at || ''} onChange={e=>update(index,'occurred_at',e.target.value)}/></label>
          <label>確認狀態<select value={item.verification_status || 'not_recorded'} onChange={e=>update(index,'verification_status',e.target.value)}>
            {Object.entries(verificationLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select></label>
          <label>既有評估內容<textarea required={traceRequired} value={item.verification_note || ''} onChange={e=>update(index,'verification_note',e.target.value)}/></label>
          <label>評估來源／紀錄位置<input required={traceRequired} value={item.verification_source || ''} onChange={e=>update(index,'verification_source',e.target.value)}/></label>
          <label>確認紀錄者<input required={traceRequired} value={item.verified_by || ''} onChange={e=>update(index,'verified_by',e.target.value)}/></label>
          <label>確認時間（含時區）<input required={traceRequired} placeholder="2026-10-06T10:00:00+08:00" value={item.verified_at || ''} onChange={e=>update(index,'verified_at',e.target.value)}/></label>
        </fieldset>;
      })}
      <button type="button" disabled={busy} onClick={()=>setItems(current=>[...current,{drug_code:'',verification_status:'unverified'}])}>新增過敏紀錄</button>
      <button type="submit" disabled={busy || !items.length}>保存過敏資料並建立新版本</button>
    </form>
  </details>;
}
