"""Synthetic engineering fixtures only. These are NOT research/clinical Gold."""
import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.alignment import align
from app.evaluation.cli import main
from app.evaluation.evaluator import aggregate, evaluate_run
from app.evaluation.export import export_report
from app.evaluation.io import content_hash, load_gold, load_manifest, load_runs, parse_json
from app.evaluation.metrics import (ROLES, ROLE_FIELDS, citations, ratio, source_consistency,
                                    source_observations, token_statistics)
from app.evaluation.schemas import GoldRecord, Manifest


@pytest.fixture
def run():
    nodes = []
    for role in ROLES:
        output = {"findings": [], "issues": []}
        if role == "case_agent":
            output["missing_fields"] = []
        else:
            field, _, abstentions = ROLE_FIELDS[role]
            output["drugs"] = [{"drug_code": "toy_drug", field: next(iter(abstentions)), "reason": "SYNTHETIC FIXTURE"}]
        nodes.append({"node_id": role, "agent_id": role, "status": "completed", "input": {"drugs": ["toy_drug"]},
                      "output": output, "elapsed_ms": 2, "attempts": [{"usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}]})
    return {"run_id": "synthetic-run", "case_id": "synthetic-case", "case_revision": 1,
            "mode": "multi-agent", "status": "partial", "is_mock": True,
            "versions": {"workflow": "agent-led-1.6.0"},
            "case_snapshot": {"case_id": "synthetic-case", "ast_results": [
                {"drug_code": "toy_drug", "interpretation_basis": "CLSI_2022_pheno",
                 "clsi_2022_phenotype": "Susceptible", "reported_sir": "S"}]},
            "nodes": nodes, "drug_assessments": [{"drug_code": "toy_drug", "status": "pending"}],
            "evidence_snapshots": [{"chunk_id": "toy-chunk", "text": "SYNTHETIC evidence text", "location": {"line": 1}}],
            "output": {"candidates": [], "avoid": []}, "elapsed_ms": 20.0, "usage": None}


def identity(run):
    return Manifest.model_validate({"schema_version": "eval-manifest-0.1", "canonicalization": "json-sorted-utf8-v1", "cases": [{
        "case_id": run["case_id"], "revision": run["case_revision"], "case_snapshot_sha256": content_hash(run["case_snapshot"]),
        "source_case_group": "SYNTHETIC-GROUP", "grouping_basis": ["synthetic_fixture"],
        "grouping_sources": ["tests/evaluation/test_offline_evaluator.py"], "drug_universe": ["toy_drug"]}]})


def annotation(run):
    return {"schema_version": "eval-gold-0.1", "record_type": "case_drug", "record_id": "toy-gold",
            "case_id": run["case_id"], "revision": run["case_revision"], "case_snapshot_sha256": content_hash(run["case_snapshot"]),
            "source_case_group": "SYNTHETIC-GROUP", "drug_code": "toy_drug", "synthetic_fixture": True,
            "labels": {"selected_source_classification": {
                "accepted_labels": ["susceptible"], "review_status": "adjudicated", "ground_truth_tier": "A_source",
                "policy_version": "SYNTHETIC-ONLY-v1", "source_rows": [{"index": 0, "field": "clsi_2022_phenotype", "value": "Susceptible"}],
                "annotation_provenance": {"source_assets": ["SYNTHETIC FIXTURE"], "annotation_guideline_version": "toy-v1",
                    "annotator_id": "synthetic-test", "reviewer_ids": ["synthetic-test-review"], "origin": "synthetic_fixture"}}}}


def metric(rows, name, *, target=None, drug=None, agent=None):
    return next(r for r in rows if r["metric"] == name and (target is None or r["scoring_target"] == target)
                and (drug is None or r["drug_code"] == drug) and (agent is None or r["agent_id"] == agent))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("wrapper", ["single", "array", "benchmark"])
def test_load_run_formats(tmp_path, run, wrapper):
    data = run if wrapper == "single" else [run] if wrapper == "array" else {"results": [run]}
    p = write(tmp_path / "runs.json", data)
    loaded, assets, diagnostics = load_runs([p])
    assert loaded == [run] and len(assets[0]["sha256"]) == 64 and diagnostics == []


@pytest.mark.parametrize("field", ["run_id", "case_id", "case_revision", "case_snapshot", "nodes", "is_mock"])
def test_missing_required_envelope(tmp_path, run, field):
    del run[field]
    with pytest.raises(ValidationError):
        load_runs([write(tmp_path / "bad.json", run)])


@pytest.mark.parametrize("field,value", [("case_revision", "1"), ("case_revision", True), ("case_revision", 0), ("nodes", {}), ("case_snapshot", []), ("is_mock", "true")])
def test_strict_schema(tmp_path, run, field, value):
    run[field] = value
    with pytest.raises(ValidationError):
        load_runs([write(tmp_path / "bad.json", run)])


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{bad'])
def test_reject_ambiguous_json(text):
    with pytest.raises(ValueError):
        parse_json(text)


def test_deduplicate_and_conflicting_ids(tmp_path, run):
    p = write(tmp_path / "runs.json", [run, run])
    runs, _, diagnostics = load_runs([p])
    assert len(runs) == 1 and diagnostics[0]["code"] == "duplicate_identical_run"
    other = copy.deepcopy(run)
    other["status"] = "failed"
    with pytest.raises(ValueError, match="conflicting contents"):
        load_runs([write(p, [run, other])])


@pytest.mark.parametrize("change,expected", [("revision", "manifest_revision_mismatch"), ("hash", "case_snapshot_hash_mismatch"), ("case", "snapshot_case_id_mismatch")])
def test_identity_mismatch(run, change, expected):
    manifest = identity(run)
    if change == "revision": run["case_revision"] = 2
    elif change == "hash": run["case_snapshot"]["new"] = "changed"
    else: run["case_snapshot"]["case_id"] = "another-case"
    rows = evaluate_run(run, manifest=manifest)
    assert rows[0]["status"] == "alignment_error" and expected in rows[0]["details"]["errors"]


def test_group_and_gold_revision_alignment(run):
    gold = GoldRecord.model_validate(annotation(run))
    gold.source_case_group = "different-group"
    assert "gold_source_case_group_mismatch" in align(run, identity(run), [gold])[2]
    gold.revision = 2
    assert "gold_revision_mismatch" in align(run, identity(run), [gold])[2]


def test_unknown_lineage_not_inferred(run):
    rows = evaluate_run(run)
    assert rows[0]["reason"] == "source_case_group_unresolved_no_manifest"
    assert all(x["source_case_group"] is None for x in rows)


def test_source_consistency_actual_error_not_missing_gold(run):
    rows = evaluate_run(run, manifest=identity(run))
    result = metric(rows, "ast_source_consistency")
    assert result["status"] == "evaluated" and result["value"] == 0
    assert metric(rows, "ast_classification_accuracy")["status"] == "missing_gold"
    assert metric(rows, "candidate_precision")["value"] is None


def test_selected_source_not_reported_override(run):
    original = run["case_snapshot"]["ast_results"][0]
    duplicate = {**original, "reported_sir": "R"}
    run["case_snapshot"]["ast_results"].append(duplicate)
    observation = source_observations(run["case_snapshot"])["toy_drug"]
    assert observation["expected"] == "susceptible"
    assert observation["flags"] == {"selected_source_conflict": False, "reported_source_conflict": True, "cross_field_conflict": True}
    assert source_consistency(observation, "resistant")["status"] == "not_evaluated"
    assert metric(evaluate_run(run), "ast_conflict_detection_accuracy")["status"] == "missing_gold"


@pytest.mark.parametrize("basis,field,value,expected", [("CLSI_2022_pheno", "clsi_2022_phenotype", None, "unknown"),
    ("source_report", "source_phenotype", "Intermediate", "intermediate"), ("legacy", "reported_sir", "R", "resistant")])
def test_source_selection_no_mic_inference(basis, field, value, expected):
    source = source_observations({"ast_results": [{"drug_code": "d", "interpretation_basis": basis, field: value, "mic": 0.001}]})["d"]
    assert source_consistency(source, expected)["value"] == 1


def test_unknown_basis_is_not_default_legacy():
    source = source_observations({"ast_results": [{"drug_code": "d", "reported_sir": "S"}]})["d"]
    assert source_consistency(source, "susceptible")["reason"] == "unknown_interpretation_basis"


def test_gold_classification_and_fixture_guard(tmp_path, run):
    data = annotation(run)
    path = write(tmp_path / "gold.json", data)
    with pytest.raises(ValueError, match="synthetic_fixture"):
        load_gold([path])
    gold = load_gold([path], allow_synthetic=True)
    rows = evaluate_run(run, manifest=identity(run), gold=gold)
    assert metric(rows, "ast_classification_accuracy")["value"] == 0
    run["nodes"][1]["output"]["drugs"][0]["assessment"] = "susceptible"
    assert metric(evaluate_run(run, manifest=identity(run), gold=gold), "ast_classification_accuracy")["value"] == 1


@pytest.mark.parametrize("wrapper", ["array", "records", "jsonl"])
def test_gold_formats(tmp_path, run, wrapper):
    record = annotation(run)
    path = tmp_path / ("gold.jsonl" if wrapper == "jsonl" else "gold.json")
    if wrapper == "jsonl": path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    else: write(path, [record] if wrapper == "array" else {"records": [record]})
    assert len(load_gold([path], allow_synthetic=True)) == 1


def test_gold_cannot_be_model_audit(run):
    record = annotation(run)
    record["labels"]["selected_source_classification"]["annotation_provenance"]["origin"] = "model_audit"
    with pytest.raises(ValidationError): GoldRecord.model_validate(record)


def test_draft_gold_not_scored(run):
    data = annotation(run)
    data["labels"]["selected_source_classification"]["review_status"] = "draft"
    assert metric(evaluate_run(run, manifest=identity(run), gold=[GoldRecord.model_validate(data)]), "ast_classification_accuracy")["status"] == "missing_gold"


def test_zero_denominator():
    assert ratio(0, 0)["value"] is None and ratio(0, 0)["reason"] == "zero_denominator"


def test_empty_citations_not_perfect(run):
    rows = evaluate_run(run)
    for name in ["quote_exact_match", "citation_id_locatability"]:
        r = metric(rows, name, target="published_output")
        assert r["value"] is None and r["denominator"] == 0


def test_unverified_citation_mechanical_only(run):
    output = {"evidence_refs": ["toy-chunk", "absent"], "quotes": [{"chunk_id": "toy-chunk", "quote": "evidence text"}], "verdict": "supported"}
    results = citations(output, run["evidence_snapshots"])
    assert results["citation_id_locatability"]["value"] == pytest.approx(2 / 3)
    assert results["quote_exact_match"]["value"] == 1
    output["quotes"][0]["quote"] = "fabricated text"
    assert citations(output, run["evidence_snapshots"])["quote_exact_match"]["value"] == 0


@pytest.mark.parametrize("bad", [{"evidence_refs": "x"}, {"evidence_refs": [{}]}, {"quotes": [{"chunk_id": "x", "quote": ""}]}])
def test_malformed_citations_invalid(run, bad):
    assert citations(bad, run["evidence_snapshots"])["citation_id_locatability"]["status"] == "invalid_output"


@pytest.mark.parametrize("change", ["missing", "duplicate", "bad_label", "dict_label"])
def test_bad_final_rows_not_abstention(run, change):
    if change == "missing": run["drug_assessments"] = []
    elif change == "duplicate": run["drug_assessments"] *= 2
    else: run["drug_assessments"][0]["status"] = {} if change == "dict_label" else "imaginary"
    rows = evaluate_run(run)
    assert metric(rows, "pending_rate")["status"] == "invalid_output"


def test_six_nodes_and_missing_node(run):
    assert metric(evaluate_run(run), "agent_node_completeness")["value"] == 1
    run["nodes"].pop(0)
    rows = evaluate_run(run)
    assert metric(rows, "agent_node_completeness")["value"] == pytest.approx(5 / 6)
    assert metric(rows, "agent_output_completeness", agent="case_agent")["status"] == "invalid_output"


def test_failed_ast_retained_not_wrong_or_abstention(run):
    run["nodes"][1]["status"] = "failed"
    rows = evaluate_run(run)
    assert metric(rows, "ast_source_consistency")["reason"] == "ast_execution_not_completed"
    assert metric(rows, "agent_failed_count")["value"] == 1


def test_resource_no_double_count_partial_and_mock(run):
    assert token_statistics(run["nodes"], True)["total_tokens"]["status"] == "not_evaluated"
    assert token_statistics(run["nodes"], False)["total_tokens"]["value"] == 72
    run["nodes"][0]["usage"] = {"total_tokens": 9999}
    run["nodes"][0]["attempts"][0]["usage"] = None
    partial = token_statistics(run["nodes"], False)["total_tokens"]
    assert partial["status"] == "not_evaluated" and partial["details"]["known_subtotal"] == 60
    run["nodes"][0]["attempts"][0]["usage"] = {"total_tokens": -1}
    assert token_statistics(run["nodes"], False)["total_tokens"]["status"] == "invalid_output"


def test_multirun_strata_and_immutability(run):
    before = copy.deepcopy(run)
    live = copy.deepcopy(run)
    live.update(run_id="synthetic-live", is_mock=False)
    rows = evaluate_run(run) + evaluate_run(live)
    summary = [x for x in aggregate(rows) if x["metric"] == "pending_rate"]
    assert len(summary) == 2 and {x["is_mock"] for x in summary} == {True, False}
    assert run == before


def test_export_json_csv_consistency_refuses_overwrite(tmp_path, run):
    rows = evaluate_run(run)
    target = tmp_path / "report"
    export_report(target, rows, {"test": "synthetic_fixture"})
    report = json.loads((target / "report.json").read_text(encoding="utf-8"))
    with (target / "observations.csv").open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == len(report["observations"])
    for row, csv_row in zip(report["observations"], csv_rows):
        assert csv_row["metric"] == row["metric"] and csv_row["status"] == row["status"]
        assert (None if csv_row["value"] == "" else float(csv_row["value"])) == row["value"]
        assert json.loads(csv_row["details"]) == row["details"]
    with pytest.raises(FileExistsError): export_report(target, rows, {})


def test_cli_inputs_unchanged_and_no_network(tmp_path, run, monkeypatch):
    import socket
    def blocked(*args, **kwargs): raise AssertionError("network forbidden")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    p = write(tmp_path / "run.json", run)
    before = p.read_bytes()
    assert main(["--runs", str(p), "--out", str(tmp_path / "out")]) == 0
    assert p.read_bytes() == before
    assert main(["--runs", str(p), "--out", str(tmp_path / "out")]) == 2


def test_cli_alignment_failure_exit_one(tmp_path, run):
    data = identity(run).model_dump()
    data["cases"][0]["revision"] = 2
    p = write(tmp_path / "run.json", run)
    m = write(tmp_path / "manifest.json", data)
    assert main(["--runs", str(p), "--manifest", str(m), "--out", str(tmp_path / "out")]) == 1


def test_import_has_no_workflow_or_database_side_effects():
    code = "import sys; import app.evaluation.cli; assert not any(x.startswith(('app.main','app.workflow','app.agents','app.rag','app.db')) for x in sys.modules)"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_future_adapter_unknown_workflow(run):
    run["versions"]["workflow"] = "future-9"
    rows = evaluate_run(run)
    assert metric(rows, "agent_output_completeness")["status"] == "not_evaluated"
    assert metric(rows, "elapsed_ms", target="saved_run_timing")["value"] == 20


def test_manifest_duplicate_identity_and_empty_drug_code(run):
    data = identity(run).model_dump()
    data["cases"] *= 2
    with pytest.raises(ValidationError): Manifest.model_validate(data)
    data["cases"] = data["cases"][:1]
    data["cases"][0]["drug_universe"] = [""]
    with pytest.raises(ValidationError): Manifest.model_validate(data)


def test_future_gold_payload_is_validated(run):
    data = annotation(run)
    data.update(record_type="retrieval_query", drug_code=None, labels={}, payload={})
    with pytest.raises(ValidationError): GoldRecord.model_validate(data)
    data["payload"] = {"query_id": "synthetic-q", "query_text": "toy", "stage": "evidence_agent", "dimension": "infection",
                       "corpus_sha256": "a" * 64, "requested_k": 2, "judgment_scope": "top_k_only", "judgments": []}
    record = GoldRecord.model_validate(data)
    assert metric(evaluate_run(run, manifest=identity(run), gold=[record]), "retrieval_recall_at_k")["value"] is None
    data["payload"]["requested_k"] = 0
    with pytest.raises(ValidationError): GoldRecord.model_validate(data)


def test_future_gold_with_labels_stays_unimplemented(run):
    data = annotation(run)
    data["record_type"] = "audit_item"
    data["payload"] = {"run_content_sha256": content_hash(run), "claim_id": "toy", "evidence_pack_sha256": "a" * 64,
                       "error_type": "SYNTHETIC", "gold_error_label": True, "expected_detection_class": "unsupported"}
    result = metric(evaluate_run(run, manifest=identity(run), gold=[GoldRecord.model_validate(data)]), "audit_error_detection_rate")
    assert result["status"] == "not_evaluated" and result["reason"] == "scorer_not_implemented_in_mvp"


def test_invalid_node_and_ast_types_diagnosed(run):
    run["nodes"][0]["status"] = {}
    assert metric(evaluate_run(run), "agent_output_completeness", agent="case_agent")["status"] == "invalid_output"
    run["case_snapshot"]["ast_results"][0]["reported_sir"] = {}
    assert metric(evaluate_run(run), "source_ast_structure")["status"] == "invalid_output"


def test_no_ast_has_no_pending_denominator(run):
    run["case_snapshot"]["ast_results"] = []
    run["drug_assessments"] = []
    assert metric(evaluate_run(run), "pending_rate")["reason"] == "zero_denominator"


def test_canonicalization_preserves_text_and_order():
    assert content_hash({"a": 1, "b": "x"}) == content_hash({"b": "x", "a": 1})
    assert content_hash({"a": "x\r\ny"}) != content_hash({"a": "x\ny"})
    assert content_hash([1, 2]) != content_hash([2, 1])


def test_empty_run_collection_rejected(tmp_path):
    with pytest.raises(ValueError, match="no runs"):
        load_runs([write(tmp_path / "empty.json", [])])


def test_duplicate_gold_rejected(tmp_path, run):
    data = annotation(run)
    with pytest.raises(ValueError, match="duplicate Gold"):
        load_gold([write(tmp_path / "dup.json", [data, data])], allow_synthetic=True)


def test_ineligible_gold_review_and_expert_requirements(run):
    data = annotation(run)
    label = data["labels"]["selected_source_classification"]
    label["annotation_provenance"]["reviewer_ids"] = []
    with pytest.raises(ValidationError): GoldRecord.model_validate(data)
    label["annotation_provenance"]["reviewer_ids"] = ["toy"]
    label["ground_truth_tier"] = "C_clinical"
    with pytest.raises(ValidationError, match="qualification_role"): GoldRecord.model_validate(data)


def test_cli_schema_and_invalid_input(tmp_path, capsys):
    assert main(["--print-schema", "gold"]) == 0
    assert "x-payload-schemas-by-record-type" in json.loads(capsys.readouterr().out)
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    assert main(["--runs", str(p), "--out", str(tmp_path / "out")]) == 2
    assert not (tmp_path / "out").exists()


def test_failed_run_without_final_output_not_misclassified(run):
    run.update(status="failed", output=None, drug_assessments=[])
    rows = evaluate_run(run)
    assert metric(rows, "pending_rate")["status"] == "not_evaluated"
    assert metric(rows, "pending_rate")["reason"] == "run_execution_failed"
    assert metric(rows, "ai_candidate_count")["status"] == "not_evaluated"
    assert metric(rows, "run_execution_failed")["value"] == 1
