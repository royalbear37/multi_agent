"""New-contract acceptance tests; no network calls or real patient data."""
import copy
import pytest
from app.agents import runtime_led as rt
from app.workflow.engine import execute, validate_review
from app.workflow.agent_led import validate_output
from tests.test_workflow import case as workflow_case


def test_evidence_coverage_preserves_empty_failed_and_omitted_groups():
    from app.workflow.agent_led import evidence_groups
    retrievals=[{'stage':'infection','drug_code':'a','status':'ok','chunk_ids':['one','two','two']},
                {'stage':'infection','drug_code':'b','status':'no_results','chunk_ids':[],'warnings':['no_documents_for_requested_genre']},
                {'stage':'infection','drug_code':'c','status':'budget_exceeded','chunk_ids':[]},
                {'stage':'clinical','drug_code':'a','status':'ok','chunk_ids':['three']}]
    groups=evidence_groups(retrievals,{'one','three'},{'infection'})
    assert len(groups)==3
    assert groups[0]['retrieved_count']==2 and groups[0]['selected_count']==1
    assert groups[0]['omitted_refs']==['two'] and groups[0]['omitted_count']==1
    assert groups[1]['retrieval_status']=='no_results' and groups[1]['evidence_refs']==[]
    assert groups[1]['warnings']==['no_documents_for_requested_genre']
    assert groups[2]['retrieval_status']=='budget_exceeded'


def case(**overrides):
    return workflow_case(**({'medications':[],'medication_history_status':'reviewed_none'} | overrides))


class Docs:
    def __init__(self): self.queries=[]
    def search(self, query, **kwargs):
        self.queries.append(query)
        return {'status':'ok','evidence':[{'chunk_id':'e1','doc_id':'d1','document_version':'1',
            'text':'DEMO_DRUG_A and amoxicillin are options for adult urinary infection in this fictional fixture. Allergy precautions, renal dose adjustment and drug interactions require individual review.',
            'location':{'page':1},'is_synthetic':True}]}


