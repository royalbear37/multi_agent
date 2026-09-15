import copy
import pytest
from app.rules.engine import RuleEngine
from app.workflow.engine import execute, validate_review
from tests.test_workflow import case, DocStub

@pytest.mark.parametrize('text',['take 2 tablets every 8 hours for 7 days','每次服用兩顆，每日三次','500 mg','q8h'])
def test_prescription_text_cannot_be_added_in_review(text):
    run=execute(case(),'rule-only',document_service=DocStub())
    edited=copy.deepcopy(run['output'])
    edited['candidates'][0]['reason']=text
    with pytest.raises(ValueError): validate_review(run,edited)

@pytest.mark.parametrize('field,value',[('unit','WRONG_UNIT'),('standard_version','unknown'),('comparator','>')])
def test_unconfigured_ast_measurement_never_passes(field,value):
    data=case(); data['ast_results'][0][field]=value
    run=execute(data,'rule-only',document_service=DocStub())
    assert run['output'] is None
    assert next(n for n in run['nodes'] if n['node_id']=='ast')['output']['system_result']=='needs_review'

def test_rule_required_fields_are_executed():
    engine=RuleEngine(); config=engine.snapshot()
    config['rules']=[{'rule_id':'NEEDS_FIELD','required_fields':['renal.unit'],'condition':{'op':'exists','path':'renal.egfr'}}]
    data=case(); data['renal']['unit']=None
    assert RuleEngine(config).evaluate(data)[0]['status']=='unknown'

@pytest.mark.parametrize('kind',['mock','live'])
def test_baseline_input_does_not_receive_rule_derived_candidate_set(monkeypatch,kind):
    from app.providers import service
    calls=[]
    class Fake:
        def status(self): return {'configured':True}
        def generate(self,context):
            calls.append(copy.deepcopy(context))
            return {'output':{'candidates':[{'drug_code':'DEMO_DRUG_A','reason':'synthetic evidence summary','rule_refs':context['rule_refs'],'evidence_refs':['demo_chunk']}],'avoid':[],'limitations':[]},'is_mock':kind=='mock','usage':None,'model':'fake'}
    monkeypatch.setattr(service,'get_provider',lambda _:Fake())
    for mode in ['rag-only','single-agent','multi-agent']:
        run=execute(case(),mode,kind,DocStub())
        assert run['output'] is not None,run
        validate_review(run,run['output'])
    assert calls[0]['allowed_drugs']==RuleEngine().allowed_drugs()
    assert calls[0]['rule_refs']==[] and 'ast_results' not in calls[0]['case_summary']
    assert calls[1]['case_summary']['ast_results']==case()['ast_results']
    assert calls[2]['allowed_drugs']==['DEMO_DRUG_A']
    assert calls[2]['node_summaries']

@pytest.mark.parametrize('bad_field,bad_value',[('drug_code','DEMO_DRUG_C'),('evidence_refs',['fabricated']),('rule_refs',['invented'])])
def test_provider_cannot_escape_shared_final_gate(monkeypatch,bad_field,bad_value):
    from app.providers import service
    class Fake:
        def status(self): return {'configured':True}
        def generate(self,context):
            item={'drug_code':'DEMO_DRUG_A','reason':'synthetic','rule_refs':context['rule_refs'],'evidence_refs':['demo_chunk']}
            item[bad_field]=bad_value
            return {'output':{'candidates':[item],'avoid':[],'limitations':[]}}
    monkeypatch.setattr(service,'get_provider',lambda _:Fake())
    run=execute(case(),'multi-agent','live',DocStub())
    assert run['gate_status']=='blocked' and run['output'] is None
    assert run['raw_baseline']['payload']

def test_later_rule_file_changes_cannot_change_review(monkeypatch):
    from app.rules import engine
    run=execute(case(),'rule-only',document_service=DocStub())
    monkeypatch.setattr(engine,'load_demo_rules',lambda: {'status':'not_configured','rules':[]})
    assert validate_review(run,run['output'])['valid']

def test_document_conflict_cannot_be_hidden_by_limit(tmp_path):
    from app.rag.service import DocumentService
    docs=DocumentService(tmp_path, retrieval_mode="lexical")
    docs.import_document('a.md',b'# POLICY\nDEMO_ORGANISM_A first','Same policy','v1')
    docs.import_document('b.md',b'# POLICY\nDEMO_ORGANISM_A second','Same policy','v2')
    assert docs.search('DEMO_ORGANISM_A',limit=1)['status']=='conflict'
