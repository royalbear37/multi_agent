"""Pure observations. No model, production validation or medical rules are called."""
from collections import Counter
from math import isfinite

ROLES = ("case_agent", "ast_agent", "evidence_agent", "clinical_agent", "synthesis_agent", "evidence_audit")
AST_LABELS = {"susceptible", "intermediate", "resistant", "unknown", "conflicting"}
FINAL_LABELS = {"reviewable", "pending", "avoid", "not_selected"}
ROLE_FIELDS = {
    "ast_agent": ("assessment", AST_LABELS, {"unknown"}),
    "evidence_agent": ("status", {"supported", "unsupported", "uncertain"}, {"uncertain"}),
    "clinical_agent": ("status", {"no_identified_risk", "caution", "avoid", "unknown"}, {"unknown"}),
    "synthesis_agent": ("status", FINAL_LABELS, {"pending"}),
    "evidence_audit": ("verdict", {"supported", "unsupported", "uncertain"}, {"uncertain"}),
}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0


def ratio(num, den):
    return {"status": "evaluated", "value": num / den, "numerator": num, "denominator": den} if den else {
        "status": "not_evaluated", "reason": "zero_denominator", "value": None, "numerator": num, "denominator": den}


def unavailable(reason, status="not_evaluated", **details):
    return {"status": status, "reason": reason, "details": details}


def category(raw):
    if not isinstance(raw, str):
        return None
    return {"s": "susceptible", "susceptible": "susceptible", "i": "intermediate", "intermediate": "intermediate",
            "r": "resistant", "resistant": "resistant"}.get(raw.strip().lower())


def source_observations(snapshot):
    """Record selected and reported categories separately; never infer from MIC."""
    rows = snapshot.get("ast_results")
    if not isinstance(rows, list) or any(not isinstance(x, dict) or not isinstance(x.get("drug_code"), str)
                                         or not x["drug_code"] for x in rows):
        raise ValueError("invalid_or_missing_ast_results")
    grouped = {}
    for index, row in enumerate(rows):
        if any(row.get(k) is not None and not isinstance(row[k], str) for k in
               ("interpretation_basis", "reported_sir", "source_phenotype", "clsi_2022_phenotype")):
            raise ValueError("invalid_ast_source_field_type")
        basis = row.get("interpretation_basis")
        field = {"CLSI_2022_pheno": "clsi_2022_phenotype", "source_report": "source_phenotype", "legacy": "reported_sir"}.get(basis)
        selected = category(row.get(field)) if field else None
        reported = category(row.get("reported_sir"))
        grouped.setdefault(row["drug_code"], []).append({
            "index": index, "basis": basis, "field": field, "raw_value": row.get(field) if field else None,
            "selected": selected, "reported": reported,
            "cross_field_conflict": bool(selected and reported and selected != reported),
        })
    result = {}
    for drug, values in grouped.items():
        selected = {x["selected"] for x in values if x["selected"]}
        reported = {x["reported"] for x in values if x["reported"]}
        flags = {"selected_source_conflict": len(selected) > 1, "reported_source_conflict": len(reported) > 1,
                 "cross_field_conflict": any(x["cross_field_conflict"] for x in values)}
        ambiguous = (any(flags.values()) or len({x["basis"] for x in values}) > 1
                     or (selected and any(x["selected"] is None for x in values)))
        unknown_basis = any(x["field"] is None for x in values)
        expected = next(iter(selected)) if len(selected) == 1 else "unknown" if not selected else None
        result[drug] = {"source_rows": values, "flags": flags, "expected": expected,
                        "policy_ambiguous": bool(ambiguous), "unknown_basis": unknown_basis}
    return result


def source_consistency(observation, predicted):
    if observation["unknown_basis"]:
        return unavailable("unknown_interpretation_basis")
    if observation["policy_ambiguous"]:
        return unavailable("source_conflict_requires_independent_policy", **observation)
    if not isinstance(predicted, str) or predicted not in AST_LABELS:
        return unavailable("missing_or_invalid_ast_assessment", "invalid_output")
    result = ratio(int(predicted == observation["expected"]), 1)
    result["details"] = {"observed": predicted, "source_category": observation["expected"],
                         "policy": "selected-source-unambiguous-v1", "clinical_gold": False}
    return result


def drug_rows(value):
    if not isinstance(value, list) or any(not isinstance(x, dict) or not isinstance(x.get("drug_code"), str)
                                          or not x["drug_code"] for x in value):
        return {}, ["missing_or_malformed_drug_rows"]
    counts = Counter(x["drug_code"] for x in value)
    errors = [f"duplicate_drug:{x}" for x, count in counts.items() if count > 1]
    return {x["drug_code"]: x for x in value if counts[x["drug_code"]] == 1}, errors


