from pathlib import Path
from io import BytesIO
import math

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.rag.service import DocumentService, DocumentServiceError, EmbeddingError, OllamaEmbeddingProvider


class FakeEmbeddings:
    provider = "fake"
    base_url = "offline://embeddings"
    prompt_version = "test-v1"

    def __init__(self, model="fake-model"):
        self.model = model
        self.calls = []

    def embed(self, inputs):
        self.calls.append(list(inputs))
        return [[1.0, 0.0] if ("kidney" in text.casefold() or "renal" in text.casefold()) else [0.0, 1.0] for text in inputs]


def test_reindex_recovers_changed_dimensions_and_preserves_old_on_failure(tmp_path):
    provider = FakeEmbeddings()
    service = DocumentService(tmp_path, embedding_provider=provider)
    service.import_document("a.txt", b"kidney", "A", "v1")
    assert service.reindex()["status"] == "ok"
    provider.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    assert service.search("renal")["status"] == "failed"
    assert service.reindex()["status"] == "ok"
    assert service.search("renal")["status"] == "ok"
    provider.embed = lambda texts: [[0.0, 0.0, 0.0] for _ in texts]
    assert service.reindex()["status"] == "failed"
    assert service.status()["index"]["embedded_chunks"] == 1
    provider.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    assert service.search("renal")["status"] == "ok"


class BrokenEmbeddings(FakeEmbeddings):
    def embed(self, inputs):
        raise EmbeddingError("embedding provider unavailable")


class InvalidEmbeddings(FakeEmbeddings):
    def embed(self, inputs):
        return [[math.nan, 0.0] for _ in inputs]


class FailSecondBatchEmbeddings(FakeEmbeddings):
    def embed(self, inputs):
        self.calls.append(list(inputs))
        if len(self.calls) > 1:
            raise EmbeddingError("embedding provider unavailable")
        return [[1.0, 0.0] for _ in inputs]


class NonUnitEmbeddings(FakeEmbeddings):
    def embed(self, inputs):
        self.calls.append(list(inputs))
        result = []
        for text in inputs:
            lowered = text.casefold()
            if lowered == "query":
                result.append([10.0, 0.0])
            elif "first" in lowered:
                result.append([1.0, 0.0])
            else:
                result.append([9.0, 9.0])
        return result


class MismatchedDimensions(FakeEmbeddings):
    def embed(self, inputs):
        self.calls.append(list(inputs))
        return [[1.0, 0.0] if text.casefold() == "query" else [1.0, 0.0, 0.0] for text in inputs]


def test_ollama_adapter_uses_embed_contract_and_embeddinggemma_tasks(monkeypatch):
    import httpx

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[3.0, 4.0]]}

    def post(url, *, json, timeout):
        calls.append((url, json, timeout))
        return Response()

    monkeypatch.setattr(httpx, "post", post)
    provider = OllamaEmbeddingProvider(model="embeddinggemma:latest")
    assert provider.embed_query("renal") == [[3.0, 4.0]]
    assert calls[0][0] == "http://127.0.0.1:11434/api/embed"
    assert calls[0][1] == {"model": "embeddinggemma:latest", "input": ["task: search result | query: renal"], "truncate": False}


def test_markdown_import_search_and_location(tmp_path: Path):
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    document = service.import_document(
        "fixture.md", b"# Section\nDEMO_DRUG_A may be considered in this fixture.\n", "Fixture", "demo-v1"
    )
    assert document["processing_status"] == "indexed"
    result = service.search("DEMO_DRUG_A")
    assert result["status"] == "ok"
    assert result["evidence"][0]["doc_id"] == document["doc_id"]
    assert result["evidence"][0]["location"]["heading_path"] == ["Section"]


def test_hash_deduplicates_and_versions_are_immutable(tmp_path: Path):
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    first = service.import_document("a.txt", b"same", "A", "v1")
    duplicate = service.import_document("different.txt", b"same", "Different", "v9")
    assert duplicate["doc_id"] == first["doc_id"]
    assert duplicate["deduplicated"] is True
    second = service.import_document("b.txt", b"new text", "A", "v2")
    assert second["doc_id"] != first["doc_id"]
    assert {d["document_version"] for d in service.list_documents()} == {"v1", "v2"}


def test_same_title_versions_are_blocked_until_pinned(tmp_path: Path):
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    service.import_document("v1.md", b"policy DEMO_DRUG_A first", "Policy", "v1")
    service.import_document("v2.md", b"policy DEMO_DRUG_A revised", "Policy", "v2")
    result = service.search("policy")
    assert result["status"] == "conflict"
    assert result["evidence"] == []
    pinned = service.search("policy", policy_refs=["v1"])
    assert pinned["status"] == "ok"
    assert {item["document_version"] for item in pinned["evidence"]} == {"v1"}

    ambiguous = service.search("policy", policy_refs=["Policy"])
    assert ambiguous["status"] == "conflict"
    assert ambiguous["evidence"] == []


