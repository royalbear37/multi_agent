import json
import urllib.error

import pytest

from app.providers.service import (
    MockProvider,
    OpenAICompatibleProvider,
    ProviderError,
    get_provider,
)


def _context():
    return {"mode": "single-agent", "case_summary": {"is_synthetic": True}, "allowed_drugs": ["DEMO_DRUG_A"], "rule_refs": ["rule.demo"], "evidence": [{"chunk_id": "doc_chunk_0001", "document_version": "v1", "text": "fixture", "is_synthetic": True, "location": {"page": 1}}]}


def test_unconfigured_is_explicit():
    provider = get_provider("unconfigured")
    assert provider.status()["status"] == "not_configured"
    with pytest.raises(ProviderError, match="模型尚未設定"):
        provider.generate(_context())


def test_mock_is_marked_and_schema_valid():
    result = get_provider("mock").generate(_context())
    assert result["is_mock"] is True
    assert result["output"]["candidates"][0]["drug_code"] == "DEMO_DRUG_A"


def test_live_adapter_rejects_contradictory_lists():
    from app.providers.service import _safe_output
    item = {'drug_code': 'DEMO_DRUG_A', 'reason': 'Fixture',
            'rule_refs': [], 'evidence_refs': []}
    with pytest.raises(ProviderError) as exc:
        _safe_output({'candidates': [item], 'avoid': [dict(item)], 'limitations': []}, _context())
    assert exc.value.code == 'CANDIDATE_AVOID_OVERLAP'


