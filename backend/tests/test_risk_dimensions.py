import copy

import pytest

from app.agents import runtime_led as rt
from app.workflow.engine import execute, validate_review
from tests.test_agent_led import Docs, case, successful


def run_variant(monkeypatch, change, value=None):
    def reply(self, agent, data, **kwargs):
        result = successful(self, agent, data, **kwargs)
        change(agent, result['output'], data)
        return result
    monkeypatch.setattr(rt.Provider, 'complete', reply)
    return execute(value or case(), 'multi-agent', 'mock', Docs())


def test_documented_caution_can_be_reviewed_and_warning_survives_review(monkeypatch):
    def change(agent, output, data):
        if agent.id == 'clinical_agent':
            row = output['drugs'][0]
            row['status'] = 'caution'
            row['risk_details']['renal'].update(status='caution',next_action='人工核對後續腎功能追蹤')
    run = run_variant(monkeypatch, change)
    assert run['output']['candidates']
    assert run['drug_assessments'][0]['review_notes'][0]['next_action'] == '人工核對後續腎功能追蹤'
    proposal = copy.deepcopy(run['output'])
    proposal['limitations'] = []
    assert any('人工核對後續腎功能追蹤' in x for x in validate_review(run, proposal)['output']['limitations'])


@pytest.mark.parametrize('variant',['missing_details','missing_fact','unprovided_fact','missing_quote',
    'missing_next_action','missing_field','blocking_issue','severe_allergy','unknown_allergy'])
def test_caution_does_not_bypass_unresolved_facts_or_evidence(monkeypatch,variant):
    def change(agent, output, data):
        if agent.id == 'clinical_agent':
            row = output['drugs'][0]
            row['status'] = 'caution'
            detail = row['risk_details']['renal']
            detail.update(status='caution',next_action='核對追蹤')
            if variant == 'missing_details': row.pop('risk_details')
            if variant == 'missing_fact': detail['fact_refs'] = []
            if variant == 'unprovided_fact': detail['fact_refs'] = ['renal.crcl']
            if variant == 'missing_quote': detail['evidence_refs'] = ['missing']
            if variant == 'missing_next_action': detail['next_action'] = ''
            if variant == 'missing_field': detail['missing_fields'] = ['renal.sampled_at']
            if variant == 'blocking_issue': output['issues'] = [{'field':'renal','impact':'必要資料待確認','action':'補齊','drug_code':row['drug_code'],'blocking':True}]
    value = case()
    if variant=='severe_allergy': value['allergies']={'status':'known_present','items':[{'drug_code':'DEMO_DRUG_A','severity':'severe'}]}
    if variant=='unknown_allergy': value['allergies']={'status':'unknown','items':[]}
    run = run_variant(monkeypatch, change, value)
    assert not run['output']['candidates']


@pytest.mark.parametrize('verdict',['supported','unsupported','uncertain'])
def test_exclusions_are_audited_without_prior_disposition(monkeypatch,verdict):
    def change(agent, output, data):
        if agent.id == 'synthesis_agent': output['drugs'][0]['status'] = 'avoid'
        if agent.id == 'evidence_audit':
            assert data['claims'] and 'status' not in data['claims'][0]
            assert not data['assessments']
            output['drugs'][0]['verdict'] = verdict
    run = run_variant(monkeypatch, change)
    assert run['drug_assessments'][0]['status'] == ('avoid' if verdict=='supported' else 'pending')


def test_fact_only_audit_checks_patient_data_not_a_document(monkeypatch):
    def change(agent, output, data):
        if agent.id == 'synthesis_agent':
            output['drugs'][0].update(status='not_selected',reason='此測試以病例事實核對為主',fact_refs=['ast_results.0.reported_sir'])
        if agent.id == 'evidence_audit':
            output['drugs'][0].update(basis='case_fact',fact_refs=['ast_results.0.reported_sir'],fact_match='supported',
                infection_match='not_applicable',population_match='not_applicable',drug_match='not_applicable',quotes=[])
    run = run_variant(monkeypatch, change)
    assert run['drug_assessments'][0]['status']=='not_selected'
    assert run['drug_assessments'][0]['audit']['fact_match']=='supported'


def test_fact_only_audit_cannot_approve_treatment_suitability(monkeypatch):
    def change(agent, output, data):
        if agent.id=='evidence_audit':
            output['drugs'][0].update(basis='case_fact',fact_refs=['ast_results.0.reported_sir'],fact_match='supported',quotes=[])
    run = run_variant(monkeypatch, change)
    assert not run['output']['candidates']


def test_audit_cannot_borrow_another_drugs_ast():
    from app.workflow.agent_led import validate_output
    data = {'drugs':['a'],'claims':[{'drug_code':'a'}],'facts':{},'evidence':[],
            'ast_results':[{'drug_code':'b','reported_sir':'S'}]}
    raw = {'drugs':[{'drug_code':'a','basis':'case_fact','fact_refs':['ast_results.0.reported_sir'],
        'fact_match':'supported','verdict':'supported','infection_match':'not_applicable',
        'population_match':'not_applicable','drug_match':'not_applicable','reason':'引用其他藥的 AST','quotes':[]}]}
    assert validate_output(rt.AGENTS[5],raw,data)['drugs'][0]['verdict']=='uncertain'


