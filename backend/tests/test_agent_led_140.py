import copy
import pytest
from app.agents import runtime_led as rt
from app.agents.citation_spans import selection_schema
from app.agents.wire_validation import checked_wire
from app.workflow.engine import execute, validate_review
from tests.test_agent_led import case, Docs, successful


def run(monkeypatch,change,value=None):
    def reply(self,agent,data,**kw):
        result=successful(self,agent,data,**kw)
        change(agent,result['output'],data)
        return result
    monkeypatch.setattr(rt.Provider,'complete',reply)
    return execute(value or case(),'multi-agent','mock',Docs())


def test_wire_required_is_checked_before_defaults_and_good_rows_survive():
    schema=selection_schema(rt.EvidenceReport)
    good={'drug_code':'a','drug_name':'a','status':'uncertain','reason':'no source','applicability':'unknown','quotes':[]}
    bad={**good,'drug_code':'b'}; bad.pop('quotes')
    output,errors=checked_wire({'drugs':[good,bad]},schema)
    assert output['drugs']==[good] and errors
    assert 'quotes' in errors[0]
    assert not checked_wire({'drugs':[good]},schema)[1]


def test_repair_only_failed_drug_preserves_other_rows(monkeypatch):
    seen=[]
    def change(agent,out,data):
        if agent.id=='clinical_agent':
            seen.append(list(data['drugs']))
            if len(seen)==1: out['drugs'][1]['quotes']=[]
            else: assert data['validation_feedback'] and data['drugs']==['amoxicillin']
    value=case(); value['ast_results'].append({**value['ast_results'][0],'drug_code':'amoxicillin'})
    result=run(monkeypatch,change,value)
    assert len(result['output']['candidates'])==2
    assert result['agent_execution']['calls']==7
    assert seen==[['DEMO_DRUG_A','amoxicillin'],['amoxicillin']]


def test_failed_repair_keeps_valid_drug_and_honors_explicit_call_limit(monkeypatch):
    def change(agent,out,data):
        if agent.id=='clinical_agent':
            for row in out['drugs']:
                if row['drug_code']=='amoxicillin': row['quotes']=[]
        if agent.id=='evidence_audit':
            for row in out['drugs']:
                if row['drug_code']=='amoxicillin': row['quotes']=[]
    value=case(); value['ast_results'].append({**value['ast_results'][0],'drug_code':'amoxicillin'})
    monkeypatch.setenv('LLM_AGENT_LED_MAX_CALLS','8')
    monkeypatch.setenv('LLM_AGENT_LED_MAX_RETRIES','1')
    result=run(monkeypatch,change,value)
    assert result['agent_execution']['calls']==8
    assert [r['drug_code'] for r in result['output']['candidates']]==['DEMO_DRUG_A']
    assert all(len(n.get('attempts',[]))<=2 for n in result['nodes'])
    assert next(n for n in result['nodes'] if n.get('agent_id')=='clinical_agent')['output']['drugs']


def test_honest_uncertainty_is_not_retried_and_is_layered(monkeypatch):
    def change(agent,out,data):
        if agent.id=='clinical_agent':
            for row in out['drugs']:
                row['status']='unknown'; row['risk_details']['renal']['status']='unknown'
                row['risk_details']['renal']['missing_fields']=['renal.sampled_at']
        if agent.id=='evidence_audit':
            for row in out['drugs']:
                row['verdict']='uncertain'
                for check in row['claim_checks']:
                    if check['dimension']=='renal': check['verdict']='uncertain'
    result=run(monkeypatch,change)
    assert result['agent_execution']['calls']==6
    assert not result['output']['candidates']
    assert len(result['output']['review_options'])==1
    assert result['output']['review_options'][0] in result['output']['pending']
    assert result['drug_assessments'][0]['result_tier']=='review_option'
    assert any(b['kind']=='case_data_missing' for b in result['drug_assessments'][0]['blockers'])
    assert validate_review(result)['output']['review_options']==result['output']['review_options']
    with pytest.raises(ValueError): validate_review(result,{'candidates':result['output']['review_options']})


