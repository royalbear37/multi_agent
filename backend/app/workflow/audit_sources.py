"""Minimum provenance checks, never a determination of clinical suitability."""
import re
from .source_scope import named_drug
from .ast_sources import CATEGORIES, validate_ast_sources



def validate_audit_sources(row, claim, data):
    if not data.get('audit_sources_required'):
        return
    issues=[]
    rows=[x for x in data.get('ast_results',[]) if x.get('drug_code')==row['drug_code']]
    check=row.get('ast_check')
    confirmed=False
    if not check:
        issues.append('缺少本藥的獨立藥敏來源核對')
    elif check['assessment']=='untested':
        confirmed=not rows and not check['category_source_refs']
    elif check['assessment']=='unknown':
        def selected_category(item):
            basis=item.get('interpretation_basis')
            field='clsi_2022_phenotype' if basis=='CLSI_2022_pheno' else 'source_phenotype' if basis=='source_report' else 'reported_sir'
            return CATEGORIES.get(str(item.get(field) or '').strip().casefold())
        # This claim means unavailable source categorization; it is distinct
        # from an agent failing to link an available category.
        confirmed=bool(rows) and all(selected_category(x) is None for x in rows) and not check['category_source_refs']
    else:
        tested={'drug_code':row['drug_code'],'reason':'獨立核對原始類別',**check}
        validate_ast_sources(tested,{'ast_sources_required':True,'ast_results':data.get('ast_results',[])})
        confirmed=tested.get('source_validation',{}).get('status')=='confirmed' and tested['assessment']==check['assessment']
    if check and not confirmed:
        issues.append('複核的藥敏類別未連到本藥選定依據；不能以過敏或腎功能欄位替代')
    claimed=check.get('claim_assessment') if check else None
    claim_consistent=bool(check) and claimed in {check['assessment'],'not_stated'}
    if not claim_consistent:
        issues.append('聲明中的個人藥敏類別未與獨立來源核對一致；未知或未測不能支持敏感斷言')
    row['ast_check_validation']={'status':'confirmed' if confirmed and claim_consistent else 'unconfirmed',
        'source_status':'confirmed' if confirmed else 'unconfirmed','claim_status':'consistent' if claim_consistent else 'unconfirmed'}
    if row['basis']!='case_fact':
        from .source_scope import source_scope_issues
        by_id={e['chunk_id']:e for e in data.get('evidence',[])}
        claim_refs=set(claim.get('evidence_refs',[]))
        claim_quotes=[q for q in row['quotes'] if q['chunk_id'] in claim_refs]
        issues.extend(source_scope_issues(row['drug_code'],'infection',claim_quotes,data.get('evidence',[])))
        sources=[by_id[q['chunk_id']] for q in claim_quotes if q['chunk_id'] in by_id]
        anchored=any(named_drug(row['drug_code'],q['quote']) or
                     (by_id.get(q['chunk_id'],{}).get('document_kind')=='drug_label' and
                      named_drug(row['drug_code'],by_id[q['chunk_id']].get('document_title','')))
                     for q in claim_quotes)
        if not claim_quotes:
            issues.append('本聲明沒有選取可核對的引文；請重新分析並明確選取來源段落，不能只列來源識別碼')
        elif not anchored:
            issues.append('選中的引文未辨識本藥，也不是本藥標示；其他藥品的段落不能支持本聲明')
        prose=claim.get('claim','')+' '+row['reason']
        identities=' '.join(str(e.get('document_title',''))+' '+str(e.get('source_url','')) for e in sources)
        if re.search(r'(?<![a-z])WHO(?![a-z])|世界衛生組織',prose,re.I) and not re.search(r'(?<![a-z])WHO(?![a-z])|世界衛生組織|who\.int',identities,re.I):
            issues.append('聲明歸因WHO，但本次選中來源沒有WHO文件')
        if re.search(r'(?<![a-z])DailyMed(?![a-z])',prose,re.I) and not re.search(r'(?<![a-z])DailyMed(?![a-z])|dailymed\.nlm',identities,re.I):
            issues.append('聲明歸因DailyMed，但本次選中來源沒有DailyMed文件')
    row['provenance_issues']=issues
    if issues:
        row['verdict']='uncertain'
        row['reason']+='；'+'；'.join(issues)
