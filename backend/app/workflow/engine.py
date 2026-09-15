"""Eight node deterministic orchestration for the synthetic prototype."""

from __future__ import annotations

import copy
import time
import uuid
import json
from pathlib import Path
from contextvars import ContextVar
from typing import Any

from app.rules.engine import RuleEngine
from .safety import gate_status, validate_provider_output


NODE_IDS = (
    "case_completeness", "ast", "resistance_context", "rapid_identification",
    "evidence_retrieval", "safety_gate", "candidate_presentation", "human_review",
)
_MISSING_PATHS = ("microbiology.organism", "encounter.infection_site")
_PINNED_RULES: ContextVar = ContextVar('pinned_rules', default=None)


def _get(data: dict[str, Any], path: str) -> Any:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _node(node_id: str, status: str, started: float, *, output: Any = None, version: str | None = None,
          errors: list[dict[str, Any]] | None = None, refs: list[str] | None = None, evidence_refs: list[str] | None = None, retry_count: int = 0) -> dict[str, Any]:
    return {
        "node_id": node_id, "status": status, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "version": version,
        "output": output, "rule_refs": refs or [], "evidence_refs": evidence_refs or [], "errors": errors or [], "retry_count": retry_count,
    }


def _summary(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "organism": _get(case, "microbiology.organism"),
        "infection_site": _get(case, "encounter.infection_site"),
        "severity": _get(case, "encounter.severity"),
        "renal": copy.deepcopy(case.get("renal")),
        "allergy_status": _get(case, "allergies.status"),
        "ast_count": len(case.get("ast_results") or []) if isinstance(case.get("ast_results"), list) else 0,
        "is_synthetic": case.get("is_synthetic") is True,
    }


def _deterministic_output(engine: RuleEngine, evaluations: list[dict[str, Any]], evidence: list[dict[str, Any]],
                          gate: str, limitations: list[str], case: dict[str, Any]) -> dict[str, Any]:
    blocked_codes = {code for x in evaluations if x.get("status") == "matched" and x.get("action") in {"avoid", "block"} for code in (x.get("drug_codes") or [])}
    avoid: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    evidence_ids = [str(x.get("chunk_id")) for x in evidence if x.get("chunk_id")]
    rule_ids = [str(x.get("rule_id")) for x in evaluations if x.get("status") == "matched" and x.get("action") == "allow_candidates"]
    for code in engine.candidate_drugs(case):
        item = {"drug_code": code, "reason": "展示規則允許；仍需人工確認。", "rule_refs": rule_ids, "evidence_refs": evidence_ids}
        if code in blocked_codes:
            item["reason"] = "展示限制命中，應避免並由人工確認。"
            avoid.append(item)
        else:
            candidates.append(item)
    if gate == "blocked":
        candidates = []
    return {"candidates": candidates, "avoid": avoid, "limitations": list(dict.fromkeys(limitations))}


