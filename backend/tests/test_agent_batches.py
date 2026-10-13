"""Regression fixtures for incomplete batches; no network or paid model calls."""
import copy

import pytest

from app.agents import runtime_led as rt
from app.agents.runtime_v2 import AgentProvider
from app.providers.service import ProviderError
from app.workflow.agent_led import validate_output
from app.workflow.agent_schedule import AgentSchedule, batch_context
from app.workflow.engine import execute
from app.workflow.partial_agents import validate_partial
from tests.test_agent_led import Docs, case, successful


class BatchDocs(Docs):
    def __init__(self, drugs):
        super().__init__()
        self.drugs = drugs

    def search(self, query, **kwargs):
        result = super().search(query, **kwargs)
        source = result['evidence'][0]
        source['text'] += ' Fictional names: ' + ', '.join(self.drugs) + '.'
        result['evidence'].append({**source, 'chunk_id': 'e2',
            'text': source['text'] + ' Gentamicin interactions with cephalosporins require review.'})
        return result


def execute_batch(monkeypatch, n=6, change=None, value=None):
    value = value or case()
    if n:
        value['ast_results'] = [{**value['ast_results'][0], 'drug_code': f'drug_{i}'} for i in range(n)]
    drugs = [a['drug_code'] for a in value['ast_results']]
    docs = BatchDocs(drugs)
    def reply(self, agent, data, **kw):
        output = successful(self, agent, data, **kw)
        for row in output['output'].get('drugs', []):
            if 'quotes' in row:
                row['quotes'] = [{'chunk_id': 'e1', 'quote': next(
                    e['text'] for e in data['evidence'] if e['chunk_id'] == 'e1')}]
        if change:
            change(agent, output['output'], data)
        return output
    monkeypatch.setattr(rt.Provider, 'complete', reply)
    return execute(value, 'multi-agent', 'mock', docs)


def node(run, role):
    return next(n for n in run['nodes'] if n.get('agent_id') == role)


@pytest.mark.parametrize('count,cap,expected', [(18, 24, 16), (18, 6, 6), (30, 24, 24)])
def test_every_assigned_drug_is_covered_within_the_call_budget(monkeypatch, count, cap, expected):
    monkeypatch.setenv('LLM_AGENT_LED_MAX_CALLS', str(cap))
    result = execute_batch(monkeypatch, count)
    assert not result['errors']
    assert len(result['output']['candidates']) == count
    assert result['agent_execution']['calls'] == expected
    assert result['budget']['max_retrieval_drugs'] == 30
    assert result['budget']['timeout_seconds'] == 1200
    for role in ('clinical_agent', 'synthesis_agent'):
        attempts = node(result, role)['attempts']
        assigned = [drug for a in attempts for drug in a['requested_drugs']]
        assert len(assigned) == len(set(assigned)) == count
        assert all(a['kind'] == 'initial' for a in attempts)
        if cap == 24:
            assert all(len(a['requested_drugs']) <= 3 for a in attempts)


def test_batch_context_scopes_sources_without_renumbering_ast_or_losing_facts():
    original = dict(drugs=['a', 'b'], facts={'renal': {'egfr': 90}},
        ast_results=[{'drug_code': 'a'}, {'drug_code': 'b'}],
        claims=[{'drug_code': 'a'}, {'drug_code': 'b'}],
        evidence=[{'chunk_id': 'a'}, {'chunk_id': 'b'}, {'chunk_id': 'common'}],
        evidence_groups=[{'drug_code': d, 'evidence_refs': [ref]}
                         for d, ref in [('a', 'a'), ('b', 'b'), (None, 'common')]],
        assessments={'clinical_agent': {'drugs': [
            {'drug_code': 'a', 'evidence_refs': ['a']}, {'drug_code': 'b', 'evidence_refs': ['b']}],
            'issues': [{'drug_code': 'a'}, {'drug_code': 'b'}, {'drug_code': None}]}})
    clinical = batch_context('clinical_agent', original, ['b'])
    assert [e['chunk_id'] for e in clinical['evidence']] == ['b', 'common']
    assert clinical['facts'] == original['facts']
    assert clinical['ast_results'][1]['drug_code'] == 'b'
    synthesis = batch_context('synthesis_agent', original, ['b'])
    assert [e['chunk_id'] for e in synthesis['evidence']] == ['b']
    assert synthesis['assessments']['clinical_agent']['issues'] == [{'drug_code': 'b'}, {'drug_code': None}]
    assert original['drugs'] == ['a', 'b'] and len(original['evidence']) == 3


