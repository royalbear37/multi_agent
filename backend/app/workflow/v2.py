"""Bounded five-agent orchestration with immutable messages and fail-closed gates."""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from app.agents import runtime_v2 as runtime
from app.agents.contracts_v2 import ASTFacts, CaseFacts, Evidence
from app.providers.service import ProviderError
from app.rules.engine import RuleEngine
from .safety import forbidden_text, validate_provider_output, normalize_demo_output


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def project(case: dict, evidence: list) -> tuple[dict, list, list]:
    def pick(obj, keys):
        return {k: obj[k] for k in keys if k in (obj or {})}
    facts = {
        **pick(case.get("microbiology"), ("organism", "specimen", "report_status")),
        **pick(case.get("encounter"), ("infection_site", "severity")),
        "clinical_context": (case.get("encounter") or {}).get("context"),
        "demographics": pick(case.get("demographics"), ("age", "sex", "weight", "weight_unit")),
        "renal": pick(case.get("renal"), ("egfr", "unit", "dialysis_status")),
        "allergies": {"status": (case.get("allergies") or {}).get("status", "unknown"),
                      "items": [pick(x, ("drug_code", "reaction", "severity"))
                                for x in (case.get("allergies") or {}).get("items", [])]},
        "medication_codes": [x["drug_code"] for x in case.get("medications", [])],
        "data_origin": case.get("data_origin", "synthetic"),
        "simulated_fields": (case.get("provenance") or {}).get("simulated_fields", []),
    }
    facts = CaseFacts.model_validate(runtime.redact(facts)).model_dump(mode="json")
    ast = [ASTFacts.model_validate(runtime.redact(pick(x, ASTFacts.model_fields))).model_dump(mode="json")
           for x in case.get("ast_results", [])]
    excerpts = [Evidence.model_validate(runtime.redact({
        "chunk_id": x["chunk_id"], "doc_id": x["doc_id"],
        "document_version": str(x.get("document_version", "")), "text": x.get("text", ""),
        "page": (x.get("location") or {}).get("page"), "population": x.get("population"),
        "is_synthetic": x.get("is_synthetic", False), "external_model_allowed": x.get("external_model_allowed", False),
    })).model_dump(mode="json") for x in evidence]
    return facts, ast, excerpts


