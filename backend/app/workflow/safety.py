"""Shared deterministic safety and controlled candidate validation."""

from __future__ import annotations

import re
from typing import Any


# This intentionally catches both common English prescription vocabulary and
# Chinese wording.  Candidate reasons are explanatory text, never a dosing API.
FORBIDDEN_TEXT = re.compile(
    r"(?i)(?:\bdose\b|\bdosage\b|\bfrequency\b|\bduration\b|\bmg\b|\bmcg\b|\bmilligram\w*\b|\bq\d{1,3}\s*h\b|\bbid\b|\btid\b|\bqid\b|\bevery\s+\d+\s*(?:hours?|hrs?|h)\b|\bper\s+day\b|\btake\s+\d+\s+(?:tablets?|pills?|capsules?)\b|\bfor\s+\d+\s+days?\b|\b\d+\s+days?\b|每天|每日|每次|每\S{0,4}小時|服用|注射|口服|靜脈|静脉|劑量|剂量|頻率|频率|療程|疗程)"
)

_CANDIDATE_KEYS = {"drug_code", "reason", "rule_refs", "evidence_refs"}
_AVOID_KEYS = {"drug_code", "reason", "rule_refs", "evidence_refs"}


def forbidden_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    # A narrow negative scope statement is not a prescription. Other text,
    # including any appended numeric instructions, still gets checked.
    checked = re.sub(r"不(?:提供|包含)劑量、頻率(?:及|與|、)療程", "", value)
    return bool(FORBIDDEN_TEXT.search(checked))


def _clean_refs(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        return None
    return list(dict.fromkeys(value))


def validate_provider_output(
    value: Any,
    *,
    allowed_drugs: set[str],
    allowed_rules: set[str],
    allowed_evidence: set[str],
    require_rule_refs: bool = False,
    require_evidence_refs: bool = False,
    allowed_avoid: set[str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate an LLM/provider object against strict, explainable boundaries."""
    errors: list[str] = []
    if not isinstance(value, dict):
        return None, ["output_not_object"]
    if set(value) - {"candidates", "avoid", "limitations"}:
        errors.append("unknown_output_field")
    candidates = value.get("candidates", [])
    avoid = value.get("avoid", [])
    limitations = value.get("limitations", [])
    if not isinstance(candidates, list) or not isinstance(avoid, list) or not isinstance(limitations, list):
        errors.append("output_lists_required")
        return None, errors
    if not all(isinstance(x, str) for x in limitations) or any(forbidden_text(x) for x in limitations):
        errors.append("forbidden_text")
    clean: dict[str, Any] = {"candidates": [], "avoid": [], "limitations": list(limitations)}
    codes = [x.get('drug_code') for x in candidates if isinstance(x, dict) and isinstance(x.get('drug_code'), str)]
    if len(codes) != len(set(codes)):
        errors.append('duplicate_candidate')
    avoid_codes = [x.get('drug_code') for x in avoid if isinstance(x, dict) and isinstance(x.get('drug_code'), str)]
    if set(codes).intersection(avoid_codes):
        errors.append('candidate_avoid_overlap')
    if len(avoid_codes) != len(set(avoid_codes)):
        errors.append('duplicate_avoid')
    for collection, keyset, destination in ((candidates, _CANDIDATE_KEYS, "candidates"), (avoid, _AVOID_KEYS, "avoid")):
        for item in collection:
            if not isinstance(item, dict) or set(item) != keyset:
                errors.append("candidate_schema_invalid")
                continue
            item_errors: list[str] = []
            code, reason = item.get("drug_code"), item.get("reason")
            rules, evidence = _clean_refs(item.get("rule_refs")), _clean_refs(item.get("evidence_refs"))
            permitted = allowed_avoid if destination == "avoid" and allowed_avoid is not None else allowed_drugs
            if not isinstance(code, str) or code not in permitted:
                item_errors.append("drug_not_allowed")
            if not isinstance(reason, str) or not reason.strip() or forbidden_text(reason):
                item_errors.append("forbidden_or_missing_reason")
            if rules is None or any(x not in allowed_rules for x in rules):
                item_errors.append("rule_ref_not_allowed")
            if require_rule_refs and not rules:
                item_errors.append("rule_ref_required")
            if evidence is None or any(x not in allowed_evidence for x in evidence):
                item_errors.append("evidence_ref_not_allowed")
            if require_evidence_refs and not evidence and not (destination == "avoid" and allowed_avoid is not None):
                item_errors.append("evidence_ref_required")
            errors.extend(item_errors)
            if not item_errors:
                clean[destination].append({"drug_code": code, "reason": reason, "rule_refs": rules, "evidence_refs": evidence})
    return (clean if not errors else None), list(dict.fromkeys(errors))


def gate_status(*, missing_fields: list[str], evaluations: list[dict[str, Any]], evidence: list[dict[str, Any]], supported: bool, require_evidence: bool = True) -> tuple[str, list[str]]:
    limitations: list[str] = []
    if not supported:
        return "blocked", ["病例或菌種不在展示支援範圍"]
    hard = [x for x in evaluations if x.get("status") == "matched" and x.get("action") in {"block", "avoid"} and x.get("severity") == "block"]
    if hard:
        limitations.extend(str(x.get("reason", "展示硬性規則命中")) for x in hard)
        return "blocked", limitations
    unknown = [x for x in evaluations if x.get("status") in {"unknown", "error"}]
    if unknown:
        limitations.append("有展示規則無法判定，需人工確認")
    if missing_fields:
        limitations.append("缺少關鍵病例資料：" + ", ".join(missing_fields))
    if not any(x.get("status") == "matched" and x.get("action") == "allow_candidates" for x in evaluations):
        limitations.append("沒有命中的候選 allowlist 規則")
    if require_evidence and not evidence:
        limitations.append("沒有可定位的展示證據")
    return ("needs_confirmation" if limitations else "ready_for_review"), limitations
