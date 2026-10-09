import copy

import pytest

from app.agents import runtime_led as rt
from app.agents.citation_spans import resolve_selections, source_spans
from app.agents.runtime_v2 import AgentProvider
from app.workflow.agent_led import validate_output
from app.workflow.engine import execute, validate_review
from tests.test_agent_led import Docs, successful, case


def test_live_clinical_contract_has_one_required_structured_risk_format():
    from app.agents.citation_spans import selection_schema
    from app.agents.contracts_led import ClinicalReport
    canonical=copy.deepcopy(ClinicalReport.model_json_schema())
    wire=selection_schema(ClinicalReport)
    risk=wire['$defs']['Risk']
    assert not {'allergy','renal','interactions'} & set(risk['properties'])
    assert 'risk_details' in risk['required']
    assert risk['properties']['risk_details']=={'$ref':'#/$defs/RiskDetails'}
    assert set(wire['$defs']['RiskDetails']['required'])=={'allergy','renal','interactions'}
    assert ClinicalReport.model_json_schema()==canonical
    old=ClinicalReport.model_validate({'drugs':[{'drug_code':'a','status':'unknown','reason':'舊回覆',
        'allergy':'未核對','renal':'未核對','interactions':'未核對'}]})
    assert old.drugs[0].risk_details is None


def test_case_missing_fields_is_explicit_on_wire_and_legacy_readable():
    from app.agents.citation_spans import selection_schema
    assert 'missing_fields' in selection_schema(rt.CaseReport)['required']
    assert 'missing_fields' not in rt.CaseReport.model_json_schema().get('required',[])
    assert rt.CaseReport.model_validate({}).missing_fields==[]


@pytest.mark.parametrize('output_type,row_name', [
    (rt.ClinicalReport, 'Risk'), (rt.AuditReport, 'AuditItem'),
])
def test_live_source_selections_are_explicit_but_unknown_can_have_no_quote(output_type,row_name):
    from app.agents.citation_spans import selection_schema
    original=copy.deepcopy(output_type.model_json_schema())
    wire=selection_schema(output_type)
    row=wire['$defs'][row_name]
    assert 'quotes' in row['required']
    assert row['properties']['quotes'].get('minItems',0)==0
    assert 'quotes' not in wire['properties']
    for name in ('RiskDimension','RiskCheck'):
        if name in wire['$defs']:
            assert {'fact_refs','evidence_refs'} <= set(wire['$defs'][name]['required'])
    assert output_type.model_json_schema()==original
    # A deliberately unsupported reply remains inspectable, never repaired
    # into evidence by copying its reference IDs or guessing source passages.
    sources={'E1':{'S1':{'text':'Exact source text available to the model.'}}}
    raw={'drugs':[{'drug_code':'a','quotes':[], 'evidence_refs':['E1']}]}
    assert resolve_selections(raw,sources)['drugs'][0]['quotes']==[]


@pytest.mark.parametrize('text', [
    'Adult urinary infection\n\n' + 'Exact original text. ' * 200,
    'CHILDREN ONLY\r\n' + '限定條件與原文' * 1000,
    'x' * 1401,
], ids=['paragraphs','unicode','short_tail'])
def test_spans_preserve_every_character_and_source_offsets(text):
    spans = source_spans(text)
    assert ''.join(p['text'] for p in spans) == text
    assert all(p['text'] == text[p['start']:p['end']] for p in spans)
    assert all(10 <= len(p['text']) <= 1600 for p in spans)


@pytest.mark.parametrize('selection', [
    {'chunk_id':'E2','span_ids':['S1']},
    {'chunk_id':'E1','span_ids':['S9']},
    {'chunk_id':'E1','span_ids':[]},
    {'chunk_id':'E1','span_ids':'S1'},
    {'chunk_id':'E1','span_ids':['S1'],'quote':'invented original'},
    {'chunk_id':'E1','quote':'invented original'},
])
def test_invalid_selectors_cannot_create_quotes(selection):
    sources = {'E1': {'S1': {'text':'Real original source.'}}}
    with pytest.raises(ValueError):
        resolve_selections({'drugs':[{'quotes':[selection]}]}, sources)


def test_partial_bad_quote_preserves_valid_source_without_claiming_support():
    data = {'drugs':['a'],'evidence':[{'chunk_id':'e1','text':'Real original source.'}]}
    raw = {'findings':[],'issues':[],'drugs':[{'drug_code':'a','drug_name':'a',
        'status':'supported','reason':'原文支持','applicability':'測試情境',
        'quotes':[{'chunk_id':'e1','quote':'Real original source.'},
                  {'chunk_id':'e1','quote':'Invented original source.'}]}]}
    value = validate_output(rt.AGENTS[2], raw, data)['drugs'][0]
    assert value['status'] == 'uncertain'
    assert value['quotes'] == raw['drugs'][0]['quotes'][:1]
    assert value['citation_validation'] == {'valid_count':1,'invalid_count':1}
    assert len(raw['drugs'][0]['quotes']) == 2


