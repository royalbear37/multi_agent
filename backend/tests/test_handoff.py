import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'backend/scripts/install_handoff.py'


def run_import(tmp_path, *args):
    env = {**os.environ, 'PROTOTYPE_DB_PATH':str(tmp_path/'prototype.db'),
           'PROTOTYPE_CATALOG_PATH':str(tmp_path/'catalog.json'), 'LLM_PROVIDER':'mock', 'RAG_RETRIEVAL_MODE':'lexical'}
    result = subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_verify_only_has_no_database_side_effect(tmp_path):
    result = run_import(tmp_path, '--verify-only')
    assert result == {'verified_cases':28,'revisions':95,'documents':24,'model_calls':0}
    assert not (tmp_path/'prototype.db').exists()
    assert not (tmp_path/'catalog.json').exists()


def test_clean_handoff_preserves_history_sources_and_existing_edits(tmp_path):
    result = run_import(tmp_path)
    assert len(result['imported_cases']) == 28
    with sqlite3.connect(tmp_path/'prototype.db') as db:
        assert db.execute('select count(*) from case_revisions').fetchone()[0] == 95
        record = json.loads(db.execute("select case_json from cases where case_id='agent-complete'").fetchone()[0])
        assert len(record['ast_results']) == 18
        assert not record['external_model_allowed'] and record['provenance']['source_record_id'] is None
        assert db.execute("select current_revision from cases where case_id='agent-complete'").fetchone()[0] == 4
        record['encounter']['context'] = 'Receiving workstation edit'
        db.execute("update cases set case_json=? where case_id='agent-complete'", (json.dumps(record),))
    result = run_import(tmp_path)
    assert not result['imported_cases'] and len(result['preserved_existing_cases']) == 28
    with sqlite3.connect(tmp_path/'prototype.db') as db:
        assert 'Receiving workstation edit' in db.execute("select case_json from cases where case_id='agent-complete'").fetchone()[0]
        assert db.execute('select count(*) from case_revisions').fetchone()[0] == 95
    with sqlite3.connect(tmp_path/'documents/rag.sqlite3') as db:
        assert db.execute('select count(*) from documents').fetchone()[0] == 24
        who = json.loads(db.execute("select metadata from documents where filename='who-lower-uti.md'").fetchone()[0])
        assert who['source_derivation']['original_hash']
    assert len(json.loads((tmp_path/'catalog.json').read_text(encoding='utf-8'))['antibiotics']) == 95


def test_handoff_cases_keep_hybrid_provenance_without_source_identity_or_permission():
    # No source linkage identifiers or portable external-model permission.
    for file in (ROOT/'data/handoff/cases').glob('*.json'):
        for revision in json.loads(file.read_text(encoding='utf-8')):
            case = revision['case']
            assert not case['external_model_allowed']
            assert case['provenance']['source_record_id'] is None
            assert case['data_origin'] == 'hybrid'
            assert case['provenance']['simulated_fields']
            assert all('anon_id' not in row.get('raw_measurement', {}) for row in case['ast_results'])


@pytest.mark.parametrize('field,stored,supplied', [('population','all','mixed'),('is_synthetic',True,False)])
def test_existing_document_conflict_is_reported_before_any_asset_import(tmp_path, monkeypatch, field, stored, supplied):
    from app import main
    from scripts.install_handoff import install

    class ExistingDocuments:
        def list_documents(self):
            return [{'content_hash':'who-hash','metadata':{field:stored},field:stored}]
        def import_document(self, *args, **kwargs):
            pytest.fail('Must preflight all documents before writing even the first one')

    monkeypatch.setattr(main, '_documents', lambda:ExistingDocuments())
    documents = [({'sha256':'new-hash','filename':'first.md'}, b'first'),
                 ({'sha256':'who-hash','filename':'WHO.pdf',field:supplied}, b'WHO')]
    with pytest.raises(ValueError, match='No handoff assets imported'):
        install((documents, [], {}), tmp_path/'catalog.json')
    assert not (tmp_path/'catalog.json').exists()
