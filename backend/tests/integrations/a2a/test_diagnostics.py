"""Synthetic response fixtures only; no live service or real credentials."""
from dataclasses import replace
import json
import socket

import httpx
import pytest

from app.integrations.a2a.client import A2AClient
from app.integrations.a2a.config import A2AConfig
from app.integrations.a2a.contracts import A2AError
from app.integrations.a2a.diagnostics import ResponseDiagnostic
from scripts.probe_itri_a2a import main


TOKEN = 'synthetic:diagnostic-secret!%'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Network forbidden in response diagnostic tests')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)


def client(handler, diagnostic=None):
    return A2AClient(A2AConfig(endpoint='https://a2a.invalid/a2a', api_key=TOKEN),
                     transport=httpx.MockTransport(handler), diagnostic=diagnostic)


def bad_response(request, *, result=None):
    return httpx.Response(200, json={'jsonrpc': '2.0', 'id': json.loads(request.content)['id'],
                                    'result': result if result is not None else {'unexpected': 'synthetic-body'}},
                          headers={'X-Synthetic-Header': 'header-only-must-not-be-collected'})


def test_disabled_by_default(tmp_path):
    with pytest.raises(A2AError) as caught:
        client(bad_response).send_message('request-only-must-not-be-collected')
    assert caught.value.code == 'INVALID_A2A_PAYLOAD'
    assert list(tmp_path.iterdir()) == []


def test_parse_failure_captures_shape_not_request_or_headers(tmp_path):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    calls = []
    def handler(request):
        calls.append(request)
        return bad_response(request, result={'id': 'synthetic-task', 'status': {'state': 'TASK_STATE_WORKING'},
                                             'history': 'invalid-list-fixture'})
    try:
        with pytest.raises(A2AError, match='INVALID_A2A_PAYLOAD') as caught:
            client(handler, diagnostic).send_message('request-only-must-not-be-collected')
        assert caught.value.http_status == 200 and diagnostic.status == 'saved'
    finally:
        diagnostic.close()
    saved = path.read_text(encoding='utf-8')
    obj = json.loads(saved)
    assert len(calls) == 1
    assert obj['operation'] == 'SendMessage' and obj['http_status'] == 200
    assert obj['request_id'] == obj['response']['id']
    assert obj['message_id'] and obj['attempts'] == 1
    assert obj['response']['result']['id'] == 'synthetic-task'
    assert obj['response_format'] == 'redacted_json'
    assert not obj['gold_eligible'] and not obj['clinical_decision_eligible']
    assert TOKEN not in saved
    assert 'request-only-must-not-be-collected' not in saved
    assert 'header-only-must-not-be-collected' not in saved


@pytest.mark.parametrize('token', [TOKEN, 'synthetic"quoted\\credential!'])
def test_recursive_and_json_escaped_secret_redaction(tmp_path, token):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    def handler(request):
        payload = {'jsonrpc': '2.0', 'id': json.loads(request.content)['id'], 'result': {
            'unsupported': {token: [token], 'authorization': 'Bearer other-secret',
                            'api_key': 'different-key', 'Cookie': 'different-cookie',
                            'note': 'Bearer synthetic-other-secret'}}}
        raw = json.dumps(payload, ensure_ascii=True)
        # Encoded JSON still must redact the decoded credential and key names.
        raw = raw.replace('synthetic', '\\u0073ynthetic')
        return httpx.Response(200, content=raw.encode(), headers={'Content-Type': 'application/json'})
    obj = client(handler, diagnostic)
    obj.config = replace(obj.config, api_key=token)
    try:
        with pytest.raises(A2AError):
            obj.send_message('synthetic-question')
    finally:
        diagnostic.close()
    saved = path.read_text(encoding='utf-8')
    parsed = json.loads(saved)
    assert token not in saved and token not in json.dumps(parsed)
    for value in ('different-key', 'different-cookie', 'other-secret', 'synthetic-other-secret'):
        assert value not in saved
    assert '[REDACTED]' in saved


@pytest.mark.parametrize('raw', [b'{"api_key":"unclosed-secret', b'\xff\xfe',
                                b'{"x":NaN}', b'{"x":1,"x":2}'])
def test_unparseable_json_omits_body_instead_of_writing_unredacted_text(tmp_path, raw):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    try:
        with pytest.raises(A2AError, match='INVALID_JSON'):
            client(lambda _: httpx.Response(200, content=raw, headers={'Content-Type': 'application/json'}),
                   diagnostic).send_message('synthetic')
    finally:
        diagnostic.close()
    saved = path.read_text(encoding='utf-8')
    obj = json.loads(saved)
    assert obj['response'] is None and obj['response_format'] == 'omitted_unparseable_json'
    assert obj['response_bytes'] == len(raw)
    assert 'unclosed-secret' not in saved


def test_oversized_redacted_snapshot_is_omitted(tmp_path, monkeypatch):
    monkeypatch.setattr('app.integrations.a2a.diagnostics.MAX_DIAGNOSTIC_BYTES', 1500)
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    try:
        with pytest.raises(A2AError):
            client(lambda r: bad_response(r, result={'unsupported': 'x' * 3000}), diagnostic).send_message('synthetic')
    finally:
        diagnostic.close()
    obj = json.loads(path.read_text())
    assert obj['response'] is None and obj['response_format'] == 'omitted_size_limit'
    assert path.stat().st_size < 1500


