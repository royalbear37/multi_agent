import runpy
import copy
import pytest
from pathlib import Path

from app import main
from app.repositories import SQLiteRepository
from app.rag.service import DocumentService
from tests.test_reported_cohort import case


def test_prepare_source_cases_preserves_reference_and_retries_failed_runs(tmp_path, monkeypatch, capsys):
    database = SQLiteRepository(tmp_path / 'demo.db')
    service = DocumentService(tmp_path / 'documents', retrieval_mode='lexical')
    monkeypatch.setattr(main, 'repo', database)
    monkeypatch.setattr(main, '_document_service_instance', service)
    monkeypatch.setattr(main, 'seed', lambda: {'imported': 0})
    monkeypatch.setenv('RAG_RETRIEVAL_MODE', 'lexical')
    monkeypatch.setenv('LLM_PROVIDER', 'mock')
    for index in range(2):
        payload = copy.deepcopy(case()); payload['case_id'] = f'cohort-test-{index}'
        main.import_case(main.ImportBody(payload=payload))
    try:
        script = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/prepare_demo.py'))
        with pytest.raises(SystemExit):
            script['main_cli']()
        failed_ids = {r['run_id'] for r in database.list_runs()}
        assert len(failed_ids) == 4
        original = service.import_document('reference.md', b'ESCHERICHIA COLI urinary tract infection reference fixture; not clinical guidance.', 'Reference fixture', 'who-v1', False)
        script['main_cli']()
        first = [r for r in database.list_runs() if r['run_id'] not in failed_ids]
        assert len(first) == 4
        assert all(r['gate_status'] == 'ready_for_review' and not r['errors'] and not r['missing_fields'] for r in first)
        assert all(r['output']['candidates'] and r['evidence_snapshots'] for r in first)
        script['main_cli']()
        assert len(database.list_runs()) == 12
        assert service.detail(original['doc_id'])['metadata']['policy_refs'] == []
    finally:
        database.close()
