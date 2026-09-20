"""Eight node deterministic orchestration for the synthetic prototype."""

from __future__ import annotations

import copy
import time
import uuid
import json
import re
from pathlib import Path
from contextvars import ContextVar
from typing import Any

from app.rules.engine import RuleEngine
from .safety import gate_status, validate_provider_output, normalize_demo_output


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
        "data_origin": case.get("data_origin", "synthetic"),
        "external_model_allowed": case.get("external_model_allowed", False),
        "demographics": copy.deepcopy(case.get("demographics")),
        "clinical_context": _get(case, "encounter.context"),
        "allergies": copy.deepcopy(case.get("allergies")),
        "medications": copy.deepcopy(case.get("medications")),
        "simulated_fields": copy.deepcopy(_get(case, "provenance.simulated_fields") or []),
    }


def evidence_query(case: dict[str, Any]) -> str:
    terms = [_get(case, 'microbiology.organism'), _get(case, 'encounter.infection_site')]
    age = _get(case, 'demographics.age')
    if isinstance(age, (int, float)) and not isinstance(age, bool):
        terms.append('adults' if age >= 18 else 'children')
    return ' '.join(str(term) for term in terms if term)


_ADULT_TERMS = re.compile(r"(?i)(?:\badults?\b|\badult[- ]onset\b|成人)")
_PEDIATRIC_TERMS = re.compile(r"(?i)(?:\bpediatri\w*\b|\bpaediatri\w*\b|\bchildren\b|\bchild\b|\binfants?\b|\bneonat\w*\b|\badolescen\w*\b|兒童|小兒|嬰兒|新生兒)")


def _case_population(case: dict[str, Any]) -> str | None:
    age = _get(case, "demographics.age")
    if not isinstance(age, (int, float)) or isinstance(age, bool):
        return None
    return "adult" if age >= 18 else "pediatric"


def _evidence_population(item: dict[str, Any], case_population: str) -> str:
    """Check a human-supplied scope label, never certify scope from keywords.

    Words can occur in negations, examples, or cross-references. They can raise
    a conflict for review but cannot establish applicability. Mixed books need
    separately curated, scope-labelled excerpts before supporting candidates.
    """
    declared = item.get("population", "unspecified")
    if declared in {"adult", "pediatric"} and declared != case_population:
        return "mismatched"
    location = item.get("location") or {}
    headings = location.get("heading_path", []) if isinstance(location, dict) else []
    text = str(item.get("text", "")) + " " + str(headings)
    adult = bool(_ADULT_TERMS.search(text))
    pediatric = bool(_PEDIATRIC_TERMS.search(text))
    if (case_population == "adult" and pediatric) or (case_population == "pediatric" and adult):
        return "unverified" if adult == pediatric else "mismatched"
    if declared not in {"all", case_population}:
        return "unverified"
    return "matched"