def _execute_workflow(case: dict[str, Any], mode: str, provider_kind: str, document_service: Any, run_id: str) -> dict[str, Any]:
    started_all = time.perf_counter()
    engine = RuleEngine(config=_PINNED_RULES.get())
    nodes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    missing: list[str] = []
    evaluations: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    is_mock = provider_kind == "mock"

    t = time.perf_counter()
    for path in _MISSING_PATHS:
        if _get(case, path) in (None, ""):
            missing.append(path)
    if _get(case, "allergies.status") in (None, "unknown"):
        missing.append("allergies.status")
    if not case.get("renal") or _get(case, "renal.egfr") is None:
        missing.append("renal.egfr")
    if not case.get("policy_refs"):
        missing.append("policy_refs")
    if not case.get("ast_results"):
        missing.append("ast_results")
    nodes.append(_node("case_completeness", "completed", t, output={"summary": _summary(case), "missing_fields": missing}, version="case-summary-1.0"))

    t = time.perf_counter()
    evaluations = engine.evaluate(case)
    ast_output = {"source_report": copy.deepcopy(case.get("ast_results") or []), "system_result": "not_configured", "system_evaluations": [], "warnings": []}
    if case.get("ast_results"):
        standards_ok = all(x.get("standard") and x.get("standard_version") for x in case["ast_results"] if isinstance(x, dict))
        ast_output["system_result"] = "evaluated_demo" if standards_ok else "needs_review"
        ast_output["system_evaluations"] = engine.evaluate_ast(case)
        if any(x['status'] != 'evaluated' for x in ast_output['system_evaluations']):
            ast_output['system_result'] = 'needs_review'
            missing.append('ast_results.unverified_or_conflicting')
        if not standards_ok:
            ast_output["warnings"].append("AST 標準版本未知，保留來源報告結果且不重新判讀。")
            missing.append("ast_results[].standard_or_version")
        if any(isinstance(x, dict) and (not x.get("unit") or not x.get("comparator")) for x in case["ast_results"]):
            ast_output["warnings"].append("MIC 單位或比較符號缺漏，不進行精確比較。")
            missing.append("ast_results[].unit_or_comparator")
        if not engine.candidate_drugs(case):
            missing.append("ast_results.no_approved_drug")
    else:
        ast_output["warnings"].append("沒有 AST；不可推定敏感。")
    nodes.append(_node("ast", "completed", t, output=ast_output, version=engine.version, refs=[x["rule_id"] for x in evaluations]))

    t = time.perf_counter()
    resistance_ref = case.get("resistance_context_ref")
    resistance = {"status": "skipped", "ref": None, "source": None}
    if resistance_ref:
        try:
            context_config=json.loads((Path(__file__).resolve().parents[3]/'configs/demo/resistance.json').read_text(encoding='utf-8'))
            records={ref:context_config['records'][ref] for ref in resistance_ref if ref in context_config['records']}
            resistance = {"status": "completed" if len(records)==len(resistance_ref) else 'not_configured', "ref": copy.deepcopy(resistance_ref), "source": "synthetic-resistance-demo-1.0", "scope": "population_context", 'version':context_config['version'], 'records':records}
            if len(records)!=len(resistance_ref): missing.append('resistance_context_ref.unconfigured')
        except (OSError, ValueError, KeyError):
            resistance={'status':'not_configured','ref':resistance_ref,'source':None}
            missing.append('resistance_context_ref.unconfigured')
    nodes.append(_node("resistance_context", resistance["status"], t, output=resistance, version="synthetic-resistance-demo-1.0"))

    t = time.perf_counter()
    rapid = case.get("rapid_identification")
    nodes.append(_node("rapid_identification", "completed" if rapid else "skipped", t,
                       output=copy.deepcopy(rapid) if rapid else {"status": "skipped", "reason": "沒有快速鑑定資料；未連線儀器。"}, version="rapid-summary-1.0"))

    t = time.perf_counter()
    query = " ".join(str(x) for x in (_get(case, "microbiology.organism"), _get(case, "encounter.infection_site")) if x)
    if document_service is None:
        search_result = {"status": "not_configured", "evidence": [], "warnings": ["文件服務未設定"]}
    else:
        try:
            search_result = document_service.search(query or "synthetic", policy_refs=case.get("policy_refs"))
        except Exception as exc:  # document service failures are data, never fatal to the whole trace
            search_result = {"status": "failed", "evidence": [], "warnings": ["文件檢索失敗"]}
            errors.append({"node_id": "evidence_retrieval", "code": "EVIDENCE_SEARCH_FAILED", "detail": type(exc).__name__})
    evidence = [copy.deepcopy(x) for x in (search_result.get("evidence") or []) if isinstance(x, dict)]
    nodes.append(_node("evidence_retrieval", "completed" if search_result.get("status") in {"ok", "completed", "no_results"} else "blocked" if search_result.get('status') == 'conflict' else str(search_result.get("status", "completed")), t,
                       output={"status": search_result.get("status"), "warnings": search_result.get("warnings", []), "count": len(evidence),
                               "retrieval_method": search_result.get("retrieval_method"), "embedding_model": search_result.get("embedding_model")}, version="retrieval-2.0",
                       evidence_refs=[str(x.get("chunk_id")) for x in evidence if x.get("chunk_id")]))

    supported = _get(case, "microbiology.organism") in {"DEMO_ORGANISM_A", "DEMO_ORGANISM_B"}
    # Every publishable candidate needs a local, versioned evidence snapshot,
    # including the deterministic baseline.  Rule-only simply does not call a
    # model; it still observes the same evidence boundary.
    if search_result.get("status") == "conflict" or any("conflict" in str(w).lower() for w in (search_result.get("warnings") or [])):
        missing.append("evidence.version_conflict")
    gate, limitations = gate_status(missing_fields=missing, evaluations=evaluations, evidence=evidence, supported=supported, require_evidence=True)
    t = time.perf_counter()
    nodes.append(_node("safety_gate", "completed" if gate != "blocked" else "blocked", t,
                       output={"gate_status": gate, "limitations": limitations}, version=engine.version,
                       refs=[x["rule_id"] for x in evaluations], evidence_refs=[str(x.get("chunk_id")) for x in evidence if x.get("chunk_id")]))

    output: dict[str, Any] | None = None
    candidate_status = "completed"
    provider_meta: dict[str, Any] = {"model": None, "usage": None, "retries": 0, "is_mock": is_mock}
    candidate_retries = 0
    quarantined_raw: Any = None
    provider_attempted = mode == "rule-only"
    t = time.perf_counter()
    if mode == "rule-only":
        output = _deterministic_output(engine, evaluations, evidence, gate, limitations, case)
    elif provider_kind == "unconfigured":
        candidate_status = "not_configured"
        errors.append({"node_id": "candidate_presentation", "code": "MODEL_NOT_CONFIGURED"})
    else:
        try:
            from app.providers.service import get_provider, ProviderError
            provider = get_provider(provider_kind)
            pstatus = provider.status()
            if not pstatus.get("configured", False):
                candidate_status = "not_configured"
                errors.append({"node_id": "candidate_presentation", "code": "MODEL_NOT_CONFIGURED"})
            else:
                provider_attempted = True
                internal_rule_refs = [x["rule_id"] for x in evaluations]
                generation_allowlist = engine.candidate_drugs(case) if mode == 'multi-agent' else engine.allowed_drugs()
                summary_for_provider = _summary(case)
                context = {"mode": mode, "case_summary": summary_for_provider, "allowed_drugs": generation_allowlist,
                           "evidence": evidence, "rule_refs": internal_rule_refs}
                if mode == "rag-only":
                    context["rule_refs"] = []
                elif mode == "single-agent":
                    context["rule_refs"] = []
                    context['case_summary']['ast_results'] = copy.deepcopy(case.get('ast_results', []))
                else:
                    # Provider adapters serialize case_summary, so bounded
                    # node summaries are included there for multi-agent input.
                    context["node_summaries"] = [{"node_id": n["node_id"], "status": n["status"], "output": n["output"]} for n in nodes]
                generated = provider.generate(context)
                quarantined_raw = copy.deepcopy(generated.get("output")) if isinstance(generated, dict) else None
                provider_meta.update({k: generated.get(k) for k in ("model", "usage", "retries", "is_mock") if k in generated})
                provider_rule_refs = [] if mode in {"rag-only", "single-agent"} else {x["rule_id"] for x in evaluations}
                candidate_payload = copy.deepcopy(generated.get("output"))
                validated, validation_errors = validate_provider_output(candidate_payload, allowed_drugs=set(engine.candidate_drugs(case)),
                                                                       allowed_rules=provider_rule_refs,
                                                                       allowed_evidence={str(x.get("chunk_id")) for x in evidence},
                                                                       require_rule_refs=mode == "multi-agent" and bool(provider_rule_refs),
                                                                       require_evidence_refs=mode != "rule-only" and bool(evidence))
                if validation_errors:
                    candidate_status = "failed"
                    errors.append({"node_id": "candidate_presentation", "code": "OUTPUT_SCHEMA_INVALID", "validation_errors": validation_errors})
                else:
                    output = validated
                    if mode in {"rag-only", "single-agent"} and output is not None:
                        allow_refs = [x["rule_id"] for x in evaluations if x.get("status") == "matched" and x.get("action") == "allow_candidates"]
                        for item in output.get("candidates", []):
                            if isinstance(item, dict) and not item.get("rule_refs"):
                                item["rule_refs"] = allow_refs
        except Exception as exc:
            code = getattr(exc, "code", "MODEL_ERROR")
            candidate_retries = int(getattr(exc, "retries", 0) or 0)
            candidate_status = "failed"
            errors.append({"node_id": "candidate_presentation", "code": str(code), "detail": type(exc).__name__, "retryable": bool(getattr(exc, "retryable", False))})
    if output is None and candidate_status == "completed":
        output = _deterministic_output(engine, evaluations, evidence, gate, limitations, case)
    output_schema_valid = output is not None
    safe_avoid = [{"drug_code": code, "reason": str(x.get("reason", "展示限制命中，應避免並由人工確認。")),
                   "rule_refs": [str(x.get("rule_id"))], "evidence_refs": []}
                  for x in evaluations if x.get("status") == "matched" and x.get("action") in {"avoid", "block"}
                  for code in (x.get("drug_codes") or [])]
    if output is not None:
        output["limitations"] = list(dict.fromkeys((output.get("limitations") or []) + limitations))
    will_publish = output is not None and candidate_status == "completed" and gate == "ready_for_review"
    nodes.append(_node("candidate_presentation", candidate_status, t, output={"published": will_publish, "withheld": not will_publish,
                                                                            "attempted": provider_attempted, "output_received": quarantined_raw is not None or mode == "rule-only"},
                       version="candidate-schema-1.0", refs=[x["rule_id"] for x in evaluations],
                       evidence_refs=[str(x.get("chunk_id")) for x in evidence if x.get("chunk_id")], retry_count=candidate_retries))

    # A second deterministic check is mandatory after generation.  Any model
    # violation or hard gate makes the candidate content non-publishable.
    if candidate_status == "failed" or gate != "ready_for_review":
        # needs_confirmation and blocked results retain their reasons in the
        # gate/node trace but never publish a candidate medication output.
        output = None
    nodes[-1]["output"]["schema_valid"] = output_schema_valid and candidate_status == "completed"
    final_gate = "blocked" if candidate_status == "failed" else gate
    t = time.perf_counter()
    nodes.append(_node("human_review", "pending", t, output={"action_required": True}, version="review-1.0"))
    if candidate_status == "not_configured":
        overall = "partial"
    elif final_gate == "blocked":
        overall = "blocked"
    else:
        overall = "awaiting_review"
    public_output = None
    if output is not None:
        public_output = {**output, "run_id": run_id, "demo_only": True, "gate_status": final_gate}
    return {
        "run_id": run_id, "case_id": case.get("case_id"), "case_snapshot": copy.deepcopy(case), "status": overall, "mode": mode, "is_mock": is_mock,
        "gate_status": final_gate, "output": public_output,
        "safety_summary": {"gate_status": gate, "limitations": list(dict.fromkeys(limitations)), "avoid": safe_avoid, "demo_only": True},
        # Persisted by the backend for research comparison, but this payload
        # must be stripped from ordinary UI/API presentation and exports.
        "raw_baseline": {"withheld": mode != "rule-only", "available": mode != "rule-only" and quarantined_raw is not None, "payload": quarantined_raw if mode != "rule-only" else None, "is_mock": is_mock},
        "nodes": nodes, "rule_evaluations": evaluations,
        "evidence_snapshots": evidence, "versions": {"rules": engine.version, "rules_snapshot": engine.snapshot(), "candidate_schema": "candidate-schema-1.0"},
        "errors": errors, "missing_fields": list(dict.fromkeys(missing)), "usage": provider_meta.get("usage"),
        "model": provider_meta.get("model"), "cost": None, "elapsed_ms": round((time.perf_counter() - started_all) * 1000, 3),
    }


