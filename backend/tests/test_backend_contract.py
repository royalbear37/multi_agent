import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module
from app.repositories import SQLiteRepository
from app.schemas.case import Case


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Never let contract tests write the user's default runtime database."""
    database=SQLiteRepository(tmp_path / "contract.db")
    monkeypatch.setattr(main_module, "repo", database)
    monkeypatch.setattr(main_module, "DB_PATH", tmp_path / "contract.db")
    # Contract fixtures are offline and opt into the explicit lexical adapter.
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "lexical")
    monkeypatch.setattr(main_module, "_document_service_instance", None)
    yield
    database.close()


def test_schema_rejects_naive_and_non_synthetic():
    fixture=json.loads(next(Path(__file__).parents[2].glob("data/synthetic/case-01*.json")).read_text())
    fixture.pop("expected", None)
    Case.model_validate(fixture)
    fixture["created_at"]="2026-01-01T00:00:00"
    try: Case.model_validate(fixture)
    except Exception: pass
    else: raise AssertionError("naive timestamp accepted")
    fixture["created_at"]="2026-01-01T00:00:00+00:00"
    fixture["encounter"]={"observed_at":"2026-01-01T00:00:00"}
    try: Case.model_validate(fixture)
    except Exception: pass
    else: raise AssertionError("naive nested timestamp accepted")


def test_seed_is_idempotent():
    with TestClient(app) as client:
        first=client.post("/api/seed"); assert first.status_code == 200
        second=client.post("/api/seed"); assert second.json()["imported"] == 0
        rows=client.get("/api/cases").json()
        assert len(rows) >= 14 and {r["case_id"] for r in rows} >= {"case-01-complete","case-14-version-conflict"}


def test_import_field_error_and_alternate():
    with TestClient(app) as client:
        bad=client.post("/api/cases/import",json={"payload":{"case_id":"bad","is_synthetic":True,"created_at":"nope"}})
        assert bad.status_code == 422
        alt={"id":"alternate-1","synthetic":True,"observed_at":"2026-01-01T00:00:00+00:00","patient":{"age":32},"infection":{"site":"demo"},"lab":{"egfr":90,"egfr_unit":"demo"},"allergy":{"status":"unknown"}}
        result=client.post("/api/cases/import",json={"payload":alt,"format":"alternate"})
        assert result.status_code == 200 and result.json()["case_id"] == "alternate-1"


def test_review_rejects_prescription_fields():
    with TestClient(app) as client:
        client.post("/api/seed")
        run=client.post("/api/runs",json={"case_id":"case-01-complete","mode":"rule-only","provider_kind":"unconfigured"}).json()
        bad={"run_id":run["run_id"],"action":"modify","reason":"test","reviewer_id":"r1","role":"research","proposed_output":{"candidates":[{"drug_code":"DEMO_DRUG_A","dose":"1"}]}}
        assert client.post("/api/reviews",json=bad).status_code == 422


def test_public_run_quarantines_baseline_payload():
    with TestClient(app) as client:
        client.post("/api/seed")
        run=client.post("/api/runs",json={"case_id":"case-01-complete","mode":"rag-only","provider_kind":"mock"}).json()
        assert "payload" not in (run.get("raw_baseline") or {})


def test_accept_uses_stored_output_and_modify_requires_replacement():
    with TestClient(app) as client:
        client.post("/api/seed")
        run=client.post("/api/runs",json={"case_id":"case-01-complete","mode":"rule-only","provider_kind":"unconfigured"}).json()
        accepted=client.post("/api/reviews",json={"run_id":run["run_id"],"action":"accept","reason":"stored output reviewed","reviewer_id":"r1","role":"physician","proposed_output":{"dose":"ignored"}})
        assert accepted.status_code == 200
        missing=client.post("/api/reviews",json={"run_id":run["run_id"],"action":"modify","reason":"replacement absent","reviewer_id":"r1","role":"physician"})
        assert missing.status_code == 422
        blank=client.post("/api/reviews",json={"run_id":run["run_id"],"action":"accept","reason":"   ","reviewer_id":"r1","role":"physician"})
        assert blank.status_code == 422
