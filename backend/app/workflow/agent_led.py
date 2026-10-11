"""Agent-led workflow. Engineering validation only; deliberately no RuleEngine."""
from __future__ import annotations
import copy
import json
import re
import time
import uuid
from pydantic import ValidationError
from app.agents import runtime_led as runtime
from app.agents.runtime_v2 import redact, setting
from app.providers.service import ProviderError
from .v2 import digest, sum_usage, utc
from .risk_details import validate_risk_details, caution_ready, fact_value
from .ast_sources import validate_ast_sources
from .claim_checks import validate_claim_checks, classify_options
from .partial_agents import validate_partial, merge_partial
from .input_context import compact_sources, assessment_source_refs
from .source_scope import source_scope_issues
from .time_budget import TimeBudget
from .audit_context import fit_audit_context
from .physician_candidates import add_physician_candidates


def text_key(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def evidence_groups(retrievals, selected_ids, stages):
    groups=[]
    for retrieval in retrievals:
        if retrieval.get('stage') not in stages:
            continue
        found=list(dict.fromkeys(retrieval.get('chunk_ids', [])))
        selected=[cid for cid in found if cid in selected_ids]
        groups.append(dict(stage=retrieval.get('stage'),drug_code=retrieval.get('drug_code'),
            dimension=retrieval.get('dimension'),
            retrieval_status=retrieval.get('status'),evidence_refs=selected,
            warnings=list(retrieval.get('warnings', [])),
            retrieved_count=len(found),selected_count=len(selected),
            omitted_count=len(found)-len(selected),
            omitted_refs=[cid for cid in found if cid not in selected_ids]))
    return groups


def check_quotes(items, evidence):
    sources = {x['chunk_id']: x['text'] for x in evidence}
    return bool(items) and all(q['quote'].strip() and q['chunk_id'] in sources and
        ' '.join(q['quote'].split()) in ' '.join(sources[q['chunk_id']].split()) for q in items)


def facts_from(case):
    fields = ('demographics', 'encounter', 'renal', 'allergies', 'microbiology',
              'medications', 'medication_history_status', 'rapid_identification', 'clinical_history', 'vitals',
              'resistance_context', 'data_origin')
    return redact({**{k: copy.deepcopy(case.get(k)) for k in fields},
                   'simulated_fields': copy.deepcopy(case.get('provenance', {}).get('simulated_fields', []))})


def synthesis_assessments(outputs):
    """Integrate attributed assessments; original quotes remain in prior nodes/snapshot.

    Repeating each full selected passage in both specialist reports and evidence
    can exceed the request budget even for 18 drugs. The independent audit still
    receives original excerpts, never these earlier support verdicts.
    """
    result = {}
    for role in ('case_agent', 'ast_agent', 'evidence_agent', 'clinical_agent'):
        assessment = copy.deepcopy(outputs.get(role, {'unavailable': True}))
        # Generic role summaries can contradict source-checked drug rows. The
        # integrator already has original case facts and the structured reports.
        assessment.pop('findings',None)
        if role=='ast_agent' and any(r.get('source_validation',{}).get('status')=='unconfirmed' for r in assessment.get('drugs',[])):
            assessment.pop('rapid_assessment',None)
            assessment.pop('resistance_assessment',None)
            assessment['source_linkage_notice']='部分藥敏類別來源未核對；依逐藥結果及原始病例事實確認，不能從其他摘要推定敏感性。'
        for row in assessment.get('drugs', []):
            # Invalid original assertions stay in the trace, not in downstream
            # clinical reasoning as competing conclusions.
            row.pop('model_reason',None)
            row.pop('model_assessment',None)
            if 'quotes' in row:
                row['evidence_refs'] = list(dict.fromkeys(q['chunk_id'] for q in row.pop('quotes')))
        result[role] = assessment
    return result


def validate_output(agent, raw, data):
    result = agent.output_type.model_validate(raw).model_dump(mode='json')
    original_risks={r['drug_code']:copy.deepcopy(r) for r in result.get('drugs',[])} if agent.id=='clinical_agent' else {}
    if redact(result) != result:
        raise ValueError('secret-like output')
    expected_codes = set(data['drugs'])
    if any(i['drug_code'] is not None and i['drug_code'] not in expected_codes for i in result.get('issues', [])):
        raise ValueError('issue refers to unknown drug')
    if agent.id == 'case_agent':
        described = {i['field'] for i in result['issues']}
        for field in result['missing_fields']:
            if field not in described:
                result['issues'].append({'field': field, 'impact': '病例 Agent 列為缺漏，尚未說明對決策的影響', 'action': '補齊資料或重新分析確認影響', 'drug_code': None, 'blocking': True})
    # Source quotes may contain label regimens; generated prose may not prescribe.
    prescription = re.compile(r'(?i)(?:每日|每天|每次|服用|給予|take|administer).{0,30}\d+\s*(?:mg|mcg|g|錠|顆)|\b\d+\s*(?:mg|mcg)\b(?!\s*/\s*(?:dL|L|kg))|\b(?:bid|tid|qid|q\d+h)\b')
    def clean(value, key=''):
        if key == 'quotes': return value
        if isinstance(value, str) and prescription.search(value): return '此段含超出本系統範圍的給藥指示，已隔離；需重新核對。'
        if isinstance(value, list): return [clean(v) for v in value]
        if isinstance(value, dict): return {k: clean(v,k) for k,v in value.items()}
        return value
    cleaned = clean(result)
    for before, after in zip(result.get('drugs', []), cleaned.get('drugs', [])):
        if before != after:
            if agent.id == 'synthesis_agent': after['status'] = 'pending'
            elif agent.id == 'clinical_agent': after['status'] = 'unknown'
            elif agent.id == 'evidence_agent': after['status'] = 'uncertain'
            elif agent.id == 'evidence_audit': after['verdict'] = 'uncertain'
    result = cleaned
    rows = result.get('drugs', [])
    codes = [x['drug_code'] for x in rows]
    if len(codes) != len(set(codes)):
        raise ValueError('duplicate drug')
    expected = {x['drug_code'] for x in data['claims']} if agent.id == 'evidence_audit' else set(data['drugs'])
    if agent.id != 'case_agent' and not expected <= set(codes):
        raise ValueError('missing per-drug assessment')
    if agent.id != 'evidence_agent' and not set(codes) <= expected:
        raise ValueError('unknown drug')
    evidence_ids = {x['chunk_id'] for x in data['evidence']}
    research_ids = {x['chunk_id'] for x in data['evidence'] if x.get('document_kind') == 'research_article'}
    for row in rows:
        if agent.id=='clinical_agent':
            original=original_risks[row['drug_code']]
            row['model_status']=original['status']
            for dimension,detail in (row.get('risk_details') or {}).items():
                detail['model_status']=original['risk_details'][dimension]['status']
        if agent.id == 'ast_agent': validate_ast_sources(row,data)
        if row.get('quotes') and not check_quotes(row['quotes'], data['evidence']):
            original_count = len(row['quotes'])
            row['quotes'] = [q for q in row['quotes'] if check_quotes([q], data['evidence'])]
            row['citation_validation'] = {'valid_count': len(row['quotes']), 'invalid_count': original_count-len(row['quotes'])}
            row['reason'] += '；引用原文無法核對，需確認。'
            if agent.id == 'evidence_audit': row['verdict'] = 'uncertain'
            elif agent.id == 'clinical_agent': row['status'] = 'unknown'
            elif agent.id == 'evidence_agent': row['status'] = 'uncertain'
        if agent.id == 'evidence_agent':
            source_issues=source_scope_issues(row['drug_code'],'infection',row['quotes'],data['evidence'])
            if source_issues:
                row['status']='uncertain'
                row['source_validation']={'status':'unconfirmed','issues':source_issues}
                row['reason']+='；'+'；'.join(source_issues)
            if row['drug_code'] not in (data.get('original_drugs') if data.get('original_drugs') is not None else expected):
                # Additional choices must be named in a real quote, not invented identifiers.
                named = bool(text_key(row['drug_name'])) and any(text_key(row['drug_name']) in text_key(q['quote']) for q in row['quotes'])
                if not named or text_key(row['drug_code']) != text_key(row['drug_name']):
                    raise ValueError('additional drug not anchored to document')
            if row['status'] == 'supported' and not row['quotes']:
                row['status'] = 'uncertain'
        if agent.id == 'clinical_agent' and not row['quotes']:
            row['status'] = 'unknown'
        if row.get('quotes') and any(q['chunk_id'] in research_ids for q in row['quotes']):
            if agent.id == 'evidence_agent' and row['status'] == 'supported':
                row['status'] = 'uncertain'
                row['reason'] += '；本流程研究文章用於背景，不能單獨作為本例用藥支持。'
            if agent.id == 'clinical_agent' and row['status'] == 'no_identified_risk':
                row['status'] = 'unknown'
                row['reason'] += '；群體研究不能單獨確認個人無風險。'
            if agent.id == 'evidence_audit':
                row['verdict'] = 'uncertain'
                row['reason'] += '；研究背景引文不能作為本流程逐藥適用性支持，需重新核對聲明與指引／標示。'
        if agent.id == 'clinical_agent': validate_risk_details(row, data)
        if agent.id == 'clinical_agent' and (row['status'] in {'no_identified_risk', 'caution'} or
                ((row.get('risk_details') or {}).get('allergy') or {}).get('status') in {'no_identified_risk', 'caution'}):
            # Consistency guard, not a cross-allergy or clinical exclusion rule:
            # a direct serious/confirmed label cannot silently become no risk.
            for label in data.get('facts', {}).get('allergies', {}).get('items', []):
                same_drug = text_key(label.get('drug_code')) == text_key(row['drug_code'])
                severity = str(label.get('severity') or '').strip().casefold()
                reaction = str(label.get('reaction') or '').casefold()
                serious = severity in {'severe', '嚴重', '重度'} or 'anaphylaxis' in reaction or '過敏性休克' in reaction
                if same_drug and label.get('verification_status') != 'ruled_out' and (serious or label.get('verification_status') == 'confirmed'):
                    row['status'] = 'unknown'
                    row['reason'] += '；同藥的已確認或嚴重過敏紀錄與「未發現風險」矛盾，需人工核對。'
                    if row.get('risk_details'):
                        row['risk_details']['allergy'].update(status='unknown', next_action='核對同藥原始反應與既有評估紀錄')
                        row['risk_details']['allergy']['reason'] += '；同藥過敏紀錄與分項結論矛盾。'
                        row['allergy'] = row['risk_details']['allergy']['reason']
                    result['issues'].append({'field':'allergies.items','drug_code':row['drug_code'],
                        'impact':'既有同藥過敏紀錄與風險結論矛盾','action':'核對原反應及既有評估，補充病例後重新分析','blocking':True})
        if agent.id == 'evidence_audit':
            claim = next(c for c in data['claims'] if c['drug_code']==row['drug_code'])
            if row['basis'] != 'case_fact' and 'evidence_refs' in claim:
                claim_refs=set(claim['evidence_refs'])
                quoted_refs={q['chunk_id'] for q in row['quotes']}
                if not claim_refs or not claim_refs & quoted_refs:
                    row['verdict']='uncertain'
                    row['reason']+='；本聲明缺少已核對的專屬引用；其他藥品或風險警語引用不能替代此聲明的來源。'
            required_facts = set(claim.get('fact_refs', []))
            if required_facts and (row['basis']=='document' or not required_facts <= set(row['fact_refs'])):
                row['verdict'] = 'uncertain'
                row['reason'] += '；聲明中的病例欄位尚未全部核對，文件引文不能替代。'
            if row['basis'] != 'case_fact':
                if row['verdict'] == 'supported' and not row['quotes']: row['verdict'] = 'uncertain'
                matches = [row[k] for k in ('infection_match','population_match','drug_match')]
                if any(value != 'supported' for value in matches):
                    row['verdict'] = 'unsupported' if 'unsupported' in matches else 'uncertain'
            if row['basis'] in {'case_fact', 'mixed'}:
                source = {**data.get('facts', {}), 'ast_results':data.get('ast_results', [])}
                if not row['fact_refs'] or any(fact_value(source,p) in (None,'',{}) for p in row['fact_refs']):
                    row['fact_match'] = 'uncertain'
                for path in row['fact_refs']:
                    if path.startswith('ast_results.'):
                        parts = path.split('.')
                        item = fact_value(source, '.'.join(parts[:2]))
                        if not isinstance(item, dict) or item.get('drug_code') != row['drug_code']:
                            row['fact_match'] = 'uncertain'
                    elif path == 'ast_results' and source['ast_results']:
                        row['fact_match'] = 'uncertain'
                    elif row['basis']=='case_fact' and path in {'allergies','allergies.items'} and (source.get('allergies') or {}).get('items'):
                        row['fact_match'] = 'uncertain'
                        row['reason'] += '；藥品過敏聲明需指向具體紀錄，不能只引用整份過敏清單。'
                    elif row['basis']=='case_fact' and path.startswith('allergies.items.'):
                        item = fact_value(source, '.'.join(path.split('.')[:3]))
                        if not isinstance(item,dict) or text_key(item.get('drug_code')) != text_key(row['drug_code']):
                            row['fact_match'] = 'uncertain'
                            row['reason'] += '；其他藥品的過敏紀錄不能單憑病例欄位推定為本藥過敏。'
                if row['fact_match'] != 'supported':
                    row['verdict'] = 'unsupported' if row['fact_match'] == 'unsupported' else 'uncertain'
            required_risks = {r['dimension']:r for r in claim.get('risk_claims', [])}
            checks = {r['dimension']:r for r in row['risk_checks']}
            if len(checks) != len(row['risk_checks']) or set(checks) != set(required_risks):
                row['verdict'] = 'uncertain'
                row['reason'] += '；分項風險與注意事項尚未全部獨立複核。'
            source = {**data.get('facts', {}), 'ast_results':data.get('ast_results', [])}
            quoted = {q['chunk_id'] for q in row['quotes']} - research_ids
            for dimension, check in checks.items():
                required = required_risks.get(dimension, {})
                check['validation_issues']=source_scope_issues(row['drug_code'],dimension,
                    [q for q in row['quotes'] if q['chunk_id'] in check['evidence_refs']],data['evidence'],
                    required.get('statement','')+' '+required.get('next_action','')+' '+check['reason'])
                if check['validation_issues']: check['verdict']='uncertain'
                if (not check['evidence_refs'] or not set(check['evidence_refs']) <= quoted or
                    not set(required.get('fact_refs', [])) <= set(check['fact_refs']) or
                    any(fact_value(source,p) in (None,'',{}) for p in check['fact_refs'])):
                    check['verdict'] = 'uncertain'
                if check['verdict'] != 'supported':
                    row['verdict'] = 'uncertain'
                    row['reason'] += f'；{dimension} 風險／注意事項尚未獲得支持。'
            from .audit_sources import validate_audit_sources
            validate_audit_sources(row,claim,data)
            if data.get('atomic_claims_required') or claim.get('claims'):
                validate_claim_checks(row,claim,data)
        if 'evidence_refs' in row and not set(row['evidence_refs']) <= evidence_ids:
            row['reference_validation']={'status':'unconfirmed','invalid_refs':[ref for ref in row['evidence_refs'] if ref not in evidence_ids]}
            row['model_reason']=row['reason']
            row['evidence_refs'] = []
            row['status'] = 'pending'
            row['reason'] = '整合回覆的引用識別碼無法核對，需重新分析；這不代表病例缺資料或藥品不適用。'
    return result


def execute(case, provider_kind, document_service, run_id, checkpoint=None):
    start = time.perf_counter()
    facts = facts_from(case)
    ast = redact(copy.deepcopy(case.get('ast_results', [])))
    drugs = list(dict.fromkeys(x['drug_code'] for x in ast))
    run = dict(run_id=run_id, case_id=case['case_id'], case_snapshot=copy.deepcopy(case),
        mode='multi-agent', decision_basis='agent', provider_kind=provider_kind,
        is_mock=provider_kind == 'mock', status='running', gate_status='needs_confirmation',
        versions={'workflow': runtime.VERSION, 'agent_contract': runtime.VERSION},
        nodes=[], errors=[], rule_evaluations=[], evidence_snapshots=[], retrievals=[],
        missing_fields=[], drug_assessments=[], output=None, safety_summary={'avoid': [], 'limitations': []})
    outputs = {}
    calls = 0
    max_calls = setting('LLM_V2_MAX_CALLS', 8, 6, 8)
    # Six specialist calls plus retrieval need their own budget. Legacy V2's
    # common 120-second deployment setting must not silently truncate this flow.
    timeout_seconds = setting('LLM_AGENT_LED_TIMEOUT_SECONDS', 780, 10, 900)
    budget = TimeBudget(start, timeout_seconds, runtime.AGENTS)
    deadline = budget.deadline
    run['budget'] = {'timeout_seconds': timeout_seconds, 'max_calls': max_calls,
        'reserved_role_seconds':dict(zip((a.id for a in runtime.AGENTS),budget.reservations)),
        'policy':'reserve_remaining_roles_before_retrieval_or_retry'}
    run['evidence_selection'] = []

    def save():
        run['agent_execution'] = {'workflow_version': runtime.VERSION, 'calls': calls, 'max_calls': max_calls}
        if checkpoint: checkpoint(copy.deepcopy(run))

    def retrieve(query, limit=3, stage='infection', drug=None, dimension=None):
        retrieval_start = time.perf_counter()
        search_bound = getattr(getattr(document_service,'embedding_provider',None),'timeout',30) if getattr(document_service,'retrieval_mode','lexical')=='embedding' else 1
        if budget.available(time.perf_counter(),agent_index,retrieval=True) < search_bound + 1:
            run['retrievals'].append({'query': query, 'stage':stage, 'drug_code':drug,'dimension':dimension,
                'chunk_ids':[], 'status': 'budget_reserved', 'count': 0,'warnings':['time_reserved_for_remaining_agents']})
            return
        try:
            search = getattr(document_service, 'search_agent_context', None) or getattr(document_service, 'search_with_context', None) or getattr(document_service, 'search', None)
            extra = {'stage': stage, 'drug_code': drug,
                'deadline':deadline-sum(budget.reservations[agent_index:])} if hasattr(document_service, 'search_agent_context') else {}
            result = search(query, limit=limit, policy_refs=case.get('policy_refs'), scope=case.get('evidence_scope', 'synthetic'), **extra) if search else {'status': 'not_configured', 'evidence': []}
        except Exception:
            result = {'status': 'failed', 'evidence': []}
        run['retrievals'].append({'query': query, 'stage': stage, 'drug_code': drug, 'dimension':dimension, 'chunk_ids': [e['chunk_id'] for e in result.get('evidence', [])], 'primary_ids':[e['chunk_id'] for e in result.get('evidence',[]) if not e.get('context_for')], 'status': result.get('status'), 'count': len(result.get('evidence', [])), 'method': result.get('retrieval_method'), 'warnings': result.get('warnings', []), 'elapsed_ms': round((time.perf_counter()-retrieval_start)*1000, 3)})
        existing = {x['chunk_id'] for x in run['evidence_snapshots']}
        for item in result.get('evidence', []):
            if item['chunk_id'] not in existing:
                run['evidence_snapshots'].append(copy.deepcopy(item))
                existing.add(item['chunk_id'])

    def evidence_for(role, codes=None):
        evidence = run['evidence_snapshots']
        if role == 'synthesis_agent':
            used_refs = assessment_source_refs(outputs)
            evidence = [e for e in evidence if e['chunk_id'] in used_refs]
            run['evidence_selection'].append({'agent_id':role,'available_chunks':len(evidence),
                'selected_chunks':len(evidence),'omitted_chunks':0,'characters':0,'source_text_sent':False})
            return [{k:e[k] for k in ('chunk_id','doc_id','is_synthetic','document_title','document_version','location','document_kind','population','jurisdiction','source_document_id') if k in e} for e in evidence]
        # Keep context bounded without modifying the original quote text.
        stage = 'clinical' if role == 'clinical_agent' else 'infection'
        stages = {'clinical', 'background'} if stage == 'clinical' else {'infection', 'guideline_options'}
        relevant=[r for r in run['retrievals'] if r.get('stage') in stages]
        pools=[r.get('primary_ids',r.get('chunk_ids',[])) for r in relevant]
        neighbors=[[cid for cid in r['chunk_ids'] if cid not in r.get('primary_ids',r['chunk_ids'])] for r in relevant]
        order=list(dict.fromkeys(cid for batches in (pools,neighbors) for index in range(max((len(p) for p in batches),default=0)) for pool in batches for cid in pool[index:index+1]))
        indexed = {e['chunk_id']: e for e in evidence}
        ranked = [indexed[cid] for cid in order if cid in indexed]
        chosen, size, context_size = [], 0, 2
        for e in ranked:
            cost = len(json.dumps(compact_sources([e])[0], ensure_ascii=False)) + 2
            # Include titles, locations and source identity in the selection
            # budget, reserving space for case facts and per-query coverage.
            if size + len(e['text']) <= 65000 and context_size + cost <= 120000:
                chosen.append(copy.deepcopy(e)); size += len(e['text']); context_size += cost
        run['evidence_selection'].append({'agent_id': role, 'available_chunks': len(ranked), 'selected_chunks': len(chosen), 'omitted_chunks': len(ranked)-len(chosen), 'characters': size, 'context_characters': context_size})
        return chosen

    from .engine import evidence_query
    query = evidence_query(case)
    for agent_index, agent in enumerate(runtime.AGENTS):
        if agent.id == 'evidence_agent':
            retrieve(query, 8)
            retrieve(query + ' recommended first choice alternative antibiotics', 4, stage='guideline_options')
            for drug in drugs[:30]: retrieve(query + ' ' + drug.replace('_', ' '), 2, drug=drug)
        if agent.id == 'clinical_agent':
            for drug in drugs[:30]:
                active = ' '.join(str(m.get('drug_code', '')) for m in case.get('medications', []) if m.get('status') == 'active')
                for dimension,terms in [('allergy','contraindications hypersensitivity allergy'),('renal','renal impairment creatinine clearance precautions'),('interactions','drug interactions '+active)]:
                    retrieve(drug.replace('_',' ')+' '+terms,2,stage='clinical',drug=drug,dimension=dimension)
            if case.get('allergies', {}).get('items'):
                retrieve('antibiotic allergy labels confirmation observational study', 2, stage='background')
        role_facts = copy.deepcopy(facts)
        if agent.id != 'ast_agent': role_facts.pop('resistance_context', None)
        data = dict(facts=role_facts, ast_results=ast, drugs=drugs, original_drugs=list(drugs), evidence=[], assessments={}, claims=[])
        data['risk_details_required'] = agent.id == 'clinical_agent'
        data['ast_sources_required'] = agent.id == 'ast_agent'
        data['audit_sources_required'] = agent.id == 'evidence_audit'
        data['atomic_claims_required'] = agent.id == 'evidence_audit'
        if agent.id == 'ast_agent': data['drugs'] = list(dict.fromkeys(x['drug_code'] for x in ast))
        if agent.id in {'evidence_agent', 'clinical_agent', 'synthesis_agent'}: data['evidence'] = evidence_for(agent.id, drugs)
        selected_ids = {e['chunk_id'] for e in data['evidence']}
        stages=({'clinical','background'} if agent.id=='clinical_agent' else
                {'infection','guideline_options'} if agent.id=='evidence_agent' else set())
        groups = evidence_groups(run['retrievals'],selected_ids,stages)
        data['evidence_groups'] = [{k:v for k,v in g.items() if k!='omitted_refs'} for g in groups]
        if stages:
            run.setdefault('evidence_coverage',[]).extend(
                dict(agent_id=agent.id,**group) for group in groups)
        if agent.id == 'synthesis_agent': data['assessments'] = synthesis_assessments(outputs)
        if agent.id == 'evidence_audit':
            proposed = outputs.get('synthesis_agent', {}).get('drugs', [])
            data['claims'] = [{'drug_code':x['drug_code'], 'claim':x['reason'], 'fact_refs':x.get('fact_refs', []),
                'evidence_refs':x.get('evidence_refs',[]),
                'claims':x.get('claims',[]),
                'ast_available':any(a['drug_code']==x['drug_code'] for a in ast)} for x in proposed]
            clinical_rows = {r['drug_code']:r for r in outputs.get('clinical_agent', {}).get('drugs', [])}
            for claim, decision in zip(data['claims'], proposed):
                details = (clinical_rows.get(claim['drug_code'], {}).get('risk_details') or {})
                claim['risk_claims'] = [dict(dimension=k, statement=d['reason'], next_action=d['next_action'],
                    fact_refs=d['fact_refs'],evidence_refs=d['evidence_refs']) for k,d in details.items()
                    if d['status'] != 'unknown' and (decision['status']=='reviewable' or d['status'] in {'caution','avoid'})]
            refs = {r for x in proposed for r in x['evidence_refs']}
            refs.update(r for x in proposed for c in x.get('claims',[]) for r in c['evidence_refs'])
            refs.update(r for claim in data['claims'] for detail in claim['risk_claims'] for r in detail['evidence_refs'])
            data['evidence'] = [x for x in run['evidence_snapshots'] if x['chunk_id'] in refs]
            data['drugs'] = [x['drug_code'] for x in data['claims']]
            data['facts'] = {k:v for k,v in role_facts.items() if k in ('demographics','encounter','clinical_history','microbiology','renal','allergies','medications','medication_history_status')}
            data['ast_results'] = ast  # Preserve source indexes used by fact_refs.
        # Enforce the existing input cap on the context we actually need, not
        # duplicated storage metadata. Full provenance remains in run snapshots.
        data['evidence'] = compact_sources(data['evidence'])
        if agent.id == 'evidence_audit':
            data = agent.input_type.model_validate(data).model_dump(mode='json')
            available = len(data['evidence'])
            data = fit_audit_context(data)
            run['evidence_selection'].append({'agent_id':agent.id,'available_chunks':available,
                'selected_chunks':len(data['evidence']),'omitted_chunks':available-len(data['evidence']),
                'characters':sum(len(e.get('text','')) for e in data['evidence'])})
            run.setdefault('evidence_coverage', []).extend(dict(agent_id=agent.id, **g) for g in data['evidence_groups'])
        node = {'node_id': agent.id, 'agent_id': agent.id, 'workflow_version': runtime.VERSION,
            'status': 'running', 'started_at': utc(), 'span_id': str(uuid.uuid4()),
            'depends_on': list(agent.dependencies), 'attempts': [], 'errors': [],
            'input': data, 'output': None, 'input_schema': 'Input', 'output_schema': agent.output_type.__name__,
            'prompt_version': runtime.VERSION, 'prompt_hash': digest(agent.common + agent.instruction),
            'input_hash': digest(data), 'rule_refs': [], 'evidence_refs': [x['chunk_id'] for x in data['evidence']],
            'is_mock': provider_kind == 'mock', 'provider_kind': provider_kind}
        run['nodes'].append(node)
        if agent.id == 'evidence_audit' and not data['claims']:
            node.update(status='not_applicable',finished_at=utc(),elapsed_ms=0,
                output={'findings':['沒有可複核聲明；未呼叫模型，不算複核通過。'],'issues':[],'drugs':[]},
                skip_reason='no_claims')
            save()
            continue
        tick = time.perf_counter()
        retained=None; unresolved=[]
        try:
            data = agent.input_type.model_validate(data).model_dump(mode='json')
            if len(json.dumps(data, ensure_ascii=False)) > 180000: raise ProviderError('AGENT_INPUT_TOO_LARGE')
            provider = runtime.Provider(provider_kind, agent)
            node['model'] = provider.model
            provider.check(case, data)
            for attempt_no in range(2):
                now = time.perf_counter()
                call_timeout = budget.call_timeout(now,agent_index,agent.max_timeout_seconds)
                if calls >= max_calls: raise ProviderError('AGENT_BUDGET_EXCEEDED')
                if call_timeout < 1: raise ProviderError('AGENT_TIME_RESERVED')
                call_deadline = now + call_timeout
                calls += 1
                attempt = {'attempt': attempt_no + 1, 'status': 'running', 'started_at': utc()}
                attempt['requested_drugs']=list(data['drugs'])
                attempt['validation_feedback']=list(data.get('validation_feedback',[]))
                attempt['timeout_seconds']=call_timeout
                attempt['reserved_downstream_seconds']=sum(budget.reservations[agent_index+1:])
                node['attempts'].append(attempt)
                save()
                try:
                    reply = provider.complete(agent, copy.deepcopy(data), timeout=call_timeout)
                    attempt.update(usage=reply.get('usage'), response_id=reply.get('response_id'), finish_reason=reply.get('finish_reason'), output_token_limit=reply.get('output_token_limit'))
                    if time.perf_counter() > call_deadline: raise ProviderError('AGENT_STAGE_TIMEOUT')
                    if reply.get('finish_reason') == 'length':
                        raise ProviderError('AGENT_OUTPUT_TRUNCATED')
                    if reply.get('citation_aliases') is not None:
                        attempt.update(citation_aliases=reply['citation_aliases'], request_input_hash=reply['request_input_hash'])
                        attempt['citation_spans'] = reply.get('citation_spans', {})
                    output, diagnostics, unresolved = validate_partial(agent,reply.get('output'),data,validate_output)
                    diagnostics=list(reply.get('wire_errors',[]))+diagnostics
                    if time.perf_counter() > deadline: raise ProviderError('AGENT_BUDGET_EXCEEDED')
                    retained=merge_partial(retained,output)
                    attempt.update(status='completed', validation_status='partial' if diagnostics else 'valid', validation_details=diagnostics[:30])
                    roles_left=len(runtime.AGENTS)-agent_index-1
                    retry_time=budget.available(time.perf_counter(),agent_index)
                    if diagnostics and attempt_no==0 and max_calls-calls>roles_left and retry_time>=1:
                        data['validation_feedback']=diagnostics[:30]
                        if unresolved:
                            data['drugs']=unresolved
                            data['claims']=[c for c in data['claims'] if c['drug_code'] in unresolved]
                        continue
                    if diagnostics and retry_time<1: node['retry_skipped_reason']='time_reserved_for_remaining_agents'
                    break
                except (ProviderError, ValidationError, ValueError, TypeError, KeyError) as exc:
                    if hasattr(exc, 'usage'):
                        attempt.update(usage=exc.usage, response_id=exc.response_id)
                    attempt.update(status='failed', validation_status='invalid', error_code=getattr(exc, 'code', 'AGENT_SCHEMA_INVALID'))
                    diagnostics = [f"{'.'.join(map(str,e['loc']))}: {e['type']}" for e in exc.errors(include_input=False,include_context=False)] if isinstance(exc,ValidationError) else getattr(exc, 'validation_details', [getattr(exc,'code',type(exc).__name__)])
                    attempt['validation_details'] = diagnostics[:30]
                    data['validation_feedback'] = diagnostics[:30]
                    roles_left = len(runtime.AGENTS) - agent_index - 1
                    if attempt_no == 1 or max_calls - calls <= roles_left or budget.available(time.perf_counter(),agent_index)<1 or isinstance(exc, ProviderError) and not exc.retryable:
                        if retained is not None: break
                        raise
                finally: attempt['finished_at'] = utc()
            output=retained
            if output is None: raise ValueError('no valid agent content')
            outputs[agent.id] = output
            uncertain = output.get('issues') or any(x.get('status') in {'uncertain','unknown','pending','caution'} or x.get('assessment') in {'unknown','conflicting'} or x.get('verdict') in {'uncertain','unsupported'} for x in output.get('drugs', []))
            node.update(output=output, output_hash=digest(output), unresolved_drugs=unresolved, status='needs_confirmation' if uncertain or unresolved else 'completed')
            if unresolved:
                node['errors'].append({'code':'AGENT_PARTIAL_INVALID','drugs':unresolved})
                run['errors'].append({'node_id':agent.id,'code':'AGENT_PARTIAL_INVALID','drugs':unresolved})
            if agent.id == 'case_agent': run['missing_fields'] = output['missing_fields']
            if agent.id == 'evidence_agent': drugs = list(dict.fromkeys(drugs + [x['drug_code'] for x in output['drugs']]))
        except Exception as exc:
            code = getattr(exc, 'code', 'AGENT_SCHEMA_INVALID')
            node.update(status='failed', errors=[{'code': code}], input=None, content_withheld=True)
            run['errors'].append({'node_id': agent.id, 'code': code})
        node.update(finished_at=utc(), elapsed_ms=round((time.perf_counter()-tick)*1000, 3), usage=sum_usage(node['attempts']), retry_count=max(0, len(node['attempts'])-1))
        save()

    by_role = {role: {x['drug_code']: x for x in out.get('drugs', [])} for role, out in outputs.items()}
    evidence_ids = {x['chunk_id'] for x in run['evidence_snapshots']}
    decisions = by_role.get('synthesis_agent', {})
    for drug in drugs:
        decision = copy.deepcopy(decisions.get(drug, {'drug_code': drug, 'status': 'pending', 'reason': '整合評估未完成', 'evidence_refs': [], 'disagreements': []}))
        ast_review = by_role.get('ast_agent', {}).get(drug)
        support = by_role.get('evidence_agent', {}).get(drug)
        risk = by_role.get('clinical_agent', {}).get(drug)
        audit = by_role.get('evidence_audit', {}).get(drug)
        blockers = []
        if not support or support['status'] != 'supported': blockers.append('文件支持未確認')
        if not risk or risk['status'] in {'unknown', 'avoid'} or (risk['status'] == 'caution' and not caution_ready(risk)):
            blockers.append('臨床風險未解決')
        if any(i.get('blocking') and i.get('drug_code') in (None, drug) for i in outputs.get('clinical_agent', {}).get('issues', [])):
            blockers.append('臨床風險仍有關鍵待確認事項')
        if ast_review and ast_review['assessment'] != 'susceptible': blockers.append('藥敏 Agent 留有不適用或不確定判斷')
        if not ast_review and drug in {x['drug_code'] for x in ast}: blockers.append('藥敏評估未完成')
        if not audit or audit['verdict'] != 'supported': blockers.append('引用複核未通過')
        if not audit or not audit.get('claim_checks_complete'): blockers.append('分項聲明尚未全部複核')
        if audit and audit.get('basis') == 'case_fact': blockers.append('病例事實核對不能取代適用性文件支持')
        if any(i.get('blocking') and i.get('drug_code') in (None, drug) for i in outputs.get('case_agent', {}).get('issues', [])) or 'case_agent' not in outputs: blockers.append('病例資料需確認')
        if decision['status'] == 'reviewable' and blockers:
            decision['status'] = 'pending'
            decision['reason'] += '；' + '；'.join(blockers)
        elif decision['status'] in {'avoid', 'not_selected'} and (not audit or audit['verdict'] != 'supported'):
            decision['status'] = 'pending'
            decision['reason'] += '；排除／未選理由尚未通過獨立複核，不能當成已確認不適用。'
        if decision['status'] == 'reviewable':
            decision['evidence_refs'] = list(dict.fromkeys(q['chunk_id'] for q in audit['quotes']))
        tested = drug in {x['drug_code'] for x in ast}
        if not tested: decision['reason'] += '；本例未測此藥 AST，不代表敏感。'
        decision.update(ast_available=tested, ast=ast_review, evidence=support, clinical=risk, audit=audit,
            source_ast=[x for x in ast if x['drug_code'] == drug])
        decision['review_notes'] = [dict(dimension=k, reason=v['reason'], next_action=v['next_action'])
            for k,v in (risk or {}).get('risk_details', {}).items() if v['status'] == 'caution'] if (risk or {}).get('risk_details') else []
        run['drug_assessments'].append(decision)
    def entry(row):
        return {'drug_code': row['drug_code'], 'reason': row['reason'], 'rule_refs': [], 'evidence_refs': [r for r in row['evidence_refs'] if r in evidence_ids]}
    candidates = [entry(x) for x in run['drug_assessments'] if x['status'] == 'reviewable']
    avoid = [entry(x) for x in run['drug_assessments'] if x['status'] == 'avoid']
    issues = [dict(issue, agent_id=role) for role, out in outputs.items() for issue in out.get('issues', [])]
    for row in outputs.get('clinical_agent', {}).get('drugs', []):
        for dimension, detail in (row.get('risk_details') or {}).items():
            if detail['status'] in {'unknown', 'caution'}:
                issues.append({'agent_id':'clinical_agent','field':dimension,'drug_code':row['drug_code'],
                    'impact':row['drug_code']+'：'+detail['reason']+('；'+detail['next_action'] if detail['next_action'] else ''),
                    'action':detail['next_action'] or '補充對應病例資料與文件後重新分析','blocking':detail['status']=='unknown'})
    if len(drugs) > 30: issues.append({'agent_id': 'evidence_agent', 'field': 'drugs', 'impact': '逐藥檢索上限 30 項；其餘項目可能缺乏專屬片段', 'action': '縮小病例範圍後重新分析'})
    for selection in run['evidence_selection']:
        if selection['omitted_chunks']:
            issues.append({'agent_id': selection['agent_id'], 'field': 'evidence_context', 'impact': f"輸入長度限制省略 {selection['omitted_chunks']} 個片段；未讀取部分不能視為已核對", 'action': '檢視引用快照，必要時縮小文件範圍重新分析'})
    run['confirmation_items'] = issues
    run['output'] = {'candidates': candidates, 'avoid': avoid, 'pending': [entry(x) for x in run['drug_assessments'] if x['status'] == 'pending'], 'limitations': [x['impact'] for x in issues]}
    classify_options(run)
    run['gate_status'] = 'ready_for_review' if candidates else 'needs_confirmation'
    run['status'] = 'awaiting_review' if candidates else 'partial'
    run['agent_candidate_boundary'] = {'allowed_drugs': [x['drug_code'] for x in candidates],
        'evidence_by_drug': {x['drug_code']: x['evidence_refs'] for x in candidates}}
    run['safety_summary'] = {'avoid': avoid, 'limitations': run['output']['limitations'], 'gate_status': run['gate_status']}
    run['nodes'].extend([{'node_id': 'candidate_presentation', 'status': 'completed', 'output': {'attempted': True, 'schema_valid': 'synthesis_agent' in outputs, 'published': bool(candidates), 'withheld': not candidates}}, {'node_id': 'human_review', 'status': 'pending', 'output': {'action_required': True}}])
    attempts = [a for n in run['nodes'] for a in n.get('attempts', [])]
    run['usage'] = sum_usage(attempts)
    run['models'] = sorted({n['model'] for n in run['nodes'] if n.get('model')})
    run['model'] = run['models'][0] if len(run['models']) == 1 else None
    run['elapsed_ms'] = round((time.perf_counter()-start)*1000, 3)
    save()
    run['agent_execution'].update(completed_agents=sum(n.get('status') in {'completed','needs_confirmation'} for n in run['nodes'] if n.get('agent_id')), usage_complete=bool(attempts) and all(a.get('usage') for a in attempts))
    add_physician_candidates(run)
    return run


def validate_review(run, proposed=None):
    from .safety import validate_provider_output
    original = run.get('output') or {}
    proposed = copy.deepcopy(original if proposed is None else proposed)
    if not isinstance(proposed, dict) or set(proposed) - {'candidates', 'avoid', 'limitations', 'pending', 'review_options', 'run_id', 'gate_status', 'demo_only'}:
        raise ValueError('invalid review object')
    if not isinstance(proposed.get('candidates', []), list):
        raise ValueError('review candidates must be a list')
    proposed = {k: proposed.get(k, []) for k in ('candidates', 'avoid', 'limitations')}
    boundary = run.get('agent_candidate_boundary', {})
    for candidate in proposed.get('candidates', []):
        if not isinstance(candidate, dict): raise ValueError('invalid review candidate')
        refs = candidate.get('evidence_refs', [])
        if not isinstance(candidate.get('drug_code'), str) or not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs) or not set(refs) <= set(boundary.get('evidence_by_drug', {}).get(candidate.get('drug_code'), [])):
            raise ValueError('review requires audited per-drug evidence; reanalyse new choices')
    value, errors = validate_provider_output(proposed, allowed_drugs=set(boundary.get('allowed_drugs', [])),
        allowed_avoid={x['drug_code'] for x in original.get('avoid', [])}, allowed_rules=set(),
        allowed_evidence={x['chunk_id'] for x in run.get('evidence_snapshots', [])}, require_rule_refs=False, require_evidence_refs=True)
    if errors or value is None: raise ValueError('agent review rejected: ' + ','.join(errors))
    value['avoid'] = copy.deepcopy(original.get('avoid', []))
    value['pending'] = copy.deepcopy(original.get('pending', []))
    if 'review_options' in original: value['review_options']=copy.deepcopy(original['review_options'])
    value['limitations'] = list(dict.fromkeys(original.get('limitations', []) + value.get('limitations', [])))
    return {'valid': True, 'output': {**value, 'run_id': run['run_id'], 'gate_status': run['gate_status'], 'demo_only': True}}