def test_fake_http_live_adapter_and_payload_allowlist():
    calls = []

    def fake_post(url, *, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return {"choices": [{"message": {"content": json_module.dumps({"candidates": [{"drug_code": "DEMO_DRUG_A", "reason": "fixture evidence supports review", "rule_refs": ["rule.demo"], "evidence_refs": ["doc_chunk_0001"]}], "avoid": [], "limitations": ["人工確認"]})}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}}

    context = _context()
    context["trace_secret"] = "do-not-send"
    context["case_summary"]["trace_secret"] = "do-not-send"
    result = OpenAICompatibleProvider("http://localhost:9000/v1", "demo-model", "secret", http_post=fake_post).generate(context)
    assert result["is_mock"] is False
    assert result["usage"]["prompt_tokens"] == 1
    assert calls[0][0].endswith("/chat/completions")
    assert "secret" not in repr(result)
    assert calls[0][1]["Authorization"] == "Bearer secret"
    body_context = json_module.loads(calls[0][2]["messages"][1]["content"])
    assert "trace_secret" not in body_context
    assert "trace_secret" not in body_context["case_summary"]
    assert set(body_context) == {"mode", "case_summary", "allowed_drugs", "evidence", "rule_refs"}
    assert "Authorization" not in body_context
    assert result["usage"] == {"prompt_tokens": 1, "completion_tokens": 2}


def test_live_rejects_unknown_drug_and_prescription_text():
    def unknown(*args, **kwargs):
        return {"choices": [{"message": {"content": json_module.dumps({"candidates": [{"drug_code": "REAL_DRUG", "reason": "ok", "rule_refs": [], "evidence_refs": []}], "avoid": [], "limitations": []})}}]}
    with pytest.raises(ProviderError) as exc:
        OpenAICompatibleProvider("http://x", "m", "k", http_post=unknown).generate(_context())
    assert exc.value.code == "UNALLOWED_DRUG"

    def forbidden(*args, **kwargs):
        return {"choices": [{"message": {"content": json_module.dumps({"candidates": [{"drug_code": "DEMO_DRUG_A", "reason": "take 500 mg twice daily", "rule_refs": [], "evidence_refs": []}], "avoid": [], "limitations": []})}}]}
    with pytest.raises(ProviderError) as exc:
        OpenAICompatibleProvider("http://x", "m", "k", http_post=forbidden).generate(_context())
    assert exc.value.code == "OUTPUT_CONTENT_FORBIDDEN"


def test_http_auth_error_is_not_retried_and_synthetic_flag_is_required():
    calls = []

    def unauthorized(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError("http://x", 401, "unauthorized", {}, None)

    with pytest.raises(ProviderError) as exc:
        OpenAICompatibleProvider("http://x", "m", "k", retries=4, http_post=unauthorized).generate(_context())
    assert exc.value.code == "PROVIDER_HTTP_ERROR"
    assert len(calls) == 1

    context = _context()
    context["case_summary"] = {"is_synthetic": False}
    with pytest.raises(ProviderError) as exc:
        OpenAICompatibleProvider("http://x", "m", "k", http_post=unauthorized).generate(context)
    assert exc.value.code == "NON_SYNTHETIC_INPUT"


def test_timeout_and_rate_limit_retry_with_bounded_count():
    body = {"candidates": [], "avoid": [], "limitations": []}
    timeout_calls = []

    def timeout_once(*args, **kwargs):
        timeout_calls.append(1)
        if len(timeout_calls) == 1:
            raise TimeoutError()
        return {"choices": [{"message": {"content": json_module.dumps(body)}}]}

    output = OpenAICompatibleProvider("http://x", "m", "k", retries=1, http_post=timeout_once).generate(_context())
    assert output["retries"] == 1
    assert len(timeout_calls) == 2

    rate_calls = []

    def rate_once(*args, **kwargs):
        rate_calls.append(1)
        if len(rate_calls) == 1:
            return 429, {}
        return {"choices": [{"message": {"content": json_module.dumps(body)}}]}

    output = OpenAICompatibleProvider("http://x", "m", "k", retries=1, http_post=rate_once).generate(_context())
    assert output["retries"] == 1
    assert len(rate_calls) == 2


def test_multi_agent_nodes_are_bounded_and_secret_fields_dropped():
    captured = {}
    body = {"candidates": [], "avoid": [], "limitations": []}

    def fake(url, **kwargs):
        captured.update(kwargs["json"])
        return {"choices": [{"message": {"content": json_module.dumps(body)}}]}

    context = _context()
    context["mode"] = "multi-agent"
    context["node_summaries"] = [{"node_id": "case_completeness", "status": "completed", "output": {"summary": {"organism": "DEMO_ORGANISM_A", "trace_secret": "do-not-send"}, "missing_fields": [], "ignored": "drop"}}]
    OpenAICompatibleProvider("http://x", "m", "k", http_post=fake).generate(context)
    sent = json_module.loads(captured["messages"][1]["content"])
    assert sent["node_summaries"][0]["output"]["summary"]["organism"] == "DEMO_ORGANISM_A"
    assert "trace_secret" not in repr(sent)
    assert "ignored" not in repr(sent)
    assert "node_summaries" in sent


def test_avoid_uses_same_strict_reference_schema():
    def fake(url, **kwargs):
        body = {"candidates": [], "avoid": [{"drug_code": "DEMO_DRUG_A", "reason": "manual confirmation", "rule_refs": ["rule.demo"], "evidence_refs": ["doc_chunk_0001"]}], "limitations": []}
        return {"choices": [{"message": {"content": json_module.dumps(body)}}]}
    result = OpenAICompatibleProvider("http://x", "m", "k", http_post=fake).generate(_context())
    assert result["output"]["avoid"][0]["evidence_refs"] == ["doc_chunk_0001"]


json_module = json


@pytest.mark.parametrize('base_url,consent,document_consent,synthetic,allowed', [
    ('https://remote.invalid/v1', False, False, False, False),
    ('https://remote.invalid/v1', False, False, None, False),
    ('https://remote.invalid/v1', True, False, False, True),
    ('https://remote.invalid/v1', False, True, False, True),
    ('https://remote.invalid/v1', False, False, True, True),
    ('http://localhost:9000/v1', False, False, False, True),
])
def test_reference_evidence_requires_consent_before_request(base_url, consent, document_consent, synthetic, allowed):
    context = _context()
    context['case_summary']['external_model_allowed'] = consent
    context['evidence'][0].update(is_synthetic=synthetic, external_model_allowed=document_consent)
    calls = []
    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return {'choices': [{'message': {'content': json.dumps({'candidates': [], 'avoid': [], 'limitations': []})}}]}
    provider = OpenAICompatibleProvider(base_url, 'demo', 'fake', http_post=fake_post)
    if allowed:
        provider.generate(context)
        assert len(calls) == 1
    else:
        with pytest.raises(ProviderError) as exc:
            provider.generate(context)
        assert exc.value.code == 'NON_SYNTHETIC_EVIDENCE'
        assert calls == []