def test_non_synthetic_is_never_searchable_and_policy_filter(tmp_path: Path):
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    service.import_document("private.txt", b"secret term", "Private", "v1", is_synthetic=False)
    assert service.search("secret term")["status"] == "no_documents"
    doc = service.import_document("policy.txt", b"policy term", "Policy", "v1", policy_refs=["P1"])
    assert service.search("policy", policy_refs=["P2"])["status"] == "no_results"
    assert service.search("policy", policy_refs=["P1"])["evidence"][0]["doc_id"] == doc["doc_id"]


def test_reference_scope_searches_only_non_synthetic_documents(tmp_path: Path):
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    reference = service.import_document("who.txt", b"secret term from WHO", "WHO", "2024", is_synthetic=False)
    service.import_document("demo.txt", b"secret term from demo", "Demo", "v1", is_synthetic=True)

    default_result = service.search("secret term")
    assert default_result["scope"] == "synthetic"
    assert default_result["evidence"]
    assert all(item["doc_id"] != reference["doc_id"] for item in default_result["evidence"])
    reference_result = service.search("secret term", scope="reference")
    assert reference_result["status"] == "ok"
    assert reference_result["scope"] == "reference"
    assert {item["doc_id"] for item in reference_result["evidence"]} == {reference["doc_id"]}


def test_reference_scope_reindex_isolated_from_synthetic_index(tmp_path: Path):
    provider = FakeEmbeddings()
    service = DocumentService(tmp_path, embedding_provider=provider)
    reference = service.import_document("who.txt", b"kidney reference", "WHO", "2024", is_synthetic=False)
    synthetic = service.import_document("demo.txt", b"kidney demo", "Demo", "v1", is_synthetic=True)

    result = service.reindex(scope="reference")
    assert result["status"] == "ok"
    assert result["scope"] == "reference"
    assert result["count"] == 1
    assert service.status(scope="reference")["index"]["embedded_chunks"] == 1
    assert service.status(scope="synthetic")["index"]["embedded_chunks"] == 0
    embedded_inputs = [text for call in provider.calls for text in call]
    assert "kidney reference" in embedded_inputs
    assert "kidney demo" not in embedded_inputs
    assert service.search("renal", scope="reference")["evidence"][0]["doc_id"] == reference["doc_id"]
    default_result = service.search("renal")
    assert all(item["doc_id"] != reference["doc_id"] for item in default_result["evidence"])
    assert synthetic["doc_id"] != reference["doc_id"]


def test_path_boundary_and_unknown_source(tmp_path: Path):
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    with pytest.raises(DocumentServiceError) as exc:
        service.import_document("../escape.txt", b"x", "x", "v1")
    assert exc.value.code == "INVALID_FILENAME"
    with pytest.raises(DocumentServiceError) as exc:
        service.detail("missing")
    assert exc.value.code == "DOCUMENT_NOT_FOUND"


def test_pdf_import_keeps_page_locations_or_reports_parse_state(tmp_path: Path):
    # A malformed PDF must be retained as a parse failure with a safe warning,
    # rather than crashing the API or fabricating evidence.
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    doc = service.import_document("broken.pdf", b"not a pdf", "Broken", "v1")
    assert doc["processing_status"] in {"parse_failed", "needs_ocr"}
    assert doc["chunk_count"] == 0


def test_valid_pdf_extracts_real_text_and_page_location(tmp_path: Path):
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 200 Td (DEMO_DRUG_A policy) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    doc = DocumentService(tmp_path, retrieval_mode="lexical").import_document("valid.pdf", output.getvalue(), "PDF Fixture", "v1")
    assert doc["processing_status"] == "indexed"
    result = DocumentService(tmp_path, retrieval_mode="lexical").search("DEMO_DRUG_A")
    assert result["evidence"][0]["location"]["page"] == 1
    source_path, mime = DocumentService(tmp_path, retrieval_mode="lexical").source(doc["doc_id"])
    assert mime == "application/pdf"
    assert source_path.read_bytes() == output.getvalue()


def test_blank_scanned_pdf_is_marked_for_ocr_and_not_indexed(tmp_path: Path):
    writer = PdfWriter()
    writer.add_blank_page(300, 300)
    output = BytesIO()
    writer.write(output)
    doc = DocumentService(tmp_path, retrieval_mode="lexical").import_document("scan.pdf", output.getvalue(), "Scan Fixture", "v1")
    assert doc["processing_status"] == "needs_ocr"
    assert "scanned_pdf_requires_ocr" in doc["processing_warnings"]
    assert doc["chunk_count"] == 0


def test_pdf_table_page_is_excluded_until_review(tmp_path: Path):
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 200 Td (|DEMO_DRUG_A|status|) Tj T* (|x|y|) Tj T* (|z|w|) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    service = DocumentService(tmp_path, retrieval_mode="lexical")
    doc = service.import_document("table.pdf", output.getvalue(), "Table Fixture", "v1")
    assert doc["processing_status"] == "needs_review"
    assert "page_1_table_needs_review" in doc["processing_warnings"]
    assert service.search("DEMO_DRUG_A")["status"] == "no_results"


