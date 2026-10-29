"""Entirely synthetic fixtures; no server or real credentials."""
from dataclasses import replace
import json
import logging
import socket
import traceback

import httpx
import pytest

from app.integrations.a2a.client import A2AClient
from app.integrations.a2a.config import A2AConfig, PROFILE
from app.integrations.a2a.contracts import A2AError, parse_response, redact
from app.integrations.a2a.service import analyze_reference
from scripts.probe_itri_a2a import main

TOKEN = 'synthetic-test-credential-never-real'
REF = 'SYNTHETIC_001'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Network access forbidden in offline tests')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


def config(**changes):
    return replace(A2AConfig(endpoint='https://a2a.invalid/a2a',
                             protocol_profile=PROFILE, api_key=TOKEN), **changes)


def message(text='Synthetic output'):
    return {'messageId': 'synthetic-message', 'role': 'ROLE_AGENT', 'parts': [{'text': text}]}


def call(handler, *, cfg=None):
    return A2AClient(cfg or config(), transport=httpx.MockTransport(handler)).send_message(
        REF)


def response(request, result=None):
    return httpx.Response(200, json={'jsonrpc': '2.0', 'id': json.loads(request.content)['id'],
                                    'result': result or {'message': message()}})


def test_message_contract():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == 'POST'
        assert str(request.url) == 'https://a2a.invalid/a2a'
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        assert request.headers['A2A-Version'] == '1.0'
        body = json.loads(request.content)
        assert body['method'] == 'SendMessage'
        assert body['params']['message']['parts'] == [{'text': REF}]
        assert body['params']['message']['role'] == 'ROLE_USER'
        assert body['params']['message']['messageId'] != body['id']
        return response(request)
    result = call(handler)
    assert result['kind'] == 'message'
    assert result['attempts'] == len(requests) == 1


@pytest.mark.parametrize('state', ['SUBMITTED', 'WORKING', 'COMPLETED', 'FAILED', 'CANCELED',
                                  'INPUT_REQUIRED', 'REJECTED', 'AUTH_REQUIRED'])
def test_task_states_no_poll(state):
    calls = []
    def handler(request):
        calls.append(request)
        return response(request, {'task': {'id': 'task-1', 'status': {'state': 'TASK_STATE_' + state},
                                          'artifacts': [{'artifactId': 'a', 'parts': [{'data': {'synthetic': True}}]}]}})
    result = call(handler)
    assert result['state'] == 'TASK_STATE_' + state
    assert len(calls) == 1


@pytest.mark.parametrize('status', [301, 302, 401, 403, 429, 500, 503])
def test_http_error_no_redirect_or_retry(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=TOKEN, headers={'Location': 'https://other.invalid/'})
    with pytest.raises(A2AError) as caught:
        call(handler)
    assert caught.value.code == 'HTTP_ERROR'
    assert caught.value.http_status == status
    assert TOKEN not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize('error,code', [(httpx.ReadTimeout, 'TIMEOUT'),
                                     (httpx.ConnectError, 'CONNECTION_ERROR'),
                                     (RuntimeError, 'TRANSPORT_ERROR')])
def test_transport_failure_safe(error, code):
    calls = []
    def handler(request):
        calls.append(request)
        raise error(TOKEN)
    with pytest.raises(A2AError) as caught:
        call(handler)
    assert caught.value.code == code
    assert caught.value.delivery_unknown
    assert TOKEN not in ''.join(traceback.format_exception(caught.value))
    assert len(calls) == 1


def test_rpc_error_safe():
    def handler(request):
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': json.loads(request.content)['id'],
                                         'error': {'code': -32001, 'message': TOKEN, 'data': TOKEN}})
    with pytest.raises(A2AError) as caught:
        call(handler)
    assert caught.value.rpc_code == -32001
    assert TOKEN not in json.dumps(caught.value.as_dict())


@pytest.mark.parametrize('raw', [b'not json', b'{"x":NaN}', b'{"x":1,"x":2}', b'\xff'])
def test_invalid_json(raw):
    with pytest.raises(A2AError, match='INVALID_JSON'):
        call(lambda _: httpx.Response(200, content=raw, headers={'Content-Type': 'application/json'}))


@pytest.mark.parametrize('result', [None, [], {}, {'message': message(), 'task': {}},
                                   {'message': {}}, {'task': {'id': 'a', 'status': {'state': 'UNKNOWN'}}},
                                   {'message': {'messageId': 'a', 'role': 'ROLE_AGENT', 'parts': [{'text': 1}]}},
                                   {'message': {'messageId': 'a', 'role': 'ROLE_AGENT', 'parts': [{'url': 'https://files.invalid/a'}]}}])
def test_invalid_payload(result):
    raw = json.dumps({'jsonrpc': '2.0', 'id': 'r', 'result': result}).encode()
    with pytest.raises(A2AError):
        parse_response(raw, 'r')


@pytest.mark.parametrize('obj', [{'jsonrpc': '1.0', 'id': 'r', 'result': {}},
                                {'jsonrpc': '2.0', 'id': 'wrong', 'result': {}},
                                {'jsonrpc': '2.0', 'id': 'r', 'result': {}, 'error': {}},
                                {'jsonrpc': '2.0', 'id': 'r', 'error': {'code': True, 'message': ''}}])
