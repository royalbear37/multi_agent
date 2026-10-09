"""Prepare source runs, or opt into isolated synthetic handoff runs; never live."""
import argparse
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Explicit command choice, not an automatic fallback on provider failure.
os.environ['RAG_RETRIEVAL_MODE'] = 'lexical'
os.environ['LLM_PROVIDER'] = 'mock'

def main_cli(synthetic=False):
    if synthetic:
        root = Path(__file__).resolve().parents[2]
        os.environ['PROTOTYPE_FIXTURE_DIR'] = str(root / 'data/synthetic')
        os.environ['PROTOTYPE_RULE_CONFIG'] = str(root / 'configs/demo/rules.json')
        os.environ['PROTOTYPE_DB_PATH'] = str(root / 'data/runtime/handoff-demo/prototype.db')
    from app import main
    seeded = main.seed()
    runs = []
    selected = (['case-15-integrated-complete', 'case-16-integrated-followup'] if synthetic else
                [x['case_id'] for x in main.list_cases() if x['case_id'].startswith('cohort-') and not x['case_id'].endswith('-allergy')][:2])
    for case_id in selected:
        if not main.repo.get_case(case_id):
            continue
        for mode in ('rule-only', 'multi-agent'):
            revision = main.repo.get_case(case_id)['revision']
            run = main.start_run(main.RunBody(case_id=case_id, mode=mode, provider_kind='mock', request_id=None))
            runs.append({'case_id': case_id, 'mode': mode, 'run_id': run['run_id'], 'status': run['status'], 'gate_status': run.get('gate_status'), 'missing_fields': run.get('missing_fields'), 'errors': run.get('errors')})
    print(json.dumps({'seed': seeded, 'retrieval': 'lexical', 'runs': runs}, ensure_ascii=True, indent=2))
    if not runs or any((r['mode'] != 'multi-agent' and r['gate_status'] != 'ready_for_review') or r['errors'] or r['missing_fields'] for r in runs):
        raise SystemExit('Walkthrough did not pass; inspect reported results. Source mode requires the CSV and WHO; --synthetic uses bundled fictional fixtures.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true', help='Use bundled fictional fixtures and an isolated handoff-demo database.')
    main_cli(parser.parse_args().synthetic)
