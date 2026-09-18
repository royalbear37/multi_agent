import copy
import csv
import json

import pytest
from app.adapters.microbiology import REQUIRED, ast_row, build_case, prepare
from app.rules.engine import RuleEngine
from app.schemas.case import Case
from app.workflow.engine import execute, validate_review


def row(drug='ceftriaxone', original='Susceptible', clsi='Susceptible', **changes):
    value = {k: '' for k in REQUIRED | {'AST_inequality','AST_val1','AST_val2'}}
    value.update(anon_id='1', pat_enc_csn_id_coded='2', order_proc_id_coded='3',
                 organism='ESCHERICHIA COLI', culture_description='URINE', antibiotic=drug,
                 has_AST='X', AST_panel='broth_microdilution', AST_val1='1',
                 AST_pheno=original, CLSI_2022_pheno=clsi)
    value.update(changes)
    return value


def case():
    return build_case(('1','2','3','ESCHERICHIA COLI'), [row(), row('ampicillin','Resistant','Resistant')], 'abc12345', 'who-v1', 1)


class Documents:
    def __init__(self): self.scopes = []
    def search(self, query, policy_refs=None, *, scope='synthetic'):
        self.scopes.append(scope)
        return {'status': 'ok', 'evidence': [{'chunk_id':'ref-1','doc_id':'who-v1','document_version':'2022','text':'Adult reference fixture for retrieval plumbing; no clinical recommendation.','location':{'page':1},'is_synthetic':False,'population':'adult'}]}


def test_actual_names_and_reference_evidence_reach_review():
    docs = Documents()
    run = execute(case(), 'rule-only', document_service=docs)
    assert run['gate_status'] == 'ready_for_review', run
    assert docs.scopes == ['reference']
    assert [x['drug_code'] for x in run['output']['candidates']] == ['ceftriaxone']
    assert [x['drug_code'] for x in run['output']['avoid']] == ['ampicillin']
    assert 'DEMO_DRUG' not in json.dumps(run) and 'DEMO_ORGANISM' not in json.dumps(run)
    assert validate_review(run, run['output'])['valid']
    edited = copy.deepcopy(run['output'])
    edited['candidates'][0]['drug_code'] = 'ampicillin'
    with pytest.raises(ValueError): validate_review(run, edited)


@pytest.mark.parametrize('label', ['Intermediate','Resistant','Susceptible dose dependent','Susceptible dose-dependent','Non-susceptible',''])
def test_non_s_is_never_coerced_to_s(label):
    value = case()
    value['ast_results'] = [ast_row(row(original=label, clsi=label))]
    assert RuleEngine().candidate_drugs(value) == []


def test_conflict_and_unknown_measurement_do_not_invent_mic():
    value = case()
    value['ast_results'].append(ast_row(row('ciprofloxacin','Susceptible','Intermediate', AST_panel='kirby_bauer', AST_val1='22')))
    assert value['ast_results'][-1].get('mic') is None
    results = RuleEngine().evaluate_ast(value)
    assert any('不同' in r['reason'] for r in results if r['drug_code']=='ciprofloxacin')
    assert RuleEngine().candidate_drugs(value) == ['ceftriaxone']


def test_allergy_excludes_one_drug_without_suppressing_alternatives():
    value = case()
    value['ast_results'].append(ast_row(row('ciprofloxacin')))
    value['allergies'] = {'status':'known_present','items':[{'drug_code':'ceftriaxone'}]}
    assert RuleEngine().candidate_drugs(value) == ['ciprofloxacin']
    run = execute(value, 'rule-only', document_service=Documents())
    assert run['gate_status'] == 'ready_for_review'
    assert {x['drug_code'] for x in run['output']['avoid']} == {'ampicillin','ceftriaxone'}


def test_preliminary_and_duplicate_conflicts_not_eligible():
    value = case()
    value['microbiology']['report_status'] = 'preliminary'
    assert not RuleEngine().candidate_drugs(value)
    value['microbiology']['report_status'] = 'final'
    value['ast_results'].append(ast_row(row('ceftriaxone','Resistant','Resistant')))
    assert not RuleEngine().candidate_drugs(value)


