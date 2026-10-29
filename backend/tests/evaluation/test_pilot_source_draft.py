"""Provisional extract checks; mutations are negative TEST fixtures, never Gold."""
import json
from pathlib import Path

import pytest

from app.evaluation.evaluator import evaluate_run
from app.evaluation.io import load_gold, load_manifest
from scripts.pilot_source_draft import ROOT, sha, validate_bundle, write_bundle


@pytest.fixture
def bundle(tmp_path):
    directory = tmp_path / "TEST-only-draft"
    write_bundle(directory)
    return directory


def read_lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def rewrite(directory, name, data):
    path = directory / name
    text = "".join(json.dumps(x) + "\n" for x in data) if name.endswith(".jsonl") else json.dumps(data)
    path.write_text(text, encoding="utf-8")
    # Deliberately refresh integrity hashes: semantic validation must still reject tampering.
    p = directory / "provenance.json"
    provenance = json.loads(p.read_text(encoding="utf-8"))
    provenance["dataset_files_sha256"][name] = sha(path)
    p.write_text(json.dumps(provenance), encoding="utf-8")


def test_complete_bundle_and_duplicate_lineage(bundle):
    result = validate_bundle(bundle)
    assert result["observations"] == 91 and result["case_drug_drafts"] == 90
    assert result["verified_gold"] == result["formal_scoring_eligible"] == 0
    assert result["observation_status_counts"] == {"no_observed_conflict": 80, "unassessable": 5,
        "historical_difference": 5, "reported_selected_conflict": 1}
    rows = load_gold([bundle / "case_drug_drafts.jsonl"])
    conflict = next(x for x in rows if x.case_id == "agent-ast-conflict" and x.drug_code == "amoxicillin_clavulanate")
    assert [x["index"] for x in conflict.payload["source_rows"]] == [0, 18]
    assert conflict.payload["selected_source_categories_observed"] == ["susceptible"]
    assert conflict.payload["contains_authored_conflict"] is True


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "path", "revision", "group", "selected", "missing", "conflict", "promote", "source_hash"])
def test_observation_corruption_rejected(bundle, mutation):
    rows = read_lines(bundle / "observations.jsonl")
    if mutation == "drop": rows.pop()
    elif mutation == "duplicate": rows[-1] = rows[0]
    elif mutation == "path": rows[0]["source_field_paths"]["reported_sir"] = "/3/case/ast_results/18/reported_sir"
    elif mutation == "revision": rows[0]["revision"] = 3
    elif mutation == "group": rows[0]["source_case_group"] = "unrelated"
    elif mutation == "selected": rows[7]["selected_source_category"] = "susceptible"
    elif mutation == "missing": rows[7]["missing_status"] = "present"
    elif mutation == "conflict": next(x for x in rows if x["ast_index"] == 18)["conflict_status"] = "no_observed_conflict"
    elif mutation == "promote": rows[0]["verification_status"] = "verified"
    else: rows[0]["source_file_hash"] = "0" * 64
    rewrite(bundle, "observations.jsonl", rows)
    with pytest.raises(ValueError): validate_bundle(bundle)


@pytest.mark.parametrize("mutation", ["lost_link", "promote", "label", "unit_conflict", "missing", "hash", "pointer"])
def test_case_drug_corruption_rejected(bundle, mutation):
    rows = read_lines(bundle / "case_drug_drafts.jsonl")
    conflict = next(x for x in rows if x["case_id"] == "agent-ast-conflict" and x["drug_code"] == "amoxicillin_clavulanate")
    if mutation == "lost_link": conflict["payload"]["observation_ids"].pop()
    elif mutation == "promote": rows[0]["payload"]["verification_status"] = "verified"
    elif mutation == "label": rows[0]["labels"]["selected_source_classification"]["accepted_labels"] = ["susceptible"]
    elif mutation == "unit_conflict": conflict["payload"]["source_conflict_flags"]["within_reported_conflict"] = False
    elif mutation == "missing": next(x for x in rows if x["drug_code"] == "ertapenem")["payload"]["selected_missing_indices"] = []
    elif mutation == "hash": rows[0]["case_snapshot_sha256"] = "0" * 64
    else: rows[0]["labels"]["source_attribution"]["source_rows"][0]["field"] = "/ast_results/1/clsi_2022_phenotype"
    rewrite(bundle, "case_drug_drafts.jsonl", rows)
    with pytest.raises(ValueError): validate_bundle(bundle)


def test_integrity_hash_and_no_overwrite(bundle):
    p = bundle / "observations.jsonl"
    p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="file hash"): validate_bundle(bundle)
    with pytest.raises(FileExistsError): write_bundle(bundle)


def test_reproducible_and_sources_unchanged(tmp_path):
    source_paths = list((ROOT / "data/handoff/cases").glob("agent-*.json"))
    before = {p: sha(p) for p in source_paths}
    a, b = tmp_path / "a", tmp_path / "b"
    write_bundle(a)
    write_bundle(b)
    assert {p: sha(p) for p in source_paths} == before
    for p in a.iterdir(): assert p.read_bytes() == (b / p.name).read_bytes()


def test_loader_accepts_drafts_but_scoring_does_not_promote(bundle):
    gold = load_gold([bundle / "case_drug_drafts.jsonl"])
    manifest = load_manifest(bundle / "manifest.json")
    case = json.loads((ROOT / "data/handoff/cases/agent-complete.json").read_text(encoding="utf-8"))[3]["case"]
    # Synthetic envelope is only an engineering fixture; no analysis is run.
    run = {"run_id": "TEST-synthetic-envelope", "case_id": "agent-complete", "case_revision": 4,
           "case_snapshot": case, "mode": "multi-agent", "is_mock": True, "status": "failed",
           "versions": {"workflow": "agent-led-1.6.0"}, "nodes": []}
    rows = evaluate_run(run, manifest=manifest, gold=gold)
    classification = [x for x in rows if x["metric"] == "ast_classification_accuracy"]
    assert len(classification) == 18
    assert all(x["status"] == "missing_gold" and x["value"] is None for x in classification)
