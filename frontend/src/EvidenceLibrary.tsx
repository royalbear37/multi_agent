import {useState} from 'react';
import {evidenceLocation, EvidenceSourceNotice} from './ClinicalContext';

export function EvidenceLibrary({run}:{run:any}) {
 const [query,setQuery]=useState('');
 const sources=run.evidence_snapshots || [];
 const groups=new Map<string,any[]>();
 for(const e of sources) {
  if(query && !`${e.document_title || e.title || e.doc_id} ${e.text}`.toLowerCase().includes(query.toLowerCase())) continue;
  const key=JSON.stringify([e.doc_id,e.document_version]);
  groups.set(key,[...(groups.get(key) || []),e]);
 }
 return <section className="panel evidence-library"><h2>文件與引用快照</h2>
  <p className="muted">{sources.length} 個檢索片段，依文件版本分組。片段存在不代表支持用藥。</p>
  <label>搜尋文件或原文<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="輸入文件名稱、藥名或關鍵字"/></label>
  {[...groups.entries()].map(([key,items])=><details key={key} className="source-group"><summary>{items[0].document_title || items[0].title || items[0].doc_id} · {items[0].document_version} · {items.length} 個片段</summary>
   <p>{items[0].is_synthetic===true?'合成測試文件':items[0].is_synthetic===false?'真實參考文件（適用性仍需核對）':'來源類型未記錄'}</p>
   <EvidenceSourceNotice item={items[0]} evidence={sources}/>
   {items.map((e:any,i:number)=><details key={`${e.chunk_id}-${i}`} className="source-excerpt"><summary>{evidenceLocation(e.location)} · 片段 {i+1}</summary>
    <blockquote>{e.text}</blockquote><small>{e.chunk_id}</small><p><a href={'/api/documents/'+encodeURIComponent(e.doc_id)+'/source'+(e.location?.page?'#page='+e.location.page:'')} target="_blank" rel="noreferrer">開啟原始文件</a></p>
   </details>)}
  </details>)}
  {!groups.size && <p>{sources.length?'沒有符合搜尋條件的片段。':'此分析沒有可用文件證據。'}</p>}
 </section>;
}