def test_research_background_cannot_make_caution_reviewable():
    from app.workflow.agent_led import validate_output, facts_from
    data={'drugs':['DEMO_DRUG_A'],'facts':facts_from(case()),'risk_details_required':True,
          'evidence':[{'chunk_id':'e1','text':Docs().search('')['evidence'][0]['text'], 'document_kind':'research_article'}]}
    raw=successful(None,rt.AGENTS[3],data)['output']
    raw['drugs'][0]['status']='caution'
    raw['drugs'][0]['risk_details']['renal'].update(status='caution',next_action='核對追蹤')
    assert validate_output(rt.AGENTS[3],raw,data)['drugs'][0]['status']=='unknown'


def test_document_audit_cannot_ignore_claims_patient_reference(monkeypatch):
    def change(agent,output,data):
        if agent.id=='synthesis_agent':
            output['drugs'][0].update(reason='本例 CrCl 為 90',fact_refs=['renal.crcl'])
        if agent.id=='evidence_audit':
            output['drugs'][0].update(basis='document',fact_refs=[])
    run=run_variant(monkeypatch,change)
    assert not run['output']['candidates']
    assert run['drug_assessments'][0]['audit']['verdict']=='uncertain'


@pytest.mark.parametrize('mode',['omitted','unsupported','missing_risk_quote'])
def test_every_caution_claim_and_next_action_requires_independent_audit(monkeypatch,mode):
    def change(agent,output,data):
        if agent.id=='clinical_agent':
            output['drugs'][0]['status']='caution'
            output['drugs'][0]['risk_details']['renal'].update(status='caution',reason='需要核對腎功能風險',next_action='核對追蹤')
        if agent.id=='evidence_audit':
            claims=data['claims'][0]['risk_claims']
            assert any(c['dimension']=='renal' and c['next_action']=='核對追蹤' for c in claims)
            checks=output['drugs'][0]['risk_checks']
            renal=next(c for c in checks if c['dimension']=='renal')
            if mode=='omitted': output['drugs'][0]['risk_checks']=[c for c in checks if c['dimension']!='renal']
            if mode=='unsupported': renal['verdict']='unsupported'
            if mode=='missing_risk_quote': renal['evidence_refs']=[]
    assert not run_variant(monkeypatch,change)['output']['candidates']


def test_absent_medication_history_is_not_reviewed_empty_list(monkeypatch):
    value=case()
    value.pop('medication_history_status')
    run=run_variant(monkeypatch,lambda *args:None,value)
    assert not run['output']['candidates']
    detail=run['drug_assessments'][0]['clinical']['risk_details']['interactions']
    assert detail['status']=='unknown'
    assert '空清單' in detail['reason']


def test_reviewed_empty_medications_can_be_explicitly_linked_without_inventing_exposure(monkeypatch):
    def change(agent,output,data):
        if agent.id=='clinical_agent':
            assert data['facts']['medications']==[]
            assert data['facts']['medication_history_status']=='reviewed_none'
            detail=output['drugs'][0]['risk_details']['interactions']
            detail['fact_refs']=['medications','medication_history_status']
    run=run_variant(monkeypatch,change)
    detail=run['drug_assessments'][0]['clinical']['risk_details']['interactions']
    assert not detail['validation_issues']
    assert run['output']['candidates']


@pytest.mark.parametrize('path',['allergies.items.0.reaction','allergies.items','allergies'])
def test_other_drug_allergy_is_not_direct_patient_fact_for_exclusion(monkeypatch,path):
    value=case(allergies={'status':'known_present','items':[{'drug_code':'OTHER_DRUG','reaction':'anaphylaxis','severity':'severe'}]})
    def change(agent,output,data):
        if agent.id=='synthesis_agent': output['drugs'][0].update(status='avoid',fact_refs=[path])
        if agent.id=='evidence_audit': output['drugs'][0].update(basis='case_fact',fact_refs=[path],fact_match='supported',quotes=[])
    run=run_variant(monkeypatch,change,value)
    assert not run['output']['avoid']
    assert run['drug_assessments'][0]['status']=='pending'


def test_all_null_renal_object_does_not_count_as_patient_data(monkeypatch):
    value=case()
    value['renal']={'egfr':None,'crcl':None,'creatinine':None}
    def change(agent,output,data):
        if agent.id=='clinical_agent': output['drugs'][0]['risk_details']['renal']['fact_refs']=['renal']
    run=run_variant(monkeypatch,change,value)
    assert not run['output']['candidates']
    assert run['drug_assessments'][0]['clinical']['risk_details']['renal']['status']=='unknown'
