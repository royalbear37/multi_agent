"""Minimal A2A transport: one request per call, no retries or redirects."""
from __future__ import annotations

from contextlib import contextmanager
import logging
import threading
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx

from .config import A2AConfig
from .contracts import A2AError, parse_response, redact, send_request, strict_json, task_request
from .diagnostics import ResponseDiagnostic


@contextmanager
def _private_transport_logs():
    # httpcore DEBUG traces can contain remote headers, including echoed secrets.
    # Suppress this synchronous call's transport logs, without changing levels
    # or suppressing another thread's existing workflow logs.
    owner = threading.get_ident()

    class OtherThreadsOnly(logging.Filter):
        def filter(self, record):
            return record.thread != owner

    guard = OtherThreadsOnly()
    loggers = [logging.getLogger(name) for name in (
        'httpx', 'httpcore.connection', 'httpcore.http11', 'httpcore.http2',
        'httpcore.proxy', 'httpcore.socks')]
    for logger in loggers:
        logger.addFilter(guard)
    try:
        yield
    finally:
        for logger in loggers:
            logger.removeFilter(guard)


class A2AClient:
    def __init__(self, config: A2AConfig, *, transport: httpx.BaseTransport | None = None,
                 diagnostic: ResponseDiagnostic | None = None):
        self.config = config
        self._transport = transport
        self._diagnostic = diagnostic

    def send_message(self, text: str, *, return_immediately: bool = False) -> dict:
        self.config.check()
        request_id, message_id = str(uuid4()), str(uuid4())
        body = send_request(text, request_id, message_id, return_immediately=return_immediately)
        raw, metadata = self._request('POST', self.config.endpoint, body=body)
        return self._parse_rpc(raw, metadata, request_id, message_id=message_id)

    def get_task(self, task_id: str) -> dict:
        self.config.check()
        request_id = str(uuid4())
        raw, metadata = self._request('POST', self.config.endpoint, body=task_request(task_id, request_id))
        result = self._parse_rpc(raw, metadata, request_id, task_response=True)
        if result['payload']['id'] != task_id:
            error = A2AError('TASK_ID_MISMATCH', http_status=metadata['http_status'])
            self._capture_failure(raw, metadata, error, 'GetTask', request_id=request_id)
            raise error
        return result

    def get_agent_card(self, url: str | None = None) -> dict:
        """One public GET; never sends a Bearer token or adopts returned URLs."""
        self.config.check(authenticated=False)
        endpoint = urlsplit(self.config.endpoint)
        card_url = url or urlunsplit((endpoint.scheme, endpoint.netloc, '/.well-known/agent-card.json', '', ''))
        try:
            card = urlsplit(card_url)
            valid = (card.scheme == 'https' and card.hostname == endpoint.hostname and card.port == endpoint.port
                     and not card.username and not card.password and not card.query and not card.fragment
                     and not any(c.isspace() for c in card_url)
                     and (not self.config.api_key or self.config.api_key not in card_url))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise A2AError('INVALID_CARD_URL')
        raw, metadata = self._request('GET', card_url, authenticated=False)
        try:
            payload = strict_json(raw)
            if (not isinstance(payload, dict) or not isinstance(payload.get('name'), str) or not payload['name'].strip()
                    or not isinstance(payload.get('skills'), list)
                    or any(not isinstance(skill, dict) or not isinstance(skill.get('id'), str) for skill in payload['skills'])):
                raise A2AError('INVALID_AGENT_CARD')
        except A2AError as exc:
            exc.http_status = metadata['http_status']
            self._capture_failure(raw, metadata, exc, 'AgentCard')
            raise
        return redact({**metadata, 'kind': 'agent_card', 'state': 'card_received', 'payload': payload}, self.config.api_key)

    def _parse_rpc(self, raw, metadata, request_id, *, message_id=None, task_response=False):
        try:
            kind, state, payload = parse_response(raw, request_id, task_response=task_response)
        except A2AError as exc:
            exc.http_status = metadata['http_status']
            if exc.code != 'RPC_ERROR':
                self._capture_failure(raw, metadata, exc, 'GetTask' if task_response else 'SendMessage',
                                      request_id=request_id, message_id=message_id)
            raise
        return redact({**metadata, 'request_id': request_id, 'message_id': message_id,
                       'kind': kind, 'state': state, 'payload': payload}, self.config.api_key)

    def _capture_failure(self, raw, metadata, error, operation, **ids):
        if self._diagnostic is not None:
            self._diagnostic.record(raw, secret=self.config.api_key, error=error,
                                    operation=operation, metadata=metadata, **ids)

    def _request(self, method, url, *, body=None, authenticated=True):
        headers = {'Accept': 'application/json', 'Accept-Encoding': 'identity'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.config.api_key
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if self.config.version_header:
            headers[self.config.version_header] = self.config.protocol_version
        start = time.monotonic()
        timeout = httpx.Timeout(min(self.config.read_timeout, self.config.deadline_seconds),
                               connect=min(self.config.connect_timeout, self.config.deadline_seconds))
        status = None
        try:
            transport = self._transport if self._transport is not None else httpx.HTTPTransport(retries=0, verify=True, trust_env=False)
            with _private_transport_logs(), httpx.Client(transport=transport, timeout=timeout, follow_redirects=False,
                              trust_env=False) as http:
                with http.stream(method, url, headers=headers, json=body) as response:
                    status = response.status_code
                    if not 200 <= status < 300:
                        raise A2AError('HTTP_ERROR', http_status=status,
                                       delivery_unknown=status >= 500)
                    if response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                        raise A2AError('INVALID_CONTENT_TYPE')
                    if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                        raise A2AError('UNSUPPORTED_ENCODING')
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > self.config.max_response_bytes:
                            raise A2AError('RESPONSE_TOO_LARGE')
                        if time.monotonic() - start > self.config.deadline_seconds:
                            raise A2AError('DEADLINE_EXCEEDED', delivery_unknown=True)
            if time.monotonic() - start > self.config.deadline_seconds:
                raise A2AError('DEADLINE_EXCEEDED', delivery_unknown=True)
        except A2AError as exc:
            if exc.http_status is None:
                exc.http_status = status
            raise
        except httpx.TimeoutException:
            raise A2AError('TIMEOUT', delivery_unknown=True) from None
        except httpx.RequestError:
            raise A2AError('CONNECTION_ERROR', delivery_unknown=True) from None
        except Exception:
            # Do not leak library exceptions, headers, URLs or response bodies.
            raise A2AError('TRANSPORT_ERROR', delivery_unknown=True) from None
        return bytes(raw), {'http_status': status,
                       'elapsed_ms': round((time.monotonic() - start) * 1000, 3),
                       'response_bytes': len(raw), 'attempts': 1}

    def stream_message(self):
        raise A2AError('STREAMING_NOT_IMPLEMENTED')
