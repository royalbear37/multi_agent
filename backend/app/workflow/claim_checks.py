"""Independent claim-level provenance; never infer clinical applicability."""
from .audit_sources import named_drug
from .risk_details import fact_value
from .source_scope import source_scope_issues
import re

DIMENSIONS={'infection','ast','allergy','renal','interactions'}


def validate_claim_checks(row, claim, data):
    expected={c['dimension']:c for c in claim.get('claims',[])}
    original_complete=len(claim.get('claims',[]))==5 and set(expected)==DIMENSIONS
    checks=row.get('claim_checks',[])
    counts={d:sum(c['dimension']==d for c in checks) for d in DIMENSIONS}
    sources={e['chunk_id']:e for e in data.get('evidence',[])}
    facts={**data.get('facts',{}),'ast_results':data.get('ast_results',[])}
    for check in checks:
        dimension=check['dimension']; original=expected.get(dimension)
        failures=[]
        if not original_complete or not original or counts[dimension]!=1:
            failures.append('缺少唯一的原始分項聲明')
        original=original or {}
        refs=set(check['evidence_refs'])
        quotes=[q for q in row['quotes'] if q['chunk_id'] in refs]
        supplied={q['chunk_id'] for q in quotes}
        if not set(original.get('fact_refs',[])) <= set(check['fact_refs']):
            failures.append('分項聲明的病例欄位未全部核對')
        for path in check['fact_refs']:
            value=fact_value(facts,path)
            if value is None or value=='' or value=={}:
                failures.append('分項引用的病例欄位未提供')
            if path.startswith('ast_results.'):
                item=fact_value(facts,'.'.join(path.split('.')[:2]))
                if not isinstance(item,dict) or item.get('drug_code')!=row['drug_code']:
                    failures.append('引用了其他藥物的 AST')
        if dimension=='ast':
            if row.get('ast_check_validation',{}).get('status')!='confirmed':
                failures.append('獨立 AST 來源尚未確認')
        else:
            failures.extend(source_scope_issues(row['drug_code'],dimension,quotes,data.get('evidence',[]),
                original.get('statement','')+' '+original.get('next_action','')+' '+check['reason']))
            if not refs or not refs <= supplied or not refs <= set(original.get('evidence_refs',[])):
                failures.append('分項聲明缺少已選取的專屬引文')
            if any(sources.get(r,{}).get('document_kind')=='research_article' for r in refs):
                failures.append('群體研究不能單獨支持個人適用性或風險')
            if not any(named_drug(row['drug_code'],q['quote']) or
                (sources.get(q['chunk_id'],{}).get('document_kind')=='drug_label' and
                 named_drug(row['drug_code'],sources[q['chunk_id']].get('document_title',''))) for q in quotes):
                failures.append('分項選段未辨識本藥或本藥標示')
            identities=' '.join(str(sources.get(r,{}).get('document_title',''))+' '+str(sources.get(r,{}).get('source_url','')) for r in refs)
            prose=original.get('statement','')+' '+check['reason']
            for pattern,label in [(r'(?<![a-z])WHO(?![a-z])|世界衛生組織|who\.int','WHO'),(r'(?<![a-z])DailyMed(?![a-z])|dailymed\.nlm','DailyMed')]:
                if re.search(pattern,prose,re.I) and not re.search(pattern,identities,re.I):
                    failures.append('分項來源歸因不符：'+label)
            if dimension=='infection' and any(check[k]!='supported' for k in ('infection_match','population_match','drug_match')):
                failures.append('感染、族群或藥品適用性未通過獨立複核')
        check['validation_issues']=list(dict.fromkeys(failures))
        check['validation_status']='checked'
        if failures: check['verdict']='uncertain'
    complete=original_complete and all(counts[d]==1 for d in DIMENSIONS)
    if row['basis']!='case_fact' and (not complete or any(c['verdict']!='supported' for c in checks)):
        row['verdict']='uncertain'
    row['claim_checks_complete']=complete


def infection_supported(audit):
    checks=[c for c in (audit or {}).get('claim_checks',[]) if c['dimension']=='infection']
    return len(checks)==1 and checks[0].get('validation_status')=='checked' and checks[0]['verdict']=='supported' and not checks[0].get('validation_issues')


