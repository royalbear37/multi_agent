"""End-to-end HTTP persistence and safety acceptance, with isolated storage."""
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main
from app.repositories import SQLiteRepository
from app.rag.service import DocumentService

@pytest.fixture
def client(tmp_path, monkeypatch):
    repository = SQLiteRepository(tmp_path / 'cases.db')
    documents = DocumentService(tmp_path / 'documents', retrieval_mode="lexical")
    monkeypatch.setattr(main, 'repo', repository)
    monkeypatch.setattr(main, '_documents', lambda: documents)
    with TestClient(main.app) as session:
        assert session.post('/api/seed').status_code == 200
        yield session, repository, documents
    repository.close()

def run_case(c, case_id='case-01-complete', mode='rule-only', **extra):
    r = c.post('/api/runs', json={'case_id':case_id, 'mode':mode, 'provider_kind':'unconfigured', **extra})
    assert r.status_code == 200, r.text
    return r.json()

def test_complete_review_survives_repository_reopen(client):
    c, repository, _ = client
    run = run_case(c)
    assert run['gate_status'] == 'ready_for_review', run
    assert run['output']['candidates']
    review = c.post('/api/reviews', json={'run_id':run['run_id'], 'action':'accept', 'reason':'synthetic acceptance', 'reviewer_id':'demo-user', 'role':'physician'})
    assert review.status_code == 200, review.text
    reopened = SQLiteRepository(repository.path)
    try:
        assert reopened.get_run(run['run_id'])['evidence_snapshots'] == run['evidence_snapshots']
        assert reopened.list_reviews(run['run_id'])[0]['reason'] == 'synthetic acceptance'
    finally:
        reopened.close()

def test_request_retry_is_idempotent_and_revision_does_not_change_old_run(client):
    c, _, _ = client
    run = run_case(c, request_id='stable-request')
    again = run_case(c, request_id='stable-request')
    assert again['run_id'] == run['run_id']
    original = c.get('/api/cases/case-01-complete').json()
    revised = copy.deepcopy(original['case'])
    revised['allergies'] = {'status':'unknown','items':[]}
    saved = c.post('/api/cases/case-01-complete/revisions',json={'payload':revised})
    assert saved.status_code == 200, saved.text
    assert saved.json()['revision'] == original['revision'] + 1
    assert c.get('/api/runs/'+run['run_id']).json() == run
    next_run = run_case(c, previous_run_id=run['run_id'])
    assert next_run['run_id'] != run['run_id']
    assert next_run['gate_status'] != 'ready_for_review'
    assert not (next_run.get('output') or {}).get('candidates')

@pytest.mark.parametrize('case_id',['case-02-renal-missing','case-03-allergy-unknown','case-04-allergy-match','case-05-resistance','case-06-mic-unit-missing','case-07-standard-unknown','case-08-conflict','case-09-no-ast-rapid','case-10-no-policy','case-11-unsupported','case-14-version-conflict'])
def test_incomplete_or_conflicting_cases_never_publish_candidates(client, case_id):
    c, _, _ = client
    run = run_case(c, case_id)
    assert run['gate_status'] != 'ready_for_review', (case_id,run)
    assert not (run.get('output') or {}).get('candidates'), (case_id,run)
    injected={'candidates':[{'drug_code':'DEMO_DRUG_A','reason':'可供考慮','rule_refs':[],'evidence_refs':[]}],'avoid':[],'limitations':[]}
    response=c.post('/api/reviews',json={'run_id':run['run_id'],'action':'modify','reason':'attempt to bypass','reviewer_id':'demo','role':'physician','proposed_output':injected})
    assert response.status_code == 422

def test_four_modes_unconfigured_and_mock_are_separate(client):
    c, _, _ = client
    for mode in ['rag-only','single-agent','multi-agent']:
        run=run_case(c,mode=mode)
        assert run['status'] in ['partial','not_configured']
        assert not run['is_mock']
        mock=c.post('/api/runs',json={'case_id':'case-01-complete','mode':mode,'provider_kind':'mock'}).json()
        assert mock['is_mock'] is True
        assert mock['gate_status'] == 'ready_for_review', mock
        assert mock['output']['candidates'], mock