def test_missing_rows_then_quote_repairs_preserve_completed_drugs(monkeypatch):
    def change(agent, out, data):
        if agent.id != 'clinical_agent':
            return
        if len(data['drugs']) > 1:
            out['drugs'] = out['drugs'][:1]
            out['issues'] = [dict(field='drug_rows', drug_code=None, blocking=True,
                                 impact='缺少其他藥品評估', action='補答')]
        elif data['drugs'] == ['drug_5']:
            row = out['drugs'][0]
            row['risk_details']['renal']['evidence_refs'].append('e2')
            if data.get('citation_repairs'):
                assert data['citation_repairs'][0]['previous_output']['risk_details']['renal']['status'] == 'no_identified_risk'
                row['quotes'].append({'chunk_id': 'e2', 'quote': data['evidence'][1]['text']})
    result = execute_batch(monkeypatch, change=change)
    clinical = node(result, 'clinical_agent')
    assert [a['kind'] for a in clinical['attempts']] == ['initial'] * 2 + ['row_repair'] * 4 + ['citation_repair']
    assert clinical['unresolved_drugs'] == [] and clinical['output']['issues'] == []
    assert len(result['output']['candidates']) == 6
    assert not result['errors']


def test_row_and_citation_retry_limits_are_separate_and_bounded():
    schedule = AgentSchedule('clinical_agent', ['a', 'b', 'c', 'd'], 1)
    first = schedule.pop()
    schedule.finish(first, ['b'], ['b: missing row'])
    # Fresh assignments take priority over retries.
    assert schedule.pop()['drugs'] == ['d']
    retry = schedule.pop()
    assert retry['kind'] == 'row_repair' and retry['drugs'] == ['b']
    repair = dict(drug_code='b', dimensions=['renal'], missing_quote_refs=['e2'])
    schedule.finish(retry, ['b'], ['b: missing quote'], [repair])
    citation = schedule.pop()
    assert citation['kind'] == 'citation_repair'
    schedule.finish(citation, ['b'], ['b: still missing quote'], [repair])
    assert schedule.pop() is None
    assert schedule.retries[('b', 'row_repair')] == schedule.retries[('b', 'citation_repair')] == 1


def test_missing_row_warning_does_not_block_complete_drug(monkeypatch):
    monkeypatch.setenv('LLM_AGENT_LED_MAX_RETRIES', '0')
    def change(agent, out, data):
        if agent.id == 'clinical_agent':
            out['drugs'] = out['drugs'][:1]
            out['issues'] = [dict(field='drug_rows', drug_code=None, blocking=True,
                                 impact='缺少其他藥品評估', action='補答')]
    result = execute_batch(monkeypatch, 3, change)
    assert [r['drug_code'] for r in result['output']['candidates']] == ['drug_0']
    issues = node(result, 'clinical_agent')['output']['issues']
    assert {i['drug_code'] for i in issues} == {'drug_1', 'drug_2'}
    assert result['drug_assessments'][0]['blockers'] == []


def test_real_global_patient_issue_remains_blocking_and_visible(monkeypatch):
    def change(agent, out, data):
        if agent.id == 'clinical_agent':
            out['issues'] = [dict(field='history', drug_code=None, blocking=True,
                                 impact='待釐清具體病例矛盾', action='核對病史')]
    result = execute_batch(monkeypatch, 3, change)
    assert not result['output']['candidates']
    assert all(any(b['kind'] == 'assessment_unconfirmed' and b['detail'] == '待釐清具體病例矛盾'
                   for b in r['blockers']) for r in result['drug_assessments'])


def test_synthesis_cannot_borrow_another_drug_or_dimension_reference():
    data = dict(drugs=['DEMO_DRUG_A'], evidence=[{'chunk_id': 'e1'}, {'chunk_id': 'e2'}],
                claims=[], assessments={'clinical_agent': {'drugs': [
                    {'drug_code': 'DEMO_DRUG_A', 'risk_details': {
                        d: {'evidence_refs': ['e1']} for d in ('renal', 'allergy', 'interactions')}},
                    {'drug_code': 'other', 'risk_details': {'renal': {'evidence_refs': ['e2']}}}]},
                    'evidence_agent': {'drugs': [{'drug_code': 'DEMO_DRUG_A', 'evidence_refs': ['e1', 'e2']}]}})
    raw = successful(None, rt.AGENTS[4], data)['output']
    raw['drugs'][0]['claims'][3]['evidence_refs'] = ['e2']
    checked, diagnostics, unresolved = validate_partial(rt.AGENTS[4], raw, data, validate_output)
    assert unresolved == ['DEMO_DRUG_A'] and diagnostics
    assert checked['drugs'][0]['status'] == 'pending'
    assert checked['drugs'][0]['reference_validation']['invalid_refs'] == ['e2']
    raw['drugs'][0]['claims'][3]['evidence_refs'] = ['e1']
    assert validate_partial(rt.AGENTS[4], raw, data, validate_output)[2] == []


