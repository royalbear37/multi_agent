import pytest
import sqlite3
from contextlib import contextmanager
from fastapi.testclient import TestClient
from app.rag.service import DocumentService, DocumentServiceError
from tests.test_rag import FakeEmbeddings


def test_delete_transaction_failure_restores_source_and_metadata(tmp_path, monkeypatch):
    service = DocumentService(tmp_path, retrieval_mode='lexical')
    doc = service.import_document('a.txt', b'kidney original', 'A', 'v1')
    path, _ = service.source(doc['doc_id'])
    original = service._connect
    @contextmanager
    def fail_commit():
        with original() as db:
            yield db
            raise sqlite3.OperationalError('simulated commit failure')
    with monkeypatch.context() as patch:
        patch.setattr(service, '_connect', fail_commit)
        with pytest.raises(sqlite3.OperationalError): service.delete_document(doc['doc_id'])
    assert path.read_bytes() == b'kidney original'
    assert service.detail(doc['doc_id'])['chunks']
    assert service.search('kidney')['evidence']


def test_delete_removes_source_fts_vectors_and_allows_reupload(tmp_path):
    service = DocumentService(tmp_path, embedding_provider=FakeEmbeddings())
    removed = service.import_document('a.txt', b'kidney guidance A', 'A', 'v1')
    kept = service.import_document('b.txt', b'kidney guidance B', 'B', 'v1')
    service.reindex()
    path, _ = service.source(removed['doc_id'])
    snapshot = service.search('kidney', policy_refs=[removed['doc_id']])['evidence']
    service.delete_document(removed['doc_id'])
    assert not path.exists()
    assert [d['doc_id'] for d in service.list_documents()] == [kept['doc_id']]
    assert snapshot[0]['text'] == 'kidney guidance A'
    with service._connect() as db:
        assert db.execute('SELECT count(*) FROM chunks_fts WHERE doc_id=?', (removed['doc_id'],)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM chunk_embeddings WHERE chunk_id NOT IN (SELECT chunk_id FROM chunks)').fetchone()[0] == 0
    assert service.search('kidney', policy_refs=[removed['doc_id']])['evidence'] == []
    with pytest.raises(DocumentServiceError): service.delete_document(removed['doc_id'])
    uploaded = service.import_document('a.txt', b'kidney guidance A', 'A', 'v1')
    assert service.source(uploaded['doc_id'])[0].is_file()


def test_delete_rejects_source_outside_storage(tmp_path):
    service = DocumentService(tmp_path / 'docs', retrieval_mode='lexical')
    doc = service.import_document('a.txt', b'kidney', 'A', 'v1')
    outside = tmp_path / 'keep.txt'
    outside.write_text('keep')
    with service._connect() as db: db.execute('UPDATE documents SET source_path=? WHERE doc_id=?', (str(outside), doc['doc_id']))
    with pytest.raises(DocumentServiceError, match='文件路徑'): service.delete_document(doc['doc_id'])
    assert outside.read_text() == 'keep'
    assert service.detail(doc['doc_id'])


def test_delete_endpoint(tmp_path, monkeypatch):
    import app.main as main
    service = DocumentService(tmp_path, retrieval_mode='lexical')
    doc = service.import_document('a.txt', b'kidney', 'A', 'v1')
    monkeypatch.setattr(main, '_documents', lambda: service)
    client = TestClient(main.app)
    assert client.delete('/api/documents/' + doc['doc_id']).json()['deleted'] is True
    assert client.get('/api/documents/' + doc['doc_id']).status_code == 404
    assert client.delete('/api/documents/' + doc['doc_id']).status_code == 404


def test_library_reference_scope_ignores_synthetic_and_respects_pins(tmp_path):
    service = DocumentService(tmp_path, retrieval_mode='lexical')
    who = service.import_document('who.txt', b'kidney guidance', 'WHO', 'v1', False, population='adult')
    service.import_document('fixture.txt', b'kidney fake', 'Fixture', 'v1', True)
    assert [e['doc_id'] for e in service.search('kidney', policy_refs=[], scope='reference')['evidence']] == [who['doc_id']]
    assert service.search('kidney', policy_refs=['missing'], scope='reference')['evidence'] == []


def test_reference_library_is_not_a_missing_policy(monkeypatch):
    from tests.test_reported_cohort import case, Documents
    from app.workflow.engine import execute
    monkeypatch.delenv('PROTOTYPE_RULE_CONFIG', raising=False)
    value = case()
    value['policy_refs'] = []
    run = execute(value, 'rule-only', 'unconfigured', Documents())
    assert 'policy_refs' not in run['missing_fields']
    assert run['output']