def normalize_demo_assessment(agent, raw, data=None):
    """Tolerate presentation differences; never create drug choices or citations."""
    if not isinstance(raw, dict):
        return raw, []
    if agent.id == 'synthesis_agent' and data is not None:
        return normalize_demo_output(raw, allowed_drugs=set(data['allowed_drugs']),
            allowed_avoid=set(data['allowed_avoid']), allowed_rules=set(data['rule_refs']),
            allowed_evidence={e['chunk_id'] for e in data['evidence']},
            require_rule_refs=True, require_evidence_refs=True)
    notes = []
    def message(model, value):
        if not isinstance(value, dict):
            return value
        result = {k: copy.deepcopy(v) for k, v in value.items() if k in model.model_fields}
        if set(value) - set(result):
            notes.append('EXTRA_FIELDS_IGNORED')
        for key in ('limitations', 'missing_fields', 'evidence_refs', 'rule_refs', 'avoid'):
            if key in model.model_fields and result.get(key) is None:
                result[key] = []
                notes.append('EMPTY_LIST_DEFAULTED')
        return result
    output = message(agent.output_type, raw)
    from app.agents.contracts_v2 import Finding, Candidate, DrugSupport
    for key, model in (('findings', Finding), ('candidates', Candidate), ('avoid', Candidate), ('support', DrugSupport)):
        if isinstance(output.get(key), list):
            output[key] = [message(model, x) for x in output[key]]
    if isinstance(output.get('needs_confirmation'), str) and output['needs_confirmation'].lower() in {'true', 'false'}:
        output['needs_confirmation'] = output['needs_confirmation'].lower() == 'true'
        notes.append('BOOLEAN_NORMALIZED')
    if agent.id == 'evidence_agent' and isinstance(output.get('support'), list):
        # Empty citations express no support; omit that entry instead of treating
        # it as a schema failure. Never supply citations on the model's behalf.
        unsupported = {x.get('drug_code') for x in output['support']
                       if isinstance(x, dict) and x.get('evidence_refs') == []}
        if unsupported:
            output['support'] = [x for x in output['support']
                                 if not isinstance(x, dict) or x.get('drug_code') not in unsupported]
            if isinstance(output.get('supported_drugs'), list):
                output['supported_drugs'] = [x for x in output['supported_drugs'] if x not in unsupported]
            notes.append('EMPTY_SUPPORT_OMITTED')
    # Omit disallowed free text instead of blocking the entire demo. References,
    # per-drug support and drug identifiers still pass the original validators.
    for item in output.get('findings', []) if isinstance(output.get('findings'), list) else []:
        if isinstance(item, dict) and isinstance(item.get('statement'), str) and forbidden_text(item['statement']):
            item['statement'] = '部分模型說明已省略，請核對來源資料。'
            notes.append('TEXT_WITHHELD')
    if isinstance(output.get('limitations'), list):
        for i, value in enumerate(output['limitations']):
            if isinstance(value, str) and (not value.strip() or forbidden_text(value)):
                output['limitations'][i] = '部分模型限制說明已省略；本結果僅供展示與人工核對。'
                notes.append('TEXT_WITHHELD')
    if agent.id == 'evidence_agent' and data is not None:
        evidence_ids = {x['chunk_id'] for x in data.get('evidence', [])}
        allowed = set(data.get('allowed_drugs', []))
        valid_support = {}
        for entry in output.get('support', []) if isinstance(output.get('support'), list) else []:
            if not isinstance(entry, dict) or not isinstance(entry.get('drug_code'), str):
                notes.append('INVALID_SUPPORT_OMITTED')
                continue
            code, refs, explanation = entry['drug_code'], entry.get('evidence_refs'), entry.get('explanation')
            if (code not in allowed or not isinstance(refs, list)
                    or not all(isinstance(ref, str) for ref in refs)
                    or not refs or not set(refs) <= evidence_ids
                    or not isinstance(explanation, str) or not explanation.strip()
                    or len(explanation) > 2000 or forbidden_text(explanation)):
                notes.append('INVALID_SUPPORT_OMITTED')
                continue
            if code in valid_support:
                notes.append('DUPLICATE_SUPPORT_MERGED')
                previous = valid_support[code]
                previous['evidence_refs'] = list(dict.fromkeys(previous['evidence_refs'] + refs))
            else:
                valid_support[code] = {**entry, 'evidence_refs': list(dict.fromkeys(refs))}
        support = list(valid_support.values())
        if output.get('support') != support or output.get('supported_drugs') != list(valid_support):
            notes.append('SUPPORT_LIST_RECONCILED')
        output['support'], output['supported_drugs'] = support, list(valid_support)
        if isinstance(output.get('findings'), list):
            for finding in output['findings']:
                if not isinstance(finding, dict):
                    continue
                refs = finding.get('evidence_refs')
                if isinstance(refs, list):
                    clean = list(dict.fromkeys(r for r in refs if isinstance(r, str) and r in evidence_ids))
                    if clean != refs or finding.get('rule_refs'):
                        finding.update(statement='摘要引用不完整，請以逐藥支持紀錄核對。', evidence_refs=clean, rule_refs=[])
                        notes.append('SUMMARY_REFERENCES_NORMALIZED')
        if notes:
            if isinstance(output.get('limitations'), list):
                output['limitations'] = output['limitations'][:19] + ['Demo 僅保留可核對的逐藥支持；不完整項目已省略，未補造引用。']
            output['needs_confirmation'] = True
    return output, sorted(set(notes))