def test_existing_diagnostic_never_overwritten(tmp_path):
    path = tmp_path / 'diagnostic.json'
    path.write_text('existing synthetic artifact')
    with pytest.raises(FileExistsError):
        ResponseDiagnostic(path)
    assert path.read_text() == 'existing synthetic artifact'


def test_first_failure_only(tmp_path):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    obj = client(bad_response, diagnostic)
    try:
        for index in range(2):
            with pytest.raises(A2AError):
                obj.send_message('synthetic')
            if index == 0:
                first = path.read_bytes()
        assert path.read_bytes() == first
    finally:
        diagnostic.close()


@pytest.mark.parametrize('mode', ['success', 'rpc_error', 'http_error', 'timeout'])
def test_no_parse_failure_stores_only_not_recorded_marker(tmp_path, mode):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    calls = []
    def handler(request):
        calls.append(request)
        if mode == 'timeout':
            raise httpx.ReadTimeout(TOKEN)
        if mode == 'http_error':
            return httpx.Response(401, text=TOKEN)
        body = {'jsonrpc': '2.0', 'id': json.loads(request.content)['id']}
        if mode == 'rpc_error':
            body['error'] = {'code': -32601, 'message': TOKEN}
        else:
            body['result'] = {'message': {'messageId': 'fixture', 'role': 'ROLE_AGENT', 'parts': [{'text': 'fixture'}]}}
        return httpx.Response(200, json=body)
    try:
        if mode == 'success':
            client(handler, diagnostic).send_message('synthetic')
        else:
            with pytest.raises(A2AError):
                client(handler, diagnostic).send_message('synthetic')
        assert diagnostic.status == 'not_recorded' and len(calls) == 1
    finally:
        diagnostic.close()
    obj = json.loads(path.read_text())
    assert obj['capture_status'] == 'not_recorded' and 'response' not in obj
    assert TOKEN not in path.read_text()


def test_diagnostic_write_failure_preserves_original_error(tmp_path):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    actual = diagnostic._file
    class BrokenFile:
        def write(self, value):
            raise OSError(TOKEN)
        def close(self):
            actual.close()
    diagnostic._file = BrokenFile()
    try:
        with pytest.raises(A2AError) as caught:
            client(bad_response, diagnostic).send_message('synthetic')
        assert caught.value.code == 'INVALID_A2A_PAYLOAD'
        assert diagnostic.status == 'write_failed' and TOKEN not in str(caught.value)
    finally:
        diagnostic.close()


def test_get_task_mismatch_captured_without_another_request(tmp_path):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': json.loads(request.content)['id'],
            'result': {'id': 'different-synthetic-task', 'status': {'state': 'TASK_STATE_WORKING'}}})
    try:
        with pytest.raises(A2AError, match='TASK_ID_MISMATCH'):
            client(handler, diagnostic).get_task('synthetic-task')
    finally:
        diagnostic.close()
    assert len(calls) == 1
    assert json.loads(path.read_text())['operation'] == 'GetTask'


def test_card_parse_failure_captured(tmp_path):
    path = tmp_path / 'diagnostic.json'
    diagnostic = ResponseDiagnostic(path)
    try:
        with pytest.raises(A2AError, match='INVALID_AGENT_CARD'):
            client(lambda _: httpx.Response(200, json={'unexpected': 'fixture'}), diagnostic).get_agent_card()
    finally:
        diagnostic.close()
    assert json.loads(path.read_text())['operation'] == 'AgentCard'


def test_cli_existing_diagnostic_refuses_before_loading_key_or_transport(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'existing.json'
    path.write_text('existing')
    monkeypatch.setattr(A2AConfig, 'from_env', lambda **kw: pytest.fail('Must not load key or send'))
    assert main(['--live', '--text', 'synthetic', '--diagnostic-out', str(path)]) == 2
    assert 'FILE_IO_ERROR' in capsys.readouterr().out
    assert path.read_text() == 'existing'


def test_cli_parse_failure_report_is_separate_from_body(tmp_path, monkeypatch, capsys):
    output, diagnostic_path = tmp_path / 'result.json', tmp_path / 'diagnostic.json'
    def fail_parse(*args, **kwargs):
        raise A2AError('INVALID_A2A_PAYLOAD')
    monkeypatch.setattr('app.integrations.a2a.client.parse_response', fail_parse)
    assert main(['--out', str(output), '--diagnostic-out', str(diagnostic_path)]) == 2
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(output.read_text())
    assert printed['error']['code'] == 'INVALID_A2A_PAYLOAD'
    assert printed['diagnostic_status'] == 'saved'
    assert 'response' not in printed and 'Synthetic transport fixture' not in json.dumps(printed)
    saved = json.loads(diagnostic_path.read_text())
    assert saved['response']['result']['message']['parts'][0]['text'].startswith('Synthetic transport fixture')


def test_cli_success_has_no_response_snapshot(tmp_path, capsys):
    path = tmp_path / 'diagnostic.json'
    assert main(['--diagnostic-out', str(path)]) == 0
    assert json.loads(path.read_text())['capture_status'] == 'not_recorded'


def test_cli_diagnostic_missing_directory_is_preflight_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(A2AConfig, 'from_env', lambda **kw: pytest.fail('Must not load key or send'))
    assert main(['--live', '--text', 'synthetic', '--diagnostic-out', str(tmp_path/'missing'/'diag.json')]) == 2
    assert 'FILE_IO_ERROR' in capsys.readouterr().out
