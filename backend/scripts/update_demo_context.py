"""Update imported hybrid demo context, preserving case revisions and source AST."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.adapters.microbiology import DEMO_CONTEXT
from app.adapters.case_adapter import normalize_case
from app.repositories import SQLiteRepository


def update(value):
    if (value.get('data_origin') != 'hybrid'
            or value.get('provenance', {}).get('source_system') != 'local-microbiology-csv'
            or 'encounter' not in value.get('provenance', {}).get('simulated_fields', [])):
        return False
    context = value.get('encounter', {}).get('context') or ''
    if not context.startswith('模擬情境：') or DEMO_CONTEXT in context:
        return False
    value['encounter']['context'] = context + DEMO_CONTEXT
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/runtime/prototype.db')
    parser.add_argument('--prepared', type=Path, default=ROOT / 'data/local/microbiology/cases.json')
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error('Existing database required')
    repo = SQLiteRepository(args.db)
    revised = []
    try:
        for record in repo.list_cases():
            value = record['case']
            if update(value):
                normalized, warnings = normalize_case(value)
                saved = repo.upsert_case(normalized.model_dump(mode='json'), value, warnings)
                revised.append({'case_id': value['case_id'], 'revision': saved['revision']})
    finally:
        repo.close()
    count = 0
    if args.prepared.is_file():
        values = json.loads(args.prepared.read_text(encoding='utf-8'))
        for value in values:
            count += int(update(value))
        if count:
            args.prepared.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'revised_cases': revised, 'prepared_updated': count}, ensure_ascii=False))


if __name__ == '__main__':
    main()
