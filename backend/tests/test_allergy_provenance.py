import copy

import pytest
from pydantic import ValidationError

from app.schemas.case import Case
from app.workflow.agent_led import facts_from, validate_output
from app.agents import runtime_led as rt
from scripts.build_allergy_cases import paired_cases
from tests.test_workflow import case as workflow_case


def case(**overrides):
    return workflow_case(created_at='2026-10-06T09:00:00+08:00', **overrides)


def test_old_allergy_label_does_not_become_confirmed():
    value = case(allergies={'status':'known_present','items':[{'drug_code':'amoxicillin'}]})
    parsed = Case.model_validate(value).model_dump(mode='json')
    assert parsed['allergies']['items'][0]['verification_status'] == 'not_recorded'
    assert parsed['allergies']['status'] == 'known_present'


@pytest.mark.parametrize('state',['confirmed','ruled_out'])
def test_verification_requires_attributed_assessment(state):
    value = case(allergies={'status':'known_present','items':[{'drug_code':'amoxicillin','verification_status':state}]})
    with pytest.raises(ValidationError): Case.model_validate(value)
    value['allergies']['items'][0].update(verification_note='人工測試評估',verification_source='test source',
        verified_by='test clinician',verified_at='2026-10-06T10:00:00+08:00')
    parsed = Case.model_validate(value).model_dump(mode='json')
    assert parsed['allergies']['status'] == 'known_present'
    assert facts_from(parsed)['allergies']['items'][0]['verification_source'] == 'test source'
    value['allergies']['items'][0]['verified_at'] = '2026-10-06T10:00:00'
    with pytest.raises(ValidationError): Case.model_validate(value)


def test_paired_cases_change_only_allergy_and_provenance():
    base = case()
    before = copy.deepcopy(base)
    cases, expected = paired_cases(base)
    assert len(cases) == len(expected) == 4
    for value in cases:
        Case.model_validate(value)
        for key in ('ast_results','renal','microbiology','encounter','medications'):
            assert value.get(key) == base.get(key)
        assert 'allergies' in value['provenance']['simulated_fields']
    assert base == before


def test_research_background_never_confirms_patient_absence_of_risk():
    data = {'drugs':['a'],'evidence':[{'chunk_id':'r','text':'Population association, not individual risk.', 'document_kind':'research_article'}]}
    raw = {'findings':[],'issues':[],'drugs':[{'drug_code':'a','status':'no_identified_risk',
        'allergy':'未確認','renal':'未確認','interactions':'未確認','reason':'研究提及',
        'quotes':[{'chunk_id':'r','quote':'Population association, not individual risk.'}]}]}
    assert validate_output(rt.AGENTS[3],raw,data)['drugs'][0]['status'] == 'unknown'


def test_research_is_searchable_as_background_but_not_guideline(tmp_path):
    from app.rag.service import DocumentService
    svc = DocumentService(tmp_path,retrieval_mode='lexical')
    doc = svc.import_document('paper.md',b'# Study\nAllergy labels and population prescribing patterns.',
        'Allergy study','2025',False,document_kind='research_article',study_design='observational')
    assert not svc.search_agent_context('allergy',stage='infection')['evidence']
    result = svc.search_agent_context('allergy',stage='background')['evidence']
    assert result and result[0]['study_design'] == 'observational'
    assert result[0]['doc_id'] == doc['doc_id']
    assert svc.search('allergy',scope='reference')['evidence']


def test_mixed_research_quote_cannot_become_audited_treatment_support():
    data = {'drugs':['a'],'claims':[{'drug_code':'a'}],'evidence':[
        {'chunk_id':'r','text':'Population prescribing association.', 'document_kind':'research_article'},
        {'chunk_id':'g','text':'A specific guideline statement.', 'document_kind':'guideline'}]}
    raw = {'findings':[],'issues':[],'drugs':[{'drug_code':'a','verdict':'supported',
        'infection_match':'supported','population_match':'supported','drug_match':'supported','reason':'混合引文',
        'quotes':[{'chunk_id':'r','quote':'Population prescribing association.'},
                  {'chunk_id':'g','quote':'A specific guideline statement.'}]}]}
    assert validate_output(rt.AGENTS[5],raw,data)['drugs'][0]['verdict'] == 'uncertain'


@pytest.mark.parametrize('severity',['severe','Severe','嚴重'])
def test_direct_severe_allergy_contradiction_cannot_publish_candidate(monkeypatch,severity):
    from tests.test_agent_led import successful, Docs
    from app.workflow.engine import execute
    monkeypatch.setattr(rt.Provider,'complete',successful)
    value = case(allergies={'status':'known_present','items':[{
        'drug_code':'DEMO_DRUG_A','reaction':'recorded reaction','severity':severity}]})
    run = execute(value,'multi-agent','mock',Docs())
    assert not run['output']['candidates']
    assert run['drug_assessments'][0]['clinical']['status'] == 'unknown'
    assert any(i['field']=='allergies.items' for i in run['confirmation_items'])
