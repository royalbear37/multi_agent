"""Small restricted rule interpreter used by the prototype workflow.

Rule conditions are data (a restricted operator set), never Python expressions.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_RULE_VERSION = "demo-rules-1.0.0"
ROOT = Path(__file__).resolve().parents[3]
RULE_CONFIG_PATH = ROOT / "configs" / "research" / "rules.json"


def load_demo_rules(path: Path | None = None) -> dict[str, Any]:
    """Load and snapshot the demo rule file, failing closed on bad config."""
    selected = path or Path(os.getenv("PROTOTYPE_RULE_CONFIG", str(RULE_CONFIG_PATH)))
    if not selected.exists():
        return {"config_version": DEFAULT_RULE_VERSION, "status": "not_configured", "rules": []}
    try:
        data = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"config_version": DEFAULT_RULE_VERSION, "status": "error", "rules": []}
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        return {"config_version": DEFAULT_RULE_VERSION, "status": "error", "rules": []}
    # Deep copy ensures a running trace cannot be changed by a later config edit.
    snapshot = copy.deepcopy(data)
    snapshot.setdefault("config_version", DEFAULT_RULE_VERSION)
    snapshot.setdefault("status", "demo_only")
    if snapshot.get("ast_mode") == "reported_phenotype":
        catalog_path = Path(os.getenv("PROTOTYPE_CATALOG_PATH", str(ROOT / "data/local/microbiology/catalog.json")))
        if catalog_path.exists():
            try:
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                snapshot["allowed_drugs"] = catalog["antibiotics"]
                snapshot["organisms"] = catalog["organisms"]
                snapshot["catalog_sha256"] = catalog["source_sha256"]
            except (OSError, ValueError, KeyError):
                snapshot["status"] = "error"
    return snapshot


def _get_path(value: dict[str, Any], path: str) -> Any:
    if '[].' in path:
        parent, child = path.split('[].', 1)
        rows = _get_path(value, parent)
        if not isinstance(rows, list) or not rows:
            return None
        values = [_get_path(row, child) for row in rows if isinstance(row, dict)]
        return values if len(values) == len(rows) and all(x is not None and x != '' for x in values) else None
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _condition(condition: Any, case: dict[str, Any]) -> str:
    """Return matched/not_matched/unknown for the restricted condition grammar."""
    if not isinstance(condition, dict):
        return "unknown"
    op = condition.get("op")
    path = condition.get("path")
    actual = _get_path(case, path) if isinstance(path, str) else None
    if op == "exists":
        return "matched" if actual is not None else "unknown"
    if actual is None:
        return "unknown"
    expected = condition.get("value")
    if op == "equals":
        return "matched" if actual == expected else "not_matched"
    if op == "in":
        choices = condition.get("values")
        return "matched" if isinstance(choices, list) and actual in choices else "not_matched"
    if op == "contains":
        if isinstance(actual, list):
            return "matched" if expected in actual else "not_matched"
        if isinstance(actual, str) and isinstance(expected, str):
            return "matched" if expected in actual else "not_matched"
        return "unknown"
    if op == "any_item_equals":
        if not isinstance(actual, list):
            return "unknown"
        key = condition.get("item_key")
        if not isinstance(key, str):
            return "unknown"
        return "matched" if any(isinstance(x, dict) and x.get(key) == expected for x in actual) else "not_matched"
    return "unknown"


class RuleEngine:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = copy.deepcopy(config if config is not None else load_demo_rules())
        self.version = str(self.config.get("config_version", DEFAULT_RULE_VERSION))

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.config)

    def evaluate(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        if self.reported_mode and self.config.get("status") != "error":
            from .reported import evaluate_rules
            return evaluate_rules(self, case)
        evaluations: list[dict[str, Any]] = []
        if self.config.get("status") in {"not_configured", "error"}:
            return [{"rule_id": "RULES_NOT_CONFIGURED", "version": self.version,
                     "status": "unknown", "severity": "block", "action": "needs_confirmation",
                     "reason": "展示規則設定不可用", "source_ref": "demo-config"}]
        for rule in self.config.get("rules", []):
            if not isinstance(rule, dict) or not rule.get("rule_id"):
                continue
            scope = rule.get("scope") or {}
            scoped_organisms = scope.get("organisms") if isinstance(scope, dict) else None
            organism = _get_path(case, "microbiology.organism")
            if isinstance(scoped_organisms, list) and organism is not None and organism not in scoped_organisms:
                result = "not_applicable"
            elif any(_get_path(case, field) is None for field in rule.get('required_fields', [])):
                result = 'unknown'
            else:
                result = _condition(rule.get("condition"), case)
            evaluations.append({
                "rule_id": str(rule["rule_id"]), "version": str(rule.get("version", self.version)),
                "status": result, "severity": rule.get("severity", "info"),
                "action": rule.get("action", "annotate"), "reason": str(rule.get("reason", "")),
                "source_ref": str(rule.get("source_ref", "demo-config")),
                "scope": copy.deepcopy(rule.get("scope", {})),
                "drug_codes": [str(x) for x in rule.get("drug_codes", []) if isinstance(x, str)],
            })
        return evaluations

    def allowed_drugs(self) -> list[str]:
        values = self.config.get("allowed_drugs", [])
        return [str(x) for x in values if isinstance(x, str)]

    @property
    def reported_mode(self) -> bool:
        return self.config.get("ast_mode") == "reported_phenotype"

    def supports(self, organism: str | None) -> bool:
        if self.reported_mode:
            return organism in self.config.get("organisms", [])
        return organism in self.config.get("approved_drugs", {})

    def candidate_drugs(self, case: dict[str, Any]) -> list[str]:
        """Return a case-specific allowlist; unknown AST data yields none."""
        if self.reported_mode:
            return [x["drug_code"] for x in self.evaluate_ast(case) if x["eligible"]]
        organism = _get_path(case, "microbiology.organism")
        mapping = self.config.get("approved_drugs", {})
        selected = mapping.get(organism, []) if isinstance(mapping, dict) else []
        ast = case.get("ast_results")
        if not isinstance(ast, list) or not ast or not isinstance(selected, list):
            return []
        # Demo config explicitly permits only reported S with a complete AST
        # measurement.  This is software behavior, not a clinical breakpoint.
        standard = self.config.get("ast_standard") or {}
        matrix = (self.config.get("ast_matrix") or {}).get(organism, {})
        reported = {
            x.get("drug_code") for x in ast if isinstance(x, dict)
            and x.get("reported_sir") == matrix.get(x.get("drug_code")) == "S"
            and x.get("standard") == standard.get("name") and x.get("standard_version") == standard.get("version")
            and x.get("unit") == standard.get('mic_unit') and x.get("comparator") in standard.get('comparators', []) and x.get("mic") is not None
        }
        return [x for x in selected if x in self.allowed_drugs() and x in reported]

    def evaluate_ast(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply only the fictional configured matrix; never infer thresholds."""
        if self.reported_mode:
            from .reported import evaluate_ast
            return evaluate_ast(self, case)
        standard = self.config.get("ast_standard") or {}
        matrix = (self.config.get("ast_matrix") or {}).get(_get_path(case, "microbiology.organism"), {})
        results: list[dict[str, Any]] = []
        for item in case.get("ast_results") or []:
            if not isinstance(item, dict):
                continue
            complete = all(item.get(k) is not None for k in ("mic", "comparator", "unit", "reported_sir")) and item.get('unit') == standard.get('mic_unit') and item.get('comparator') in standard.get('comparators', [])
            standard_ok = item.get("standard") == standard.get("name") and item.get("standard_version") == standard.get("version")
            expected = matrix.get(item.get("drug_code")) if isinstance(matrix, dict) else None
            status = "evaluated" if complete and standard_ok and expected is not None and item.get("reported_sir") == expected else "needs_review"
            results.append({"drug_code": item.get("drug_code"), "status": status, "source_reported_sir": item.get("reported_sir"), "configured_demo_result": expected if status == "evaluated" else None})
        return results
