"""Denominator-aware benchmark aggregation for synthetic workflow runs."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def _metric(num: int, den: int, *, status: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"value": _ratio(num, den), "numerator": num, "denominator": den}
    if status:
        value["status"] = status
    return value


def _expect(expectations: dict[str, Any], case_id: str) -> dict[str, Any]:
    value = expectations.get(case_id, {}) if isinstance(expectations, dict) else {}
    return value if isinstance(value, dict) else {}


def _core(results: list[dict[str, Any]], expectations: dict[str, Any]) -> dict[str, Any]:
    total = len(results)
    statuses = Counter(str(r.get("status")) for r in results)
    missing_tp = missing_pred = missing_actual = 0
    block_tp = block_actual = unnecessary_block = 0
    expected_rule_total = expected_rule_pass = 0
    citation_total = citation_valid = location_total = location_valid = 0
    schema_total = schema_valid = whitelist_violations = 0
    for result in results:
        case_id = str(result.get("case_id", ""))
        exp = _expect(expectations, case_id)
        if "missing_fields" in exp and isinstance(exp["missing_fields"], list):
            predicted = set(result.get("missing_fields") or [])
            actual = set(exp["missing_fields"])
            missing_tp += len(predicted & actual)
            missing_pred += len(predicted)
            missing_actual += len(actual)
        if "expected_block" in exp and isinstance(exp["expected_block"], bool):
            blocked = result.get("gate_status") == "blocked"
            expected = exp["expected_block"]
            block_tp += int(blocked and expected)
            block_actual += int(expected)
            unnecessary_block += int(blocked and not expected)
        expected_rules = exp.get("rule_evaluations")
        actual_rules = {str(x.get("rule_id")): x.get("status") for x in result.get("rule_evaluations", []) if isinstance(x, dict)}
        items = expected_rules.items() if isinstance(expected_rules, dict) else ((x.get("rule_id"), x.get("status")) for x in expected_rules if isinstance(x, dict) and "rule_id" in x and "status" in x) if isinstance(expected_rules, list) else ()
        for rule_id, expected_status in items:
            expected_rule_total += 1
            expected_rule_pass += int(actual_rules.get(str(rule_id)) == expected_status)

        output = result.get("output") or {}
        refs: list[str] = []
        if isinstance(output, dict):
            for group in (output.get("candidates", []), output.get("avoid", [])):
                for item in group or []:
                    if isinstance(item, dict):
                        refs.extend(str(x) for x in (item.get("evidence_refs") or []) if isinstance(x, str))
        snapshots = {str(x.get("chunk_id")): x for x in result.get("evidence_snapshots", []) if isinstance(x, dict) and x.get("chunk_id")}
        citation_total += len(refs)
        citation_valid += sum(1 for ref in refs if ref in snapshots)
        location_total += sum(1 for ref in refs if ref in snapshots)
        location_valid += sum(1 for ref in refs if ref in snapshots and snapshots[ref].get("location"))

        presentation = next((n for n in result.get("nodes", []) if n.get("node_id") == "candidate_presentation"), {})
        if presentation.get("output", {}).get("attempted"):
            schema_total += 1
            schema_valid += int(bool((presentation.get("output") or {}).get("schema_valid")))
        whitelist_violations += sum(1 for err in result.get("errors", []) if any(t in str(err).upper() for t in ("NOT_ALLOWED", "UNALLOWED", "WHITELIST")))

    labeled_nonblock = sum(1 for r in results if _expect(expectations, str(r.get("case_id", ""))).get("expected_block") is False)
    agent_nodes = [n for r in results for n in r.get("nodes", []) if n.get("agent_id")]
    agent_ids = sorted({n["agent_id"] for n in agent_nodes})
    def agent_stats(nodes):
        attempts = [a for n in nodes for a in n.get("attempts", [])]
        tokens = [a["usage"]["total_tokens"] for a in attempts if "total_tokens" in (a.get("usage") or {})]
        return {"executions": len(nodes), "calls": len(attempts),
                "failed": sum(n["status"] == "failed" for n in nodes),
                "skipped": sum(n["status"] == "skipped" for n in nodes),
                "known_total_tokens": sum(tokens) if tokens else None,
                "usage_complete": bool(attempts) and len(tokens) == len(attempts),
                "elapsed_ms": round(sum(n.get("elapsed_ms", 0) for n in nodes), 3)}
    return {
        "agent_execution": agent_stats(agent_nodes),
        "by_agent": {agent_id: agent_stats([n for n in agent_nodes if n["agent_id"] == agent_id]) for agent_id in agent_ids},
        "total_cases": total, "status_counts": dict(statuses),
        "completion": _metric(sum(1 for r in results if r.get("gate_status") == "ready_for_review" and r.get("output") is not None), total),
        "failed_ratio": _metric(statuses.get("failed", 0), total), "blocked_ratio": _metric(statuses.get("blocked", 0), total),
        "not_configured_ratio": _metric(statuses.get("partial", 0) + statuses.get("not_configured", 0), total),
        "safety_withholding": _metric(sum(1 for r in results if r.get("gate_status") in {"needs_confirmation", "blocked"}), total),
        "rule_test_pass_rate": _metric(expected_rule_pass, expected_rule_total), "missing_precision": _metric(missing_tp, missing_pred), "missing_recall": _metric(missing_tp, missing_actual),
        "expected_safety_block_recall": _metric(block_tp, block_actual), "unnecessary_block_rate": _metric(unnecessary_block, labeled_nonblock),
        "citation_id_validity": _metric(citation_valid, citation_total), "citation_location_validity": _metric(location_valid, location_total),
        "citation_support_conclusion": _metric(0, 0, status="not_evaluated"), "schema_validity": _metric(schema_valid, schema_total),
        "whitelist_violation_rate": _metric(whitelist_violations, schema_total), "appropriateness": _metric(0, 0, status="not_evaluated"),
        "expert_agreement": _metric(0, 0, status="not_evaluated"), "clinical_utility": _metric(0, 0, status="not_evaluated"),
    }


def summarize(results: list[dict[str, Any]], expectations: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize runs; unlabeled clinical metrics remain N/A."""
    expectations = expectations or {}
    summary = _core(results, expectations)
    modes = sorted({str(r.get("mode")) for r in results if r.get("mode")})
    summary["by_mode"] = {mode: _core([r for r in results if r.get("mode") == mode], expectations) for mode in modes}
    groups = sorted({f"{r.get('mode')}:{'mock' if r.get('is_mock') else 'live_or_none'}" for r in results})
    summary["by_execution"] = {key: _core([r for r in results if f"{r.get('mode')}:{'mock' if r.get('is_mock') else 'live_or_none'}" == key], expectations) for key in groups}
    return summary
