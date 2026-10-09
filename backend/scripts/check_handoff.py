"""Check the clone's required handoff assets without a database or API call."""
from pathlib import Path
from install_reference_bundle import verified_files

ROOT = Path(__file__).resolve().parents[2]


def check(root=ROOT):
    required = [
        'backend/requirements.lock.txt', 'frontend/package-lock.json',
        'backend/.env.example', 'scripts/setup.ps1', 'scripts/demo.ps1',
        'configs/demo/rules.json', 'configs/research/rules.json',
        'data/synthetic/case-15-integrated-complete.json',
        'data/synthetic/case-16-integrated-followup.json',
        'data/demo_documents/synthetic_policy.md',
        'who_aware_antibiotic_book.pdf',
        'data/handoff/manifest.json', 'scripts/handoff.ps1',
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise ValueError('Missing required files: ' + ', '.join(missing))
    verified = verified_files(root / 'data/public_references/dailymed')
    if len(verified) != 20:
        raise ValueError('Expected 20 pinned DailyMed references')
    print('PASS: required files, WHO PDF, 20 DailyMed text/XML hashes.')
    print('Current cases: run install_handoff.py --verify-only for schema/hash checks.')
    print('Raw CSV, .env and previous runs remain separate from Git.')
    print('No database changes, network requests or model calls.')


if __name__ == '__main__':
    try:
        check()
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
