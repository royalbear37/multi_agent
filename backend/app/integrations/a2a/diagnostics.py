"""Opt-in response-only diagnostics. Never persist unredacted response bytes."""
import json
from pathlib import Path

from .contracts import A2AError, redact, strict_json


MAX_DIAGNOSTIC_BYTES = 2 * 1024 * 1024


class ResponseDiagnostic:
    """Reserve a new file before sending; retain only the first parse failure."""

    def __init__(self, path: Path):
        self._file = Path(path).open('x', encoding='utf-8')
        self.status = 'not_recorded'

    def record(self, raw: bytes, *, secret: str, error: A2AError, operation: str,
               metadata: dict, request_id=None, message_id=None):
        if self.status != 'not_recorded':
            return
        report = {
            'schema_version': 'a2a-response-diagnostic-0.1',
            'capture_status': 'saved', 'untrusted': True,
            'clinical_decision_eligible': False, 'gold_eligible': False,
            'operation': operation, 'request_id': request_id, 'message_id': message_id,
            'error': error.as_dict(),
            'http_status': metadata.get('http_status'),
            'response_bytes': len(raw), 'elapsed_ms': metadata.get('elapsed_ms'),
            'attempts': metadata.get('attempts'),
        }
        try:
            try:
                report['response'] = strict_json(raw)
                report['response_format'] = 'redacted_json'
            except A2AError:
                # Malformed JSON cannot reliably be redacted by field; don't
                # write raw text/base64, including JSON-escaped credentials.
                report.update(response=None, response_format='omitted_unparseable_json')
            report = redact(report, secret)
            serialized = json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            if len(serialized.encode('utf-8')) > MAX_DIAGNOSTIC_BYTES:
                report.update(response=None, response_format='omitted_size_limit')
                serialized = json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            self._file.write(serialized + '\n')
            self._file.flush()
            self.status = 'saved'
        except (OSError, ValueError, TypeError, RecursionError):
            # A diagnostic write failure must not replace the original error,
            # disclose a library exception, trigger a retry or print raw data.
            self.status = 'write_failed'

    def close(self):
        try:
            if self.status == 'not_recorded':
                self._file.write(json.dumps({'schema_version': 'a2a-response-diagnostic-0.1',
                                            'capture_status': 'not_recorded',
                                            'reason': 'no_captured_parse_failure'}) + '\n')
            self._file.close()
        except OSError:
            self.status = 'write_failed'