def validate_assessment(agent, raw, data):
    output = agent.output_type.model_validate(raw).model_dump(mode="json")
    if runtime.redact(output) != output:
        raise ValueError("secret-like output")
    texts = output["limitations"] + ([x["reason"] for x in output["candidates"] + output["avoid"]]
                                      if agent.id == "synthesis_agent" else [x["statement"] for x in output["findings"]])
    if any(not text.strip() or len(text) > 2000 or forbidden_text(text) for text in texts):
        raise ValueError("forbidden output content")
    if agent.id == "synthesis_agent":
        checked, errors = validate_provider_output(
            output, allowed_drugs=set(data["allowed_drugs"]), allowed_avoid=set(data["allowed_avoid"]),
            allowed_rules=set(data["rule_refs"]), allowed_evidence={e["chunk_id"] for e in data["evidence"]},
            require_rule_refs=True, require_evidence_refs=True)
        if errors:
            raise ValueError("synthesis output rejected")
        support = {x["drug_code"]: set(x["evidence_refs"]) for x in data["evidence_assessment"]["support"]}
        for candidate in checked["candidates"]:
            if not set(candidate["evidence_refs"]) <= support.get(candidate["drug_code"], set()):
                raise ValueError("synthesis changed the specialist's per-drug evidence")
        return checked
    rules = set(data.get("rule_refs", []))
    evidence = {x["chunk_id"] for x in data.get("evidence", [])}
    for finding in output["findings"]:
        if not set(finding["rule_refs"]) <= rules or not set(finding["evidence_refs"]) <= evidence:
            raise ValueError("unknown reference")
    scopes = {"ast_agent": ("reviewed_drugs", {x["drug_code"] for x in data.get("ast_results", [])}),
              "evidence_agent": ("supported_drugs", set(data.get("allowed_drugs", []))),
              "clinical_agent": ("excluded_drugs", set(data.get("allowed_drugs", []) + data.get("hard_exclusions", [])))}
    if agent.id in scopes:
        field, allowed = scopes[agent.id]
        if not set(output[field]) <= allowed or len(output[field]) != len(set(output[field])):
            raise ValueError("unknown or duplicate drug")
    if agent.id == "evidence_agent":
        supported = output["supported_drugs"]
        support = output["support"]
        if sorted(supported) != sorted(x["drug_code"] for x in support):
            raise ValueError("each supported drug needs exactly one support record")
        for item in support:
            if not set(item["evidence_refs"]) <= evidence or forbidden_text(item["explanation"]):
                raise ValueError("invalid per-drug support")
    return output


