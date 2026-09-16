"""End-to-end checks for the complete synthetic interaction fixtures."""

import json
from pathlib import Path

from app.rag.service import DocumentService
from app.schemas.case import Case
from app.workflow.engine import execute


ROOT = Path(__file__).resolve().parents[2]
CASE_IDS = ("case-15-integrated-complete", "case-16-integrated-followup")


class FlatMockEmbeddings:
    """Offline embedding double: stable vectors make retrieval deterministic."""

    provider = "synthetic-test"
    model = "synthetic-flat-v1"
    base_url = "offline://synthetic-embeddings"
    prompt_version = "synthetic-test-v1"

    def __init__(self):
        self.calls = []

    def embed(self, inputs):
        self.calls.append(list(inputs))
        return [[1.0, 0.0] for _ in inputs]


def _fixture(case_id: str) -> dict:
    return json.loads((ROOT / "data" / "synthetic" / f"{case_id}.json").read_text(encoding="utf-8"))


def test_complete_interactive_cases_run_with_mock_embedding_and_llm(tmp_path):
    embeddings = FlatMockEmbeddings()
    documents = DocumentService(tmp_path / "documents", embedding_provider=embeddings)
    policy = ROOT / "data" / "demo_documents" / "synthetic_policy.md"
    documents.import_document(
        policy.name,
        policy.read_bytes(),
        "synthetic_policy",
        "demo-v1",
        is_synthetic=True,
        policy_refs=["demo-policy-v1"],
    )

    for case_id in CASE_IDS:
        case = _fixture(case_id)
        Case.model_validate(case)
        run = execute(case, "multi-agent", "mock", documents, run_id=f"run-{case_id}")

        assert run["gate_status"] == "ready_for_review", (case_id, run)
        assert run["missing_fields"] == []
        assert run["errors"] == []
        assert run["evidence_snapshots"]
        assert run["output"]["candidates"]
        assert run["output"]["candidates"][0]["drug_code"] == "DEMO_DRUG_A"
        assert run["output"]["avoid"] == []
        assert run["nodes"][-2]["node_id"] == "candidate_presentation"
        assert run["nodes"][-2]["output"]["published"] is True
        assert run["nodes"][-2]["output"]["schema_valid"] is True
        assert run["nodes"][3]["status"] == "completed"  # rapid identification
        assert all(node["status"] in {"completed", "pending"} for node in run["nodes"])

    assert embeddings.calls  # both document and query vectors used
