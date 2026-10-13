"""Citation omissions are repaired; reference IDs alone never certify support."""
import copy

import pytest

from app.agents import runtime_led as rt
from app.agents.runtime_v2 import AgentProvider
from app.workflow.agent_led import validate_output
from app.workflow.citation_repairs import citation_repair
from app.workflow.engine import execute, validate_review
from tests.test_agent_led import Docs, case, successful


class RepairDocs(Docs):
    def search(self, query, **kwargs):
        source = super().search(query, **kwargs)['evidence'][0]
        return {'status': 'ok', 'evidence': [
            {**source, 'chunk_id': f'e{i}', 'text': source['text'] + f' Original passage {i}.'}
            for i in range(1, 6)]}


def quote(data, cid):
    source = next(e for e in data['evidence'] if e['chunk_id'] == cid)
    return {'chunk_id': cid, 'quote': source['text']}


def run(monkeypatch, change, value=None):
    def reply(self, agent, data, **kwargs):
        result = successful(self, agent, data, **kwargs)
        change(agent, result['output'], data)
        return result
    monkeypatch.setattr(rt.Provider, 'complete', reply)
    return execute(value or case(), 'multi-agent', 'mock', RepairDocs())


def test_partial_clinical_quotes_are_repaired_without_losing_other_drug(monkeypatch):
    calls = 0
    def change(agent, output, data):
        nonlocal calls
        if agent.id != 'clinical_agent':
            return
        calls += 1
        row = next(r for r in output['drugs'] if r['drug_code'] == 'amoxicillin')
        if calls == 1:
            for dimension, cid in [('allergy', 'e2'), ('renal', 'e3'), ('interactions', 'e4')]:
                row['risk_details'][dimension]['evidence_refs'].append(cid)
        else:
            assert data['drugs'] == ['amoxicillin']
            repair, = data['citation_repairs']
            assert repair['previous_output']['status'] == 'no_identified_risk'
            assert all(d['status'] == 'no_identified_risk'
                       for d in repair['previous_output']['risk_details'].values())
            assert repair['missing_quote_refs'] == ['e2', 'e3', 'e4']
            assert {e['chunk_id'] for e in data['evidence']} == {'e1', 'e2', 'e3', 'e4'}
            assert data['facts']['allergies']['status'] == 'known_none'
            assert data['facts']['medication_history_status'] == 'reviewed_none'
            row.update(copy.deepcopy(repair['previous_output']))
            row['quotes'] += [quote(data, cid) for cid in repair['missing_quote_refs']]
    value = case()
    value['ast_results'].append({**value['ast_results'][0], 'drug_code': 'amoxicillin'})
    result = run(monkeypatch, change, value)
    assert calls == 2 and len(result['output']['candidates']) == 2
    clinical = next(n for n in result['nodes'] if n.get('agent_id') == 'clinical_agent')
    assert clinical['attempts'][0]['validation_status'] == 'partial'
    assert clinical['attempts'][1]['input_evidence_chunks'] == 4
    assert clinical['attempts'][1]['citation_repairs'][0]['drug_code'] == 'amoxicillin'
    assert clinical['unresolved_drugs'] == []
    assert validate_review(result)['valid']


@pytest.mark.parametrize('field', ['claim_checks', 'risk_checks'])
def test_audit_omitted_quotes_get_independent_repair(monkeypatch, field):
    calls = 0
    def change(agent, output, data):
        nonlocal calls
        if agent.id == 'clinical_agent':
            output['drugs'][0]['quotes'].append(quote(data, 'e2'))
            output['drugs'][0]['risk_details']['renal']['evidence_refs'].append('e2')
        if agent.id == 'synthesis_agent':
            output['drugs'][0]['claims'][3]['evidence_refs'].append('e2')
        if agent.id != 'evidence_audit':
            return
        calls += 1
        row = output['drugs'][0]
        check = next(c for c in row[field] if c['dimension'] == 'renal')
        check['evidence_refs'] = ['e1', 'e2']
        if calls > 1:
            assert not data['assessments']
            repair, = data['citation_repairs']
            assert repair['previous_output']['verdict'] == 'supported'
            assert repair['missing_quote_refs'] == ['e2']
            assert {e['chunk_id'] for e in data['evidence']} == {'e1', 'e2'}
            row['quotes'].append(quote(data, 'e2'))
    result = run(monkeypatch, change)
    assert calls == 2 and result['output']['candidates']
    assert result['drug_assessments'][0]['audit']['verdict'] == 'supported'
    assert validate_review(result)['valid']


