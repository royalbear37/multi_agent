import runpy
from pathlib import Path

from app import main
from app.repositories import SQLiteRepository
from app.rag.service import DocumentService


def test_prepare_preserves_legacy_policy_and_reuses_successful_runs(tmp_path, monkeypatch, capsys):
    database = SQLiteRepository(tmp_path / 'demo.db')
    service = DocumentService(tmp_path / 'documents', retrieval_mode='lexical')
    monkeypatch.setattr(main, 'repo', database)
    monkeypatch.setattr(main, '_document_service_instance', service)
    monkeypatch.setenv('RAG_RETRIEVAL_MODE', 'lexical')
    monkeypatch.setenv('LLM_PROVIDER', 'mock')
    original = service.import_document('synthetic_policy.md', (main.ROOT / 'data/demo_documents/synthetic_policy.md').read_bytes(), 'synthetic_policy', 'demo-v1', True)
    try:
        script = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/prepare_demo.py'))
        script['main_cli']()
        first = database.list_runs()
        assert len(first) == 4
        assert all(r['gate_status'] == 'ready_for_review' and not r['errors'] and not r['missing_fields'] for r in first)
        assert all(r['output']['candidates'] and r['evidence_snapshots'] for r in first)
        script['main_cli']()
        assert {r['run_id'] for r in database.list_runs()} == {r['run_id'] for r in first}
        assert service.detail(original['doc_id'])['metadata']['policy_refs'] == []
    finally:
        database.close()