@pytest.mark.parametrize('kind',['wrong_drug','wrong_infection','wrong_population','source_conflict'])
def test_wrong_support_cannot_become_review_option(monkeypatch,kind):
    def change(agent,out,data):
        if agent.id=='clinical_agent': out['drugs'][0]['status']='unknown'
        if agent.id=='evidence_audit':
            check=out['drugs'][0]['claim_checks'][0]
            if kind=='wrong_drug': check['evidence_refs']=[]
            if kind=='wrong_infection': check['infection_match']='unsupported'
            if kind=='wrong_population': check['population_match']='unsupported'
    value=case()
    if kind=='source_conflict':
        value['ast_results'][0].update(interpretation_basis='CLSI_2022_pheno',clsi_2022_phenotype='Resistant',reported_sir='S')
    result=run(monkeypatch,change,value)
    assert not result['output']['candidates'] and not result['output']['review_options']


def test_risk_queries_are_separate_and_audit_has_no_upstream_verdict(monkeypatch):
    def change(agent,out,data):
        if agent.id=='evidence_audit':
            assert not data['assessments']
            assert all('status' not in c and all('verdict' not in d for d in c['claims']) for c in data['claims'])
    result=run(monkeypatch,change)
    queries=[r for r in result['retrievals'] if r['stage']=='clinical']
    assert {r['dimension'] for r in queries}=={'allergy','renal','interactions'}
    assert len({r['query'] for r in queries})==3
    assert len(result['evidence_snapshots'])==1


def test_untested_guideline_option_is_not_called_susceptible(monkeypatch):
    def change(agent,out,data):
        if agent.id=='evidence_agent':
            out['drugs'].append({**copy.deepcopy(out['drugs'][0]),'drug_code':'amoxicillin','drug_name':'amoxicillin'})
        if agent.id=='clinical_agent':
            for row in out['drugs']:
                if row['drug_code']=='amoxicillin': row['status']='unknown'
    result=run(monkeypatch,change)
    option=next(r for r in result['drug_assessments'] if r['drug_code']=='amoxicillin')
    assert option['result_tier']=='review_option' and not option['ast_available']
    assert option['audit']['ast_check']['assessment']=='untested'
    assert option['ast'] is None


def test_wire_partial_bad_selector_cannot_remove_other_drug(monkeypatch):
    from app.agents.runtime_v2 import AgentProvider
    def transport(self,agent,data,**kw):
        base=dict(drug_name='a',status='supported',reason='test',applicability='test')
        return {'output':{'drugs':[{**base,'drug_code':'a','quotes':[{'chunk_id':'E1','span_ids':['S1']}]},
            {**base,'drug_code':'b','quotes':[{'chunk_id':'E1','span_ids':['missing']}]}]},'usage':{'total_tokens':20}}
    monkeypatch.setattr(AgentProvider,'complete',transport)
    result=rt.Provider('live',rt.AGENTS[2]).complete(rt.AGENTS[2],{'evidence':[{'chunk_id':'source','text':'Actual original source text.'}]},timeout=1)
    assert [r['drug_code'] for r in result['output']['drugs']]==['a']
    assert result['usage']['total_tokens']==20 and result['wire_errors']


def test_fact_only_empty_medications_is_not_sufficient_for_drug_safety(monkeypatch):
    def change(agent,out,data):
        if agent.id=='clinical_agent':
            row=out['drugs'][0]
            row['status']='unknown'
            row['risk_details']['interactions'].update(status='unknown',fact_refs=['medications','medication_history_status'],evidence_refs=[])
        if agent.id=='evidence_audit':
            for check in out['drugs'][0]['claim_checks']:
                if check['dimension']=='interactions': check.update(fact_refs=['medications','medication_history_status'],evidence_refs=[])
    result=run(monkeypatch,change)
    assert not result['output']['candidates']
    assert result['output']['review_options']
    check=next(c for c in result['drug_assessments'][0]['audit']['claim_checks'] if c['dimension']=='interactions')
    assert check['verdict']=='uncertain'


