"""Offline by default; --live performs only the explicitly selected operation."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx

from app.integrations.a2a.client import A2AClient
from app.integrations.a2a.config import A2AConfig
from app.integrations.a2a.contracts import A2AError, send_request
from app.integrations.a2a.diagnostics import ResponseDiagnostic
from app.integrations.a2a.service import analyze_reference, poll_task, shadow_result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Use HTTPS; no approval file')
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--text', '--reference', dest='text', help='Explicit synthetic input; may trigger inference')
    operation.add_argument('--card', action='store_true', help='One public GET; no credential loaded or sent')
    operation.add_argument('--task-id', help='Read an existing task; never submits SendMessage')
    parser.add_argument('--card-url', help='Optional same-origin discovery URL')
    parser.add_argument('--return-immediately', action='store_true')
    parser.add_argument('--poll-count', type=int, default=1, help='Explicit GetTask count, 1 to 5; default 1')
    parser.add_argument('--poll-interval', type=float, default=2.0)
    parser.add_argument('--dry-run', action='store_true', help='Print SendMessage JSON; no key or network')
    parser.add_argument('--mock-response', choices=['message', 'task'], default='message')
    parser.add_argument('--out', type=Path, help='New sidecar; never overwrite')
    parser.add_argument('--diagnostic-out', type=Path,
                        help='New response-only, redacted parse-failure diagnostic; opt-in, never overwrite')
    args = parser.parse_args(argv)
    if args.card_url and not args.card:
        parser.error('--card-url requires --card')
    if args.dry_run and (args.card or args.task_id):
        parser.error('--dry-run applies to SendMessage only')
    if args.return_immediately and (args.card or args.task_id):
        parser.error('--return-immediately applies to SendMessage only')
    if not args.task_id and (args.poll_count != 1 or args.poll_interval != 2.0):
        parser.error('poll options require --task-id')
    output = None
    diagnostic = None
    try:
        if args.out:
            output = args.out.open('x', encoding='utf-8')
        if args.diagnostic_out:
            diagnostic = ResponseDiagnostic(args.diagnostic_out)
        text = args.text if args.text is not None else 'SYNTHETIC_DEMO_001'
        if args.dry_run:
            report = {'transport_mode': 'dry_run', 'request': send_request(text, str(uuid4()), str(uuid4()),
                                                                        return_immediately=args.return_immediately)}
        else:
            if args.live:
                if args.text is None and not args.card and not args.task_id:
                    raise A2AError('MISSING_INPUT')
                config = A2AConfig.from_env(credentials=not args.card)
                client = A2AClient(config, diagnostic=diagnostic)
            else:
                # Never read live credentials/environment in mock mode.
                config = A2AConfig(endpoint='https://a2a.invalid/a2a', api_key='synthetic-' + uuid4().hex)

                def respond(request):
                    if request.method == 'GET':
                        return httpx.Response(200, json={'name': 'Synthetic Agent Card', 'protocolVersion': '1.0',
                                                       'skills': [{'id': 'synthetic-fixture'}]})
                    body = json.loads(request.content)
                    task = {'id': args.task_id or 'synthetic-task', 'status': {'state': 'TASK_STATE_WORKING'}}
                    message = {'messageId': 'synthetic-response', 'role': 'ROLE_AGENT',
                               'parts': [{'text': 'Synthetic transport fixture; no medical inference.'}]}
                    result = task if body['method'] == 'GetTask' else (
                        {'message': message} if args.mock_response == 'message' else {'task': task})
                    return httpx.Response(200, json={'jsonrpc': '2.0', 'id': body['id'], 'result': result})

                client = A2AClient(config, transport=httpx.MockTransport(respond), diagnostic=diagnostic)
            if args.card:
                report = shadow_result(client, client.get_agent_card(args.card_url))
            elif args.task_id:
                report = poll_task(client, args.task_id, max_polls=args.poll_count, interval=args.poll_interval)
            else:
                report = analyze_reference(client, text, return_immediately=args.return_immediately)
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        if output:
            output.write(serialized + '\n')
        print(serialized)
        return 0
    except A2AError as exc:
        report = {'error': exc.as_dict()}
        if diagnostic is not None:
            report['diagnostic_status'] = diagnostic.status
        serialized = json.dumps(report)
        if output:
            output.write(serialized + '\n')
        print(serialized)
        return 2
    except OSError:
        print('{"error":{"code":"FILE_IO_ERROR"}}')
        return 2
    finally:
        if diagnostic is not None:
            diagnostic.close()
        if output:
            output.close()


if __name__ == '__main__':
    raise SystemExit(main())