def completeness(rows, universe, field, allowed):
    indexed, errors = drug_rows(rows)
    missing = sorted(set(universe) - set(indexed))
    extra = sorted(set(indexed) - set(universe))
    illegal = sorted(x for x, row in indexed.items() if not isinstance(row.get(field), str) or row[field] not in allowed)
    num = sum(x in indexed and x not in illegal for x in universe)
    details = {"missing_drugs": missing, "extra_drugs": extra, "illegal_labels": illegal, "errors": errors,
               "valid_rows": num, "expected_rows": len(universe)}
    if errors or missing or extra or illegal:
        return unavailable("incomplete_or_invalid_rows", "invalid_output", **details)
    result = ratio(num, len(universe))
    result["details"] = details
    return result


def abstention(rows, universe, field, allowed, abstentions):
    complete = completeness(rows, universe, field, allowed)
    if complete["status"] != "evaluated":
        return complete
    indexed, _ = drug_rows(rows)
    return ratio(sum(indexed[x][field] in abstentions for x in universe), len(universe))


def citations(output, snapshots):
    """Only output evidence_refs / quotes; never count retrieved input as citations."""
    if not isinstance(output, dict):
        return {name: unavailable("output_unavailable") for name in ("citation_id_locatability", "citation_location_availability", "quote_exact_match")}
    if not isinstance(snapshots, list) or any(not isinstance(s, dict) or not isinstance(s.get("chunk_id"), str) for s in snapshots):
        return {name: unavailable("snapshots_unavailable") for name in ("citation_id_locatability", "citation_location_availability", "quote_exact_match")}
    counts = Counter(s["chunk_id"] for s in snapshots)
    if any(v > 1 for v in counts.values()):
        return {name: unavailable("ambiguous_snapshot_ids", "invalid_output") for name in ("citation_id_locatability", "citation_location_availability", "quote_exact_match")}
    index = {s["chunk_id"]: s for s in snapshots}
    refs, quotes, malformed = [], [], []

    def walk(value, path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "evidence_refs":
                    if not isinstance(child, list) or any(not isinstance(x, str) or not x for x in child):
                        malformed.append(path + "/evidence_refs")
                    else:
                        refs.extend(dict.fromkeys(child))
                elif key == "quotes":
                    if not isinstance(child, list):
                        malformed.append(path + "/quotes")
                    else:
                        for q in child:
                            if not isinstance(q, dict) or not isinstance(q.get("chunk_id"), str) or not isinstance(q.get("quote"), str) or not q["quote"]:
                                malformed.append(path + "/quotes")
                            else:
                                refs.append(q["chunk_id"])
                                quotes.append(q)
                else:
                    walk(child, path + "/" + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, path + "/" + str(i))
    walk(output)
    if malformed:
        return {name: unavailable("malformed_citations", "invalid_output", paths=malformed) for name in ("citation_id_locatability", "citation_location_availability", "quote_exact_match")}
    # A link is a statement occurrence; copied outputs are scored under separate targets.
    return {
        "citation_id_locatability": ratio(sum(ref in index for ref in refs), len(refs)),
        "citation_location_availability": ratio(sum(bool(index.get(ref, {}).get("location")) for ref in refs), len(refs)),
        "quote_exact_match": ratio(sum(isinstance(index.get(q["chunk_id"], {}).get("text"), str)
                                       and q["quote"] in index[q["chunk_id"]]["text"] for q in quotes), len(quotes)),
    }


def token_statistics(nodes, is_mock):
    if is_mock:
        return {name: unavailable("mock_has_no_model_usage") for name in ("input_tokens", "output_tokens", "total_tokens")}
    attempts = [a for n in nodes for a in n.get("attempts", [])] if all(isinstance(n.get("attempts", []), list) for n in nodes) else None
    if attempts is None or any(not isinstance(a, dict) for a in attempts):
        return {name: unavailable("invalid_attempts", "invalid_output") for name in ("input_tokens", "output_tokens", "total_tokens")}
    if not attempts:
        return {name: unavailable("attempt_usage_unavailable") for name in ("input_tokens", "output_tokens", "total_tokens")}
    output = {}
    for name, aliases in (("input_tokens", ("input_tokens", "prompt_tokens")), ("output_tokens", ("output_tokens", "completion_tokens")), ("total_tokens", ("total_tokens",))):
        values, invalid = [], False
        for a in attempts:
            usage = a.get("usage")
            if usage is not None and not isinstance(usage, dict):
                invalid = True
                continue
            usage = usage or {}
            found = [usage[k] for k in aliases if k in usage]
            if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in found) or len(set(map(str, found))) > 1:
                invalid = True
            elif found:
                values.append(found[0])
        details = {"known_subtotal": sum(values) if values else None, "known_attempts": len(values), "total_attempts": len(attempts),
                   "coverage": len(values) / len(attempts), "scope": "saved_attempts_only"}
        if invalid:
            output[name] = unavailable("invalid_usage", "invalid_output", **details)
        elif len(values) != len(attempts):
            output[name] = unavailable("incomplete_usage", **details)
        else:
            output[name] = {"status": "evaluated", "value": sum(values), "details": details}
    return output
