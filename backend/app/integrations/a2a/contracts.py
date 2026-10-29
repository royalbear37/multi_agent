"""Bounded A2A 1.0 JSON-RPC subset, not a clinical output contract."""
from __future__ import annotations

import json
import re
from typing import Any


class A2AError(RuntimeError):
    """Only locally defined codes and numeric statuses may leave the boundary."""

    def __init__(self, code: str, *, http_status: int | None = None,
                 rpc_code: int | None = None, delivery_unknown: bool = False):
        self.code = code
        self.http_status = http_status
        self.rpc_code = rpc_code
        self.delivery_unknown = delivery_unknown
        super().__init__(code)

    def as_dict(self) -> dict:
        return dict(code=self.code, http_status=self.http_status,
                    rpc_code=self.rpc_code, delivery_unknown=self.delivery_unknown)


def redact(value: Any, secret: str) -> Any:
    """Scrub exact runtime credential, bearer text and secret-bearing keys."""
    if isinstance(value, str):
        value = value.replace(secret, '[REDACTED]') if secret else value
        return re.sub(r'(?i)Bearer\s+\S+', 'Bearer [REDACTED]', value)
    if isinstance(value, list):
        return [redact(x, secret) for x in value]
    if isinstance(value, dict):
        return {redact(k, secret): ('[REDACTED]' if re.search(
            r'(?i)token|secret|authorization|api.?key|password|cookie', k)
            else redact(v, secret)) for k, v in value.items()}
    return value


def strict_json(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError('nonfinite number')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise A2AError('INVALID_JSON') from None


def send_request(text: str, request_id: str, message_id: str, *, return_immediately: bool = False) -> dict:
    if not isinstance(text, str) or not text.strip() or len(text) > 32768:
        raise A2AError('INVALID_INPUT')
    if type(return_immediately) is not bool:
        raise A2AError('INVALID_INPUT')
    params = {'message': {'messageId': message_id, 'role': 'ROLE_USER', 'parts': [{'text': text}]}}
    if return_immediately:
        params['configuration'] = {'returnImmediately': True}
    return {'jsonrpc': '2.0', 'id': request_id, 'method': 'SendMessage', 'params': params}


def task_request(task_id: str, request_id: str) -> dict:
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 1024 or any(ord(c) < 32 for c in task_id):
        raise A2AError('INVALID_TASK_ID')
    return {'jsonrpc': '2.0', 'id': request_id, 'method': 'GetTask', 'params': {'id': task_id}}


STATES = {'TASK_STATE_SUBMITTED', 'TASK_STATE_WORKING', 'TASK_STATE_COMPLETED',
          'TASK_STATE_FAILED', 'TASK_STATE_CANCELED', 'TASK_STATE_INPUT_REQUIRED',
          'TASK_STATE_REJECTED', 'TASK_STATE_AUTH_REQUIRED'}


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _parts(value):
    if not isinstance(value, list) or not value:
        raise A2AError('INVALID_A2A_PAYLOAD')
    for part in value:
        if not isinstance(part, dict):
            raise A2AError('INVALID_A2A_PAYLOAD')
        content = set(part) & {'text', 'data', 'url', 'raw', 'file'}
        if len(content) != 1:
            raise A2AError('INVALID_A2A_PAYLOAD')
        if content & {'url', 'raw', 'file'}:
            raise A2AError('UNSUPPORTED_PART')
        if 'text' in part and not isinstance(part['text'], str):
            raise A2AError('INVALID_A2A_PAYLOAD')
        if 'data' in part and not isinstance(part['data'], dict):
            raise A2AError('INVALID_A2A_PAYLOAD')


def _message(value):
    if not isinstance(value, dict) or not _nonempty(value.get('messageId')) or value.get('role') not in {'ROLE_USER', 'ROLE_AGENT'}:
        raise A2AError('INVALID_A2A_PAYLOAD')
    _parts(value.get('parts'))


def parse_response(raw: bytes, request_id: str, *, task_response: bool = False) -> tuple[str, str, dict]:
    obj = strict_json(raw)
    if not isinstance(obj, dict) or obj.get('jsonrpc') != '2.0' or obj.get('id') != request_id:
        raise A2AError('INVALID_RPC_ENVELOPE')
    if ('result' in obj) == ('error' in obj):
        raise A2AError('INVALID_RPC_ENVELOPE')
    if 'error' in obj:
        error = obj['error']
        if not isinstance(error, dict) or type(error.get('code')) is not int or not isinstance(error.get('message'), str):
            raise A2AError('INVALID_RPC_ENVELOPE')
        raise A2AError('RPC_ERROR', rpc_code=error['code'])
    result = obj['result']
    if not isinstance(result, dict) or ('message' in result and 'task' in result):
        raise A2AError('INVALID_A2A_PAYLOAD')
    # Accept the observed ITRI direct Task layout as well as the wrapped
    # layout. Reject ambiguous mixtures rather than choosing one branch.
    if ('message' in result or 'task' in result) and ('id' in result or 'status' in result):
        raise A2AError('INVALID_A2A_PAYLOAD')
    if 'message' in result:
        if task_response:
            raise A2AError('INVALID_A2A_PAYLOAD')
        _message(result['message'])
        if result['message']['role'] != 'ROLE_AGENT':
            raise A2AError('INVALID_A2A_PAYLOAD')
        return 'message', 'message_received', result['message']
    # Both layouts must pass exactly the same Task validation below;
    # an arbitrary object containing only an id is not a Task.
    task = result['task'] if 'task' in result else result
    if not isinstance(task, dict) or not _nonempty(task.get('id')) or not isinstance(task.get('status'), dict):
        raise A2AError('INVALID_A2A_PAYLOAD')
    state = task['status'].get('state')
    if not isinstance(state, str) or state not in STATES:
        raise A2AError('INVALID_TASK_STATE')
    if 'message' in task['status']:
        _message(task['status']['message'])
    for key in ('history', 'artifacts'):
        if key in task and not isinstance(task[key], list):
            raise A2AError('INVALID_A2A_PAYLOAD')
    for message in task.get('history', []):
        _message(message)
    for artifact in task.get('artifacts', []):
        if not isinstance(artifact, dict) or not _nonempty(artifact.get('artifactId')):
            raise A2AError('INVALID_A2A_PAYLOAD')
        _parts(artifact.get('parts'))
    return 'task', state, task