def classify_options(run):
    for row in run['drug_assessments']:
        audit=row.get('audit') or {}; ast=row.get('ast') or {}; risk=row.get('clinical') or {}
        supported={c['dimension'] for c in audit.get('claim_checks',[]) if c['verdict']=='supported'}
        known_avoid=risk.get('status')=='avoid' or risk.get('model_status')=='avoid' or any(d.get('status')=='avoid' or d.get('model_status')=='avoid' for d in (risk.get('risk_details') or {}).values())
        ast_ok=(not row['ast_available'] or (ast.get('assessment')=='susceptible' and ast.get('source_validation',{}).get('status')=='confirmed'))
        is_option=row['status']=='pending' and infection_supported(audit) and ast_ok and not known_avoid
        row['result_tier']='candidate' if row['status']=='reviewable' else 'review_option' if is_option else 'pending' if row['status']=='pending' else row['status']
        blockers=[]
        if known_avoid: blockers.append({'kind':'reported_avoid','detail':'臨床 Agent 回報避用風險；未複核部分仍待確認，不能提升為待審閱選項'})
        for node in run['nodes']:
            if node.get('agent_id') and row['drug_code'] in node.get('unresolved_drugs',[]):
                blockers.append({'kind':'model_output_incomplete','agent_id':node['agent_id'],'detail':'模型回覆格式或引用尚未補齊'})
        for issue in run.get('confirmation_items', []):
            if (issue.get('agent_id') in {'case_agent', 'clinical_agent'} and issue.get('blocking')
                    and issue.get('drug_code') in (None, row['drug_code'])):
                blockers.append({'kind':'assessment_unconfirmed','agent_id':issue['agent_id'],
                                 'detail':issue['impact']})
        for group in run.get('evidence_coverage',[]):
            if group.get('drug_code') not in (None,row['drug_code']): continue
            kind='retrieval_failed' if group['retrieval_status'] not in {'ok','no_results'} else 'retrieval_empty' if not group['retrieved_count'] else 'input_omitted' if group['omitted_count'] else None
            if kind: blockers.append({'kind':kind,'dimension':group.get('dimension'),'detail':'查詢或輸入片段尚未完整提供'})
            if group.get('unsent_count'):
                blockers.append({'kind':'input_not_sent','dimension':group.get('dimension'),
                                 'detail':'已準備的片段尚未納入此藥的模型呼叫；請查看執行預算或輸入錯誤'})
        for dimension,detail in (risk.get('risk_details') or {}).items():
            if detail.get('missing_fields'): blockers.append({'kind':'case_data_missing','dimension':dimension,'detail':'、'.join(detail['missing_fields'])})
            if detail.get('status')=='unknown': blockers.append({'kind':'risk_unconfirmed','dimension':dimension,'detail':detail['reason']})
        if risk and not risk.get('quotes'):
            blockers.append({'kind':'model_citation_missing','agent_id':'clinical_agent','detail':'臨床回覆沒有選取引文；不代表病例或文件不存在'})
        if audit and audit.get('basis')!='case_fact' and not audit.get('quotes'):
            blockers.append({'kind':'model_citation_missing','agent_id':'evidence_audit','detail':'複核回覆沒有選取引文；無法核對其支持聲明'})
        if not infection_supported(audit): blockers.append({'kind':'citation_unsupported','dimension':'infection','detail':'感染適用性尚未通過獨立複核'})
        for check in audit.get('claim_checks',[]):
            if check['dimension']!='infection' and (check['verdict']!='supported' or check.get('validation_issues')):
                blockers.append({'kind':'citation_unsupported','dimension':check['dimension'],
                    'detail':'；'.join(check.get('validation_issues') or [check['reason']])})
        if not ast_ok: blockers.append({'kind':'ast_unconfirmed','dimension':'ast','detail':'藥敏來源缺漏、衝突或非敏感判讀'})
        row['blockers']=blockers
    codes={r['drug_code'] for r in run['drug_assessments'] if r['result_tier']=='review_option'}
    run['output']['review_options']=[dict(x) for x in run['output']['pending'] if x['drug_code'] in codes]
