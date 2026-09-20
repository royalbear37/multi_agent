import copy
import json
import pytest

from app.providers.service import OpenAICompatibleProvider
from app.workflow.engine import execute, validate_review
from app.workflow.safety import normalize_demo_output
from app.agents import runtime_v2
from tests.test_workflow import case, DocStub


@pytest.mark.parametrize('mode', ['rag-only', 'single-agent'])
def test_live_protocol_tolerates_text_and_extra_fields_in_baseline_modes(monkeypatch, mode):
    monkeypatch.setenv('LLM_BASE_URL', 'http://localhost:9999/v1')
    monkeypatch.setenv('LLM_MODEL', 'offline-test')
    monkeypatch.setenv('LLM_API_KEY', 'offline-test')
    def reply(self, payload):
        context = json.loads(payload['messages'][1]['content'])
        candidate = {'drug_code':'DEMO_DRUG_A', 'reason':'不提供劑量建議',
                     'rule_refs':context['rule_refs'], 'evidence_refs':['demo_chunk'], 'extra':'ignored'}
        raw = {'candidates':[candidate, copy.deepcopy(candidate), {**candidate,'drug_code':'invented'}],
               'avoid':None, 'limitations':['不提供給藥療程'], 'extra':'ignored'}
        return {'choices':[{'message':{'content':json.dumps(raw)}}], 'usage':{'total_tokens':10}}, 0
    monkeypatch.setattr(OpenAICompatibleProvider, '_request', reply)
    run = execute(case(), mode, 'live', DocStub())
    assert run['output'], run['errors']
    assert len(run['output']['candidates']) == 1
    assert '說明已省略' in run['output']['candidates'][0]['reason']
    assert validate_review(run, run['output'])['valid']
    node = next(n for n in run['nodes'] if n['node_id']=='candidate_presentation')
    assert 'TEXT_WITHHELD' in node['demo_adjustments']
    assert 'INVALID_ITEM_OMITTED' in node['demo_adjustments']


def test_invalid_citation_is_omitted_never_replaced_with_available_citation():
    value = {'candidates':[{'drug_code':'a', 'reason':'test', 'rule_refs':[], 'evidence_refs':['invented']}],
             'avoid':[], 'limitations':[]}
    result, notes = normalize_demo_output(value, allowed_drugs={'a'}, allowed_avoid=set(),
        allowed_rules=set(), allowed_evidence={'real'}, require_evidence_refs=True)
    assert result['candidates'] == []
    assert notes == ['INVALID_ITEM_OMITTED']


def test_mixed_valid_and_invalid_candidates_keep_only_verified_item():
    item = {'drug_code':'a', 'reason':'test', 'rule_refs':[], 'evidence_refs':['real']}
    value = {'candidates':[item, {**item, 'drug_code':'b', 'evidence_refs':['invented']}],
             'avoid':[], 'limitations':[]}
    result, notes = normalize_demo_output(value, allowed_drugs={'a', 'b'}, allowed_avoid=set(),
        allowed_rules=set(), allowed_evidence={'real'}, require_evidence_refs=True)
    assert result['candidates'] == [item]
    assert 'INVALID_ITEM_OMITTED' in notes


def test_historical_legacy_run_is_labelled_without_rewriting_stored_mode():
    from app.main import _public_run
    stored = {'mode':'multi-agent', 'nodes':[], 'output':None}
    public = _public_run(stored)
    assert public['mode'] == stored['mode'] == 'multi-agent'
    assert public['display_mode'] == 'multi-agent-legacy'
    assert 'display_mode' not in stored


def test_historical_benchmark_labels_aggregate_without_rewriting_modes():
    from app.main import _public_benchmark
    old = {'mode':'multi-agent', 'nodes':[]}
    new = {**old, 'agent_execution':{'calls':5}}
    assert _public_benchmark({'results':[old]})['display_modes']['multi-agent'] == 'multi-agent-legacy'
    assert _public_benchmark({'results':[new]})['display_modes']['multi-agent'] == 'multi-agent'
    assert _public_benchmark({'results':[old, new]})['display_modes']['multi-agent'] == 'multi-agent-mixed'


def test_v2_synthesis_text_uses_same_demo_tolerance(monkeypatch):
    original = runtime_v2.mock_output
    def changed(agent, data):
        value = original(agent, data)
        if agent.id == 'synthesis_agent':
            value['candidates'][0]['reason'] = '不提供劑量與療程'
        return value
    monkeypatch.setattr(runtime_v2, 'mock_output', changed)
    run = execute(case(), 'multi-agent', 'mock', DocStub())
    assert run['output'], run['errors']
    assert '說明已省略' in run['output']['candidates'][0]['reason']


def test_rule_only_keeps_observed_exclusion_with_demo_results(monkeypatch):
    from tests.test_reported_cohort import case as source_case, Documents
    monkeypatch.delenv('PROTOTYPE_RULE_CONFIG', raising=False)
    run = execute(source_case(), 'rule-only', 'unconfigured', Documents())
    assert run['output']
    assert 'ampicillin' in {x['drug_code'] for x in run['output']['avoid']}
    assert 'ampicillin' not in {x['drug_code'] for x in run['output']['candidates']}
