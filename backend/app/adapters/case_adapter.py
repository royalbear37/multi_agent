"""Input adapters. Raw payload is retained by the repository; only normalized
data crosses into the workflow.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from app.schemas.case import AlternateCase, Case


class CaseAdapter(Protocol):
    version: str
    def normalize(self, payload: dict[str, Any]) -> Case: ...


class CanonicalCaseAdapter:
    version = "canonical-1"
    def normalize(self, payload: dict[str, Any]) -> Case:
        return Case.model_validate(payload)


class AlternateCaseAdapter:
    version = "alternate-1"
    def normalize(self, payload: dict[str, Any]) -> Case:
        alt = AlternateCase.model_validate(payload)
        p, inf, lab, allergy = alt.patient, alt.infection, alt.lab, alt.allergy
        status = allergy.get("status", "unknown")
        items = allergy.get("items", []) if status == "known_present" else []
        ast = []
        for item in lab.get("ast", []) or []:
            ast.append({
                "drug_code": item.get("drug", item.get("drug_code")),
                "mic": item.get("mic"), "comparator": item.get("comparator"),
                "unit": item.get("unit"), "reported_sir": item.get("sir", item.get("reported_sir")),
                "method": item.get("method"), "standard": item.get("standard"),
                "standard_version": item.get("standard_version"), "source": "alternate",
            })
        return Case.model_validate({
            "case_id": alt.id, "schema_version": "1.0", "is_synthetic": alt.synthetic,
            "source": "alternate", "created_at": alt.observed_at.isoformat(),
            "demographics": {"age": p.get("age"), "sex": p.get("sex"), "weight": p.get("weight"), "weight_unit": p.get("weight_unit")},
            "encounter": {"infection_site": inf.get("site"), "severity": inf.get("severity"), "context": inf.get("context"), "observed_at": alt.observed_at.isoformat()},
            "renal": {"egfr": lab.get("egfr"), "unit": lab.get("egfr_unit"), "creatinine": lab.get("creatinine"), "creatinine_unit": lab.get("creatinine_unit")},
            "allergies": {"status": status, "items": items},
            "microbiology": {"specimen": lab.get("specimen"), "organism": lab.get("organism"), "report_status": lab.get("report_status"), "collected_at": alt.observed_at.isoformat()},
            "ast_results": ast,
            "rapid_identification": lab.get("rapid_identification"),
            "medications": p.get("medications", []),
            "resistance_context_ref": inf.get("resistance_context_ref", []),
            "policy_refs": inf.get("policy_refs", []),
            "provenance": {"source_system": "alternate-fixture", "imported_at": datetime.now(timezone.utc).isoformat(), "adapter_version": self.version},
        })


def normalize_case(payload: dict[str, Any], fmt: str = "canonical") -> tuple[Case, list[str]]:
    adapter = AlternateCaseAdapter() if fmt == "alternate" else CanonicalCaseAdapter()
    case = adapter.normalize(payload)
    warnings: list[str] = []
    if case.allergies.status == "unknown": warnings.append("過敏史未知，不得視為無過敏")
    if not case.renal.egfr and not case.renal.creatinine: warnings.append("缺少腎功能資料")
    if not case.ast_results: warnings.append("尚無 AST 結果")
    for i, ast in enumerate(case.ast_results):
        if ast.mic is not None and (ast.comparator is None or not ast.unit):
            warnings.append(f"AST[{i}] MIC 缺少比較符號或單位，系統不做精確比較")
        if ast.reported_sir and (not ast.standard or not ast.standard_version):
            warnings.append(f"AST[{i}] 標準名稱／版本未知，保留來源結果並要求人工確認")
    if case.renal.egfr is not None and not case.renal.unit:
        warnings.append("腎功能 eGFR 缺少單位")
    if case.renal.creatinine is not None and not case.renal.creatinine_unit:
        warnings.append("腎功能肌酸酐缺少單位")
    if case.microbiology.organism is None: warnings.append("缺少菌種")
    return case, warnings
