import copy
import json
from app.workflow.physician_candidates import add_physician_candidates
from app.workflow.audit_context import fit_audit_context


def test_missing_audit_and_general_warnings_do_not_hide_physician_candidates():
    run={'decision_basis':'agent','case_snapshot':{'allergies':{'status':'known_none','items':[]}},
         'output':{'candidates':[]},'drug_assessments':[
             {'drug_code':'amoxicillin_clavulanate','status':'pending','audit':None},
             {'drug_code':'amikacin','status':'pending','clinical':{'status':'caution'},'audit':None},
             {'drug_code':'unknown','status':'pending','ast':{'assessment':'conflicting'}},
             {'drug_code':'not_selected','status':'not_selected'}]}
    before=copy.deepcopy(run)
    add_physician_candidates(run)
    assert len(run['physician_candidates'])==4
    assert run['output']==before['output'] and run['drug_assessments']==before['drug_assessments']
    assert all(x['verification_status']=='incomplete' for x in run['physician_candidates'])


def test_confirmed_resistance_and_direct_severe_allergy_are_separate_not_hidden():
    run={'decision_basis':'agent','case_snapshot':{'allergies':{'status':'known_present','items':[
         {'drug_code':'amoxicillin','severity':'severe','verification_status':'confirmed'}]}},
         'drug_assessments':[{'drug_code':'amoxicillin','status':'pending'},
         {'drug_code':'tetracycline','status':'pending','ast':{'assessment':'resistant','source_validation':{'status':'confirmed'}}},
         {'drug_code':'other','status':'pending','clinical':{'model_status':'avoid'}},
         {'drug_code':'bad-source','status':'pending','ast':{'assessment':'resistant','source_validation':{'status':'unconfirmed'}}}]}
    add_physician_candidates(run)
    assert {x['drug_code'] for x in run['physician_candidates']}=={'other','bad-source'}
    assert {x['drug_code'] for x in run['physician_excluded']}=={'amoxicillin','tetracycline'}
    assert all(x['exclusion_reasons'] for x in run['physician_excluded'])


def test_audit_input_budget_preserves_claims_and_round_robins_real_sources():
    claims=[{'drug_code':drug,'claims':[{'dimension':'infection','statement':'Check against original',
             'evidence_refs':[f'{drug}1',f'{drug}2']}]} for drug in ['a','b','c']]
    data={'facts':{'allergies':{'status':'known_none'}},'claims':claims,
          'evidence':[{'chunk_id':f'{drug}{i}','text':drug*2000,'document_title':drug} for drug in ['a','b','c'] for i in [1,2]]}
    original=copy.deepcopy(data)
    fitted=fit_audit_context(data, limit=8500)
    assert len(json.dumps(fitted,ensure_ascii=False))<=8500
    assert fitted['claims']==original['claims'] and fitted['facts']==original['facts'] and data==original
    assert [e['chunk_id'] for e in fitted['evidence']]==['a1','b1','c1']
    assert all(e in original['evidence'] for e in fitted['evidence'])
    assert all(g['omitted_count']==1 for g in fitted['evidence_groups'])


def test_public_view_and_export_do_not_rewrite_saved_analysis(tmp_path,monkeypatch):
    from app import main
    from app.repositories import SQLiteRepository
    from fastapi.testclient import TestClient
    repo=SQLiteRepository(tmp_path/'view.db');monkeypatch.setattr(main,'repo',repo)
    run={'run_id':'old','case_id':'case','mode':'multi-agent','decision_basis':'agent','status':'partial',
         'output':{'candidates':[]},'drug_assessments':[{'drug_code':'amikacin','status':'pending'}]}
    repo.upsert_case({'case_id':'case'},{},[])
    repo.create_run('old','case','multi-agent','mock',None,None,run)
    client=TestClient(main.app)
    assert client.get('/api/runs/old').json()['physician_candidates'][0]['drug_code']=='amikacin'
    assert client.get('/api/runs/old/export').json()['physician_candidates'][0]['verification_status']=='incomplete'
    assert repo.get_run('old')==run
    repo.close()