def successful(self, agent, data, **kwargs):
    base={'findings':[], 'issues':[]}
    q=[{'chunk_id':'e1','quote':'DEMO_DRUG_A and amoxicillin are options for adult urinary infection in this fictional fixture. Allergy precautions, renal dose adjustment and drug interactions require individual review.'}]
    if agent.id=='case_agent': out={**base,'missing_fields':[]}
    elif agent.id=='ast_agent': out={**base,'drugs':[{'drug_code':d,'assessment':'susceptible','reason':'來源判讀一致',
        'category_source_refs':[f'ast_results.{i}.reported_sir' for i,a in enumerate(data['ast_results']) if a['drug_code']==d]} for d in data['drugs']], 'rapid_assessment':'已比對', 'resistance_assessment':'群體資料不替代 AST'}
    elif agent.id=='evidence_agent': out={**base,'drugs':[{'drug_code':d,'drug_name':d,'status':'supported','reason':'文件符合情境','applicability':'adult urinary infection','quotes':q} for d in data['drugs']]}
    elif agent.id=='clinical_agent': out={**base,'drugs':[{'drug_code':d,'status':'no_identified_risk','reason':'已核對提供資料','allergy':'已核對','renal':'已核對','interactions':'已核對','quotes':q,
        'risk_details':{dimension:{'status':'no_identified_risk','reason':'測試用已核對',
            'fact_refs':[path],'evidence_refs':['e1'],'missing_fields':[],'next_action':''}
            for dimension,path in [('allergy','allergies.status'),('renal','renal.egfr'),('interactions','medications')]}}
        for d in data['drugs']]}
    elif agent.id=='synthesis_agent': out={**base,'drugs':[{'drug_code':d,'status':'reviewable','reason':'文件符合本例，供審閱','evidence_refs':['e1'],'disagreements':[]} for d in data['drugs']]}
    else: out={**base,'drugs':[{'drug_code':c['drug_code'],'verdict':'supported','infection_match':'supported','population_match':'supported','drug_match':'supported','reason':'原文支持','quotes':q,
        'ast_check':{'assessment':'susceptible' if any(a['drug_code']==c['drug_code'] for a in data['ast_results']) else 'untested',
                     'claim_assessment':'not_stated',
                     'category_source_refs':[f'ast_results.{i}.reported_sir' for i,a in enumerate(data['ast_results']) if a['drug_code']==c['drug_code']]},
        'risk_checks':[{'dimension':r['dimension'],'verdict':'supported','reason':'獨立測試核對',
                        'fact_refs':r['fact_refs'],'evidence_refs':['e1']} for r in c.get('risk_claims', [])]}
        for c in data['claims']]}
    if agent.id=='synthesis_agent':
        for row in out['drugs']:
            row['fact_refs']=[]
            row['claims']=[{'dimension':dimension,'statement':'測試用分項聲明','fact_refs':[],'evidence_refs':['e1'] if dimension!='ast' else [],'next_action':''}
                for dimension in ('infection','ast','allergy','renal','interactions')]
    if agent.id=='evidence_audit':
        for row in out['drugs']:
            row['fact_refs']=[]
            claim=next(c for c in data['claims'] if c['drug_code']==row['drug_code'])
            row['claim_checks']=[{'dimension':c['dimension'],'verdict':'supported','reason':'測試用獨立核對','fact_refs':c['fact_refs'],'evidence_refs':c['evidence_refs'],
                'infection_match':'supported','population_match':'supported','drug_match':'supported'} for c in claim.get('claims',[])]
    return {'output':out,'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}


def test_no_rules_in_execution_or_review_and_six_real_calls(monkeypatch):
    import app.workflow.engine as engine
    monkeypatch.setattr(engine,'RuleEngine',lambda *a,**k: pytest.fail('RuleEngine called'))
    monkeypatch.setattr(rt.Provider,'complete',successful)
    docs=Docs(); run=execute(case(),'multi-agent','mock',docs)
    assert run['decision_basis']=='agent' and run['rule_evaluations']==[]
    assert run['agent_execution']['calls']==6 and run['output']['candidates']
    assert len(set(docs.queries))>=3
    assert validate_review(run)['valid']
    nodes={n['node_id']:n for n in run['nodes']}
    assert not nodes['evidence_audit']['input']['assessments']
    for role in ('ast_agent','evidence_agent','clinical_agent'):
        assert not nodes[role]['input']['assessments']
        assert 'case_assessment' not in nodes[role]['input']


def test_invalid_ast_source_is_pending_and_original_assertion_not_forwarded(monkeypatch):
    def changed(self,agent,data,**kw):
        reply=successful(self,agent,data,**kw)
        if agent.id=='ast_agent':
            reply['output']['drugs'][0].update(category_source_refs=['CSV description'],reason='unsupported positive assertion')
            reply['output']['findings']=['unsupported generic susceptibility summary']
            reply['output']['rapid_assessment']='unsupported positive rapid summary'
        if agent.id=='synthesis_agent':
            ast=data['assessments']['ast_agent']['drugs'][0]
            assert ast['assessment']=='unknown'
            assert 'model_reason' not in ast
            assert 'unsupported positive assertion' not in ast['reason']
            assert 'findings' not in data['assessments']['ast_agent']
            assert 'rapid_assessment' not in data['assessments']['ast_agent']
            assert 'source_linkage_notice' in data['assessments']['ast_agent']
        return reply
    monkeypatch.setattr(rt.Provider,'complete',changed)
    run=execute(case(),'multi-agent','mock',Docs())
    node=next(n for n in run['nodes'] if n['node_id']=='ast_agent')
    assert node['status']=='needs_confirmation'
    assert node['output']['drugs'][0]['model_reason']=='unsupported positive assertion'
    assert not run['output']['candidates']


def test_risk_quotes_cannot_replace_missing_claim_references_in_audit(monkeypatch):
    def changed(self,agent,data,**kw):
        reply=successful(self,agent,data,**kw)
        if agent.id=='clinical_agent':
            reply['output']['drugs'][0]['status']='caution'
            reply['output']['drugs'][0]['risk_details']['renal'].update(status='caution',next_action='人工核對後續追蹤')
        if agent.id=='synthesis_agent': reply['output']['drugs'][0]['evidence_refs']=['Unknown document title']
        if agent.id=='evidence_audit':
            assert data['claims'][0]['evidence_refs']==[]
            assert data['evidence']  # Risk-specific sources are still available.
        return reply
    monkeypatch.setattr(rt.Provider,'complete',changed)
    run=execute(case(),'multi-agent','mock',Docs())
    row=run['drug_assessments'][0]
    assert row['reference_validation']['invalid_refs']==['Unknown document title']
    assert row['audit']['verdict']=='uncertain'
    assert '專屬引用' in row['audit']['reason']
    assert not run['output']['candidates']


def test_avoid_is_not_published_when_audit_quote_identifies_only_another_drug(monkeypatch):
    text='Amoxicillin is mentioned in this fictional test reference.'
    class OtherDrugDocs(Docs):
        def search(self,query,**kwargs):
            result=super().search(query,**kwargs)
            result['evidence'][0]['text']=text
            return result
    def changed(self,agent,data,**kw):
        reply=successful(self,agent,data,**kw)
        for row in reply['output'].get('drugs',[]):
            if 'quotes' in row: row['quotes']=[{'chunk_id':'e1','quote':text}]
        if agent.id=='synthesis_agent': reply['output']['drugs'][0]['status']='avoid'
        return reply
    monkeypatch.setattr(rt.Provider,'complete',changed)
    run=execute(case(),'multi-agent','mock',OtherDrugDocs())
    assert not run['errors']
    assert not run['output']['avoid']
    assert run['drug_assessments'][0]['status']=='pending'
    assert run['drug_assessments'][0]['audit']['provenance_issues']


@pytest.mark.parametrize('mutation',['fabricated_quote','unrelated_page_566','clinical_disagreement','ast_conflict','untested'])
def test_per_drug_uncertainty_and_guideline_options(monkeypatch,mutation):
    def changed(self,agent,data,**kw):
        r=successful(self,agent,data,**kw); o=r['output']
        if mutation=='fabricated_quote' and agent.id=='evidence_audit': o['drugs'][0]['quotes'][0]['quote']='This sentence does not exist in the source.'
        if mutation=='unrelated_page_566' and agent.id=='evidence_audit': o['drugs'][0].update(verdict='unsupported',reason='WHO 第 566 頁沒有支持此藥與情境',quotes=[])
        if mutation=='clinical_disagreement' and agent.id=='clinical_agent': o['drugs'][0]['status']='avoid'
        if mutation=='ast_conflict' and agent.id=='ast_agent': o['drugs'][0]['assessment']='conflicting'
        if mutation=='untested' and agent.id=='evidence_agent': o['drugs'].append({**copy.deepcopy(o['drugs'][0]),'drug_code':'amoxicillin','drug_name':'amoxicillin'})
        return r
    monkeypatch.setattr(rt.Provider,'complete',changed)
    run=execute(case(),'multi-agent','mock',Docs())
    if mutation=='untested':
        row=next(x for x in run['drug_assessments'] if x['drug_code']=='amoxicillin')
        assert row['ast_available'] is False and '未測' in row['reason']
    else:
        assert not run['output']['candidates']
        assert run['output']['pending'] and run['nodes'][0]['output'] is not None


def test_unknown_drug_cannot_be_injected_by_synthesis_or_review(monkeypatch):
    monkeypatch.setattr(rt.Provider,'complete',successful)
    run=execute(case(),'multi-agent','mock',Docs())
    edited=copy.deepcopy(run['output']); edited['candidates'][0]['drug_code']='fabricated'
    with pytest.raises(ValueError): validate_review(run,edited)
    original=successful
    def changed(self,agent,data,**kw):
        r=original(self,agent,data,**kw)
        if agent.id=='synthesis_agent': r['output']['drugs'][0]['drug_code']='fabricated'
        return r
    monkeypatch.setattr(rt.Provider,'complete',changed)
    rejected=execute(case(),'multi-agent','mock',Docs())
    assert not rejected['output']['candidates'] and rejected['errors']


def test_missing_data_no_longer_skips_agents_and_mock_never_certifies():
    value=case(); value['renal']={}; value['ast_results']=[]
    run=execute(value,'multi-agent','mock',Docs())
    assert run['agent_execution']['calls']==5
    assert next(n for n in run['nodes'] if n['node_id']=='evidence_audit')['status']=='not_applicable'
    assert run['output']['candidates']==[]


def test_audit_cannot_support_mismatched_infection_even_with_real_quote(monkeypatch):
    def changed(self, agent, data, **kw):
        r = successful(self,agent,data,**kw)
        if agent.id == 'evidence_audit': r['output']['drugs'][0]['infection_match'] = 'unsupported'
        return r
    monkeypatch.setattr(rt.Provider,'complete',changed)
    run = execute(case(),'multi-agent','mock',Docs())
    assert run['drug_assessments'][0]['audit']['verdict'] == 'unsupported'
    assert not run['output']['candidates']
    audit = next(n for n in run['nodes'] if n['node_id']=='evidence_audit')
    assert all('status' not in claim for claim in audit['input']['claims'])


def test_short_citation_identifiers_round_trip_without_changing_original_text(monkeypatch):
    from app.agents.runtime_v2 import AgentProvider
    data = dict(facts={},ast_results=[],drugs=['a'],evidence=[{'chunk_id':'long_original_id','text':'exact original text','source_document_id':'sha256:original'}],assessments={},claims=[])
    def fake(self, agent, wire, **kw):
        assert wire['evidence'] == [{'chunk_id':'E1','source_document_id':'sha256:original','passages':[{'span_id':'S1','text':'exact original text'}]}]
        quote_schema = agent.output_type.model_json_schema()['$defs']['Quote']
        assert set(quote_schema['properties']) == {'chunk_id','span_ids'}
        return {'output':{'drugs':[{'drug_code':'a','drug_name':'a','status':'supported','reason':'source','applicability':'case','quotes':[{'chunk_id':'E1','span_ids':['S1']}]}]}}
    monkeypatch.setattr(AgentProvider,'complete',fake)
    result = rt.Provider('live',rt.AGENTS[2]).complete(rt.AGENTS[2],data,timeout=1)
    assert result['output']['drugs'][0]['quotes'][0]['chunk_id'] == 'long_original_id'
    assert result['output']['drugs'][0]['quotes'][0]['quote'] == 'exact original text'
    assert result['citation_spans']['E1']['S1'] == {'start':0,'end':19}
    assert data['evidence'][0]['chunk_id'] == 'long_original_id'


@pytest.mark.parametrize('mutation', ['missing_without_issue', 'prescription', 'blank_quote'])
def test_review_findings_cannot_bypass_publication_checks(monkeypatch, mutation):
    def changed(self, agent, data, **kw):
        r = successful(self, agent, data, **kw)
        if mutation == 'missing_without_issue' and agent.id == 'case_agent': r['output']['missing_fields'] = ['allergies.status']
        if mutation == 'prescription' and agent.id == 'synthesis_agent': r['output']['drugs'][0]['reason'] = '每日服用 5 mg'
        if mutation == 'blank_quote' and agent.id == 'evidence_audit': r['output']['drugs'][0]['quotes'][0]['quote'] = ' ' * 12
        return r
    monkeypatch.setattr(rt.Provider, 'complete', changed)
    run = execute(case(), 'multi-agent', 'mock', Docs())
    assert not run['output']['candidates']
    assert '每日服用' not in str(run['output'])


def test_retries_reserve_one_call_for_every_remaining_role(monkeypatch):
    seen = {}
    def changed(self, agent, data, **kw):
        seen[agent.id] = seen.get(agent.id, 0) + 1
        if agent.id in ('case_agent', 'ast_agent', 'evidence_agent') and seen[agent.id] == 1:
            return {'output': {'invalid': True}}
        return successful(self, agent, data, **kw)
    monkeypatch.setattr(rt.Provider, 'complete', changed)
    monkeypatch.setenv('LLM_V2_MAX_CALLS', '8')
    run = execute(case(), 'multi-agent', 'mock', Docs())
    assert seen['evidence_audit'] == 1 and run['agent_execution']['calls'] == 8
    assert run['nodes'][2]['status'] == 'failed'


@pytest.mark.parametrize('bad', [None, {}, ['e1', {}], 'e1'])
def test_malformed_review_refs_return_validation_error(monkeypatch, bad):
    monkeypatch.setattr(rt.Provider, 'complete', successful)
    run = execute(case(), 'multi-agent', 'mock', Docs())
    edited = copy.deepcopy(run['output']); edited['candidates'][0]['evidence_refs'] = bad
    with pytest.raises(ValueError): validate_review(run, edited)


def test_document_routing_respects_case_scope_and_drug_identity(tmp_path):
    from app.rag.service import DocumentService
    svc = DocumentService(tmp_path, retrieval_mode='lexical')
    a = svc.import_document('a.md', b'# Label\namoxicillin renal risk', 'DailyMed amoxicillin', '1', False, document_kind='drug_label')
    b = svc.import_document('b.md', b'# Label\nciprofloxacin renal risk', 'DailyMed ciprofloxacin', '1', False, document_kind='drug_label')
    result = svc.search_agent_context('renal risk', drug_code='amoxicillin', stage='clinical')
    assert {e['doc_id'] for e in result['evidence']} == {a['doc_id']}
    assert not svc.search_agent_context('renal risk', policy_refs=[b['doc_id']], drug_code='amoxicillin', stage='clinical')['evidence']


def test_partial_failure_keeps_valid_specialist_output(monkeypatch):
    def changed(self,agent,data,**kw):
        if agent.id=='ast_agent': return {'output':{'wrong':'shape'},'usage':{'total_tokens':7}}
        return successful(self,agent,data,**kw)
    monkeypatch.setattr(rt.Provider,'complete',changed)
    run=execute(case(),'multi-agent','mock',Docs())
    from app.main import _public_run
    nodes={n['node_id']:n for n in _public_run(run)['nodes']}
    assert nodes['case_agent']['output'] and nodes['clinical_agent']['output']
    assert nodes['ast_agent']['output'] is None
    assert not run['output']['candidates']
    assert run['usage']['total_tokens']>=14


def test_pinned_corpus_supports_distinct_queries_and_survives_deletion(tmp_path):
    from app.rag.service import DocumentService
    svc=DocumentService(tmp_path/'docs',retrieval_mode='lexical')
    a=svc.import_document('a.md',b'# infection\namoxicillin urinary evidence','A','1',False)
    svc.import_document('b.md',b'# interactions\nciprofloxacin tizanidine interactions','B','1',False)
    with svc.snapshot() as frozen:
        svc.delete_document(a['doc_id'])
        first=frozen.search('amoxicillin',scope='reference')['evidence']
        second=frozen.search('tizanidine',scope='reference')['evidence']
        assert first and second and first[0]['doc_id']!=second[0]['doc_id']
    assert not frozen.db_path.exists()


def test_review_cannot_fabricate_rule_refs_or_overlapping_dispositions(monkeypatch):
    monkeypatch.setattr(rt.Provider,'complete',successful)
    run=execute(case(),'multi-agent','mock',Docs())
    for change in ('rules','overlap'):
        proposed=copy.deepcopy(run['output'])
        if change=='rules': proposed['candidates'][0]['rule_refs']=['invented']
        else: proposed['avoid']=[copy.deepcopy(proposed['candidates'][0])]
        with pytest.raises(ValueError): validate_review(run,proposed)


def test_raw_mic_medication_status_and_rapid_data_reach_agents(monkeypatch):
    monkeypatch.setattr(rt.Provider,'complete',successful)
    value=case(); value['medications']=[{'drug_code':'tizanidine','status':'held'}]; value['rapid_identification']={'method':'MALDI-TOF','result':'different'}
    run=execute(value,'multi-agent','mock',Docs())
    node=next(n for n in run['nodes'] if n['node_id']=='clinical_agent')
    assert node['input']['facts']['medications'][0]['status']=='held'
    assert node['input']['facts']['rapid_identification']['result']=='different'
    assert node['input']['ast_results'][0]['mic']==1
