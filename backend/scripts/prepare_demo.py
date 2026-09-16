"""Prepare persisted, explicitly offline synthetic runs without paid API calls."""
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Explicit command choice, not an automatic fallback on provider failure.
os.environ['RAG_RETRIEVAL_MODE'] = 'lexical'
os.environ['LLM_PROVIDER'] = 'mock'

from app import main

def main_cli():
    seeded = main.seed()
    # Older seeds stored the same policy bytes without policy_refs. Keep that
    # historical record intact; add an explicitly labelled, linked demo copy.
    service = main._documents()
    if not service.search('DEMO_ORGANISM_A', policy_refs=['demo-policy-v1']).get('evidence'):
        policy = (main.ROOT / 'data/demo_documents/synthetic_policy.md').read_bytes()
        service.import_document('prepared_walkthrough.md', policy + b'\n\nSYNTHETIC prepared walkthrough copy v1.\n',
                                'SYNTHETIC prepared walkthrough policy', 'demo-walkthrough-v1', True,
                                policy_refs=['demo-policy-v1'])
    runs = []
    for case_id in ('case-15-integrated-complete', 'case-16-integrated-followup'):
        if not main.repo.get_case(case_id):
            continue
        for mode in ('rule-only', 'multi-agent'):
            revision = main.repo.get_case(case_id)['revision']
            run = main.start_run(main.RunBody(case_id=case_id, mode=mode, provider_kind='mock', request_id=f'prepared-offline-v2:{case_id}:{revision}:{mode}'))
            runs.append({'case_id': case_id, 'mode': mode, 'run_id': run['run_id'], 'status': run['status'], 'gate_status': run.get('gate_status'), 'missing_fields': run.get('missing_fields'), 'errors': run.get('errors')})
    print(json.dumps({'seed': seeded, 'retrieval': 'lexical', 'runs': runs}, ensure_ascii=True, indent=2))
    if not runs or any(r['gate_status'] != 'ready_for_review' or r['errors'] or r['missing_fields'] for r in runs):
        raise SystemExit('Prepared demo did not pass; inspect the reported results.')

if __name__ == '__main__':
    main_cli()
