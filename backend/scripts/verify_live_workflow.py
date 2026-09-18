"""Verify the configured model using independently authored synthetic data.

No cohort rows are read. Run with --live to explicitly make three model calls.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def verification_summary(result):
    """Keep errors and reference snapshots with each mode for later diagnosis."""
    runs = result.get('results', result.get('runs', []))
    if not isinstance(runs, list) or not runs or not all(isinstance(run, dict) for run in runs):
        raise ValueError('Expected a non-empty runs/results array in the verification report')
    return {
        'benchmark_id': result.get('benchmark_id'),
        'clinical_support': 'not_evaluated',
        'runs': [
            {**{key: run.get(key) for key in (
                'run_id', 'mode', 'gate_status', 'model', 'usage', 'errors', 'output',
                'missing_fields', 'evidence_snapshots')},
             'nodes': [node for node in run.get('nodes', []) if isinstance(node, dict) and
                       node.get('node_id') in {'evidence_retrieval', 'candidate_presentation'}]}
            for run in runs
        ],
    }


def verification_passed(summary):
    runs = summary.get('runs', [])
    if not runs:
        return False
    for run in runs:
        output = run.get('output')
        if run.get('errors') or run.get('gate_status') != 'ready_for_review' or not isinstance(output, dict):
            return False
        candidates, avoided = output.get('candidates'), output.get('avoid')
        if not isinstance(candidates, list) or not isinstance(avoided, list):
            return False
        codes = []
        for item in candidates + avoided:
            if not isinstance(item, dict) or not isinstance(item.get('drug_code'), str):
                return False
            codes.append(item['drug_code'])
        if len(codes) != len(set(codes)):
            return False
    return True


def inspection_summary(summary):
    """Print structural diagnostics without patient fields or raw model text."""
    results = []
    for run in summary['runs']:
        output = run.get('output') or {}
        candidates = {x.get('drug_code') for x in output.get('candidates', []) if isinstance(x, dict)}
        avoided = {x.get('drug_code') for x in output.get('avoid', []) if isinstance(x, dict)}
        references = run.get('evidence_snapshots')
        nodes = run.get('nodes') or []
        retrieval = next((node.get('output', {}) for node in nodes if node.get('node_id') == 'evidence_retrieval'), {})
        results.append({
            'run_id': run.get('run_id'), 'mode': run.get('mode'),
            'gate_status': run.get('gate_status'),
            'error_codes': [error.get('code') if isinstance(error, dict) else str(error) for error in (run.get('errors') or [])],
            'validation_errors': [item for error in (run.get('errors') or []) if isinstance(error, dict)
                                  for item in error.get('validation_errors', [])],
            'missing_fields': run.get('missing_fields'),
            'candidate_count': len(candidates), 'avoid_count': len(avoided),
            'candidate_avoid_overlap_count': len(candidates & avoided),
            'reference_snapshots_available': isinstance(references, list),
            'reference_count': len(references) if isinstance(references, list) else None,
            'population_filter': retrieval.get('population_filter'),
        })
    return {'benchmark_id': summary.get('benchmark_id'), 'software_checks_passed': verification_passed(summary),
            'clinical_support': 'not_evaluated', 'runs': results}


def save_verification(directory, summary):
    path = directory / 'verification.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--live', action='store_true', help='Call the configured generation API (may incur fees)')
    action.add_argument('--inspect', type=Path, help='Read an existing verification or benchmark JSON offline; no model calls')
    parser.add_argument('--policy-ref')
    parser.add_argument('--modes', nargs='+', choices=['rule-only','rag-only','single-agent','multi-agent'], default=['rule-only','rag-only','single-agent','multi-agent'])
    parser.add_argument('--diagnose', action='store_true', help='Save model responses from this synthetic fixture locally for validation debugging')
    args = parser.parse_args()
    if args.inspect:
        try:
            summary = verification_summary(json.loads(args.inspect.read_text(encoding='utf-8-sig')))
        except (OSError, ValueError) as exc:
            parser.error('Cannot inspect verification report: ' + str(exc))
        print(json.dumps(inspection_summary(summary), ensure_ascii=True, indent=2))
        return
    if not args.policy_ref:
        parser.error('--policy-ref is required with --live')
    from app import main as api
    from app.providers.service import get_provider
    if not get_provider('live').status()['configured']:
        raise SystemExit('Generation model is not configured')
    documents = api._documents()
    if documents is None or args.policy_ref not in {v for d in documents.list_documents() if not d['is_synthetic'] for v in (d['doc_id'], d['document_version'])}:
        raise SystemExit('Reference document not found')
    directory = api.DB_PATH.parent / 'live-verifications' / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    if args.diagnose:
        from app.providers import service
        original_factory = service.get_provider
        responses = []
        def diagnostic_provider(kind):
            provider = original_factory(kind)
            if kind == 'live':
                request = provider._request
                def capture(payload):
                    response, retries = request(payload)
                    prompt = json.loads(payload['messages'][1]['content'])
                    responses.append({'mode': prompt.get('mode'), 'choices': response.get('choices', [])})
                    with (directory / f'response-{len(responses):03d}.json').open('x', encoding='utf-8') as stream:
                        json.dump(responses[-1], stream, ensure_ascii=False, indent=2)
                    return response, retries
                provider._request = capture
            return provider
        service.get_provider = diagnostic_provider
    now = datetime.now(timezone.utc).isoformat()
    case = {
        'case_id': 'synthetic-realnames-live-validation', 'created_at': now,
        'is_synthetic': True, 'data_origin': 'synthetic', 'evidence_scope': 'reference',
        'source': '獨立編寫的軟體驗證病例；所有觀測值皆合成，未取用 CSV 病人列。',
        'demographics': {'age': 38, 'sex': 'female', 'weight': 62, 'weight_unit': 'kg'},
        'encounter': {'infection_site': 'urinary tract infection', 'severity': 'stable',
                      'context': '合成情境：排尿疼痛與頻尿，無發燒或側腰痛；非妊娠，無導尿管。'},
        'renal': {'egfr': 95, 'unit': 'mL/min/1.73m2', 'dialysis_status': 'none'},
        'allergies': {'status': 'known_none', 'items': []},
        'microbiology': {'organism': 'ESCHERICHIA COLI', 'specimen': 'URINE', 'report_status': 'final'},
        'ast_results': [
            {'drug_code': drug, 'reported_sir': sir, 'source_phenotype': label,
             'interpretation_basis': 'source_report', 'source': 'independently authored synthetic observation'}
            for drug, sir, label in [('nitrofurantoin','S','Susceptible'), ('ampicillin','R','Resistant')]
        ],
        'policy_refs': [args.policy_ref],
        'provenance': {'source_system': 'independent-software-fixture',
                       'simulated_fields': ['demographics','encounter','renal','allergies','microbiology','ast_results']},
    }
    api.import_case(api.ImportBody(payload=case))
    result = api.benchmark(api.BenchmarkBody(case_ids=[case['case_id']],
                           modes=args.modes, provider_kind='live'))
    summary = verification_summary(result)
    path = save_verification(directory, summary)
    print(json.dumps({'report_path': str(path), **inspection_summary(summary)}, ensure_ascii=True, indent=2))
    if not verification_passed(summary):
        raise SystemExit('One or more modes failed or withheld output; inspect the saved verification report')


if __name__ == '__main__':
    main()