def test_standard_label_mismatch_and_duplicate_review_are_rejected():
    value=case(); value['ast_results'][0]['standard_version']='2025'
    assert not RuleEngine().candidate_drugs(value)
    run=execute(case(),'rule-only',document_service=Documents())
    proposed=copy.deepcopy(run['output'])
    proposed['candidates'].append(copy.deepcopy(proposed['candidates'][0]))
    with pytest.raises(ValueError): validate_review(run,proposed)


def test_stream_groups_nonadjacent_rows_and_marks_simulated_fields(tmp_path):
    path = tmp_path / 'source.csv'
    data = [row(), row('ampicillin', anon_id='4', order_proc_id_coded='8', mult_org_ast='X'), row('ampicillin','Resistant','Resistant')]
    with path.open('w',newline='',encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader(); writer.writerows(data)
    out = tmp_path/'prepared'
    report = prepare(path, out, 'who-v1', per_site=1)
    cases = json.loads((out/'cases.json').read_text(encoding='utf-8'))
    assert report['rows'] == 3 and report['cases'] == 2
    assert len(cases[0]['ast_results']) == 2
    assert cases[0]['data_origin'] == 'hybrid' and cases[0]['is_synthetic'] is False
    assert cases[0]['external_model_allowed'] is False
    assert 'renal' in cases[0]['provenance']['simulated_fields']
    assert cases[0]['microbiology']['collected_at'] is None
    for value in cases: Case.model_validate(value)


def test_source_case_needs_origin_and_provenance():
    value=case(); value['data_origin']='synthetic'
    with pytest.raises(ValueError): Case.model_validate(value)
    value=case(); value['provenance']['simulated_fields']=[]
    with pytest.raises(ValueError): Case.model_validate(value)


def test_provider_local_source_input_and_no_outbound_identifiers():
    from app.providers.service import OpenAICompatibleProvider, ProviderError
    from app.workflow.engine import _summary
    payloads=[]
    def post(url, **kwargs):
        payloads.append(kwargs['json'])
        return {'choices':[{'message':{'content':'{"candidates":[],"avoid":[],"limitations":[]}'}}]}
    context={'case_summary':_summary(case()),'allowed_drugs':['ceftriaxone'],'evidence':[],'rule_refs':[]}
    local=OpenAICompatibleProvider('http://127.0.0.1:11434/v1','local','unused',http_post=post)
    local.generate(context)
    sent=json.loads(payloads[0]['messages'][1]['content'])['case_summary']
    assert sent['data_origin']=='hybrid' and 'case_id' not in sent
    assert 'source_record_id' not in json.dumps(payloads)
    remote=OpenAICompatibleProvider('https://provider.invalid/v1','remote','unused',http_post=post)
    with pytest.raises(ProviderError): remote.generate(context)
    context['case_summary']['external_model_allowed']=True
    remote.generate(context)


def test_mock_multiagent_uses_real_names():
    run=execute(case(), 'multi-agent','mock',Documents())
    assert run['gate_status']=='ready_for_review', run['errors']
    assert run['output']['candidates'][0]['drug_code']=='ceftriaxone'
    assert run['output']['avoid'][0]['drug_code']=='ampicillin'


def test_negative_scope_statement_does_not_disable_prescription_checks():
    from app.workflow.safety import forbidden_text
    from app.providers.service import _safe_output, ProviderError
    disclaimer='本建議不包含劑量、頻率及療程，需人工確認。'
    assert not forbidden_text(disclaimer)
    for suffix in [' 500 mg', ' 每日兩次', ' q8h', ' take 2 tablets']:
        assert forbidden_text(disclaimer + suffix)
    context={'allowed_drugs':[],'rule_refs':[],'evidence':[]}
    assert _safe_output({'candidates':[],'avoid':[],'limitations':[disclaimer]},context)
    with pytest.raises(ProviderError):
        _safe_output({'candidates':[],'avoid':[],'limitations':[disclaimer+' 500 mg']},context)


def test_evidence_query_preserves_age_population():
    from app.workflow.engine import evidence_query
    value=case()
    assert evidence_query(value).endswith('adults')
    value['demographics']['age']=10
    assert evidence_query(value).endswith('children')
    value['demographics']['age']=None
    assert 'children' not in evidence_query(value) and 'adults' not in evidence_query(value)


def test_reference_evidence_is_filtered_by_patient_population():
    class MixedDocuments:
        def search(self, query, policy_refs=None, *, scope='synthetic'):
            return {'status': 'ok', 'evidence': [
                {'chunk_id':'adult','text':'Guidance for adults.', 'population':'adult'},
                {'chunk_id':'child','text':'Pediatric guidance for children.', 'population':'pediatric'},
                {'chunk_id':'unknown','text':'Guidance without a named age group.', 'population':'mixed'},
            ]}

    adult = execute(case(), 'rule-only', document_service=MixedDocuments())
    assert adult['gate_status'] == 'ready_for_review'
    assert adult['output']['candidates'][0]['evidence_refs'] == ['adult']
    population = next(n for n in adult['nodes'] if n['node_id'] == 'evidence_retrieval')['output']['population_filter']
    assert {k: population[k] for k in ('case_population','matched','mismatched','unverified')} == {'case_population':'adult', 'matched':1, 'mismatched':1, 'unverified':1}
    assert [e['chunk_id'] for e in population['excluded']] == ['child', 'unknown']

    child_case = case()
    child_case['demographics']['age'] = 10
    child = execute(child_case, 'rule-only', document_service=MixedDocuments())
    assert child['output']['candidates'][0]['evidence_refs'] == ['child']


def test_reference_evidence_requires_age_and_verified_population():
    value = case()
    value['demographics']['age'] = None
    run = execute(value, 'rule-only', document_service=Documents())
    assert run['gate_status'] == 'needs_confirmation'
    assert run['output'] is None
    assert 'demographics.age_for_evidence' in run['missing_fields']

    class PediatricOnly:
        def search(self, query, policy_refs=None, *, scope='synthetic'):
            return {'status':'ok', 'evidence':[{'chunk_id':'peds','text':'Children only guidance.', 'population':'pediatric'}]}
    mismatched = execute(case(), 'rule-only', document_service=PediatricOnly())
    assert mismatched['gate_status'] == 'needs_confirmation'
    assert mismatched['output'] is None
    assert 'evidence.population_applicability' in mismatched['missing_fields']


@pytest.mark.parametrize('text', [
    'Not applicable to adults.',
    'Adult guidance is discussed elsewhere; this fragment has no recommendation.',
    '成人不適用本段。',
    'Adults and children have different sections.',
])
def test_age_keywords_do_not_certify_unlabelled_evidence(text):
    from app.workflow.engine import _evidence_population
    assert _evidence_population({'text': text}, 'adult') != 'matched'
    assert _evidence_population({'text': text, 'population': 'mixed'}, 'adult') != 'matched'


@pytest.mark.parametrize('population', ['all', 'adult'])
def test_document_label_cannot_override_pediatric_fragment(population):
    from app.workflow.engine import _evidence_population
    assert _evidence_population(
        {'text': 'Pediatric chart for children.', 'population': population}, 'adult'
    ) != 'matched'


@pytest.mark.parametrize('mode', ['rag-only','single-agent','multi-agent'])
def test_no_applicable_reference_skips_generation(monkeypatch, mode):
    from app.providers import service
    def unexpected_provider(kind):
        raise AssertionError('Generation should not be attempted without applicable evidence')
    monkeypatch.setattr(service, 'get_provider', unexpected_provider)
    class Unlabelled:
        def search(self, *args, **kwargs):
            return {'status':'ok', 'evidence':[{'chunk_id':'unverified', 'text':'Adults only?'}]}
    run = execute(case(), mode, 'live', Unlabelled())
    assert run['output'] is None
    assert run['gate_status'] == 'needs_confirmation'
    assert run['errors'] == []
    node = next(n for n in run['nodes'] if n['node_id'] == 'candidate_presentation')
    assert node['status'] == 'skipped' and node['output']['attempted'] is False


def test_legacy_unlabelled_snapshot_cannot_be_accepted_as_population_verified():
    run = execute(case(), 'rule-only', document_service=Documents())
    run['evidence_snapshots'][0].pop('population')
    with pytest.raises(ValueError, match='population-labelled'):
        validate_review(run, run['output'])