def test_repair_can_remove_an_unnecessary_reference(monkeypatch):
    calls = 0
    def change(agent, output, data):
        nonlocal calls
        if agent.id == 'clinical_agent':
            calls += 1
            if calls == 1:
                output['drugs'][0]['risk_details']['allergy']['evidence_refs'].append('e2')
            else:
                assert data['citation_repairs'][0]['missing_quote_refs'] == ['e2']
                # The model retains the sufficient original quote and removes
                # its extra reference; no automatic subset/pruning is applied.
    result = run(monkeypatch, change)
    assert calls == 2 and result['output']['candidates']
    assert result['drug_assessments'][0]['clinical']['risk_details']['allergy']['evidence_refs'] == ['e1']


def test_failed_citation_repair_stays_unknown_within_existing_budget(monkeypatch):
    monkeypatch.setenv('LLM_AGENT_LED_MAX_RETRIES', '1')
    def change(agent, output, data):
        if agent.id == 'clinical_agent':
            output['drugs'][0]['risk_details']['allergy']['evidence_refs'].append('e2')
    result = run(monkeypatch, change)
    row = result['drug_assessments'][0]
    assert row['clinical']['risk_details']['allergy']['status'] == 'unknown'
    assert not result['output']['candidates']
    clinical = next(n for n in result['nodes'] if n.get('agent_id') == 'clinical_agent')
    assert len(clinical['attempts']) == 2 and clinical['unresolved_drugs'] == ['DEMO_DRUG_A']
    assert any(b['kind'] == 'model_output_incomplete' for b in row['blockers'])


@pytest.mark.parametrize('unknown', [False, True])
def test_absent_sources_or_honest_unknown_do_not_trigger_citation_repair(unknown):
    data = {'facts': {}, 'drugs': ['a'], 'evidence': [{'chunk_id': 'e1'}]}
    row = {'drug_code': 'a', 'quotes': [], 'risk_details': {'allergy': {
        'status': 'unknown' if unknown else 'no_identified_risk',
        'evidence_refs': ['e1' if unknown else 'never_supplied']}}}
    assert citation_repair('clinical_agent', row, data) is None


def test_valid_source_selection_still_cannot_replace_wrong_drug_label():
    data = {'facts': {'allergies': {'status': 'known_none'}, 'renal': {'egfr': 90},
                      'medications': [], 'medication_history_status': 'reviewed_none'},
            'drugs': ['ampicillin'], 'evidence': [
                {'chunk_id': 'e1', 'text': 'Ampicillin allergy, renal dose adjustment and drug interactions.',
                 'document_kind': 'drug_label', 'document_title': 'Ampicillin'},
                {'chunk_id': 'e2', 'text': 'Ampicillin and sulbactam allergy precautions.',
                 'document_kind': 'drug_label', 'document_title': 'Ampicillin and sulbactam'}]}
    row = successful(None, rt.AGENTS[3], data)['output']['drugs'][0]
    row['quotes'] = [quote(data, 'e1')]
    row['risk_details']['allergy']['evidence_refs'].append('e2')
    assert citation_repair('clinical_agent', row, data)
    row['quotes'].append(quote(data, 'e2'))
    checked = validate_output(rt.AGENTS[3], {'drugs': [row]}, data)['drugs'][0]
    assert checked['risk_details']['allergy']['status'] == 'unknown'
    assert any('複方' in issue for issue in checked['risk_details']['allergy']['validation_issues'])


def test_repair_source_ids_and_previous_references_use_same_wire_aliases(monkeypatch):
    data = {'facts': {}, 'drugs': ['DEMO_DRUG_A'], 'evidence': RepairDocs().search('')['evidence'][:2]}
    row = successful(None, rt.AGENTS[3], data)['output']['drugs'][0]
    row['risk_details']['allergy']['evidence_refs'].append('e2')
    data['citation_repairs'] = [citation_repair('clinical_agent', row, data)]
    def transport(self, agent, wire, **kwargs):
        repair, = wire['citation_repairs']
        assert repair['missing_quote_refs'] == ['E2']
        assert repair['previous_output']['risk_details']['allergy']['evidence_refs'] == ['E1', 'E2']
        result = copy.deepcopy(repair['previous_output'])
        for dimension in ('allergy', 'renal', 'interactions'):
            result.pop(dimension, None)
        result['quotes'] = [{'chunk_id': 'E1', 'span_ids': ['S1']},
                            {'chunk_id': 'E2', 'span_ids': ['S1']}]
        return {'output': {'drugs': [result]}, 'usage': {'total_tokens': 1}}
    monkeypatch.setattr(AgentProvider, 'complete', transport)
    reply = rt.Provider('live', rt.AGENTS[3]).complete(rt.AGENTS[3], data, timeout=1)
    assert not reply['wire_errors']
    assert {q['chunk_id'] for q in reply['output']['drugs'][0]['quotes']} == {'e1', 'e2'}
    assert data['citation_repairs'][0]['missing_quote_refs'] == ['e2']