def test_semantic_quote_repair_keeps_alternative_sources_and_rechecks_statement(monkeypatch):
    def change(agent, out, data):
        if agent.id == 'clinical_agent':
            row = out['drugs'][0]
            detail = row['risk_details']['interactions']
            detail.update(status='caution', reason='若併用 cephalosporins，需核對交互作用。', next_action='核對併用藥物')
            if data.get('citation_repairs'):
                repair, = data['citation_repairs']
                assert repair['missing_quote_refs'] == []
                assert 'interactions' in repair['validation_issues']
                assert {e['chunk_id'] for e in data['evidence']} == {'e1', 'e2'}
                detail['evidence_refs'].append('e2')
                row['quotes'].append({'chunk_id': 'e2', 'quote': data['evidence'][1]['text']})
        if agent.id == 'evidence_audit':
            row = out['drugs'][0]
            row['quotes'].append({'chunk_id': 'e2', 'quote': data['evidence'][1]['text']})
            next(c for c in row['risk_checks'] if c['dimension'] == 'interactions')['evidence_refs'].append('e2')
    value = case()
    value['ast_results'][0]['drug_code'] = 'gentamicin'
    result = execute_batch(monkeypatch, 0, change, value)
    assert [a['kind'] for a in node(result, 'clinical_agent')['attempts']] == ['initial', 'citation_repair']
    assert result['drug_assessments'][0]['clinical']['risk_details']['interactions']['status'] == 'caution'
    assert len(result['output']['candidates']) == 1


@pytest.mark.parametrize('missing', [False, True])
def test_ast_source_mismatch_gets_targeted_repair_without_inventing_missing_clsi(monkeypatch, missing):
    count = 0
    def change(agent, out, data):
        nonlocal count
        if agent.id == 'ast_agent':
            count += 1
            row = out['drugs'][0]
            row['assessment'] = 'intermediate'
            row['category_source_refs'] = ['ast_results.0.source_phenotype', 'ast_results.0.clsi_2022_phenotype']
            if count > 1:
                assert any('selected_field' in s for s in data['validation_feedback'])
                row['category_source_refs'] = [] if missing else ['ast_results.0.clsi_2022_phenotype']
                if missing:
                    row['assessment'] = 'unknown'
        if agent.id == 'evidence_audit':
            out['drugs'][0]['ast_check'].update(assessment='unknown' if missing else 'intermediate',
                category_source_refs=[] if missing else ['ast_results.0.clsi_2022_phenotype'])
    value = case()
    value['ast_results'][0].update(interpretation_basis='CLSI_2022_pheno', reported_sir='I',
        source_phenotype='Susceptible', clsi_2022_phenotype=None if missing else 'Intermediate')
    result = execute_batch(monkeypatch, 0, change, value)
    assert count == 2
    ast = result['drug_assessments'][0]['ast']
    assert ast['assessment'] == ('unknown' if missing else 'intermediate')
    assert not result['output']['candidates']  # Intermediate is not susceptible.


def test_completed_batches_survive_failure_and_unsent_batches_are_visible(monkeypatch):
    count = 0
    def change(agent, out, data):
        nonlocal count
        if agent.id == 'clinical_agent':
            count += 1
            if count == 2:
                raise ProviderError('AGENT_STAGE_TIMEOUT')
    result = execute_batch(monkeypatch, 9, change)
    clinical = node(result, 'clinical_agent')
    assert len(clinical['output']['drugs']) == 3
    assert clinical['unresolved_drugs'] == [f'drug_{i}' for i in range(3, 9)]
    assert len(result['output']['candidates']) == 3
    coverage = [g for g in result['evidence_coverage'] if g['agent_id'] == 'clinical_agent']
    assert all(g['unsent_count'] == 2 for g in coverage if g['drug_code'] == 'drug_8')
    assert all(g['unsent_count'] == 0 for g in coverage if g['drug_code'] == 'drug_0')
    assert any(b['kind'] == 'input_not_sent' for b in result['drug_assessments'][8]['blockers'])


def test_wire_schema_requires_complete_batch_but_preserves_valid_partial_rows(monkeypatch):
    data = dict(drugs=['a', 'b', 'c'], evidence=[])
    def transport(self, agent, wire, **kw):
        schema = agent.output_type.model_json_schema()['properties']['drugs']
        assert schema['minItems'] == schema['maxItems'] == 3
        return {'output': {'drugs': [dict(drug_code='a', status='pending', reason='未核對',
            evidence_refs=[], fact_refs=[], disagreements=[], claims=[dict(dimension=d,
                statement='未核對', fact_refs=[], evidence_refs=[], next_action='')
                for d in ('infection', 'ast', 'allergy', 'renal', 'interactions')])]}}
    monkeypatch.setattr(AgentProvider, 'complete', transport)
    reply = rt.Provider('live', rt.AGENTS[4]).complete(rt.AGENTS[4], data, timeout=1)
    assert len(reply['output']['drugs']) == 1
    assert any('minItems' in d for d in reply['wire_errors'])
