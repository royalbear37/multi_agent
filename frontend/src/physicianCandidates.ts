export function physicianCandidates(run:any):any[] {
  return run.physician_candidates ?? (run.drug_assessments || []).filter((r:any)=>r.status!=='avoid').map((r:any)=>({...r,verification_status:r.status==='reviewable'?'complete':'incomplete'}));
}

export function physicianExcluded(run:any):any[] {
  return run.physician_excluded ?? (run.drug_assessments || []).filter((r:any)=>r.status==='avoid');
}

export function riskNextAction(run:any, dimension:string, detail:any):string {
  const text=detail?.next_action || '';
  if(dimension!=='allergy' || run.case_snapshot?.allergies?.status!=='known_none' || detail?.status==='avoid') return text;
  // Only remove a repeated generic history request, retaining specific drug warnings.
  return text.replace(/^(?:請|再次)?(?:詢問|確認|補充|補齊)(?:病人|患者|病患|既往|完整|詳細|既有|的)*過敏(?:史|紀錄|狀態)[，,。；;？?！!\s]*/, '');
}
