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
    runs = []
    for case_id in [x['case_id'] for x in main.list_cases() if x['case_id'].startswith('cohort-') and not x['case_id'].endswith('-allergy')][:2]:
        if not main.repo.get_case(case_id):
            continue
        for mode in ('rule-only', 'multi-agent'):
            revision = main.repo.get_case(case_id)['revision']
            run = main.start_run(main.RunBody(case_id=case_id, mode=mode, provider_kind='mock', request_id=None))
            runs.append({'case_id': case_id, 'mode': mode, 'run_id': run['run_id'], 'status': run['status'], 'gate_status': run.get('gate_status'), 'missing_fields': run.get('missing_fields'), 'errors': run.get('errors')})
    print(json.dumps({'seed': seeded, 'retrieval': 'lexical', 'runs': runs}, ensure_ascii=True, indent=2))
    if not runs or any(r['gate_status'] != 'ready_for_review' or r['errors'] or r['missing_fields'] for r in runs):
        raise SystemExit('Source-case walkthrough did not pass. Import the CSV and WHO first; inspect reported results.')

if __name__ == '__main__':
    main_cli()