def execute_v2(case, provider_kind, document_service, run_id, checkpoint=None):
    from .engine import _execute_workflow
    start = time.perf_counter()
    # Reuse the tested deterministic pipeline with generation disabled.
    run = _execute_workflow(copy.deepcopy(case), "rule-only", "unconfigured", document_service, run_id)
    preflight_output = run.get("output")
    run.update(mode="multi-agent", is_mock=provider_kind == "mock", output=None,
               model=None, usage=None, cost=None,
               raw_baseline={"withheld": True, "available": False, "payload": None})
    run["versions"]["workflow"] = "multi-agent-v2.4-demo"
    run["versions"]["agent_contract"] = "agents-v2.4-demo"
    run["nodes"] = [n for n in run["nodes"] if n["node_id"] not in {"candidate_presentation", "human_review"}]
    traces, outputs, span_ids = [], {}, {}
    max_calls = runtime.setting("LLM_V2_MAX_CALLS", 8, 1, 10)
    max_retries = runtime.setting("LLM_V2_MAX_RETRIES", 1, 0, 1)
    deadline = start + runtime.setting("LLM_V2_TIMEOUT_SECONDS", 120, 10, 300)
    calls, stop, candidate_valid = 0, None, False
    def save_progress():
        if checkpoint:
            snapshot = copy.deepcopy(run)
            snapshot.update(status="running", output=None, nodes=copy.deepcopy(run["nodes"] + traces),
                            agent_execution={"calls": calls, "max_calls": max_calls})
            checkpoint(snapshot)
    if run["gate_status"] != "ready_for_review":
        stop = "PREFLIGHT_WITHHELD"
    try:
        facts, ast, evidence = project(case, run["evidence_snapshots"])
    except (ValueError, TypeError, KeyError):
        facts, ast, evidence = {}, [], []
        stop = "AGENT_INPUT_INVALID"
        run["gate_status"] = "blocked"
        run["errors"].append({"node_id": "case_agent", "code": stop})
    engine = RuleEngine(config=run["versions"]["rules_snapshot"])
    allowed = engine.candidate_drugs(case)
    hard_avoid = copy.deepcopy(run["safety_summary"].get("avoid", []))
    hard_codes = [x["drug_code"] for x in hard_avoid]
    rule_refs = [x["rule_id"] for x in run["rule_evaluations"]]
    for agent in runtime.AGENTS:
        tick = time.perf_counter()
        span_id = str(uuid.uuid4())
        trace = {"node_id": agent.id, "agent_id": agent.id, "span_id": span_id, "run_id": run_id,
                 "parent_span_ids": [span_ids[x] for x in agent.dependencies],
                 "depends_on": list(agent.dependencies), "status": "skipped", "started_at": utc(),
                 "version": runtime.PROMPT_VERSION, "prompt_version": runtime.PROMPT_VERSION,
                 "prompt_hash": digest(runtime.COMMON + agent.instruction),
                 "input_schema": agent.input_type.__name__, "output_schema": agent.output_type.__name__,
                 "input": None, "output": None, "model": None, "provider_kind": provider_kind,
                 "is_mock": provider_kind == "mock", "usage": None, "attempts": [], "errors": [],
                 "rule_refs": [], "evidence_refs": [], "retry_count": 0}
        span_ids[agent.id] = span_id
        traces.append(trace)
        if stop:
            trace["skip_reason"] = stop
        else:
            try:
                data = {"facts": facts}
                if agent.dependencies:
                    data["case_assessment"] = outputs["case_agent"]
                if agent.id == "case_agent":
                    data.update(ast_results=ast)
                elif agent.id == "ast_agent":
                    data.update(ast_results=ast, allowed_drugs=allowed, rule_refs=rule_refs)
                elif agent.id == "evidence_agent":
                    data.update(evidence=evidence, allowed_drugs=allowed)
                elif agent.id == "clinical_agent":
                    data.update(allowed_drugs=allowed, hard_exclusions=hard_codes, rule_refs=rule_refs)
                elif agent.id == "synthesis_agent":
                    narrowed = [x for x in allowed if x in outputs["ast_agent"]["reviewed_drugs"]
                                and x in outputs["evidence_agent"]["supported_drugs"]
                                and x not in outputs["clinical_agent"]["excluded_drugs"] and x not in hard_codes]
                    if not narrowed:
                        raise ProviderError("AGENT_NO_SUPPORTED_CANDIDATES")
                    run["v2_candidate_boundary"] = {
                        "allowed_drugs": list(narrowed),
                        "evidence_by_drug": {x["drug_code"]: list(x["evidence_refs"])
                                             for x in outputs["evidence_agent"]["support"] if x["drug_code"] in narrowed},
                    }
                    data.update(ast_assessment=outputs["ast_agent"], evidence_assessment=outputs["evidence_agent"],
                                clinical_assessment=outputs["clinical_agent"], evidence=evidence,
                                allowed_drugs=narrowed, allowed_avoid=hard_codes, rule_refs=rule_refs)
                data = agent.input_type.model_validate(copy.deepcopy(data)).model_dump(mode="json")
                if len(json.dumps(data, ensure_ascii=False)) > 100000:
                    raise ProviderError("AGENT_INPUT_TOO_LARGE")
                trace["input"], trace["input_hash"] = copy.deepcopy(data), digest(data)
                provider = runtime.AgentProvider(provider_kind, agent)
                trace["model"] = provider.model or None
                provider.check(case, data)
                raw = None
                for attempt_no in range(max_retries + 1):
                    remaining = deadline - time.perf_counter()
                    if calls >= max_calls or remaining < 1:
                        raise ProviderError("AGENT_BUDGET_EXCEEDED")
                    calls += 1
                    attempt_tick = time.perf_counter()
                    attempt = {"attempt": attempt_no + 1, "started_at": utc(), "status": "running", "usage": None}
                    trace["attempts"].append(attempt)
                    trace["status"] = "running"
                    save_progress()
                    try:
                        reply = provider.complete(agent, copy.deepcopy(data), timeout=min(20.0, remaining))
                        attempt.update(status="completed", usage=reply.get("usage"), response_id=reply.get("response_id"))
                        raw = reply.get("output")
                        break
                    except ProviderError as exc:
                        attempt.update(status="failed", error_code=exc.code)
                        if not exc.retryable or attempt_no == max_retries:
                            raise
                    except Exception:
                        attempt.update(status="failed", error_code="AGENT_EXECUTION_FAILED")
                        raise
                    finally:
                        attempt.update(finished_at=utc(), elapsed_ms=round((time.perf_counter() - attempt_tick) * 1000, 3))
                raw, adjustments = normalize_demo_assessment(agent, raw, data)
                trace['demo_adjustments'] = adjustments
                output = validate_assessment(agent, raw, data)
                trace["attempts"][-1]["validation_status"] = "valid"
                if time.perf_counter() > deadline:
                    raise ProviderError("AGENT_BUDGET_EXCEEDED")
                outputs[agent.id] = copy.deepcopy(output)
                trace.update(status="completed", output=copy.deepcopy(output), output_hash=digest(output),
                             rule_refs=data.get("rule_refs", []), evidence_refs=[e["chunk_id"] for e in data.get("evidence", [])])
                if agent.id == "synthesis_agent" and not output["candidates"]:
                    raise ProviderError("AGENT_NO_SUPPORTED_CANDIDATES")
                if agent.id != "synthesis_agent" and (output["needs_confirmation"] or output.get("missing_fields")
                                                     or (agent.id == "evidence_agent" and not output["supported_drugs"])):
                    trace["status"] = "needs_confirmation"
                    trace["errors"] = [{"code": "AGENT_NEEDS_CONFIRMATION"}]
                    run["errors"].append({"node_id": agent.id, "code": "AGENT_NEEDS_CONFIRMATION"})
                    run['safety_summary']['limitations'].append(
                        f'{agent.id} 有待確認事項；本次為寬鬆 demo，候選僅供展示，仍需人工核對。')
            except (ProviderError, ValidationError, ValueError, TypeError, KeyError) as exc:
                stop = exc.code if isinstance(exc, ProviderError) else "AGENT_SCHEMA_INVALID"
                if isinstance(exc, ValidationError):
                    trace['validation_issues'] = [{'type': e['type']} for e in exc.errors(include_input=False, include_context=False)][:10]
                elif stop == 'AGENT_SCHEMA_INVALID':
                    reasons = {'secret-like output', 'forbidden output content', 'synthesis output rejected',
                               "synthesis changed the specialist's per-drug evidence", 'unknown reference',
                               'unknown or duplicate drug', 'each supported drug needs exactly one support record',
                               'invalid per-drug support'}
                    trace['validation_issues'] = [{'type': type(exc).__name__,
                                                   'reason': str(exc) if str(exc) in reasons else 'invalid_structure'}]
                if stop == "AGENT_SCHEMA_INVALID" and trace["attempts"]:
                    trace["attempts"][-1]["validation_status"] = "invalid"
                if trace["status"] != "needs_confirmation":
                    trace["status"] = "not_configured" if stop == "MODEL_NOT_CONFIGURED" else "failed"
                trace["errors"] = [{"code": stop}]
                run["errors"].append({"node_id": agent.id, "code": stop})
                run["gate_status"] = "needs_confirmation" if stop in {
                    "MODEL_NOT_CONFIGURED", "NON_SYNTHETIC_INPUT", "AGENT_NEEDS_CONFIRMATION", "AGENT_NO_SUPPORTED_CANDIDATES"
                } else "blocked"
            except Exception:
                stop = "AGENT_EXECUTION_FAILED"
                trace.update(status="failed", errors=[{"code": stop}])
                run["errors"].append({"node_id": agent.id, "code": stop})
                run["gate_status"] = "blocked"
        trace.update(finished_at=utc(), elapsed_ms=round((time.perf_counter() - tick) * 1000, 3),
                     retry_count=max(0, len(trace["attempts"]) - 1))
        trace["usage"] = sum_usage(trace["attempts"])
        save_progress()
    if not stop:
        proposed = copy.deepcopy(outputs["synthesis_agent"])
        proposed["avoid"] = hard_avoid
        limitations = run["safety_summary"]["limitations"] + proposed["limitations"]
        for output in outputs.values():
            limitations += output.get("limitations", [])
        proposed["limitations"] = list(dict.fromkeys(limitations))
        # Repeat the established final review validator using pinned rules and evidence.
        from .engine import validate_review
        try:
            check_run = {**run, "output": preflight_output, "gate_status": "ready_for_review"}
            run["output"] = validate_review(check_run, proposed)["output"]
            candidate_valid = True
        except ValueError:
            run["gate_status"] = "blocked"
            run["errors"].append({"node_id": "candidate_presentation", "code": "V2_FINAL_VALIDATION_FAILED"})
    run["nodes"].extend(traces)
    run["nodes"].extend([
        {"node_id": "candidate_presentation", "status": "completed" if candidate_valid else "blocked" if traces[-1]["attempts"] else "skipped",
         "output": {"attempted": bool(traces[-1]["attempts"]), "schema_valid": candidate_valid,
                    "published": candidate_valid, "withheld": not candidate_valid}, "version": "v2-final-gate-1"},
        {"node_id": "human_review", "status": "pending", "output": {"action_required": True}},
    ])
    run["status"] = "awaiting_review" if candidate_valid else "partial" if stop == "MODEL_NOT_CONFIGURED" else "blocked" if run["gate_status"] == "blocked" else "awaiting_review"
    run["safety_summary"]["gate_status"] = run["gate_status"]
    run["usage"] = sum_usage([a for t in traces for a in t["attempts"]])
    run["models"] = sorted({t["model"] for t in traces if t["attempts"] and t["model"]})
    run["model"] = run["models"][0] if len(run["models"]) == 1 else None
    run["agent_execution"] = {"workflow_version": "multi-agent-v2.4-demo", "calls": calls, "max_calls": max_calls,
                              "completed_agents": sum(t["status"] == "completed" for t in traces),
                              "usage_complete": all(all(k in (a.get("usage") or {}) for k in ("prompt_tokens", "completion_tokens", "total_tokens")) for t in traces for a in t["attempts"]) and calls > 0}
    run["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return run


def sum_usage(attempts):
    known = [a["usage"] for a in attempts if a.get("usage")]
    return {key: sum(u.get(key, 0) for u in known) for key in ("prompt_tokens", "completion_tokens", "total_tokens") if any(key in u for u in known)} if known else None


def public_agent_nodes(nodes, *, publish: bool):
    result = copy.deepcopy(nodes)
    for node in result:
        if node.get("agent_id") and (not publish or node.get("status") not in {"completed", "needs_confirmation"}):
            node["input"] = None
            node["output"] = None
            node["content_withheld"] = True
    return result
