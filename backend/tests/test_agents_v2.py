"""Offline v2 behavior and isolation checks; never use source data or live APIs."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.agents import runtime_v2 as runtime
from app.providers.service import ProviderError
from app.workflow.engine import execute, validate_review
from app.workflow.v2 import public_agent_nodes
from tests.test_workflow import case, DocStub


def agents(run):
    return [n for n in run["nodes"] if n.get("agent_id")]


@pytest.mark.parametrize('local,consent,allowed', [(False,False,False),(False,True,True),(True,False,True)])
def test_reference_evidence_uses_explicit_case_consent_or_local_transport(monkeypatch, local, consent, allowed):
    monkeypatch.setenv('LLM_BASE_URL', 'http://localhost:1234/v1' if local else 'https://example.invalid/v1')
    monkeypatch.setenv('LLM_MODEL', 'test')
    monkeypatch.setenv('LLM_API_KEY', 'unused')
    provider = runtime.AgentProvider('live', runtime.AGENTS[2])
    data = {'evidence':[{'is_synthetic':False, 'external_model_allowed':False}]}
    value = {'is_synthetic':True, 'external_model_allowed':consent}
    if allowed:
        provider.check(value, data)
    else:
        with pytest.raises(ProviderError) as error: provider.check(value, data)
        assert error.value.code == 'NON_SYNTHETIC_EVIDENCE'


def test_five_independent_calls_receive_validated_upstream_results(monkeypatch):
    recorded = []
    original = runtime.AgentProvider.complete
    def spy(self, agent, data, **kwargs):
        recorded.append((agent.id, copy.deepcopy(data)))
        return original(self, agent, data, **kwargs)
    monkeypatch.setattr(runtime.AgentProvider, "complete", spy)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["gate_status"] == "ready_for_review", run["errors"]
    assert run["output"] and validate_review(run, run["output"])["valid"]
    assert [x[0] for x in recorded] == [a.id for a in runtime.AGENTS]
    traces = agents(run)
    assert len({n["span_id"] for n in traces}) == 5
    assert len({n["prompt_hash"] for n in traces}) == 5
    assert len(traces[-1]["parent_span_ids"]) == 4
    assert recorded[-1][1]["ast_assessment"] == traces[1]["output"]
    assert recorded[-1][1]["evidence_assessment"] == traces[2]["output"]
    assert recorded[-1][1]["clinical_assessment"] == traces[3]["output"]
    assert all(n["input_hash"] and n["output_hash"] and n["finished_at"] >= n["started_at"] for n in traces)
    assert run["agent_execution"]["calls"] == 5
    assert run["usage"] is None and run["agent_execution"]["usage_complete"] is False


def test_missing_case_fields_prevent_all_generation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("provider called despite preflight failure")
    monkeypatch.setattr(runtime.AgentProvider, "complete", forbidden)
    run = execute(case(allergies={"status": "unknown", "items": []}), "multi-agent-v2", "mock", DocStub())
    assert run["output"] is None
    assert run["gate_status"] == "needs_confirmation"
    assert all(n["status"] == "skipped" for n in agents(run))
    assert run["agent_execution"]["calls"] == 0


@pytest.mark.parametrize("role,change", [
    ("case_agent", lambda o: o.update(findings=42)),
    ("ast_agent", lambda o: o.update(reviewed_drugs=["invented"])),
    ("case_agent", lambda o: o["findings"][0].update(evidence_refs=["invented"])),
    ("clinical_agent", lambda o: o.update(excluded_drugs=['invented'])),
    ("synthesis_agent", lambda o: o["candidates"][0].update(drug_code="DEMO_DRUG_C")),
    ("synthesis_agent", lambda o: o["candidates"][0].update(evidence_refs=["invented"])),
])
def test_invalid_agent_output_blocks_downstream_and_public_content(monkeypatch, role, change):
    original = runtime.mock_output
    def altered(agent, data):
        out = original(agent, data)
        if agent.id == role:
            change(out)
        return out
    monkeypatch.setattr(runtime, "mock_output", altered)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["output"] is None and run["gate_status"] in {"blocked", "needs_confirmation"}
    traces = agents(run)
    index = [x["agent_id"] for x in traces].index(role)
    assert traces[index]["status"] == "failed"
    assert all(x["status"] == "skipped" and not x["attempts"] for x in traces[index + 1:])
    public = public_agent_nodes(run["nodes"], publish=False)
    assert all(x["output"] is None and x["input"] is None for x in public if x.get("agent_id"))


def test_demo_specialist_uncertainty_is_retained_in_result(monkeypatch):
    original = runtime.mock_output
    def uncertain(agent, data):
        result = original(agent, data)
        if agent.id == "clinical_agent":
            result["needs_confirmation"] = True
        return result
    monkeypatch.setattr(runtime, "mock_output", uncertain)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run['output'] and run['gate_status'] == 'ready_for_review'
    assert agents(run)[3]['status'] == 'needs_confirmation'
    assert any('clinical_agent' in x for x in run['output']['limitations'])


@pytest.mark.parametrize("role", ["case_agent", "ast_agent", "evidence_agent"])
def test_demo_uncertainty_allows_result_with_explicit_limitations(monkeypatch, role):
    original = runtime.mock_output
    def uncertain(agent, data):
        result = original(agent, data)
        if agent.id == role:
            result['needs_confirmation'] = True
        return result
    monkeypatch.setattr(runtime, 'mock_output', uncertain)
    run = execute(case(), 'multi-agent-v2', 'mock', DocStub())
    traces = agents(run)
    assert all(n['attempts'] for n in traces[:4])
    assert traces[-1]['status'] == 'completed'
    assert run['output'] and run['gate_status'] == 'ready_for_review'
    assert any(role in x for x in run['output']['limitations'])


def test_demo_normalizes_presentation_without_inventing_choices(monkeypatch):
    original = runtime.mock_output
    def changed(agent, data):
        result = original(agent, data)
        if agent.id == 'case_agent':
            result.update(extra='ignored', missing_fields=None, needs_confirmation='false')
            result['findings'][0] = {'statement': '不提供劑量建議'}
        return result
    monkeypatch.setattr(runtime, 'mock_output', changed)
    run = execute(case(), 'multi-agent-v2', 'mock', DocStub())
    assert run['output']
    assert 'TEXT_WITHHELD' in agents(run)[0]['demo_adjustments']
    assert agents(run)[0]['output']['findings'][0]['evidence_refs'] == []


def test_empty_support_becomes_unsupported_without_fabricated_citation():
    from app.workflow.v2 import normalize_demo_assessment
    agent = next(a for a in runtime.AGENTS if a.id == 'evidence_agent')
    raw = {'findings': [], 'limitations': [], 'needs_confirmation': True,
           'supported_drugs': ['a', 'b'], 'support': [
               {'drug_code': 'a', 'evidence_refs': [], 'explanation': 'unsupported'},
               {'drug_code': 'b', 'evidence_refs': ['real_chunk'], 'explanation': 'supported'}]}
    result, notes = normalize_demo_assessment(agent, raw)
    assert result['supported_drugs'] == ['b']
    assert [x['drug_code'] for x in result['support']] == ['b']
    assert notes == ['EMPTY_SUPPORT_OMITTED']


@pytest.mark.parametrize('variation', ['summary_no_refs', 'summary_bad_refs', 'duplicate', 'list_mismatch', 'one_bad_support'])
def test_evidence_demo_keeps_valid_per_drug_support(monkeypatch, variation):
    original = runtime.mock_output
    def changed(agent, data):
        result = original(agent, data)
        if agent.id == 'evidence_agent':
            if variation == 'summary_no_refs':
                result['findings'][0]['evidence_refs'] = []
            elif variation == 'summary_bad_refs':
                result['findings'][0]['evidence_refs'] = ['invented']
            elif variation == 'duplicate':
                result['support'].append(copy.deepcopy(result['support'][0]))
            elif variation == 'list_mismatch':
                result['supported_drugs'] = []
            else:
                result['support'].append({'drug_code':'invented', 'evidence_refs':['fake'], 'explanation':'unsupported'})
        return result
    monkeypatch.setattr(runtime, 'mock_output', changed)
    run = execute(case(), 'multi-agent-v2', 'mock', DocStub())
    assert run['output'], run['errors']
    assert agents(run)[2]['status'] in {'completed', 'needs_confirmation'}
    assert agents(run)[2]['output']['supported_drugs'] == ['DEMO_DRUG_A']
    assert run['output']['candidates'][0]['evidence_refs'] == ['demo_chunk']


def test_no_valid_evidence_support_still_runs_clinical_agent(monkeypatch):
    original = runtime.mock_output
    def changed(agent, data):
        result = original(agent, data)
        if agent.id == 'evidence_agent':
            result['support'][0]['evidence_refs'] = ['invented']
        return result
    monkeypatch.setattr(runtime, 'mock_output', changed)
    run = execute(case(), 'multi-agent-v2', 'mock', DocStub())
    assert agents(run)[2]['status'] == 'needs_confirmation'
    assert agents(run)[2]['output']['support'] == []
    assert agents(run)[3]['status'] == 'completed'
    assert run['output'] is None
    assert run['errors'][-1]['code'] == 'AGENT_NO_SUPPORTED_CANDIDATES'


def test_case_agent_receives_source_ast_and_culture_without_identifiers():
    value = case()
    value['microbiology'].update(specimen='BLOOD', report_status='final', collected_at='PRIVATE_TIME')
    run = execute(value, 'multi-agent-v2', 'mock', DocStub())
    data = agents(run)[0]['input']
    assert data['facts']['specimen'] == 'BLOOD'
    assert data['facts']['report_status'] == 'final'
    assert data['ast_results'][0]['drug_code'] == value['ast_results'][0]['drug_code']
    assert 'PRIVATE_TIME' not in json.dumps(data)


def test_disagreement_narrows_to_empty_without_calling_synthesis(monkeypatch):
    original = runtime.mock_output
    def exclude(agent, data):
        result = original(agent, data)
        if agent.id == "clinical_agent":
            result["excluded_drugs"] = data["allowed_drugs"]
        return result
    monkeypatch.setattr(runtime, "mock_output", exclude)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["gate_status"] == "needs_confirmation" and run["output"] is None
    assert agents(run)[-1]["attempts"] == []


def test_retry_accounting_and_usage_aggregation(monkeypatch):
    seen = []
    def fake(self, agent, data, **kwargs):
        seen.append(agent.id)
        if len(seen) == 1:
            raise ProviderError("PROVIDER_RATE_LIMIT", retryable=True)
        return {"output": runtime.mock_output(agent, data), "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}
    monkeypatch.setattr(runtime.AgentProvider, "complete", fake)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["output"]
    assert run["agent_execution"]["calls"] == 6
    assert agents(run)[0]["retry_count"] == 1
    assert agents(run)[0]["attempts"][0]["error_code"] == "PROVIDER_RATE_LIMIT"
    assert run["usage"]["total_tokens"] == 50
    assert not run["agent_execution"]["usage_complete"]  # failed call cost is unknown


def test_budget_exhaustion_never_falls_back_to_legacy_candidate(monkeypatch):
    monkeypatch.setenv("LLM_V2_MAX_CALLS", "2")
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["agent_execution"]["calls"] == 2
    assert run["output"] is None and run["gate_status"] == "blocked"
    assert run["errors"][-1]["code"] == "AGENT_BUDGET_EXCEEDED"


def test_unconfigured_is_partial_and_makes_no_call(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    run = execute(case(), "multi-agent-v2", "unconfigured", DocStub())
    assert run["status"] == "partial" and run["output"] is None
    assert run["agent_execution"]["calls"] == 0


def test_checkpoint_saves_call_start_and_completed_messages_before_next_agent():
    checkpoints = []
    run = execute(case(), "multi-agent-v2", "mock", DocStub(), checkpoint=lambda x: checkpoints.append(copy.deepcopy(x)))
    assert run["output"]
    assert all(x["output"] is None and x["status"] == "running" for x in checkpoints)
    assert agents(checkpoints[0])[0]["attempts"][0]["status"] == "running"
    assert agents(checkpoints[1])[0]["status"] == "completed"
    assert agents(checkpoints[2])[0]["output"] == agents(run)[0]["output"]


def test_review_retains_v2_specialist_boundary():
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    run["v2_candidate_boundary"]["allowed_drugs"] = []
    with pytest.raises(ValueError):
        validate_review(run, run["output"])
    run["v2_candidate_boundary"]["allowed_drugs"] = ["DEMO_DRUG_A"]
    run["v2_candidate_boundary"]["evidence_by_drug"] = {}
    with pytest.raises(ValueError, match="per-drug"):
        validate_review(run, run["output"])


def test_invalid_json_still_records_provider_usage(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "unused")
    monkeypatch.setattr(runtime.OpenAICompatibleProvider, "_request", lambda *a: ({
        "choices": [{"finish_reason": "length", "message": {"content": "{"}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}}, 0))
    run = execute(case(), "multi-agent-v2", "live", DocStub())
    assert run["output"] is None and run["usage"]["total_tokens"] == 6
    assert agents(run)[0]["attempts"][0]["validation_status"] == "invalid"


def test_deadline_discards_a_late_success(monkeypatch):
    from app.workflow import v2
    ticks = [0.0]
    monkeypatch.setattr(v2.time, "perf_counter", lambda: ticks[0])
    def late(self, agent, data, **kwargs):
        ticks[0] = 1000.0
        return {"output": runtime.mock_output(agent, data), "usage": None}
    monkeypatch.setattr(runtime.AgentProvider, "complete", late)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["output"] is None and run["agent_execution"]["calls"] == 1
    assert run["errors"][-1]["code"] == "AGENT_BUDGET_EXCEEDED"


def test_nonretryable_failure_does_not_consume_second_call(monkeypatch):
    def fail(*a, **kw):
        raise ProviderError("PROVIDER_HTTP_ERROR", retryable=False)
    monkeypatch.setattr(runtime.AgentProvider, "complete", fail)
    run = execute(case(), "multi-agent-v2", "mock", DocStub())
    assert run["agent_execution"]["calls"] == 1
    assert agents(run)[0]["attempts"][0]["status"] == "failed"


def test_reported_mode_v2_preserves_source_avoid_and_population_gate(monkeypatch):
    from tests.test_reported_cohort import case as source_case, Documents
    monkeypatch.delenv("PROTOTYPE_RULE_CONFIG", raising=False)
    monkeypatch.setenv("PROTOTYPE_CATALOG_PATH", "nonexistent-test-catalog.json")
    run = execute(source_case(), "multi-agent-v2", "mock", Documents())
    assert run["output"], run["errors"]
    assert [x["drug_code"] for x in run["output"]["avoid"]] == ["ampicillin"]
    assert validate_review(run, run["output"])["valid"]
    class Mismatch(Documents):
        def search(self, *a, **kw):
            result = super().search(*a, **kw)
            result["evidence"][0]["population"] = "pediatric"
            return result
    withheld = execute(source_case(), "multi-agent-v2", "mock", Mismatch())
    assert withheld["output"] is None and withheld["agent_execution"]["calls"] == 0


def test_live_adapter_uses_separate_prompts_and_projected_payloads(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "unused-offline-key")
    monkeypatch.setenv("LLM_V2_SYNTHESIS_AGENT_MODEL", "test-synthesis-model")
    payloads = []
    def request(self, payload):
        payloads.append(copy.deepcopy(payload))
        index = len(payloads) - 1
        data = json.loads(payload["messages"][1]["content"])["input"]
        output = runtime.mock_output(runtime.AGENTS[index], data)
        return {"id": "test-response", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}, 0
    monkeypatch.setattr(runtime.OpenAICompatibleProvider, "_request", request)
    data = case(case_id="PRIVATE_CASE_IDENTIFIER", provenance={"source_record_id": "PRIVATE_SOURCE_IDENTIFIER"})
    data["renal"]["sampled_at"] = "PRIVATE_TIMESTAMP"
    class SyntheticDocuments(DocStub):
        def search(self, *args, **kwargs):
            result = super().search(*args, **kwargs)
            result['evidence'][0]['is_synthetic'] = True
            return result
    run = execute(data, "multi-agent-v2", "live", SyntheticDocuments())
    assert run["output"], run["errors"]
    assert len(payloads) == 5
    assert len({p["messages"][0]["content"] for p in payloads}) == 5
    assert payloads[-1]["model"] == "test-synthesis-model"
    assert "PRIVATE_" not in json.dumps(payloads)
    assert "unused-offline-key" not in json.dumps(run)
    assert run["usage"]["total_tokens"] == 75 and run["agent_execution"]["usage_complete"]


def test_source_external_permission_checked_before_every_agent(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "unused")
    def unexpected(*args, **kwargs):
        pytest.fail("source case sent without permission")
    monkeypatch.setattr(runtime.AgentProvider, "complete", unexpected)
    run = execute(case(is_synthetic=False, data_origin="hybrid", external_model_allowed=False), "multi-agent-v2", "live", DocStub())
    assert run["output"] is None and run["agent_execution"]["calls"] == 0
    assert run["errors"][-1]["code"] == "NON_SYNTHETIC_INPUT"


def test_api_persists_v2_and_all_exports_quarantine_blocked_content(tmp_path, monkeypatch):
    import app.main as main
    from app.repositories import SQLiteRepository
    db = SQLiteRepository(tmp_path / "v2.db")
    monkeypatch.setattr(main, "repo", db)
    monkeypatch.setattr(main, "_documents", lambda: DocStub())
    data = case(created_at="2026-09-18T00:00:00Z")
    try:
        with TestClient(main.app) as client:
            assert client.post("/api/cases/import", json={"payload": data}).status_code == 200
            body = {"case_id": data["case_id"], "mode": "multi-agent-v2", "provider_kind": "mock", "request_id": "once"}
            run = client.post("/api/runs", json=body).json()
            assert run["output"], run.get("errors")
            assert client.post("/api/runs", json=body).json()["run_id"] == run["run_id"]
            saved = db.get_run(run["run_id"])
            assert agents(saved)[-1]["input"]["clinical_assessment"]
            saved.update(output=None, gate_status="blocked", status="blocked")
            db.save_run(run["run_id"], saved)
            for suffix in ("", "/trace", "/export"):
                public = client.get("/api/runs/" + run["run_id"] + suffix).json()
                assert all(n["input"] is None and n["output"] is None for n in agents(public))
            benchmark = client.post("/api/benchmarks", json={"case_ids": [data["case_id"]], "modes": ["multi-agent", "multi-agent-v2"], "provider_kind": "mock"})
            assert benchmark.status_code == 200
            assert "multi-agent-v2" in benchmark.json()["summary"]["by_mode"]
    finally:
        db.close()
