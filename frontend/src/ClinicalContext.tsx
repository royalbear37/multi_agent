import {AllergyContext} from './AllergyContext';

const fieldLabels: Record<string, string> = {
  demographics: '年齡與基本資料', encounter: '感染情境與嚴重度', renal: '腎功能',
  allergies: '過敏資料', medications: '用藥資料',
};

export function CaseContext({ value, snapshot = false }: { value: any; snapshot?: boolean }) {
  if (!value) return <p>未保存分析當時的病例摘要，請核對原始病例版本。</p>;
  const simulated: string[] = value.provenance?.simulated_fields ?? [];
  const encounterSimulated = value.is_synthetic || simulated.some(x => x === 'encounter' || x.startsWith('encounter.'));
  const severity: Record<string, string> = {stable:'穩定', severe:'嚴重', critical:'危重', unknown:'未知'};
  return <section aria-label={snapshot ? '分析當時的病例情境' : '病例情境'}>
    {snapshot && <h3>分析當時的病例情境</h3>}
    <p>菌種：{value.microbiology?.organism || '未提供'} · 年齡：{value.demographics?.age ?? '未知'}</p>
    <p><strong>{encounterSimulated ? '模擬設定，非已確認的臨床事實：' : '病例記錄（仍需核對）：'}</strong>
      感染情境 {value.encounter?.infection_site || '未知'}；嚴重度 {severity[value.encounter?.severity] || value.encounter?.severity || '未知'}。</p>
    <p>{value.encounter?.context || '未提供臨床情境說明。'}</p>
    <AllergyContext value={value.allergies}/>
    <p>用藥紀錄核對：{({reviewed_none:'已確認目前無用藥',reviewed_list:'已核對目前用藥清單',unknown:'尚未確認清單完整性'} as Record<string,string>)[value.medication_history_status || 'unknown']}。</p>
    {value.renal?.crcl != null && <p>CrCl：{value.renal.crcl} {value.renal.crcl_unit}；方法：{value.renal.crcl_calculation_method}。與 eGFR 分別保留。</p>}
    {!!Object.keys(value.clinical_history || {}).length && <details><summary>病史與檢查</summary><table><tbody>{Object.entries(value.clinical_history).map(([k,v])=><tr key={k}><th>{k}</th><td>{String(v)}</td></tr>)}</tbody></table></details>}
    {!!Object.keys(value.vitals || {}).length && <details><summary>生命徵象</summary><table><tbody>{Object.entries(value.vitals).map(([k,v])=><tr key={k}><th>{k}</th><td>{String(v)}</td></tr>)}</tbody></table></details>}
    {!!value.resistance_context?.length && <details><summary>資料集抗藥背景（非院內統計）</summary><table><thead><tr><th>藥品</th><th>判讀來源</th><th>有效分母</th><th>S／I／R</th><th>缺漏／衝突</th></tr></thead><tbody>{value.resistance_context.map((r:any,i:number)=><tr key={i}><td>{r.drug_code}</td><td>{r.basis}</td><td>{r.denominator}</td><td>{r.S}／{r.I}／{r.R}</td><td>{r.missing}／{r.conflicting}</td></tr>)}</tbody></table><p>來源：{value.resistance_context[0]?.source}；版本：{value.resistance_context[0]?.source_sha256}</p></details>}
    {!!simulated.length && <p>模擬資料：{simulated.map(x => fieldLabels[x] || x).join('、')}。</p>}
    {encounterSimulated && snapshot && <p className="alert">下方模型理由可能沿用上述模擬設定；不能據此認定已確診感染或生命徵象穩定。請先核對情境與缺漏，再審閱候選。</p>}
  </section>;
}

export function evidenceLocation(location: any): string {
  const parts = [];
  if (location?.page != null) parts.push(`第 ${location.page} 頁`);
  if (location?.start_line != null) parts.push(`第 ${location.start_line}${location.end_line != null ? `–${location.end_line}` : ''} 行`);
  if (location?.section) parts.push(String(location.section));
  if (location?.heading_path?.length) parts.push(location.heading_path.join(' › '));
  return parts.join(' · ') || '未記錄頁碼或段落位置';
}

export function EvidenceSourceNotice({item,evidence=[]}:{item:any;evidence?:any[]}) {
  const related=item?.source_document_id ? [...new Set(evidence.filter(e=>e.source_document_id===item.source_document_id && e.doc_id!==item.doc_id).map(e=>e.document_title || '參考文件'))] : [];
  if (!item?.source_derivation && !related.length) return null;
  return <p>同一原始文件：{item.source_derivation?.original_title || item.document_title || '參考文件'}{item.source_derivation?.original_version && ` · 版本 ${item.source_derivation.original_version}`}。全文與節錄的多個片段不能視為多份獨立證據；仍需逐項核對適用條件。</p>;
}

export function CandidateEvidence({ refs = [], evidence = [], audited=false }: { refs?: string[]; evidence?: any[]; audited?: boolean }) {
  if (!refs.length) return <p>未提供文件引用。</p>;
  return <div aria-label="此藥品的引用證據">{audited ? <p>已完成 Agent 獨立引用複核；可在逐藥決策表查看原文與複核理由，仍待人工審閱。</p> : <p className="alert"><strong>引用適用性尚未驗證。</strong>目前只確認引用片段存在；尚未證明其中的感染部位、病原條件與此病例相符。條件不符時，請勿接受該候選。</p>}{refs.map(ref => {
    const item = evidence.find(e => e.chunk_id === ref);
    if (!item) return <p key={ref}>引用片段未保存在本次分析，無法核對。</p>;
    return <details key={ref}>
      <summary>{item.document_title || item.title || '參考文件'} · {evidenceLocation(item.location)} · 版本 {item.document_version || '未記錄'}</summary>
      <blockquote>{item.text}</blockquote>
      <EvidenceSourceNotice item={item} evidence={evidence}/>
      <p>這是引用原文，仍需核對是否支持此藥品與病例情境。</p>
      <a href={`/api/documents/${encodeURIComponent(item.doc_id)}/source${item.location?.page ? '#page=' + item.location.page : ''}`} target="_blank" rel="noreferrer">開啟此頁原始文件</a>
      {' · '}<a href={`/api/documents/${encodeURIComponent(item.doc_id)}/source`} download>下載原始文件</a>
      <p className="muted">若新分頁空白或瀏覽器未顯示 PDF，請下載後以 PDF 閱讀器開啟，再跳至上述頁碼。</p>
    </details>;
  })}</div>;
}
