"""Build/validate provisional source extracts. No clinical labels or DB writes.

Run from backend/: python -m scripts.pilot_source_draft build|validate DIRECTORY
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from app.evaluation.io import content_hash, load_gold, load_manifest, read_json

ROOT = Path(__file__).resolve().parents[2]
CASES = ("agent-complete", "agent-ast-conflict", "agent-allergy", "agent-renal", "agent-evidence-mismatch")
GROUP = "G01-provisional"
POLICY = "ast-source-policy-0.1-draft"
FIELDS = ("drug_code", "reported_sir", "source_phenotype", "clsi_2022_phenotype", "interpretation_basis")
SELECT = {"CLSI_2022_pheno": "clsi_2022_phenotype", "source_report": "source_phenotype", "legacy": "reported_sir"}
CATEGORY = {"S": "susceptible", "I": "intermediate", "R": "resistant", "Susceptible": "susceptible",
            "Intermediate": "intermediate", "Resistant": "resistant"}
TASKS = ("selected_source_classification", "source_conflict_detection", "source_attribution", "selected_source_missing_handling")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pointer(value, path):
    if not path.startswith("/"):
        raise ValueError("absolute JSON pointer required")
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def sources(root=ROOT):
    manifest_path = root / "data/handoff/manifest.json"
    manifest = read_json(manifest_path)
    result = []
    for name in CASES:
        matches = [x for x in manifest["cases"] if x["case_id"] == name]
        if len(matches) != 1:
            raise ValueError(f"manifest case identity ambiguous: {name}")
        entry = matches[0]
        path = root / entry["path"]
        if sha(path) != entry["sha256"] or entry["revision"] != 4:
            raise ValueError(f"source hash/revision mismatch: {name}")
        history = read_json(path)
        revisions = [(i, x) for i, x in enumerate(history) if x["revision"] == 4]
        if len(revisions) != 1 or revisions[0][1]["case"]["case_id"] != name:
            raise ValueError(f"source revision ambiguous: {name}")
        i, item = revisions[0]
        result.append((entry, i, item["case"], history))
    return result


def observation_status(row):
    field = SELECT.get(row.get("interpretation_basis"))
    selected = CATEGORY.get(row.get(field)) if field else None
    reported, historical = CATEGORY.get(row.get("reported_sir")), CATEGORY.get(row.get("source_phenotype"))
    missing = "unknown_basis" if not field else "missing" if row.get(field) is None else "unrecognized" if selected is None else "present"
    cross = bool(selected and reported and selected != reported)
    historical_difference = bool(selected and historical and selected != historical)
    conflict = ("reported_selected_conflict" if cross else "unassessable" if missing != "present" or reported is None
                else "historical_difference" if historical_difference else "no_observed_conflict")
    return field, selected, missing, conflict, historical_difference


def build_bundle(root=ROOT):
    observations, drafts, identities, assets = [], [], [], []
    for entry, history_index, case, history in sources(root):
        case_id = case["case_id"]
        snapshot_hash = content_hash(case)
        source_hash = case.get("provenance", {}).get("source_file_sha256")
        asset = {"case_id": case_id, "revision": 4, "source_case_group": GROUP,
                 "source_asset_path": entry["path"], "source_asset_sha256": entry["sha256"],
                 "history_array_index": history_index, "case_snapshot_sha256": snapshot_hash,
                 "source_file_hash": source_hash, "source_record_id": case.get("provenance", {}).get("source_record_id"),
                 "source_provenance": case.get("provenance", {})}
        assets.append(asset)
        grouped = defaultdict(list)
        for index, row in enumerate(case["ast_results"]):
            field, selected, missing, conflict, historical = observation_status(row)
            prefix = f"/{history_index}/case/ast_results/{index}"
            item = {"schema_version": "pilot-ast-observation-0.1", "observation_id": f"{case_id}:r4:ast:{index}",
                    "case_id": case_id, "revision": 4, "source_case_group": GROUP, "ast_index": index,
                    **{key: row.get(key) for key in FIELDS}, "selected_source_category": selected,
                    "selected_source_field": field, "selected_source_field_path": prefix + "/" + field if field else None,
                    "source_field_paths": {key: prefix + "/" + key for key in FIELDS},
                    "conflict_status": conflict, "missing_status": missing, "historical_source_difference": historical,
                    "source_file_hash": source_hash, "source_asset_path": entry["path"],
                    "source_asset_sha256": entry["sha256"], "case_snapshot_sha256": snapshot_hash,
                    "verification_status": "provisional", "review_status": "pending_review",
                    "row_origin": "authored_conflict_append" if case_id == "agent-ast-conflict" and index == 18 else "source_preserved_in_handoff",
                    "annotation_provenance": {"extraction_method": "direct_json_field_copy_and_explicit_category_mapping",
                        "extractor": "backend/scripts/pilot_source_draft.py", "extractor_sha256": sha(Path(__file__)),
                        "policy_version": POLICY, "independent_human_verified": False,
                        "annotator_id": None, "reviewer_ids": [], "source_record_pointer": prefix,
                        "row_origin_basis": "backend/scripts/build_agent_cases.py:77" if case_id == "agent-ast-conflict" and index == 18 else "handoff case provenance"}}
            observations.append(item)
            grouped[row["drug_code"]].append(item)
        identities.append({"case_id": case_id, "revision": 4, "case_snapshot_sha256": snapshot_hash,
                           "source_case_group": GROUP, "grouping_basis": ["builder_derivation", "provisional_dev_group_not_patient_id"],
                           "grouping_sources": ["backend/scripts/build_agent_cases.py:73-80", "docs/AST_GOLD_POLICY_REVIEW.md"],
                           "drug_universe": list(grouped)})
        for drug, obs in grouped.items():
            selected = sorted({x["selected_source_category"] for x in obs if x["selected_source_category"]})
            reported = {CATEGORY.get(x["reported_sir"]) for x in obs} - {None}
            flags = {"within_selected_conflict": len(selected) > 1, "within_reported_conflict": len(reported) > 1,
                     "reported_vs_selected_conflict": any(x["conflict_status"] == "reported_selected_conflict" for x in obs)}
            status = "observed_conflict" if any(flags.values()) else "unassessable" if any(x["conflict_status"] == "unassessable" for x in obs) else "no_observed_conflict"
            source_rows = [{"index": x["ast_index"], "field": f"/ast_results/{x['ast_index']}/{x['selected_source_field']}",
                            "value": x.get(x["selected_source_field"]), "asset_field_path": x["selected_source_field_path"],
                            "observation_id": x["observation_id"]} for x in obs]
            provenance = {"source_assets": [entry["path"] + "#" + x["selected_source_field_path"] for x in obs],
                          "annotation_guideline_version": POLICY, "annotator_id": None, "qualification_role": None,
                          "reviewer_ids": [], "origin": "independent_source"}
            drafts.append({"schema_version": "eval-gold-0.1", "record_type": "case_drug",
                           "record_id": f"pilot-a-source-v0.1:{case_id}:r4:{drug}", "case_id": case_id, "revision": 4,
                           "case_snapshot_sha256": snapshot_hash, "source_case_group": GROUP, "drug_code": drug,
                           "synthetic_fixture": False,
                           "labels": {task: {"label": None, "accepted_labels": None, "review_status": "draft",
                               "ground_truth_tier": "A_source", "policy_version": POLICY, "annotation_provenance": provenance,
                               "source_rows": source_rows, "conditions": []} for task in TASKS},
                           "payload": {"verification_status": "provisional", "review_status": "pending_review",
                               "source_asset_path": entry["path"], "source_asset_sha256": entry["sha256"],
                               "source_file_hash": source_hash, "history_array_index": history_index,
                               "observation_ids": [x["observation_id"] for x in obs], "source_rows": source_rows,
                               "selected_source_categories_observed": selected, "conflict_status": status,
                               "source_conflict_flags": flags, "selected_missing_indices": [x["ast_index"] for x in obs if x["missing_status"] != "present"],
                               "historical_difference_indices": [x["ast_index"] for x in obs if x["historical_source_difference"]],
                               "contains_authored_conflict": any(x["row_origin"] == "authored_conflict_append" for x in obs),
                               "pending_questions": ["approve_task_policy", "independent_source_review", "approve_scoring_eligibility"]}})
    manifest = {"schema_version": "eval-manifest-0.1", "canonicalization": "json-sorted-utf8-v1", "cases": identities}
    provenance = {"dataset_version": "pilot-a-source-v0.1-provisional", "status": "provisional", "clinical_gold": False,
                  "handoff_manifest_path": "data/handoff/manifest.json", "handoff_manifest_sha256": sha(root / "data/handoff/manifest.json"),
                  "handoff_manifest_version": read_json(root / "data/handoff/manifest.json")["version"],
                  "extractor_sha256": sha(Path(__file__)), "canonicalization": "json-sorted-utf8-v1", "cases": assets}
    return observations, drafts, manifest, provenance


def write_bundle(destination, root=ROOT):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"refusing overwrite: {destination}")
    observations, drafts, manifest, provenance = build_bundle(root)
    destination.mkdir(parents=True, exist_ok=False)
    for filename, values in (("observations.jsonl", observations), ("case_drug_drafts.jsonl", drafts)):
        (destination / filename).write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in values), encoding="utf-8")
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    provenance["dataset_files_sha256"] = {name: sha(destination / name) for name in ("observations.jsonl", "case_drug_drafts.jsonl", "manifest.json")}
    (destination / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_bundle(directory, root=ROOT):
    """Audit against raw assets and invariant counts, not against generator output."""
    directory = Path(directory)
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    observations = [json.loads(x) for x in (directory / "observations.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    drafts = load_gold([directory / "case_drug_drafts.jsonl"])
    manifest = load_manifest(directory / "manifest.json")
    provenance = read_json(directory / "provenance.json")
    require(provenance["status"] == "provisional" and provenance["clinical_gold"] is False, "release status")
    require(provenance["handoff_manifest_sha256"] == sha(root / "data/handoff/manifest.json"), "handoff manifest hash")
    require(set(provenance["dataset_files_sha256"]) == {"observations.jsonl", "case_drug_drafts.jsonl", "manifest.json"}, "file hash inventory")
    require(provenance["extractor_sha256"] == sha(Path(__file__)), "extractor version changed")
    for name, digest in provenance["dataset_files_sha256"].items():
        require(sha(directory / name) == digest, f"dataset file hash: {name}")
    raw = {entry["case_id"]: (entry, i, case, history) for entry, i, case, history in sources(root)}
    require(len(provenance["cases"]) == 5 and {x["case_id"] for x in provenance["cases"]} == set(CASES), "provenance cases")
    for asset in provenance["cases"]:
        entry, i, case, _ = raw[asset["case_id"]]
        require(asset["source_asset_path"] == entry["path"] and asset["source_asset_sha256"] == entry["sha256"], "provenance asset hash")
        require(asset["revision"] == 4 and asset["history_array_index"] == i and asset["case_snapshot_sha256"] == content_hash(case), "provenance revision")
        require(asset["source_provenance"] == case["provenance"] and asset["source_file_hash"] == case["provenance"]["source_file_sha256"], "provenance source")
    expected_keys = {(name, 4, i) for name, (_, _, case, _) in raw.items() for i in range(len(case["ast_results"]))}
    keys = [(x["case_id"], x["revision"], x["ast_index"]) for x in observations]
    require(len(keys) == len(set(keys)) == 91 and set(keys) == expected_keys, "observation coverage/duplicates")
    obs_by_id = {}
    for o in observations:
        entry, history_index, case, history = raw[o["case_id"]]
        row = case["ast_results"][o["ast_index"]]
        require(o["observation_id"] == f"{o['case_id']}:r4:ast:{o['ast_index']}", "observation identity")
        require(o["source_asset_path"] == entry["path"] and o["source_asset_sha256"] == entry["sha256"], "asset identity")
        require(o["case_snapshot_sha256"] == content_hash(case) and o["source_file_hash"] == case["provenance"]["source_file_sha256"], "source hashes")
        require(o["source_case_group"] == GROUP, "source group")
        require(o["verification_status"] == "provisional" and o["review_status"] == "pending_review", "observation promoted")
        require(o["annotation_provenance"]["annotator_id"] is None and not o["annotation_provenance"]["reviewer_ids"]
                and o["annotation_provenance"]["independent_human_verified"] is False, "invented human verification")
        for field in FIELDS:
            path = f"/{history_index}/case/ast_results/{o['ast_index']}/{field}"
            require(o["source_field_paths"][field] == path and pointer(history, path) == o[field] == row.get(field), "source field path/value")
        # All five pilot assets explicitly select CLSI; do not call production/evaluator source logic.
        require(o["interpretation_basis"] == "CLSI_2022_pheno" and o["selected_source_field"] == "clsi_2022_phenotype", "selected field")
        require(o["selected_source_field_path"] == o["source_field_paths"]["clsi_2022_phenotype"], "selected pointer")
        selected = CATEGORY.get(row["clsi_2022_phenotype"])
        require(o["selected_source_category"] == selected, "selected value fabricated")
        require(o["missing_status"] == ("missing" if row["clsi_2022_phenotype"] is None else "present"), "missing status")
        index = o["ast_index"]
        expected_status = "reported_selected_conflict" if o["case_id"] == "agent-ast-conflict" and index == 18 else "unassessable" if index == 7 else "historical_difference" if index == 11 else "no_observed_conflict"
        require(o["conflict_status"] == expected_status and o["historical_source_difference"] == (index == 11), "conflict/historical status")
        require(o["row_origin"] == ("authored_conflict_append" if o["case_id"] == "agent-ast-conflict" and index == 18 else "source_preserved_in_handoff"), "row origin")
        obs_by_id[o["observation_id"]] = o
    expected_units = {(o["case_id"], o["revision"], o["drug_code"]) for o in observations}
    require(len(drafts) == len(expected_units) == 90 and {(g.case_id, g.revision, g.drug_code) for g in drafts} == expected_units, "case drug coverage")
    links = []
    for g in drafts:
        related = [o for o in observations if (o["case_id"], o["revision"], o["drug_code"]) == (g.case_id, g.revision, g.drug_code)]
        p = g.payload
        expected_ids = [o["observation_id"] for o in related]
        require(p["observation_ids"] == expected_ids, "lost duplicate observation")
        links.extend(p["observation_ids"])
        require(g.case_snapshot_sha256 == related[0]["case_snapshot_sha256"] and g.source_case_group == GROUP, "Gold alignment")
        require(p["verification_status"] == "provisional" and p["review_status"] == "pending_review", "draft promoted")
        require(set(g.labels) == set(TASKS), "task labels")
        for label in g.labels.values():
            require(label.review_status == "draft" and label.label is None and label.accepted_labels is None, "draft label became Gold")
            require(label.ground_truth_tier == "A_source" and label.policy_version == POLICY, "label policy/tier")
            require(label.annotation_provenance.annotator_id is None and label.annotation_provenance.reviewer_ids == [], "invented annotator")
            require(len(label.source_rows) == len(related) and label.source_rows == p["source_rows"], "label source links")
        for source, o in zip(p["source_rows"], related):
            require(source["index"] == o["ast_index"] and source["observation_id"] == o["observation_id"], "source row index")
            require(source["field"] == f"/ast_results/{o['ast_index']}/clsi_2022_phenotype" and source["asset_field_path"] == o["selected_source_field_path"], "Gold source pointer")
            require(source["value"] == o["clsi_2022_phenotype"], "Gold source value")
        conflict = g.case_id == "agent-ast-conflict" and g.drug_code == "amoxicillin_clavulanate"
        missing = g.drug_code == "ertapenem"
        require(p["conflict_status"] == ("observed_conflict" if conflict else "unassessable" if missing else "no_observed_conflict"), "unit conflict overwritten")
        require(p["source_conflict_flags"] == {"within_selected_conflict": False, "within_reported_conflict": conflict, "reported_vs_selected_conflict": conflict}, "unit flags")
        require(p["selected_missing_indices"] == ([7] if missing else []), "unit missing overwritten")
    require(Counter(links) == Counter(obs_by_id.keys()), "observation linkage coverage")
    require(len(manifest.cases) == 5 and {x.case_id for x in manifest.cases} == set(CASES), "manifest cases")
    for c in manifest.cases:
        case = raw[c.case_id][2]
        require(c.revision == 4 and c.case_snapshot_sha256 == content_hash(case) and c.source_case_group == GROUP, "manifest alignment")
        require(c.drug_universe == list(dict.fromkeys(x["drug_code"] for x in case["ast_results"])), "drug universe")
    return {"status": "passed", "observations": 91, "case_drug_drafts": 90, "verified_gold": 0,
            "observation_status_counts": dict(Counter(x["conflict_status"] for x in observations)),
            "case_drug_status_counts": dict(Counter(g.payload["conflict_status"] for g in drafts)),
            "gold_loader_compatible": True, "formal_scoring_eligible": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "validate"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        write_bundle(args.directory)
    print(json.dumps(validate_bundle(args.directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