def _filter_population_evidence(case: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    population = _case_population(case)
    counts = {"matched": 0, "mismatched": 0, "unverified": 0}
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for original in evidence:
        item = copy.deepcopy(original)
        applicability = _evidence_population(item, population) if population else "unverified"
        counts[applicability] += 1
        item["population_applicability"] = applicability
        if applicability == "matched":
            accepted.append(item)
        else:
            excluded.append({key: item.get(key) for key in
                             ("chunk_id", "doc_id", "document_version", "location",
                              "population", "population_applicability")})
    return accepted, {"case_population": population or "unknown", **counts,
                      "excluded": excluded, "policy_version": "population-label-1.0"}


def _deterministic_output(engine: RuleEngine, evaluations: list[dict[str, Any]], evidence: list[dict[str, Any]],
                          gate: str, limitations: list[str], case: dict[str, Any]) -> dict[str, Any]:
    blocked_codes = {code for x in evaluations if x.get("status") == "matched" and x.get("action") in {"avoid", "block"} for code in (x.get("drug_codes") or [])}
    avoid: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    evidence_ids = [str(x.get("chunk_id")) for x in evidence if x.get("chunk_id")]
    rule_ids = [str(x.get("rule_id")) for x in evaluations if x.get("status") == "matched" and x.get("action") == "allow_candidates"]
    for code in engine.candidate_drugs(case):
        item = {"drug_code": code, "reason": "來源藥敏為 S，未命中已記錄的同名過敏；檢索文件供審閱，尚未確認感染適用性。" if engine.reported_mode else "展示規則允許；仍需人工確認。", "rule_refs": rule_ids, "evidence_refs": evidence_ids}
        if code in blocked_codes:
            item["reason"] = "展示限制命中，應避免並由人工確認。"
            avoid.append(item)
        else:
            candidates.append(item)
    if gate == "blocked":
        candidates = []
    if engine.reported_mode:
        avoid = [{"drug_code": code, "reason": x["reason"], "rule_refs": [x["rule_id"]], "evidence_refs": []}
                 for x in evaluations if x.get("action") == "avoid" for code in x.get("drug_codes", [])]
    return {"candidates": candidates, "avoid": avoid, "limitations": list(dict.fromkeys(limitations))}


def _execute_workflow(case: dict[str, Any], mode: str, provider_kind: str, document_service: Any, run_id: str) -> dict[str, Any]:
    if mode not in {"rule-only", "rag-only", "single-agent"}:
        raise ValueError("unsupported baseline workflow mode")
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
    if not case.get("policy_refs") and case.get('evidence_scope') != 'reference':
        missing.append("policy_refs")
    if not case.get("ast_results"):
        missing.append("ast_results")
    nodes.append(_node("case_completeness", "completed", t, output={"summary": _summary(case), "missing_fields": missing}, version="case-summary-1.0"))

    t = time.perf_counter()
    evaluations = engine.evaluate(case)
    ast_output = {"source_report": copy.deepcopy(case.get("ast_results") or []), "system_result": "not_configured", "system_evaluations": [], "warnings": []}
    if case.get("ast_results"):
        standards_ok = all(x.get("standard") and x.get("standard_version") for x in case["ast_results"] if isinstance(x, dict))
        ast_output["system_result"] = "source_phenotype_reviewed" if engine.reported_mode else "evaluated_demo" if standards_ok else "needs_review"
        ast_output["system_evaluations"] = engine.evaluate_ast(case)
        if any(x['status'] != 'evaluated' for x in ast_output['system_evaluations']):
            ast_output['system_result'] = 'needs_review'
            missing.append('ast_results.unverified_or_conflicting')
        if not standards_ok and not engine.reported_mode:
            ast_output["warnings"].append("AST 標準版本未知，保留來源報告結果且不重新判讀。")
            missing.append("ast_results[].standard_or_version")
        if not engine.reported_mode and any(isinstance(x, dict) and (not x.get("unit") or not x.get("comparator")) for x in case["ast_results"]):
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
    query = evidence_query(case)
    if document_service is None:
        search_result = {"status": "not_configured", "evidence": [], "warnings": ["文件服務未設定"]}
    else:
        try:
            kwargs = {"scope": "reference"} if case.get("evidence_scope") == "reference" else {}
            search_result = document_service.search(query or "synthetic", policy_refs=case.get("policy_refs"), **kwargs)
        except Exception as exc:  # document service failures are data, never fatal to the whole trace
            search_result = {"status": "failed", "evidence": [], "warnings": ["文件檢索失敗"]}
            errors.append({"node_id": "evidence_retrieval", "code": "EVIDENCE_SEARCH_FAILED", "detail": type(exc).__name__})
    retrieved_evidence = [copy.deepcopy(x) for x in (search_result.get("evidence") or []) if isinstance(x, dict)]
    population_filter: dict[str, Any] | None = None
    if case.get("evidence_scope") == "reference":
        evidence, population_filter = _filter_population_evidence(case, retrieved_evidence)
        if population_filter["case_population"] == "unknown":
            missing.append("demographics.age_for_evidence")
        if retrieved_evidence and not evidence:
            missing.append("evidence.population_applicability")
    else:
        evidence = retrieved_evidence
    nodes.append(_node("evidence_retrieval", "completed" if search_result.get("status") in {"ok", "completed", "no_results"} else "blocked" if search_result.get('status') == 'conflict' else str(search_result.get("status", "completed")), t,
                       output={"status": search_result.get("status"), "warnings": search_result.get("warnings", []), "count": len(evidence),
                               "retrieved_count": len(retrieved_evidence), "population_filter": population_filter,
                               "retrieval_method": search_result.get("retrieval_method"), "embedding_model": search_result.get("embedding_model")}, version="retrieval-2.1",
                       evidence_refs=[str(x.get("chunk_id")) for x in evidence if x.get("chunk_id")]))

    supported = engine.supports(_get(case, "microbiology.organism"))
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
    demo_adjustments = []
    quarantined_raw: Any = None
    provider_attempted = mode == "rule-only"
    t = time.perf_counter()
    if mode == "rule-only":
        output = _deterministic_output(engine, evaluations, evidence, gate, limitations, case)
    elif population_filter is not None and not evidence:
        # No applicable reference input: do not spend a generation call on an
        # output which the final gate must withhold.
        candidate_status = "skipped"
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
                generation_allowlist = engine.allowed_drugs()
                if engine.reported_mode:
                    # Baselines receive source-tested names, not the entire cohort vocabulary.
                    generation_allowlist = list(dict.fromkeys(x['drug_code'] for x in case.get('ast_results', []) if x['drug_code'] in engine.allowed_drugs()))
                summary_for_provider = _summary(case)
                context = {"mode": mode, "demo_relaxed": True, "case_summary": summary_for_provider, "allowed_drugs": generation_allowlist,
                           "evidence": evidence, "rule_refs": []}
                if engine.reported_mode:
                    context['allowed_avoid'] = list(dict.fromkeys(x['drug_code'] for x in case.get('ast_results', [])))
                if mode == "rag-only":
                    context["rule_refs"] = []
                elif mode == "single-agent":
                    context["rule_refs"] = []
                    context['case_summary']['ast_results'] = copy.deepcopy(case.get('ast_results', []))
                generated = provider.generate(context)
                quarantined_raw = copy.deepcopy(generated.get("output")) if isinstance(generated, dict) else None
                provider_meta.update({k: generated.get(k) for k in ("model", "usage", "retries", "is_mock") if k in generated})
                provider_rule_refs = []
                candidate_payload = copy.deepcopy(generated.get("output"))
                candidate_payload, repaired = normalize_demo_output(candidate_payload,
                    allowed_drugs=set(engine.candidate_drugs(case)),
                    allowed_avoid={code for x in evaluations if x.get('action') == 'avoid' for code in x.get('drug_codes', [])} if engine.reported_mode else set(engine.allowed_drugs()),
                    allowed_rules=set(provider_rule_refs), allowed_evidence={str(x.get('chunk_id')) for x in evidence},
                    require_rule_refs=False, require_evidence_refs=bool(evidence))
                demo_adjustments = sorted(set(generated.get('demo_adjustments', []) + context.get('demo_adjustments', []) + repaired))
                validated, validation_errors = validate_provider_output(candidate_payload, allowed_drugs=set(engine.candidate_drugs(case)),
                                                                       allowed_avoid={code for x in evaluations if x.get('action') == 'avoid' for code in x.get('drug_codes', [])} if engine.reported_mode else None,
                                                                       allowed_rules=provider_rule_refs,
                                                                       allowed_evidence={str(x.get("chunk_id")) for x in evidence},
                                                                       require_rule_refs=False,
                                                                       require_evidence_refs=mode != "rule-only" and bool(evidence))
                if validation_errors:
                    candidate_status = "failed"
                    errors.append({"node_id": "candidate_presentation", "code": "OUTPUT_SCHEMA_INVALID", "validation_errors": validation_errors})
                elif not validated.get("candidates"):
                    candidate_status = "needs_confirmation"
                    errors.append({"node_id": "candidate_presentation", "code": "NO_VALID_CANDIDATES"})
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
        if engine.reported_mode:
            # Source exclusions cannot disappear because a model omits them.
            output['avoid'] = safe_avoid
            limitations = limitations + ["敏感選項不等於建議治療；感染適用性、交叉過敏與腎功能調整仍需核對。", "引用片段為檢索結果，不代表每項藥物已獲指引支持。"]
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
    nodes[-1]['demo_adjustments'] = demo_adjustments
    final_gate = "blocked" if candidate_status == "failed" else ("needs_confirmation" if candidate_status == "needs_confirmation" and gate == "ready_for_review" else gate)
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


def execute(case: dict[str, Any], mode: str, provider_kind: str = "unconfigured", document_service: Any = None, run_id: str | None = None, *, rules_snapshot: dict | None = None, checkpoint=None) -> dict[str, Any]:
    if mode not in {"rule-only", "rag-only", "single-agent", "multi-agent"}:
        raise ValueError("unsupported workflow mode")
    if provider_kind not in {"unconfigured", "mock", "live"}:
        raise ValueError("unsupported provider kind")
    run_id = run_id or str(uuid.uuid4())
    # Distinct runners own their information scope and provider semantics.
    from app.agents.runners import RUNNERS
    token = _PINNED_RULES.set(copy.deepcopy(rules_snapshot))
    try:
        if mode == "multi-agent":
            from .v2 import execute_v2
            return execute_v2(case, provider_kind, document_service, run_id, checkpoint=checkpoint)
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
    if "v2_candidate_boundary" in run or run.get("agent_execution") is not None or run.get("mode") == "multi-agent-v2":
        boundary = run.get("v2_candidate_boundary") or {}
        allowed &= set(boundary.get("allowed_drugs", []))
        evidence_by_drug = boundary.get("evidence_by_drug", {})
        for candidate in proposed.get("candidates", []):
            if isinstance(candidate, dict):
                refs = candidate.get("evidence_refs")
                code = candidate.get("drug_code")
                if not isinstance(code, str) or not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs) or not refs or not set(refs) <= set(evidence_by_drug.get(code, [])):
                    raise ValueError("v2 review requires the pinned per-drug specialist evidence")
    evals = run.get("rule_evaluations") or []
    hard_avoid = {x.get("drug_code") for x in (run.get("output") or {}).get("avoid", []) if isinstance(x, dict)}
    review_evidence = run.get("evidence_snapshots", [])
    if isinstance(case_snapshot, dict) and case_snapshot.get("evidence_scope") == "reference":
        review_evidence, _ = _filter_population_evidence(case_snapshot, review_evidence)
        if proposed.get("candidates") and not review_evidence:
            raise ValueError("review requires population-labelled evidence; re-run after confirming document scope")
    validated, errors = validate_provider_output(proposed, allowed_drugs=allowed,
                                                 allowed_avoid=hard_avoid if engine.reported_mode else None,
                                                 allowed_rules={str(x.get("rule_id")) for x in evals},
                                                 allowed_evidence={str(x.get("chunk_id")) for x in review_evidence},
                                                 require_rule_refs=bool(evals), require_evidence_refs=bool(run.get("evidence_snapshots")))
    if errors or validated is None:
        raise ValueError("review output rejected: " + ",".join(errors))
    if any(x.get("drug_code") in hard_avoid for x in validated.get("candidates", [])):
        raise ValueError("review cannot move an avoided drug into candidates")
    if engine.reported_mode:
        validated['avoid'] = copy.deepcopy((run.get('output') or {}).get('avoid', []))
    return {"valid": True, "output": {**validated, "run_id": run.get("run_id"), "demo_only": True, "gate_status": run.get("gate_status")}}
