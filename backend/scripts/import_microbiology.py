"""Stream a local CSV, prepare mixed-origin scenarios, optionally install them."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.adapters.microbiology import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--policy-ref', required=True, help='Existing reference document ID or version')
    parser.add_argument('--out', type=Path, default=ROOT / 'data/local/microbiology')
    parser.add_argument('--per-site', type=int, default=4)
    parser.add_argument('--install', action='store_true', help='Add prepared cases to the configured local DB')
    args = parser.parse_args()
    if not 1 <= args.per_site <= 10:
        parser.error('--per-site must be between 1 and 10')
    if args.install:
        from app import main as api
        if args.policy_ref not in {v for d in api._documents().list_documents() if not d['is_synthetic'] for v in (d['doc_id'], d['document_version'], d['title'])}:
            raise SystemExit('Reference document not found. No files prepared or cases installed.')
    report = prepare(args.csv, args.out, args.policy_ref, args.per_site)
    if args.install:
        count = 0
        for case in json.loads((args.out / 'cases.json').read_text(encoding='utf-8')):
            if not api.repo.get_case(case['case_id']):
                api.import_case(api.ImportBody(payload=case))
                count += 1
        report['installed'] = count
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
