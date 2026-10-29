"""Observed redacted ITRI transport fixture plus synthetic invalid variants. Not Gold."""
from copy import deepcopy
import json
from pathlib import Path
import socket

import httpx
import pytest

from app.integrations.a2a.client import A2AClient
from app.integrations.a2a.config import A2AConfig
from app.integrations.a2a.contracts import A2AError, STATES, parse_response
from scripts.probe_itri_a2a import main


FIXTURE = json.loads((Path(__file__).parent/'fixtures/itri_submitted_task_redacted.json').read_text(encoding='utf-8'))
TASK_ID = '29f4d601440343918e32dbc8e6c099a8'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Network forbidden in Task layout tests')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)


def parse_result(result, task_response=False):
    return parse_response(json.dumps({'jsonrpc': '2.0', 'id': 'synthetic-rpc', 'result': result}).encode(),
                          'synthetic-rpc', task_response=task_response)


def test_exact_saved_response_replays_without_modification():
    response = deepcopy(FIXTURE['response'])
    before = deepcopy(response)
    kind, state, task = parse_response(json.dumps(response, ensure_ascii=False).encode(), response['id'])
    assert kind == 'task' and state == 'TASK_STATE_SUBMITTED'
    assert task['id'] == TASK_ID
    assert task['status']['message']['parts'][0]['text'] == '已受理，排隊中'
    assert task == before['result'] and response == before
    assert FIXTURE['fixture_type'] == 'observed_redacted_transport_response' and not FIXTURE['clinical_gold']


@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('task_response', [False, True])
@pytest.mark.parametrize('state', sorted(STATES))
def test_both_layouts_share_state_validation(wrapped, task_response, state):
    task = deepcopy(FIXTURE['response']['result'])
    task['status']['state'] = state  # Explicit synthetic state variant.
    kind, actual, payload = parse_result({'task': task} if wrapped else task, task_response)
    assert (kind, actual, payload['id']) == ('task', state, TASK_ID)
    assert payload['status']['message'] == task['status']['message']


@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('task', [
    {}, {'id': 'synthetic'}, {'status': {'state': 'TASK_STATE_SUBMITTED'}},
    {'id': '', 'status': {'state': 'TASK_STATE_SUBMITTED'}},
    {'id': 12, 'status': {'state': 'TASK_STATE_SUBMITTED'}},
    {'id': 'synthetic', 'status': []}, {'id': 'synthetic', 'status': {}},
    {'id': 'synthetic', 'status': {'state': 'UNRECOGNIZED'}},
    {'id': 'synthetic', 'status': {'state': 1}},
    {'id': 'synthetic', 'status': {'state': 'TASK_STATE_SUBMITTED', 'message': {}}},
    {'id': 'synthetic', 'status': {'state': 'TASK_STATE_SUBMITTED'}, 'history': 'invalid'},
    {'id': 'synthetic', 'status': {'state': 'TASK_STATE_SUBMITTED'}, 'artifacts': [{}]},
])
def test_invalid_tasks_are_rejected_in_both_layouts(wrapped, task):
    with pytest.raises(A2AError):
        parse_result({'task': task} if wrapped else task)


@pytest.mark.parametrize('result', [None, [], {'id': 'not-a-task'},
    {'task': {}, 'message': {}},
    {'id': 'synthetic', 'status': {'state': 'TASK_STATE_SUBMITTED'}, 'task': {}},
    {'id': 'synthetic', 'status': {'state': 'TASK_STATE_SUBMITTED'}, 'message': {}},
])
def test_arbitrary_or_ambiguous_result_is_rejected(result):
    with pytest.raises(A2AError):
        parse_result(result)


@pytest.mark.parametrize('task_response', [False, True])
def test_rpc_error_is_not_swallowed(task_response):
    raw = json.dumps({'jsonrpc': '2.0', 'id': 'synthetic-rpc',
                      'error': {'code': -32602, 'message': 'synthetic-error'}}).encode()
    with pytest.raises(A2AError) as caught:
        parse_response(raw, 'synthetic-rpc', task_response=task_response)
    assert caught.value.code == 'RPC_ERROR' and caught.value.rpc_code == -32602


def test_saved_task_still_requires_matching_rpc_id():
    with pytest.raises(A2AError, match='INVALID_RPC_ENVELOPE'):
        parse_response(json.dumps(FIXTURE['response']).encode(), 'different-rpc-id')


def test_message_stays_message_and_cannot_be_get_task_result():
    message = {'messageId': 'synthetic-message', 'role': 'ROLE_AGENT', 'parts': [{'text': 'synthetic'}]}
    assert parse_result({'message': message}) == ('message', 'message_received', message)
    with pytest.raises(A2AError):
        parse_result({'message': message}, task_response=True)


@pytest.mark.parametrize('method', ['SendMessage', 'GetTask'])
@pytest.mark.parametrize('wrapped', [False, True])
def test_client_saved_task_one_transport_call(method, wrapped):
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body['method'] == method
        response = deepcopy(FIXTURE['response'])
        response['id'] = body['id']  # Replay with this test request's correlation ID.
        if wrapped:
            response['result'] = {'task': response['result']}
        return httpx.Response(200, json=response)
    obj = A2AClient(A2AConfig(endpoint='https://a2a.invalid/a2a', api_key='synthetic-fixture-key'),
                    transport=httpx.MockTransport(handler))
    result = obj.get_task(TASK_ID) if method == 'GetTask' else obj.send_message('synthetic-question')
    assert result['http_status'] == 200 and result['kind'] == 'task'
    assert result['state'] == 'TASK_STATE_SUBMITTED' and result['payload']['id'] == TASK_ID
    assert result['attempts'] == len(calls) == 1
    if method == 'GetTask':
        assert calls[0]['params'] == {'id': TASK_ID}


def test_cli_get_task_once_never_sends_message_or_sleeps(monkeypatch, capsys):
    calls = []
    def get_task(self, task_id):
        calls.append(task_id)
        return {'kind': 'task', 'state': 'TASK_STATE_SUBMITTED', 'payload': deepcopy(FIXTURE['response']['result'])}
    monkeypatch.setattr(A2AClient, 'get_task', get_task)
    monkeypatch.setattr(A2AClient, 'send_message', lambda *a, **kw: pytest.fail('No SendMessage allowed'))
    monkeypatch.setattr('app.integrations.a2a.service.time.sleep', lambda *a: pytest.fail('No extra polling'))
    assert main(['--task-id', TASK_ID, '--poll-count', '1']) == 0
    report = json.loads(capsys.readouterr().out)
    assert calls == [TASK_ID] and report['poll_count'] == 1
    assert report['result']['payload']['id'] == TASK_ID
