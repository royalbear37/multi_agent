"""Verify the configured model using independently authored synthetic data.

No cohort rows are read. Run with --live to explicitly make three model calls.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Call the configured generation API (may incur fees)')
    parser.add_argument('--policy-ref', required=True)
    parser.add_argument('--modes', nargs='+', choices=['rule-only','rag-only','single-agent','multi-agent'], default=['rule-only','rag-only','single-agent','multi-agent'])
    parser.add_argument('--diagnose', action='store_true', help='Save model responses from this synthetic fixture locally for validation debugging')
    args = parser.parse_args()
    if not args.live:
        parser.error('Specify --live to run the generation verification')
    from app import main as api
    from app.providers.service import get_provider
    if not get_provider('live').status()['configured']:
        raise SystemExit('Generation model is not configured')
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
                    responses.append(response.get('choices', []))
                    (api.DB_PATH.parent / 'synthetic-live-responses.json').write_text(json.dumps(responses,ensure_ascii=False,indent=2),encoding='utf-8')
                    return response, retries
                provider._request = capture
            return provider
        service.get_provider = diagnostic_provider
    documents = api._documents()
    if args.policy_ref not in {v for d in documents.list_documents() if not d['is_synthetic'] for v in (d['doc_id'], d['document_version'])}:
        raise SystemExit('Reference document not found')
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
    summary = {'benchmark_id': result['benchmark_id'], 'case_id': case['case_id'], 'runs': [
        {k: run.get(k) for k in ('run_id','mode','gate_status','model','usage','errors','output')}
        for run in result['results']]}
    path = api.DB_PATH.parent / 'live-verification.json'
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if any(run.get('errors') for run in result['results']):
        raise SystemExit('One or more modes failed; inspect the saved verification report')


if __name__ == '__main__':
    main()
