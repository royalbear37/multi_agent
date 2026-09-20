"""Shared deterministic safety and controlled candidate validation."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


# This intentionally catches both common English prescription vocabulary and
# Chinese wording.  Candidate reasons are explanatory text, never a dosing API.
FORBIDDEN_TEXT = re.compile(
    r"(?i)(?:\bdose\b|\bdosage\b|\bfrequency\b|\bduration\b|\b(?:mg|mcg|g|gram|milligram)\b|\bq\d{1,3}\s*h\b|\bbid\b|\btid\b|\bqid\b|\bevery\s+\d+\s*(?:hours?|hrs?|h)\b|\b(?:twice|three|once)\s+(?:daily|a\s+day)\b|\b(?:intravenous|iv|intramuscular|im|oral|po)\b|\bper\s+day\b|\btake\s+\d+\s+(?:tablets?|pills?|capsules?)\b|\bfor\s+\d+\s+days?\b|\b\d+\s+days?\b|每天|每日|每次|每\S{0,4}小時|一日\s*\d+\s*次|服用|注射|口服|靜脈|静脉|靜滴|劑量|剂量|頻率|频率|療程|疗程)"
)

_CANDIDATE_KEYS = {"drug_code", "reason", "rule_refs", "evidence_refs"}
_AVOID_KEYS = {"drug_code", "reason", "rule_refs", "evidence_refs"}


def forbidden_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    # A narrow negative scope statement is not a prescription. Other text,
    # including any appended numeric instructions, still gets checked.
    checked = unicodedata.normalize("NFKC", value)
    checked = re.sub(r"不(?:提供|包含)劑量、頻率(?:及|與|、)療程", "", checked)
    return bool(FORBIDDEN_TEXT.search(checked))


def _clean_refs(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        return None
    return list(dict.fromkeys(value))


def normalize_demo_output(value: Any, *, allowed_drugs: set[str], allowed_avoid: set[str],
                          allowed_rules: set[str], allowed_evidence: set[str],
                          require_rule_refs: bool = False, require_evidence_refs: bool = False):
    """Repair presentation and retain only individually valid demo entries."""
    if not isinstance(value, dict):
        return value, []
    notes = []
    if set(value) - {'candidates', 'avoid', 'limitations'}:
        notes.append('EXTRA_FIELDS_IGNORED')
    result = {'candidates': [], 'avoid': [], 'limitations': []}
    for key in ('candidates', 'avoid'):
        entries = value.get(key)
        if entries is None:
            entries = []
            notes.append('EMPTY_LIST_DEFAULTED')
        if not isinstance(entries, list):
            return value, []
        seen = set()
        for item in entries:
            if not isinstance(item, dict):
                notes.append('INVALID_ITEM_OMITTED')
                continue
            code = item.get('drug_code')
            allowed = allowed_drugs if key == 'candidates' else allowed_avoid
            refs = _clean_refs(item.get('rule_refs') or [])
            erefs = _clean_refs(item.get('evidence_refs') or [])
            if (not isinstance(code, str) or code not in allowed or refs is None or erefs is None
                    or not set(refs) <= allowed_rules or not set(erefs) <= allowed_evidence
                    or (key == 'candidates' and require_rule_refs and not refs)
                    or (key == 'candidates' and require_evidence_refs and not erefs)):
                notes.append('INVALID_ITEM_OMITTED')
                continue
            if code in seen:
                notes.append('DUPLICATE_ITEM_OMITTED')
                continue
            seen.add(code)
            reason = item.get('reason')
            if not isinstance(reason, str) or not reason.strip() or forbidden_text(reason):
                reason = '模型原說明已省略；此項僅供 demo 核對，適用性仍待確認。'
                notes.append('TEXT_WITHHELD')
            if set(item) - _CANDIDATE_KEYS:
                notes.append('EXTRA_FIELDS_IGNORED')
            result[key].append({'drug_code': code, 'reason': reason, 'rule_refs': refs, 'evidence_refs': erefs})
    # A contradictory candidate must not survive merely because the model's
    # avoid entry was itself invalid and omitted above.
    avoid_codes = {x['drug_code'] for x in result['avoid']}
    avoid_codes.update(x['drug_code'] for x in (value.get('avoid') or [])
                       if isinstance(x, dict) and isinstance(x.get('drug_code'), str)
                       and x['drug_code'] in allowed_drugs)
    if any(x['drug_code'] in avoid_codes for x in result['candidates']):
        result['candidates'] = [x for x in result['candidates'] if x['drug_code'] not in avoid_codes]
        notes.append('OVERLAPPING_CANDIDATE_OMITTED')
    limits = value.get('limitations') or []
    if isinstance(limits, str):
        limits = [limits]
        notes.append('LIMITATION_LIST_NORMALIZED')
    if not isinstance(limits, list):
        return value, []
    for text in limits:
        if not isinstance(text, str) or not text.strip() or forbidden_text(text):
            notes.append('TEXT_WITHHELD')
            continue
        result['limitations'].append(text)
    if notes:
        result['limitations'].append('Demo 已整理輸出格式並省略無法核對的項目或文字；未補造藥敏或引用。')
    return result, sorted(set(notes))


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
