"""Per-request retrieval deadline, no cold indexing during a paid agent run."""
from app.rag import service as rag
from tests.test_rag import FakeEmbeddings


def test_agent_cold_index_is_actionable_and_other_search_keeps_lazy_indexing(tmp_path,monkeypatch):
    monkeypatch.setattr(rag.time,'perf_counter',lambda:0)
    provider=FakeEmbeddings()
    service=rag.DocumentService(tmp_path,embedding_provider=provider,retrieval_mode='embedding')
    service.import_document('source.txt',b'renal risk passage','Reference','1')
    result=service.search_agent_context('renal',scope='synthetic',deadline=20)
    assert result['status']=='index_required' and result['warnings']==['agent_index_not_ready']
    assert provider.calls==[]
    assert service.search('renal')['status']=='ok'
    assert len(provider.calls)==2
    result=service.search_agent_context('renal',scope='synthetic',deadline=20)
    assert result['status']=='ok' and len(provider.calls)==3


def test_query_timeout_is_request_local_and_late_results_are_discarded(tmp_path,monkeypatch):
    clock=[0.0];calls=[];delay=[0]
    monkeypatch.setattr(rag.time,'perf_counter',lambda:clock[0])
    def embed(self,inputs):
        calls.append(self.timeout);clock[0]+=delay[0]
        return [[1.0,0.0] for _ in inputs]
    monkeypatch.setattr(rag.OllamaEmbeddingProvider,'embed',embed)
    provider=rag.OllamaEmbeddingProvider(timeout=30)
    service=rag.DocumentService(tmp_path,embedding_provider=provider,retrieval_mode='embedding')
    service.import_document('source.txt',b'renal risk passage','Reference','1')
    assert service.reindex()['status']=='ok'
    delay[0]=3
    result=service.search_agent_context('renal',scope='synthetic',deadline=2)
    assert calls[-1]==2 and provider.timeout==30
    assert result['status']=='budget_reserved' and result['evidence']==[]
    count=len(calls)
    assert service.search_agent_context('renal',scope='synthetic',deadline=2)['status']=='budget_reserved'
    assert len(calls)==count