def test_selected_real_quote_still_requires_semantic_support():
    raw = {'findings':[],'issues':[],'drugs':[{'drug_code':'a','verdict':'supported',
        'infection_match':'unsupported','population_match':'unsupported','drug_match':'supported',
        'reason':'不同感染與族群','quotes':[{'chunk_id':'E1','span_ids':['S1']}]}]}
    sources = {'E1':{'S1':{'text':'Drug a for febrile neutropenia only.'}}}
    restored = resolve_selections(raw, sources)
    result = validate_output(rt.AGENTS[5],restored,{'drugs':['a'], 'claims':[{'drug_code':'a'}],
        'evidence':[{'chunk_id':'E1','text':sources['E1']['S1']['text']}]})
    assert result['drugs'][0]['verdict'] == 'unsupported'


def test_wire_selection_roundtrip_execution_review_and_trace(monkeypatch):
    def fake_transport(self, agent, wire, **kw):
        result = successful(self,agent,wire,**kw)
        for row in result['output'].get('drugs', []):
            if agent.id=='clinical_agent':
                for field in ('allergy','renal','interactions'): row.pop(field,None)
            if 'quotes' in row:
                row['quotes'] = [{'chunk_id':'E1','span_ids':['S1']}]
            if 'evidence_refs' in row:
                row['evidence_refs'] = ['E1']
        def aliases(value):
            if isinstance(value,dict): return {k:aliases(v) for k,v in value.items()}
            if isinstance(value,list): return [aliases(v) for v in value]
            return 'E1' if value=='e1' else value
        result['output']=aliases(result['output'])
        return result
    monkeypatch.setattr(AgentProvider,'complete',fake_transport)
    monkeypatch.setattr(rt.Provider,'check',lambda *args:None)
    value = case()
    before = copy.deepcopy(value)
    run = execute(value,'multi-agent','live',Docs())
    assert not run['errors']
    assert run['agent_execution']['calls'] == 6
    assert run['output']['candidates']
    assert validate_review(run)['valid']
    node = next(n for n in run['nodes'] if n['node_id']=='evidence_agent')
    assert node['attempts'][0]['citation_spans']['E1']['S1']['start'] == 0
    assert node['output']['drugs'][0]['quotes'][0]['chunk_id'] == 'e1'
    assert value == before


def test_synthesis_does_not_duplicate_long_quotes_but_audit_keeps_source(monkeypatch):
    import json
    names=' '.join(f'drug_{i}' for i in range(18))+'. Allergy precautions, renal adjustment and drug interactions. '
    class LongDocs:
        def search(self,query,**kwargs):
            return {'evidence':[{'chunk_id':'e1','text':names+'Original context. '*3500,'document_kind':'guideline'}]}
    def long_report(self,agent,data,**kwargs):
        reply=successful(self,agent,data,**kwargs)
        for row in reply['output'].get('drugs',[]):
            if 'quotes' in row: row['quotes']=[{'chunk_id':'e1','quote':names+'Original context. '*70} for _ in range(4)]
        if agent.id=='synthesis_agent':
            assert all('text' not in e for e in data['evidence'])
            assert all('quotes' not in row for row in data['assessments']['clinical_agent']['drugs'])
            assert data['assessments']['clinical_agent']['drugs'][0]['evidence_refs']==['e1']
            assert len(json.dumps(data,ensure_ascii=False))<180000
        if agent.id=='evidence_audit':
            assert data['evidence'][0]['text']==names+'Original context. '*3500
            assert not data['assessments']
        return reply
    monkeypatch.setattr(rt.Provider,'complete',long_report)
    value=case()
    value['ast_results']=[{**value['ast_results'][0],'drug_code':f'drug_{i}'} for i in range(18)]
    run=execute(value,'multi-agent','mock',LongDocs())
    assert not run['errors']
    assert len(run['output']['candidates'])==18
    assert run['agent_execution']['calls']==6


def test_invalid_selection_preserves_model_usage_for_retry_accounting(monkeypatch):
    def fake(self,agent,data,**kw):
        return {'output':{'drugs':[{'drug_code':'a','drug_name':'a','status':'supported','reason':'source','applicability':'case','quotes':[{'chunk_id':'E1','span_ids':['S999']}]}]},
                'usage':{'total_tokens':123},'response_id':'fixture-response'}
    monkeypatch.setattr(AgentProvider,'complete',fake)
    reply=rt.Provider('live',rt.AGENTS[2]).complete(rt.AGENTS[2],
        {'evidence':[{'chunk_id':'original','text':'Original source text.'}]},timeout=1)
    assert reply['usage'] == {'total_tokens':123}
    assert reply['response_id'] == 'fixture-response'
    assert reply['output']['drugs']==[] and reply['wire_errors']
