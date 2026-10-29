"""Synthetic transport-only tests. No real credentials or clinical gold."""
from dataclasses import replace
import json
import socket
import string

import httpx
import pytest

from app.integrations.a2a.client import A2AClient
from app.integrations.a2a.config import A2AConfig
from app.integrations.a2a.contracts import A2AError
from app.integrations.a2a.service import poll_task
from scripts.probe_itri_a2a import main


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Offline test attempted a network request')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)


def client(handler, **changes):
    return A2AClient(A2AConfig(endpoint='https://a2a.invalid/a2a',
                               api_key='synthetic-credential', **changes), transport=httpx.MockTransport(handler))


def test_plain_question_without_approval_file():
    def handler(request):
        data = json.loads(request.content)
        assert data['params']['message']['parts'] == [{'text': '合成測試：什麼是 MIC？'}]
        assert data['params']['configuration'] == {'returnImmediately': True}
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': data['id'], 'result': {
            'message': {'messageId': 'synthetic', 'role': 'ROLE_AGENT', 'parts': [{'text': 'fixture'}]}}})
    assert client(handler).send_message('合成測試：什麼是 MIC？', return_immediately=True)['kind'] == 'message'


@pytest.mark.parametrize('text', ['', ' ', {}, None, 'x' * 32769], ids=['empty', 'blank', 'dict', 'null', 'oversized'])
def test_invalid_text_before_transport(text):
    with pytest.raises(A2AError, match='INVALID_INPUT'):
        client(lambda _: pytest.fail('Must not send')).send_message(text)


@pytest.mark.parametrize('token', ['Bearer synthetic-value', 'synthetic\nvalue', '合成金鑰',
                                 'synthetic\rvalue', 'synthetic\tvalue', 'synthetic\x00value',
                                 'synthetic\x7fvalue', ' synthetic', 'synthetic ', 'synthetic value'])
def test_bad_header_credential_local_only(token):
    obj = client(lambda _: pytest.fail('Must not send'))
    obj.config = replace(obj.config, api_key=token)
    with pytest.raises(A2AError) as caught:
        obj.send_message('synthetic')
    assert caught.value.code == 'INVALID_CREDENTIAL' and caught.value.http_status is None


@pytest.mark.parametrize('symbol', list(string.punctuation), ids=lambda s: 'ascii-' + str(ord(s)))
def test_opaque_credential_preserved_and_redacted(symbol):
    token = 'synthetic' + symbol + 'credential'
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers['Authorization'] == 'Bearer ' + token
        body = json.loads(request.content)
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': body['id'], 'result': {
            'message': {'messageId': 'fixture', 'role': 'ROLE_AGENT', 'parts': [{'text': token}]}}})
    obj = client(handler)
    obj.config = replace(obj.config, api_key=token)
    result = obj.send_message('synthetic')
    assert len(calls) == 1 and result['attempts'] == 1
    assert result['payload']['parts'] == [{'text': '[REDACTED]'}]
    assert token not in json.dumps(result) + repr(obj.config)


def test_header_safe_credential_can_still_be_rejected_by_server():
    token = 'synthetic:credential!%'
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers['Authorization'] == 'Bearer ' + token
        return httpx.Response(401, text=token)
    obj = client(handler)
    obj.config = replace(obj.config, api_key=token)
    with pytest.raises(A2AError) as caught:
        obj.send_message('synthetic')
    assert len(calls) == 1
    assert caught.value.code == 'HTTP_ERROR' and caught.value.http_status == 401
    assert token not in str(caught.value)


@pytest.mark.parametrize('state', ['SUBMITTED', 'WORKING', 'COMPLETED', 'FAILED', 'CANCELED',
                                  'INPUT_REQUIRED', 'REJECTED', 'AUTH_REQUIRED'])
def test_get_task_contract(state):
    calls = []
    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body['method'] == 'GetTask' and body['params'] == {'id': 'synthetic-task'}
        assert request.headers['Authorization'] == 'Bearer synthetic-credential'
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': body['id'], 'result': {
            'id': 'synthetic-task', 'status': {'state': 'TASK_STATE_' + state}}})
    assert client(handler).get_task('synthetic-task')['state'] == 'TASK_STATE_' + state
    assert len(calls) == 1


@pytest.mark.parametrize('task_id', ['', ' ', None, 'bad\nvalue'])
def test_invalid_task_id(task_id):
    with pytest.raises(A2AError, match='INVALID_TASK_ID'):
        client(lambda _: pytest.fail('Must not send')).get_task(task_id)


def test_get_task_id_mismatch():
    def handler(request):
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': json.loads(request.content)['id'],
            'result': {'id': 'different-task', 'status': {'state': 'TASK_STATE_COMPLETED'}}})
    with pytest.raises(A2AError, match='TASK_ID_MISMATCH'):
        client(handler).get_task('synthetic-task')


def test_card_public_get_no_bearer_no_redirect_or_adoption():
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'GET' and request.content == b''
        assert str(request.url) == 'https://a2a.invalid/.well-known/agent-card.json'
        assert 'authorization' not in request.headers
        return httpx.Response(200, json={'name': 'Synthetic Card', 'skills': [], 'url': 'https://untrusted.invalid'})
    obj = client(handler)
    obj.config = replace(obj.config, api_key='')
    result = obj.get_agent_card()
    assert result['kind'] == 'agent_card' and result['http_status'] == 200
    assert obj.config.endpoint == 'https://a2a.invalid/a2a' and len(seen) == 1