def test_embedding_retrieval_finds_semantic_match_and_persists(tmp_path: Path):
    provider = FakeEmbeddings()
    service = DocumentService(tmp_path, embedding_provider=provider)
    doc = service.import_document("semantic.txt", b"The patient has kidney dysfunction.", "Semantic", "v1")
    service.import_document("other.txt", b"The culture grew an unrelated organism.", "Other", "v1")
    result = service.search("renal complications", limit=1)
    assert result["status"] == "ok"
    assert result["evidence"][0]["doc_id"] == doc["doc_id"]
    assert result["evidence"][0]["score"] == 1.0
    assert service.status()["index"]["embedded_chunks"] == 2

    reopened = DocumentService(tmp_path, embedding_provider=FakeEmbeddings())
    assert reopened.search("renal complications", limit=1)["status"] == "ok"
    assert len(reopened.embedding_provider.calls) == 1  # query only; chunk vectors were persisted


def test_embedding_search_ranks_by_cosine_after_normalization(tmp_path: Path):
    service = DocumentService(tmp_path, embedding_provider=NonUnitEmbeddings())
    first = service.import_document("first.txt", b"first", "First", "v1")
    service.import_document("second.txt", b"second", "Second", "v1")
    result = service.search("query", limit=1)
    assert result["status"] == "ok"
    assert result["evidence"][0]["doc_id"] == first["doc_id"]


def test_embedding_dimension_mismatch_returns_no_evidence_and_does_not_index(tmp_path: Path):
    provider = MismatchedDimensions()
    service = DocumentService(tmp_path, embedding_provider=provider)
    service.import_document("a.txt", b"kidney finding", "Policy", "v1")
    result = service.search("query")
    assert result["status"] == "failed"
    assert result["evidence"] == []
    assert "embedding_dimension_mismatch" in result["warnings"]
    assert service.status()["index"]["embedded_chunks"] == 0


def test_embedding_index_excludes_non_synthetic_documents(tmp_path: Path):
    provider = FakeEmbeddings()
    service = DocumentService(tmp_path, embedding_provider=provider)
    service.import_document("private.txt", b"kidney private", "Private", "v1", is_synthetic=False)
    service.import_document("public.txt", b"kidney public", "Public", "v1")
    assert service.reindex()["status"] == "ok"
    embedded_inputs = [text for call in provider.calls for text in call]
    assert "kidney private" not in embedded_inputs
    assert "kidney public" in embedded_inputs


def test_embedding_model_switch_creates_new_fingerprint(tmp_path: Path):
    first = DocumentService(tmp_path, embedding_provider=FakeEmbeddings("model-a"))
    first.import_document("a.txt", b"kidney finding", "Policy", "v1")
    first.search("renal")
    second = DocumentService(tmp_path, embedding_provider=FakeEmbeddings("model-b"))
    result = second.search("renal")
    assert result["status"] == "ok"
    assert second.status()["index"]["embedded_chunks"] == 1
    with second._connect() as db:
        assert db.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[0] == 2


def test_embedding_failure_returns_no_evidence(tmp_path: Path):
    service = DocumentService(tmp_path, embedding_provider=BrokenEmbeddings())
    service.import_document("a.txt", b"kidney finding", "Policy", "v1")
    result = service.search("renal")
    assert result["status"] == "failed"
    assert result["evidence"] == []
    assert "embedding_unavailable" in result["warnings"]


def test_invalid_embedding_vectors_are_rejected(tmp_path: Path):
    service = DocumentService(tmp_path, embedding_provider=InvalidEmbeddings())
    service.import_document("a.txt", b"kidney finding", "Policy", "v1")
    result = service.search("renal")
    assert result["status"] == "failed"
    assert result["evidence"] == []
    assert "embedding_invalid_vector" in result["warnings"]


def test_embedding_policy_filter_and_limit_one_version_guard(tmp_path: Path):
    service = DocumentService(tmp_path, embedding_provider=FakeEmbeddings())
    service.import_document("v1.txt", b"kidney guidance", "Policy", "v1", policy_refs=["P1"])
    service.import_document("v2.txt", b"kidney guidance revised", "Policy", "v2", policy_refs=["P2"])
    assert service.search("renal", limit=1)["status"] == "conflict"
    pinned = service.search("renal", limit=1, policy_refs=["P1"])
    assert pinned["status"] == "ok"
    assert pinned["evidence"][0]["document_version"] == "v1"
    assert service.search("renal", policy_refs=["missing"])["evidence"] == []


def test_reindex_rolls_back_partial_batch_on_provider_failure(tmp_path: Path):
    provider = FailSecondBatchEmbeddings()
    service = DocumentService(tmp_path, embedding_provider=provider)
    content = "\n".join(f"# Section {number}\nkidney guidance {number}" for number in range(33)).encode()
    service.import_document("many.md", content, "Many", "v1")
    result = service.reindex()
    assert result["status"] == "failed"
    assert result["count"] == 0
    assert service.status()["index"]["embedded_chunks"] == 0
