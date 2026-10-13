"""Capacity and recovery regressions using local transports only."""
import copy
import json

from jsonschema import Draft202012Validator

from app.agents import runtime_led as rt, runtime_v2 as legacy
from app.agents.citation_spans import selection_schema
from app.agents.limits import AgentLedLimits
from app.agents.source_options import bind_source_options
from app.agents.structured_output import strict_output_schema
from app.agents.wire_validation import checked_wire
from app.workflow.engine import execute
from tests.test_agent_led import Docs, case, successful


def test_current_limits_do_not_inherit_the_old_eight_call_cap(monkeypatch):
    monkeypatch.setenv('LLM_V2_MAX_CALLS', '8')
    monkeypatch.delenv('LLM_AGENT_LED_MAX_CALLS', raising=False)
    limits = AgentLedLimits.from_env()
    assert limits.max_calls == 40
    monkeypatch.setenv('LLM_AGENT_LED_MAX_CALLS', '40')
    monkeypatch.setenv('LLM_AGENT_LED_MAX_INPUT_CHARS', '1200000')
    limits = AgentLedLimits.from_env()
    assert limits.max_calls == 40 and limits.audit_input_chars == 1198000


def test_live_audit_requests_strict_schema_with_required_ast_check(monkeypatch):
    captured = []
    monkeypatch.setenv('LLM_AGENT_STRUCTURED_OUTPUTS', 'true')
    def request(self, payload):
        captured.append(payload)
        return {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}, 0
    monkeypatch.setattr(legacy.OpenAICompatibleProvider, '_request', request)
    agent = next(a for a in rt.AGENTS if a.id == 'evidence_audit')
    canonical = copy.deepcopy(agent.output_type.model_json_schema())
    rt.Provider('live', agent).complete(agent, {'evidence': [], 'ast_results': []}, timeout=1)
    fmt = captured[0]['response_format']
    assert fmt['type'] == 'json_schema' and fmt['json_schema']['strict'] is True
    schema = fmt['json_schema']['schema']
    Draft202012Validator.check_schema(schema)
    assert 'ast_check' in schema['$defs']['AuditItem']['required']
    assert schema['$defs']['AuditItem']['properties']['ast_check'] == {'$ref': '#/$defs/ASTCheck'}
    assert json.loads(captured[0]['messages'][1]['content'])['output_schema'] == schema
    for definition in [schema, *schema['$defs'].values()]:
        if 'properties' in definition:
            assert set(definition['required']) == set(definition['properties'])
            assert definition['additionalProperties'] is False
    assert agent.output_type.model_json_schema() == canonical


def test_large_source_catalog_keeps_local_reference_checks():
    aliases = [f'E{i}' for i in range(1200)]
    wire = bind_source_options(selection_schema(rt.AuditReport), [], aliases)
    original = copy.deepcopy(wire)
    strict = strict_output_schema(wire)
    Draft202012Validator.check_schema(strict)
    assert wire == original
    assert all('enum' not in definition for name, definition in strict['$defs'].items()
               if name.startswith('StrictSourceSelection'))
    raw = {'drugs': [{'drug_code': 'a', 'verdict': 'uncertain', 'fact_refs': [],
        'ast_check': {'assessment': 'untested', 'claim_assessment': 'not_stated', 'category_source_refs': []},
        'claim_checks': [], 'infection_match': 'uncertain', 'population_match': 'uncertain',
        'drug_match': 'uncertain', 'reason': '待核對', 'quotes': [{'chunk_id': 'invented', 'span_ids': ['S1']}]}]}
    checked, diagnostics = checked_wire(raw, wire)
    assert checked['drugs'] == [] and any('enum' in error for error in diagnostics)


def test_final_audit_can_repair_after_the_old_eight_call_limit(monkeypatch):
    attempts = {}
    monkeypatch.setenv('LLM_AGENT_LED_MAX_CALLS', '24')
    monkeypatch.setenv('LLM_AGENT_LED_MAX_RETRIES', '3')
    def reply(self, agent, data, **kwargs):
        attempts[agent.id] = attempts.get(agent.id, 0) + 1
        count = attempts[agent.id]
        if (agent.id in {'clinical_agent', 'synthesis_agent'} and count == 1) or (agent.id == 'evidence_audit' and count < 4):
            return {'output': {'findings': [], 'issues': [], 'drugs': []},
                    'wire_errors': ['drugs.0: required: ast_check'] if agent.id == 'evidence_audit' else [],
                    'finish_reason': 'stop', 'usage': {'total_tokens': 10}}
        return successful(self, agent, data, **kwargs)
    monkeypatch.setattr(rt.Provider, 'complete', reply)
    result = execute(case(), 'multi-agent', 'mock', Docs())
    assert result['agent_execution']['calls'] == 11
    assert attempts['evidence_audit'] == 4 and not result['errors']
    assert result['output']['candidates']
    audit = next(n for n in result['nodes'] if n.get('agent_id') == 'evidence_audit')
    assert 'required: ast_check' in audit['attempts'][1]['validation_feedback'][0]
    assert audit['output']['drugs'][0]['ast_check_validation']['status'] == 'confirmed'


def test_sources_above_old_context_limits_are_supplied_unchanged(monkeypatch):
    class FullDocs(Docs):
        def search(self, query, **kwargs):
            base = super().search(query, **kwargs)['evidence'][0]
            extras = [{**base, 'chunk_id': f'context-{i}', 'text': 'Original unmodified passage. ' * 80,
                       'document_title': 'Document metadata ' * 20} for i in range(156)]
            return {'status': 'ok', 'evidence': [base, *extras]}
    seen = {}
    def reply(self, agent, data, **kwargs):
        seen[agent.id] = copy.deepcopy(data)
        return successful(self, agent, data, **kwargs)
    monkeypatch.setattr(rt.Provider, 'complete', reply)
    result = execute(case(), 'multi-agent', 'mock', FullDocs())
    clinical = seen['clinical_agent']
    assert 300000 < len(json.dumps(clinical, ensure_ascii=False)) < 1000000
    assert len(clinical['evidence']) == 157
    assert all(e['text'] == 'Original unmodified passage. ' * 80 for e in clinical['evidence'] if e['chunk_id'] != 'e1')
    assert all(s['omitted_chunks'] == 0 for s in result['evidence_selection'])
    assert not result['errors'] and result['output']['candidates']