@pytest.mark.parametrize('url', ['http://a2a.invalid/card', 'https://different.invalid/card',
                               'https://a2a.invalid/card?secret=x', 'https://user:password@a2a.invalid/card'])
def test_invalid_card_url_no_transport(url):
    with pytest.raises(A2AError, match='INVALID_CARD_URL'):
        client(lambda _: pytest.fail('Must not send')).get_agent_card(url)


@pytest.mark.parametrize('status', [301, 401, 403, 404, 500])
def test_card_http_status_single_request(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={'Location': 'https://other.invalid'}, text='not exposed')
    with pytest.raises(A2AError) as caught:
        client(handler).get_agent_card()
    assert caught.value.http_status == status and len(calls) == 1


@pytest.mark.parametrize('payload', [{}, {'name': 'x'}, {'name': '', 'skills': []}, {'name': 'x', 'skills': [1]}])
def test_invalid_card(payload):
    with pytest.raises(A2AError, match='INVALID_AGENT_CARD') as caught:
        client(lambda _: httpx.Response(200, json=payload)).get_agent_card()
    assert caught.value.http_status == 200


def test_rpc_error_keeps_http_and_rpc_codes():
    def handler(request):
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': json.loads(request.content)['id'],
            'error': {'code': -32601, 'message': 'Bearer synthetic-secret'}})
    with pytest.raises(A2AError) as caught:
        client(handler).get_task('synthetic-task')
    assert caught.value.as_dict() == {'code': 'RPC_ERROR', 'http_status': 200,
                                     'rpc_code': -32601, 'delivery_unknown': False}


def test_bounded_poll_stops_at_terminal(monkeypatch):
    sleeps, methods = [], []
    states = iter(['WORKING', 'COMPLETED'])
    monkeypatch.setattr('app.integrations.a2a.service.time.sleep', sleeps.append)
    def handler(request):
        body = json.loads(request.content)
        methods.append(body['method'])
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': body['id'], 'result': {
            'id': 'synthetic-task', 'status': {'state': 'TASK_STATE_' + next(states)}}})
    report = poll_task(client(handler), 'synthetic-task', max_polls=5)
    assert methods == ['GetTask', 'GetTask'] and sleeps == [2.0]
    assert report['poll_count'] == 2 and report['result']['state'] == 'TASK_STATE_COMPLETED'


def test_poll_does_not_retry_error():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('synthetic-credential')
    with pytest.raises(A2AError, match='TIMEOUT'):
        poll_task(client(handler), 'synthetic-task', max_polls=5)
    assert len(calls) == 1


@pytest.mark.parametrize('options', [{'max_polls': 0}, {'max_polls': 6}, {'max_polls': True},
                                     {'interval': 0}, {'interval': float('nan')}])
def test_invalid_poll_options(options):
    with pytest.raises(A2AError, match='INVALID_POLL_OPTIONS'):
        poll_task(client(lambda _: pytest.fail('Must not send')), 'synthetic-task', **options)


def test_cli_dry_run_never_reads_credentials(monkeypatch, capsys):
    monkeypatch.setattr(A2AConfig, 'from_env', lambda **kw: pytest.fail('Must not load env'))
    assert main(['--dry-run', '--text', 'synthetic-question']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['transport_mode'] == 'dry_run' and data['request']['method'] == 'SendMessage'


def test_card_cli_skips_credential_loading(monkeypatch, capsys):
    seen = []
    def load_env(*, credentials=True):
        seen.append(credentials)
        return A2AConfig(endpoint='https://a2a.invalid/a2a')
    def card(self, url):
        self.config.check(authenticated=False)
        return {'kind': 'agent_card', 'payload': {'name': 'fixture'}}
    monkeypatch.setattr(A2AConfig, 'from_env', load_env)
    monkeypatch.setattr(A2AClient, 'get_agent_card', card)
    assert main(['--live', '--card']) == 0
    assert seen == [False]


def test_cli_live_without_key_stops_locally(monkeypatch, capsys):
    monkeypatch.delenv('ITRI_A2A_API_KEY', raising=False)
    assert main(['--live', '--text', 'synthetic']) == 2
    assert json.loads(capsys.readouterr().out)['error']['code'] == 'MISSING_API_KEY'


@pytest.mark.parametrize('argv', [['--card'], ['--task-id', 'synthetic-task'], ['--mock-response', 'task']])
def test_mock_operations(argv, capsys):
    assert main(argv) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['transport_mode'] == 'mock' and not data['gold_eligible']


def test_live_cli_single_send_without_local_approval(monkeypatch, capsys):
    calls = []
    def load_env(*, credentials=True):
        return A2AConfig(endpoint='https://a2a.invalid/a2a', api_key='synthetic-credential')
    def send(self, text, **options):
        calls.append((text, options))
        self.config.check()
        return {'kind': 'message', 'state': 'message_received', 'payload': {}}
    monkeypatch.setattr(A2AConfig, 'from_env', load_env)
    monkeypatch.setattr(A2AClient, 'send_message', send)
    assert main(['--live', '--text', 'synthetic']) == 0
    assert calls == [('synthetic', {'return_immediately': False})]