def execute(case: dict[str, Any], mode: str, provider_kind: str = "unconfigured", document_service: Any = None, run_id: str | None = None, *, rules_snapshot: dict | None = None) -> dict[str, Any]:
    if mode not in {"rule-only", "rag-only", "single-agent", "multi-agent"}:
        raise ValueError("unsupported workflow mode")
    if provider_kind not in {"unconfigured", "mock", "live"}:
        raise ValueError("unsupported provider kind")
    run_id = run_id or str(uuid.uuid4())
    # Distinct runners own their information scope and provider semantics.
    from app.agents.runners import RUNNERS
    token = _PINNED_RULES.set(copy.deepcopy(rules_snapshot))
    try:
        return RUNNERS[mode].run(case, provider_kind, document_service, run_id)
    finally:
        _PINNED_RULES.reset(token)


def validate_review(run: dict[str, Any], proposed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a review edit against the same hard candidate boundary."""
    if proposed is None:
        proposed = copy.deepcopy(run.get("output") or {"candidates": [], "avoid": [], "limitations": []})
    else:
        # API callers may send the previously returned public output verbatim;
        # run metadata belongs to the envelope rather than candidate schema.
        proposed = {k: copy.deepcopy(v) for k, v in proposed.items() if k not in {"run_id", "demo_only", "gate_status"}}
    if run.get("gate_status") != "ready_for_review" and proposed.get("candidates"):
        raise ValueError("run is not ready; resolve safety gate before publishing candidates")
    snapshot = (run.get("versions") or {}).get("rules_snapshot")
    engine = RuleEngine(config=snapshot) if isinstance(snapshot, dict) else RuleEngine()
    case_snapshot = run.get("case_snapshot")
    allowed = set(engine.candidate_drugs(case_snapshot)) if isinstance(case_snapshot, dict) else set()
    evals = run.get("rule_evaluations") or []
    hard_avoid = {x.get("drug_code") for x in (run.get("output") or {}).get("avoid", []) if isinstance(x, dict)}
    validated, errors = validate_provider_output(proposed, allowed_drugs=allowed,
                                                 allowed_rules={str(x.get("rule_id")) for x in evals},
                                                 allowed_evidence={str(x.get("chunk_id")) for x in run.get("evidence_snapshots", [])},
                                                 require_rule_refs=bool(evals), require_evidence_refs=bool(run.get("evidence_snapshots")))
    if errors or validated is None:
        raise ValueError("review output rejected: " + ",".join(errors))
    if any(x.get("drug_code") in hard_avoid for x in validated.get("candidates", [])):
        raise ValueError("review cannot move an avoided drug into candidates")
    return {"valid": True, "output": {**validated, "run_id": run.get("run_id"), "demo_only": True, "gate_status": run.get("gate_status")}}
