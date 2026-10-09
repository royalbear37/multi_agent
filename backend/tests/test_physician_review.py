import copy
import pytest
from fastapi.testclient import TestClient
from app import main
from app.repositories import SQLiteRepository

@pytest.fixture
def review_env(tmp_path,monkeypatch):
 repo=SQLiteRepository(tmp_path/'physician.db');monkeypatch.setattr(main,'repo',repo)
 run={'run_id':'r','case_id':'c','mode':'multi-agent','decision_basis':'agent','case_revision':4,
      'versions':{'workflow':'agent-led-1.4.1'},'gate_status':'needs_confirmation',
      'case_snapshot':{'allergies':{'status':'known_none','items':[]}},
      'output':{'candidates':[],'pending':[],'avoid':[]},'agent_candidate_boundary':{'allowed_drugs':[],'evidence_by_drug':{}},
      'drug_assessments':[{'drug_code':'a','status':'pending','blockers':[{'detail':'來源尚未確認'}],'source_ast':[{'drug_code':'a','reported_sir':'R'}]},
                          {'drug_code':'b','status':'avoid','reason':'來源記載限制'}]}
 repo.upsert_case({'case_id':'c'}, {'case_id':'c'}, [])
 repo.create_run('r','c','multi-agent','mock',None,None,run)
 yield TestClient(main.app),run,repo
 repo.close()

def body(**change):
 return {'run_id':'r','action':'drug_review','reason':'醫師逐藥判斷','reviewer_id':'test-doctor','role':'physician',
         'drug_decisions':[{'drug_code':'a','decision':'conditional','reason':'需先核對限制','conditions':'確認來源後再判斷','acknowledged_warnings':True}],**change}

def test_conditional_decision_preserves_original_run_warnings_and_export(review_env):
 client,run,repo=review_env
 result=client.post('/api/reviews',json=body());assert result.status_code==200,result.text
 value=result.json()
 assert value['new_output'] is None and value['system_status_unchanged']
 assert value['drug_decisions'][0]['system_assessment']==run['drug_assessments'][0]
 assert repo.get_run('r')==run
 assert client.get('/api/reviews/'+value['review_id']+'/export').json()==value
 assert client.get('/api/runs/r/export').json()['drug_assessments']==run['drug_assessments']
 assert client.get('/api/reviews?run_id=r').json()==[value]

@pytest.mark.parametrize('change',[{'drug_code':'new'},{'conditions':' '},{'reason':' '},{'acknowledged_warnings':False},{'acknowledged_warnings':'true'}])
def test_invalid_decisions_rejected(review_env,change):
 client,run,repo=review_env;request=body();request['drug_decisions'][0].update(change)
 assert client.post('/api/reviews',json=request).status_code==422
 assert not repo.list_reviews('r') and repo.get_run('r')==run

def test_duplicate_unselected_role_and_system_replacement_rejected(review_env):
 client,_,_=review_env
 request=body();request['drug_decisions']*=2
 for request in [request,body(drug_decisions=[]),body(role='research'),body(proposed_output={}),body(reviewer_id='   ')]:
  assert client.post('/api/reviews',json=request).status_code==422

def test_human_adoption_of_avoid_is_attributed_not_system_promotion(review_env):
 client,run,repo=review_env
 request=body();request['drug_decisions']=[{'drug_code':'b','decision':'adopt','reason':'醫師說明另行判斷依據','acknowledged_warnings':True}]
 value=client.post('/api/reviews',json=request);assert value.status_code==200
 assert value.json()['drug_decisions'][0]['system_assessment']['status']=='avoid'
 assert repo.get_run('r')['output']['candidates']==[]
 request=body(action='modify',drug_decisions=[],proposed_output={'candidates':[{'drug_code':'b','reason':'override','evidence_refs':[],'rule_refs':[]}],'avoid':[],'limitations':[]})
 assert client.post('/api/reviews',json=request).status_code==422

def test_decline_does_not_require_adoption_ack_and_other_modes_unchanged(review_env):
 client,run,repo=review_env
 request=body();request['drug_decisions']=[{'drug_code':'a','decision':'decline','reason':'不採用'}]
 assert client.post('/api/reviews',json=request).status_code==200
 changed=copy.deepcopy(run);changed['decision_basis']='rule';repo.save_run('r',changed)
 assert client.post('/api/reviews',json=body()).status_code==422
 assert client.get('/api/reviews/missing/export').status_code==404
