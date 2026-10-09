"""Restore the reviewed handoff cases and reference corpus without model calls.

Existing cases are preserved. Use a fresh DB to reproduce the supplied revisions.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def read_asset(root, item):
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Asset outside repository')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('Hash mismatch: ' + item['path'])
    return raw


def verify(root=ROOT):
    from app.schemas.case import Case
    manifest = json.loads((root / 'data/handoff/manifest.json').read_text(encoding='utf-8'))
    documents = [(item, read_asset(root, item)) for item in manifest['documents']]
    cases = []
    for item in manifest['cases']:
        history = json.loads(read_asset(root, item))
        if [r['revision'] for r in history] != list(range(1, item['revision'] + 1)):
            raise ValueError('Non-contiguous revisions: ' + item['case_id'])
        for revision in history:
            case = Case.model_validate(revision['case'])
            if case.case_id != item['case_id'] or case.external_model_allowed or case.provenance.source_record_id:
                raise ValueError('Case identity/permission check failed: ' + item['case_id'])
        cases.append((item, history))
    catalog = json.loads(read_asset(root, manifest['catalog']))
    # Verify the WHO excerpt against the supplied original before registering lineage.
    from scripts.link_who_source import extraction_comparison_text
    from scripts.prepare_agent_references import extract_who_lower_uti
    excerpt = next(raw for item, raw in documents if item['filename'] == 'who-lower-uti.md')
    original = next(item for item, raw in documents if item['filename'] == 'who_aware_antibiotic_book.pdf')
    if extraction_comparison_text(excerpt.decode('utf-8')) != extraction_comparison_text(extract_who_lower_uti(root / original['path'])):
        raise ValueError('WHO excerpt does not match original PDF')
    return documents, cases, catalog


def install(verified, catalog_path):
    from app import main
    documents, cases, catalog = verified
    if catalog_path.exists() and json.loads(catalog_path.read_text(encoding='utf-8')) != catalog:
        raise ValueError('Existing catalog differs; choose a new PROTOTYPE_CATALOG_PATH. Nothing overwritten.')
    service = main._documents()
    existing = {item['content_hash']:item for item in service.list_documents()}
    # Check every collision before any import; never change a user's labels silently.
    for item, _ in documents:
        previous = existing.get(item['sha256'])
        if previous:
            metadata = previous.get('metadata', {})
            comparable = {**metadata, 'is_synthetic':previous.get('is_synthetic'),
                          'title':previous.get('title'), 'version':previous.get('document_version')}
            defaults = {'population':'unspecified','document_kind':'reference','study_design':'not_recorded',
                        'policy_refs':[], 'source_url':None, 'jurisdiction':None,
                        'is_synthetic':None, 'title':None, 'version':None}
            for field, default in defaults.items():
                if field in item and item[field] != comparable.get(field, default):
                    raise ValueError('Existing document metadata differs (' + item['filename'] + ': ' + field +
                                     '). No handoff assets imported. Review its label in the document library, or set PROTOTYPE_DB_PATH to a fresh database before retrying.')
    mapping = {}
    for item, raw in documents:
        options = {k:item[k] for k in ('policy_refs','population','source_url','jurisdiction','document_kind','study_design') if k in item}
        result = service.import_document(item['filename'], raw, item['title'], item['version'], item['is_synthetic'], **options)
        mapping[item['original_doc_id']] = result['doc_id']
    for item, _ in documents:
        if item.get('source_derivation'):
            derivation = item['source_derivation']
            service.register_source_derivation(mapping[item['original_doc_id']], derivation['original_hash'], item['sha256'], derivation['reason'])
    imported, skipped = [], []
    for item, history in cases:
        if main.repo.get_case(item['case_id']):
            skipped.append(item['case_id'])
            continue
        for revision in history:
            payload = copy.deepcopy(revision['case'])
            payload['policy_refs'] = [mapping.get(ref, ref) for ref in payload.get('policy_refs', [])]
            main.import_case(main.ImportBody(payload=payload))
        imported.append(item['case_id'])
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    if not catalog_path.exists():
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report = {'imported_cases': imported, 'preserved_existing_cases': skipped, 'documents':len(documents),
              'document_id_mapping':mapping, 'model_calls':0, 'vector_index':'not built; rebuild reference index for embedding mode'}
    (main.DB_PATH.parent / 'handoff-install.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    verified = verify()
    if args.verify_only:
        print(json.dumps({'verified_cases':len(verified[1]),'revisions':sum(len(h) for _,h in verified[1]),'documents':len(verified[0]),'model_calls':0}))
    else:
        # Load .env before resolving the same catalog setting used by RuleEngine.
        from app import main
        path = Path(os.getenv('PROTOTYPE_CATALOG_PATH', str(ROOT / 'data/local/microbiology/catalog.json')))
        print(json.dumps(install(verified, path), ensure_ascii=True, indent=2))
