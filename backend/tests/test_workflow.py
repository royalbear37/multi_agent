from app.workflow.benchmark import summarize
from app.workflow.engine import execute, validate_review
from app.workflow.safety import validate_provider_output


class DocStub:
    def search(self, query, policy_refs=None):
        return {"status": "ok", "warnings": [], "evidence": [{"chunk_id": "demo_chunk", "doc_id": "demo_doc", "document_version": "1", "text": "synthetic evidence", "location": {"page": 1}}]}


def case(**overrides):
    value = {
        "case_id": "SYNTH_CASE_001",
        "schema_version": "1.0",
        "is_synthetic": True,
        "encounter": {"infection_site": "DEMO_SITE", "severity": "demo"},
        "renal": {"egfr": 90, "unit": "mL/min/1.73m2"},
        "policy_refs": ["demo-policy-v1"],
        "allergies": {"status": "known_none", "items": []},
        "microbiology": {"organism": "DEMO_ORGANISM_A"},
        "ast_results": [{"drug_code": "DEMO_DRUG_A", "standard": "DEMO", "standard_version": "1", "reported_sir": "S", "mic": 1, "comparator": "=", "unit": "demo-unit"}],
        "resistance_context_ref": ["demo-resistance-v1"],
    }
    value.update(overrides)
    return value


def test_workflow_has_eight_nodes_and_is_deterministic_without_model():
    run = execute(case(), "rule-only", document_service=DocStub())
    assert [node["node_id"] for node in run["nodes"]] == [
        "case_completeness", "ast", "resistance_context", "rapid_identification",
        "evidence_retrieval", "safety_gate", "candidate_presentation", "human_review",
    ]
    assert run["status"] == "awaiting_review"
    assert run["output"]["demo_only"] is True
    assert all("dose" not in str(item).lower() for item in run["output"]["candidates"])


def test_unknown_allergy_and_missing_ast_require_confirmation():
    run = execute(case(allergies={"status": "unknown", "items": []}, ast_results=[]), "rule-only")
    assert run["gate_status"] == "needs_confirmation"
    assert "allergies.status" in run["missing_fields"]
    assert "ast_results" in run["missing_fields"]


def test_hard_demo_restriction_blocks_candidates():
    run = execute(case(allergies={"status": "known_present", "items": [{"drug_code": "DEMO_DRUG_A", "reaction": "demo", "severity": "severe"}]}), "rule-only")
    assert run["gate_status"] == "blocked"
    assert run["output"] is None
    assert any(x["rule_id"] == "DEMO_ALLERGY_A" and x["status"] == "matched" for x in run["rule_evaluations"])


def test_unconfigured_provider_is_partial_and_all_modes_are_distinct():
    runs = [execute(case(), mode, "unconfigured", DocStub()) for mode in ("rule-only", "rag-only", "single-agent", "multi-agent")]
    assert runs[0]["status"] == "awaiting_review"
    assert all(run["status"] == "partial" for run in runs[1:])
    assert {run["mode"] for run in runs} == {"rule-only", "rag-only", "single-agent", "multi-agent"}


def test_provider_output_rejects_free_text_dose_and_unknown_codes():
    output, errors = validate_provider_output(
        {"candidates": [{"drug_code": "DEMO_DRUG_X", "reason": "dose 5 mg", "rule_refs": [], "evidence_refs": []}], "avoid": [], "limitations": []},
        allowed_drugs={"DEMO_DRUG_A"}, allowed_rules=set(), allowed_evidence=set(),
    )
    assert output is None
    assert "drug_not_allowed" in errors
    assert "forbidden_or_missing_reason" in errors


def test_review_cannot_move_avoided_drug_to_candidate():
    run = execute(case(allergies={"status": "known_present", "items": [{"drug_code": "DEMO_DRUG_A"}]}), "rule-only")
    proposed = {"candidates": [{"drug_code": "DEMO_DRUG_A", "reason": "可考慮", "rule_refs": [], "evidence_refs": []}], "avoid": [], "limitations": []}
    try:
        validate_review(run, proposed)
    except ValueError as exc:
        assert "ready" in str(exc) or "avoided" in str(exc)
    else:
        raise AssertionError("unsafe review edit was accepted")


def test_review_uses_case_specific_allowlist():
    run = execute(case(), "rule-only", document_service=DocStub())
    proposed = {"candidates": [{"drug_code": "DEMO_DRUG_C", "reason": "可考慮", "rule_refs": ["DEMO_CANDIDATE_ALLOWLIST"], "evidence_refs": ["demo_chunk"]}], "avoid": [], "limitations": []}
    try:
        validate_review(run, proposed)
    except ValueError as exc:
        assert "drug_not_allowed" in str(exc)
    else:
        raise AssertionError("case-specific allowlist was bypassed")


def test_benchmark_reports_real_denominators_and_na_zero_denominator():
    runs = [execute(case(case_id="A"), "rule-only"), execute(case(case_id="B", ast_results=[]), "rule-only")]
    summary = summarize(runs, {"A": {"expected_block": False}, "B": {"missing_fields": ["ast_results"]}})
    assert summary["total_cases"] == 2
    assert summary["expected_safety_block_recall"]["value"] is None
    assert summary["expected_safety_block_recall"]["denominator"] == 0
    assert summary["missing_recall"]["denominator"] == 1
