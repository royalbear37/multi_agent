"""Pure Run -> metric rows transformation, including explicit ineligible outcomes."""
from collections import Counter

from .alignment import align
from .io import content_hash
from .metrics import (ROLES, ROLE_FIELDS, AST_LABELS, FINAL_LABELS, abstention, citations,
                      completeness, drug_rows, number, ratio, source_consistency, source_observations,
                      token_statistics, unavailable)
from .schemas import Metric, RunEnvelope

FUTURE = {
    "retrieval_recall_at_k": {"retrieval_query"}, "retrieval_precision_at_k": {"retrieval_query"},
    "critical_evidence_missing_rate": {"retrieval_query", "evidence_span"},
    "source_attribution_accuracy": {"run_claim"}, "claim_support_precision": {"run_claim", "proposition_inventory"},
    "claim_support_recall": {"proposition_inventory"}, "claim_support_f1": {"proposition_inventory"},
    "audit_error_detection_rate": {"audit_item"}, "unsupported_claim_rate": {"run_claim"},
    "clinical_risk_accuracy": {"clinical_risk"}, "candidate_precision": {"final_decision"},
    "candidate_recall": {"final_decision"}, "unsafe_recommendation_rate": {"final_decision"},
}


def evaluate_run(run, *, manifest=None, gold=()):
    RunEnvelope.model_validate(run)
    identity, related, errors = align(run, manifest, gold)
    versions = run.get("versions")
    workflow = versions.get("workflow") if isinstance(versions, dict) else None
    base = {"run_id": run["run_id"], "case_id": run["case_id"], "revision": run["case_revision"],
            "source_case_group": identity.source_case_group if identity else None, "mode": run["mode"],
            "is_mock": run["is_mock"], "workflow": workflow if isinstance(workflow, str) else None}
    observations = []

    def add(name, result, target="run", drug=None, agent=None):
        observations.append(Metric(**base, metric=name, scoring_target=target, drug_code=drug,
                                   agent_id=agent, **result).model_dump())

    if errors:
        add("identity_alignment", unavailable("identity_mismatch", "alignment_error", errors=errors))
        return observations
    add("identity_alignment", {"status": "evaluated", "value": 1.0, "details": {"case_snapshot_sha256": content_hash(run["case_snapshot"])}}
        if identity else unavailable("source_case_group_unresolved_no_manifest"))

    try:
        sources = source_observations(run["case_snapshot"])
    except ValueError as exc:
        sources = None
        add("source_ast_structure", unavailable(str(exc), "invalid_output", owner="saved_input_snapshot"))
    universe = identity.drug_universe if identity else list(sources or {})
    if identity and sources is not None and set(sources) - set(universe):
        add("identity_alignment", unavailable("manifest_omits_source_drugs", "alignment_error"))
        return observations
    scope = "manifest_drug_universe" if identity else "source_drugs_only"
    nodes = run["nodes"]
    supported = run["mode"] == "multi-agent" and workflow == "agent-led-1.6.0"
    role_nodes = {role: [n for n in nodes if n.get("agent_id") == role] for role in ROLES}
    ast_node = role_nodes["ast_agent"][0] if len(role_nodes["ast_agent"]) == 1 else None
    ast_output = ast_node.get("output") if ast_node else None
    ast_rows, ast_errors = drug_rows(ast_output.get("drugs") if isinstance(ast_output, dict) else None)

    if supported:
        add("agent_node_completeness", ratio(sum(len(role_nodes[r]) == 1 for r in ROLES), len(ROLES)), "workflow_structure")
        for role in ROLES:
            matches = role_nodes[role]
            if len(matches) != 1:
                add("agent_output_completeness", unavailable("missing_or_duplicate_agent_node", "invalid_output"), "normalized_agent_output", agent=role)
                continue
            node = matches[0]
            output = node.get("output")
            if not isinstance(node.get("status"), str):
                result = unavailable("invalid_node_status_type", "invalid_output")
            elif node.get("status") in {"failed", "skipped", "pending", "running"}:
                result = unavailable("execution_not_completed", node_status=node.get("status"))
            elif node.get("status") not in {"completed", "needs_confirmation"}:
                result = unavailable("unknown_node_status", "invalid_output")
            elif not isinstance(output, dict) or any(not isinstance(output.get(k), list) for k in ("findings", "issues")):
                result = unavailable("malformed_report_structure", "invalid_output")
            elif role == "case_agent":
                result = ratio(1, 1) if isinstance(output.get("missing_fields"), list) else unavailable("missing_fields_not_list", "invalid_output")
            else:
                field, allowed, abstentions = ROLE_FIELDS[role]
                inp = node.get("input")
                assigned = inp.get("drugs") if isinstance(inp, dict) else None
                if not isinstance(assigned, list) or any(not isinstance(x, str) or not x for x in assigned) or len(set(assigned)) != len(assigned):
                    result = unavailable("assigned_drug_universe_unavailable")
                else:
                    result = completeness(output.get("drugs"), assigned, field, allowed)
                    add("agent_abstention_rate", abstention(output.get("drugs"), assigned, field, allowed, abstentions),
                        "normalized_agent_output", agent=role)
            add("agent_output_completeness", result, "normalized_agent_output", agent=role)
            if number(node.get("elapsed_ms")):
                add("elapsed_ms", {"status": "evaluated", "value": node["elapsed_ms"]}, "saved_node_timing", agent=role)
            else:
                add("elapsed_ms", unavailable("node_latency_unavailable"), "saved_node_timing", agent=role)
            if node.get("status") in ("completed", "needs_confirmation"):
                for name, result in citations(output, run.get("evidence_snapshots")).items():
                    add(name, result, "normalized_agent_output", agent=role)
    else:
        add("agent_output_completeness", unavailable("unsupported_workflow_or_mode"), "normalized_agent_output")

    if sources is not None:
        for drug, source in sources.items():
            add("source_conflict_present", {"status": "evaluated", "value": float(any(source["flags"].values())), "details": source}, "saved_case_source", drug)
            if not supported:
                result = unavailable("unsupported_workflow_or_mode")
            elif not ast_node or ast_errors:
                result = unavailable("missing_or_invalid_ast_report", "invalid_output")
            elif ast_node.get("status") not in ("completed", "needs_confirmation"):
                result = unavailable("ast_execution_not_completed")
            else:
                result = source_consistency(source, ast_rows.get(drug, {}).get("assessment"))
            add("ast_source_consistency", result, "normalized_agent_output", drug, "ast_agent")
            matches = [g for g in related if g.record_type == "case_drug" and g.drug_code == drug
                       and "selected_source_classification" in g.labels]
            if len(matches) > 1:
                result = unavailable("ambiguous_gold_records", "alignment_error")
            elif identity is None:
                result = unavailable("source_case_group_unresolved_no_manifest")
            elif not matches or matches[0].labels["selected_source_classification"].review_status != "adjudicated":
                result = unavailable("independent_adjudicated_ast_gold_missing", "missing_gold")
            elif not supported:
                result = unavailable("unsupported_workflow_or_mode")
            elif not ast_node or ast_node.get("status") not in ("completed", "needs_confirmation"):
                result = unavailable("ast_execution_not_completed")
            else:
                label = matches[0].labels["selected_source_classification"]
                accepted = label.accepted_labels
                predicted = ast_rows.get(drug, {}).get("assessment")
                if not accepted or not set(accepted) <= AST_LABELS or label.ground_truth_tier != "A_source" or not label.source_rows:
                    result = unavailable("ast_gold_policy_or_source_rows_incomplete", "missing_gold")
                elif not isinstance(predicted, str) or predicted not in AST_LABELS or ast_errors:
                    result = unavailable("invalid_ast_assessment", "invalid_output")
                else:
                    result = ratio(int(predicted in accepted), 1)
                    result["details"] = {"gold_record_id": matches[0].record_id, "policy_version": label.policy_version,
                                         "synthetic_fixture": matches[0].synthetic_fixture}
            add("ast_classification_accuracy", result, "normalized_agent_output", drug, "ast_agent")
            # Legacy free-text findings do not expose an unambiguous binary detection prediction.
            conflict_gold = any(g.record_type == "case_drug" and g.drug_code == drug
                                and "source_conflict_detection" in g.labels for g in related)
            add("ast_conflict_detection_accuracy", unavailable("structured_prediction_binding_not_available" if conflict_gold else "independent_conflict_gold_missing",
                                                                 "not_evaluated" if conflict_gold else "missing_gold"),
                "normalized_agent_output", drug, "ast_agent")

    if run["status"] == "failed":
        add("output_completeness", unavailable("run_execution_failed"), scope)
        add("pending_rate", unavailable("run_execution_failed"), scope)
    elif supported and sources is not None:
        rows = run.get("drug_assessments")
        add("output_completeness", completeness(rows, universe, "status", FINAL_LABELS), scope)
        add("pending_rate", abstention(rows, universe, "status", FINAL_LABELS, {"pending"}), scope)
        indexed, row_errors = drug_rows(rows)
        for drug in universe:
            row = indexed.get(drug)
            valid = row is not None and isinstance(row.get("status"), str) and row["status"] in FINAL_LABELS and not row_errors
            add("pending_indicator", ratio(int(row["status"] == "pending"), 1) if valid else unavailable("missing_or_invalid_drug_row", "invalid_output"), scope, drug)
    else:
        add("pending_rate", unavailable("source_or_workflow_unavailable"), scope)

    output = run.get("output")
    for name, result in citations(output, run.get("evidence_snapshots")).items():
        add(name, result, "published_output")
    candidates = output.get("candidates") if isinstance(output, dict) else None
    if isinstance(candidates, list) and all(isinstance(x, dict) and isinstance(x.get("drug_code"), str) for x in candidates):
        add("ai_candidate_count", {"status": "evaluated", "value": len(candidates)}, "published_ai_candidates")
    else:
        add("ai_candidate_count", unavailable("run_execution_failed") if run["status"] == "failed"
            else unavailable("candidates_missing_or_invalid", "invalid_output"), "published_ai_candidates")
    elapsed = run.get("elapsed_ms")
    add("elapsed_ms", {"status": "evaluated", "value": elapsed} if number(elapsed) else unavailable("latency_missing_or_invalid"), "saved_run_timing")
    add("run_execution_failed", {"status": "evaluated", "value": float(run["status"] == "failed")}, "engineering")
    add("agent_failed_count", {"status": "evaluated", "value": sum(n.get("status") == "failed" for n in nodes if n.get("agent_id"))}, "engineering")
    for name, result in token_statistics([n for n in nodes if n.get("agent_id")], run["is_mock"]).items():
        add(name, result, "saved_attempt_usage")
    add("estimated_cost", unavailable("mock_has_no_model_usage" if run["is_mock"] else "price_and_complete_usage_not_available"), "resources")
    for name, types in FUTURE.items():
        has_gold = any(g.record_type in types and any(label.review_status == "adjudicated" for label in g.labels.values()) for g in related)
        add(name, unavailable("scorer_not_implemented_in_mvp" if has_gold else "independent_gold_missing",
                              "not_evaluated" if has_gold else "missing_gold"), "future_gold_metric")
    return observations


def aggregate(observations):
    """Descriptive strata only; no pooling Mock/live or inference of independent N."""
    groups = {}
    keys = ("mode", "is_mock", "workflow", "source_case_group", "metric", "scoring_target", "agent_id")
    for row in observations:
        key = tuple(row[k] for k in keys)
        groups.setdefault(key, []).append(row)
    result = []
    for key, rows in sorted(groups.items(), key=lambda item: repr(item[0])):
        good = [x for x in rows if x["status"] == "evaluated" and x["value"] is not None]
        ratios = [x for x in good if x["denominator"] is not None and x["denominator"] > 0]
        denominator = sum(x["denominator"] for x in ratios)
        result.append({**dict(zip(keys, key)), "n_requested": len(rows), "n_evaluable": len(good),
                       "status_counts": dict(sorted(Counter(x["status"] for x in rows).items())),
                       "run_count": len({x["run_id"] for x in rows}),
                       "macro_mean": sum(x["value"] for x in good) / len(good) if good else None,
                       "micro_value": sum(x["numerator"] for x in ratios) / denominator if denominator else None,
                       "micro_denominator": denominator if ratios else None,
                       "independent_sample_count": None})
    return result