def test_document_multipart_roundtrip_and_missing_source(client):
    c, _, _ = client
    r=c.post('/api/documents/import',data={'title':'正式文件保存測試','version':'2026.1','is_synthetic':'false'},files={'file':('reference.md',b'# REFERENCE\nDOCUMENT_TEST_TOKEN','text/markdown')})
    assert r.status_code == 200,r.text
    doc=r.json()
    assert doc['document_version']=='2026.1'
    assert doc['is_synthetic'] is False
    assert c.get('/api/documents/'+doc['doc_id']+'/source').content == b'# REFERENCE\nDOCUMENT_TEST_TOKEN'
    assert not c.get('/api/documents/search?q=DOCUMENT_TEST_TOKEN').json()['evidence']
    assert c.get('/api/documents/missing/source').status_code==404

def test_restart_recovers_running_task(client):
    _, repository, _ = client
    repository.create_run('interrupted-test','case-01-complete','rule-only','unconfigured',None,None,{'run_id':'interrupted-test','status':'running'})
    assert repository.recover_running()==1
    assert repository.get_run('interrupted-test')['status']=='failed'

def test_valid_modify_and_reject_are_saved_without_mutating_run(client):
    c, _, _ = client
    run=run_case(c)
    edited=copy.deepcopy(run['output'])
    edited['candidates'][0]['reason']='人工核對 synthetic 證據，保留此展示候選。'
    body={'run_id':run['run_id'],'action':'modify','reason':'展示修改','reviewer_id':'demo-pharmacist','role':'pharmacist','proposed_output':edited}
    response=c.post('/api/reviews',json=body)
    assert response.status_code==200,response.text
    assert response.json()['new_output']['candidates'][0]['reason']==edited['candidates'][0]['reason']
    body.update(action='reject',reason='展示拒絕');body.pop('proposed_output')
    assert c.post('/api/reviews',json=body).status_code==200
    assert len(c.get('/api/reviews',params={'run_id':run['run_id']}).json())==2
    assert c.get('/api/runs/'+run['run_id']).json()==run

def test_benchmark_records_all_modes_and_keeps_configuration(client):
    c, repository, _ = client
    request={'case_ids':['case-01-complete','case-03-allergy-unknown'],'modes':['rule-only','rag-only','single-agent','multi-agent'],'provider_kind':'mock','request_id':'benchmark-idempotence'}
    result=c.post('/api/benchmarks',json=request)
    assert result.status_code==200,result.text
    b=result.json()
    assert len(b['results'])==8
    assert set(b['summary']['by_mode'])==set(request['modes'])
    assert b['is_mock'] is True
    assert c.post('/api/benchmarks',json=request).json()['benchmark_id']==b['benchmark_id']
    export=c.get('/api/benchmarks/'+b['benchmark_id']+'/export').json()
    assert export['disclaimer']==main.DISCLAIMER
    for run in export['results']:
        assert 'payload' not in run.get('raw_baseline',{})
        assert run['case_snapshot']['is_synthetic'] is True
        assert repository.get_run(run['run_id'])

def test_unknown_model_does_not_count_as_generated_schema_success():
    from app.workflow.benchmark import summarize
    result={'case_id':'X','mode':'multi-agent','status':'partial','gate_status':'ready_for_review','output':None,'nodes':[{'node_id':'candidate_presentation','status':'not_configured','output':{'schema_valid':False}}]}
    summary=summarize([result],{})
    assert summary['schema_validity']['denominator']==0
    assert summary['rule_test_pass_rate']['value'] is None
    assert summary['missing_precision']['value'] is None

def test_no_clinical_rule_claim_from_unrecognized_standard(client):
    c, _, _ = client
    case=c.get('/api/cases/case-01-complete').json()['case']
    case['case_id']='unsupported-standard'
    case['ast_results'][0]['standard']='UNCONFIGURED_REAL_STANDARD'
    c.post('/api/cases/import',json={'payload':case}).raise_for_status()
    run=run_case(c,'unsupported-standard')
    assert run['gate_status']!='ready_for_review'
    assert not (run.get('output') or {}).get('candidates')
