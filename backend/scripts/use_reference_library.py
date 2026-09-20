"""Move local microbiology demo cases to reference-library search, with revisions."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.repositories import SQLiteRepository
from app.adapters.case_adapter import normalize_case


def update(case):
    if case.get('provenance', {}).get('source_system') != 'local-microbiology-csv':
        return False
    if case.get('evidence_scope') == 'reference' and not case.get('policy_refs'):
        return False
    case.update(evidence_scope='reference', policy_refs=[])
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/runtime/prototype.db')
    args = parser.parse_args()
    if not args.db.is_file(): parser.error('Existing database required')
    repo = SQLiteRepository(args.db)
    changed = []
    try:
        for record in repo.list_cases():
            case = record['case']
            if update(case):
                normalized, warnings = normalize_case(case)
                result = repo.upsert_case(normalized.model_dump(mode='json'), case, warnings)
                changed.append({'case_id': case['case_id'], 'revision': result['revision']})
    finally:
        repo.close()
    path = ROOT / 'data/local/microbiology/cases.json'
    prepared = 0
    if path.is_file():
        cases = json.loads(path.read_text(encoding='utf-8'))
        prepared = sum(int(update(c)) for c in cases)
        if prepared: path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'changed': changed, 'prepared': prepared}, ensure_ascii=False))


if __name__ == '__main__': main()
