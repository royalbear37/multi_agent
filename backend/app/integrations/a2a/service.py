"""Shadow-only result envelope. No repository, workflow or evaluator imports."""
import hashlib
import math
import time

import httpx

from .client import A2AClient
from .contracts import A2AError


def analyze_reference(client: A2AClient, reference: str, *, return_immediately: bool = False) -> dict:
    return shadow_result(client, client.send_message(reference, return_immediately=return_immediately))


def shadow_result(client: A2AClient, result: dict) -> dict:
    return {'schema_version': 'a2a-shadow-0.1', 'untrusted': True,
            'clinical_decision_eligible': False, 'gold_eligible': False,
            'application_validation': 'not_evaluated',
            'transport_mode': 'mock' if isinstance(client._transport, httpx.MockTransport) else 'live',
            'protocol_profile': client.config.protocol_profile,
            'version_header_sent': client.config.version_header is not None,
            'endpoint_sha256': hashlib.sha256(client.config.endpoint.encode()).hexdigest(),
            'usage': None, 'estimated_cost': None, 'result': result}


def poll_task(client: A2AClient, task_id: str, *, max_polls: int = 1, interval: float = 2.0) -> dict:
    """Explicit, bounded status reads; never sends another SendMessage or retries failures."""
    if (type(max_polls) is not int or not 1 <= max_polls <= 5 or type(interval) not in (int, float)
            or not math.isfinite(interval) or not 1 <= interval <= 60):
        raise A2AError('INVALID_POLL_OPTIONS')
    results = []
    for index in range(max_polls):
        if index:
            time.sleep(interval)
        result = client.get_task(task_id)
        results.append(result)
        if result['state'] not in {'TASK_STATE_SUBMITTED', 'TASK_STATE_WORKING'}:
            break
    report = shadow_result(client, results[-1])
    report['polls'] = results
    report['poll_count'] = len(results)
    return report