def test_invalid_envelope(obj):
    with pytest.raises(A2AError, match='INVALID_RPC_ENVELOPE'):
        parse_response(json.dumps(obj).encode(), 'r')


@pytest.mark.parametrize('changes,code', [({'api_key': ''}, 'MISSING_API_KEY'), ({'protocol_profile': 'a2a-0.3'}, 'UNSUPPORTED_PROTOCOL_VERSION'),
    ({'protocol_version': '2.0'}, 'UNSUPPORTED_PROTOCOL_VERSION'),
    ({'endpoint': 'http://a2a.invalid'}, 'INVALID_ENDPOINT'),
    ({'endpoint': 'https://user:password@a2a.invalid'}, 'INVALID_ENDPOINT'),
    ({'endpoint': 'https://a2a.invalid/?secret=x'}, 'INVALID_ENDPOINT'),
    ({'version_header': 'Authorization'}, 'INVALID_VERSION_HEADER'),
    ({'read_timeout': float('nan')}, 'INVALID_CONFIG'),
    ({'max_response_bytes': 0}, 'INVALID_CONFIG')])
def test_config_denied_before_transport(changes, code):
    def handler(_):
        pytest.fail('Transport must not be called')
    with pytest.raises(A2AError, match=code):
        call(handler, cfg=config(**changes))


def test_missing_key_without_transport():
    with pytest.raises(A2AError, match='MISSING_API_KEY'):
        A2AClient(A2AConfig()).send_message(REF)


def test_minimal_projection_rejects_case():
    with pytest.raises(A2AError, match='INVALID_INPUT'):
        A2AClient(config()).send_message({'case_id': 'local'})


def test_redaction_and_untrusted_envelope(caplog):
    caplog.set_level('DEBUG')
    client = A2AClient(config(), transport=httpx.MockTransport(lambda r: response(r, {
        'message': message(TOKEN + ' Bearer other-secret')})))
    report = analyze_reference(client, REF)
    assert TOKEN not in json.dumps(report) + caplog.text + repr(config())
    assert 'other-secret' not in json.dumps(report)
    assert report['untrusted'] and not report['gold_eligible']
    assert not report['clinical_decision_eligible']
    assert report['transport_mode'] == 'mock' and report['usage'] is None
    assert redact({'api_key': TOKEN, TOKEN: [TOKEN]}, TOKEN) == {
        'api_key': '[REDACTED]', '[REDACTED]': ['[REDACTED]']}


def test_transport_debug_headers_suppressed_and_filter_restored(caplog):
    caplog.set_level('DEBUG')
    logger = logging.getLogger('httpcore.http11')
    original_filters = list(logger.filters)
    def handler(request):
        logger.debug('remote header %s', TOKEN)
        return response(request)
    call(handler)
    assert TOKEN not in caplog.text
    assert logger.filters == original_filters
    logger.debug('ordinary transport log restored')
    assert 'ordinary transport log restored' in caplog.text


def test_version_header_explicit_omission():
    def handler(r):
        assert 'A2A-Version' not in r.headers
        return response(r)
    call(handler, cfg=config(version_header=None))


@pytest.mark.parametrize('headers,content,code', [
    ({'Content-Type': 'text/html'}, b'{}', 'INVALID_CONTENT_TYPE'),
    ({'Content-Type': 'application/json'}, b' ' * 400, 'RESPONSE_TOO_LARGE'),
])
def test_response_bounds(headers, content, code):
    with pytest.raises(A2AError, match=code):
        call(lambda _: httpx.Response(200, content=content, headers=headers), cfg=config(max_response_bytes=300))


def test_deadline(monkeypatch):
    import app.integrations.a2a.client as module
    ticks = iter([0, 50])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(A2AError, match='DEADLINE_EXCEEDED'):
        call(response)


def test_streaming_not_implemented():
    client = A2AClient(config())
    for function, args in [(client.stream_message, ())]:
        with pytest.raises(A2AError, match='NOT_IMPLEMENTED'):
            function(*args)


def test_cli_mock_ignores_live_env_and_preserves_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('ITRI_A2A_ENDPOINT', 'https://must-not-call.invalid')
    monkeypatch.setenv('ITRI_A2A_API_KEY', TOKEN)
    output = tmp_path / 'result.json'
    assert main(['--out', str(output)]) == 0
    saved = output.read_bytes()
    report = json.loads(saved)
    assert report['transport_mode'] == 'mock'
    assert TOKEN not in capsys.readouterr().out
    assert main(['--out', str(output)]) == 2
    assert saved == output.read_bytes()
    assert main(['--mock-response', 'task']) == 0


def test_cli_live_requires_explicit_input(capsys):
    assert main(['--live']) == 2
    assert 'MISSING_INPUT' in capsys.readouterr().out


def test_env_default_and_invalid(monkeypatch):
    monkeypatch.delenv('ITRI_A2A_PROTOCOL_PROFILE', raising=False)
    assert A2AConfig.from_env().protocol_profile == PROFILE
    monkeypatch.setenv('ITRI_A2A_CONNECT_TIMEOUT_SECONDS', TOKEN)
    with pytest.raises(A2AError) as caught:
        A2AConfig.from_env()
    assert TOKEN not in str(caught.value)