@pytest.mark.parametrize('dimension',['infection','renal'])
def test_duplicate_original_claim_is_not_overwritten_into_support(monkeypatch,dimension):
    def change(agent,out,data):
        if agent.id=='synthesis_agent':
            claims=out['drugs'][0]['claims']
            claims.append(copy.deepcopy(next(c for c in claims if c['dimension']==dimension)))
        if agent.id=='evidence_audit':
            # The model only checks one of the duplicate source claims.
            out['drugs'][0]['claim_checks']=list({c['dimension']:c for c in out['drugs'][0]['claim_checks']}.values())
    result=run(monkeypatch,change)
    assert not result['output']['candidates'] and not result['output']['review_options']


def test_reported_avoid_is_visible_and_not_promoted_even_without_audit_support(monkeypatch):
    def change(agent,out,data):
        if agent.id=='clinical_agent':
            out['drugs'][0]['risk_details']['allergy'].update(status='avoid',evidence_refs=[])
        if agent.id=='evidence_audit':
            for c in out['drugs'][0]['claim_checks']:
                if c['dimension']=='allergy': c['verdict']='uncertain'
    result=run(monkeypatch,change)
    assert not result['output']['review_options']
    assert any(b['kind']=='reported_avoid' for b in result['drug_assessments'][0]['blockers'])


def test_repair_replaces_drug_specific_issue_without_erasing_global_issue(monkeypatch):
    count=0
    def change(agent,out,data):
        nonlocal count
        if agent.id=='clinical_agent':
            count+=1
            if count==1:
                out['drugs'][0]['quotes']=[]
                out['issues']=[dict(field='quotes',impact='尚待補正',action='選取引文',drug_code='DEMO_DRUG_A',blocking=True),
                    dict(field='history',impact='全域限制保留',action='人工核對',blocking=False)]
    result=run(monkeypatch,change)
    assert result['output']['candidates']
    issues=next(n for n in result['nodes'] if n.get('agent_id')=='clinical_agent')['output']['issues']
    assert not any(i['field']=='quotes' for i in issues)
    assert any(i['field']=='history' for i in issues)


def test_repair_cannot_turn_unanchored_extra_drug_into_original_drug(monkeypatch):
    count=0
    def change(agent,out,data):
        nonlocal count
        if agent.id=='evidence_agent':
            count+=1
            if count==1:
                out['drugs'].append({**copy.deepcopy(out['drugs'][0]),'drug_code':'invented','drug_name':'invented'})
            else:
                assert data['original_drugs']==['DEMO_DRUG_A']
    result=run(monkeypatch,change)
    evidence=next(n for n in result['nodes'] if n.get('agent_id')=='evidence_agent')
    assert count==4
    assert [r['drug_code'] for r in evidence['output']['drugs']]==['DEMO_DRUG_A']
    assert not any(r['drug_code']=='invented' for r in result['drug_assessments'])


def test_avoid_is_preserved_when_prescription_prose_is_isolated(monkeypatch):
    def change(agent,out,data):
        if agent.id=='clinical_agent': out['drugs'][0].update(status='avoid',reason='給予 500 mg 的文字應隔離')
    result=run(monkeypatch,change)
    risk=result['drug_assessments'][0]['clinical']
    assert risk['status']=='unknown' and risk['model_status']=='avoid'
    assert not result['output']['review_options']


def test_missing_original_claims_cannot_make_unvalidated_checks_into_options(monkeypatch):
    def change(agent,out,data):
        if agent.id=='synthesis_agent': out['drugs'][0].pop('claims')
        if agent.id=='evidence_audit':
            out['drugs'][0]['claim_checks']=[dict(dimension=d,verdict='supported',reason='unverified',fact_refs=[],evidence_refs=['e1'],infection_match='supported',population_match='supported',drug_match='supported') for d in ('infection','ast','allergy','renal','interactions')]
    result=run(monkeypatch,change)
    assert not result['output']['candidates'] and not result['output']['review_options']
    assert all(c['verdict']=='uncertain' for c in result['drug_assessments'][0]['audit']['claim_checks'])
