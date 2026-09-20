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
    {!!simulated.length && <p>模擬資料：{simulated.map(x => fieldLabels[x] || x).join('、')}。</p>}
    {encounterSimulated && snapshot && <p className="alert">下方模型理由可能沿用上述模擬設定；不能據此認定已確診感染或生命徵象穩定。請先核對情境與缺漏，再審閱候選。</p>}
  </section>;
}

export function evidenceLocation(location: any): string {
  const parts = [];
  if (location?.page != null) parts.push(`第 ${location.page} 頁`);
  if (location?.start_line != null) parts.push(`第 ${location.start_line}${location.end_line != null ? `–${location.end_line}` : ''} 行`);
  if (location?.section) parts.push(String(location.section));
  return parts.join(' · ') || '未記錄頁碼或段落位置';
}

export function CandidateEvidence({ refs = [], evidence = [] }: { refs?: string[]; evidence?: any[] }) {
  if (!refs.length) return <p>未提供文件引用。</p>;
  return <div aria-label="此藥品的引用證據"><p className="alert"><strong>引用適用性尚未驗證。</strong>目前只確認引用片段存在；尚未證明其中的感染部位、病原條件與此病例相符。條件不符時，請勿接受該候選。</p>{refs.map(ref => {
    const item = evidence.find(e => e.chunk_id === ref);
    if (!item) return <p key={ref}>引用片段未保存在本次分析，無法核對。</p>;
    return <details key={ref}>
      <summary>{item.document_title || item.title || '參考文件'} · {evidenceLocation(item.location)} · 版本 {item.document_version || '未記錄'}</summary>
      <blockquote>{item.text}</blockquote>
      <p>這是引用原文，仍需核對是否支持此藥品與病例情境。</p>
      <a href={`/api/documents/${encodeURIComponent(item.doc_id)}/source${item.location?.page ? '#page=' + item.location.page : ''}`} target="_blank" rel="noreferrer">開啟此頁原始文件</a>
      {' · '}<a href={`/api/documents/${encodeURIComponent(item.doc_id)}/source`} download>下載原始文件</a>
      <p className="muted">若新分頁空白或瀏覽器未顯示 PDF，請下載後以 PDF 閱讀器開啟，再跳至上述頁碼。</p>
    </details>;
  })}</div>;
}
