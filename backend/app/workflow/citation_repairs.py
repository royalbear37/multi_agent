"""Repair declared references without inventing quotations or support verdicts."""
from __future__ import annotations

import copy
from .source_scope import source_scope_issues


def citation_repair(agent_id, row, data, checked=None):
    if not isinstance(row, dict):
        return None
    if agent_id == 'clinical_agent':
        details = row.get('risk_details') or {}
        if not isinstance(details, dict):
            return None
        checks = [(dimension, detail) for dimension, detail in
                  details.items() if isinstance(detail, dict) and
                  detail.get('status') in {'no_identified_risk', 'caution', 'avoid'}]
    elif agent_id == 'evidence_audit' and row.get('basis') != 'case_fact':
        checks = [(check.get('dimension'), check) for field in ('claim_checks', 'risk_checks')
                  for check in (row.get(field, []) if isinstance(row.get(field, []), list) else [])
                  if isinstance(check, dict) and check.get('verdict') == 'supported'
                  and check.get('dimension') != 'ast']
    else:
        return None
    available = {e['chunk_id'] for e in data.get('evidence', [])}
    quoted = {q['chunk_id'] for q in row.get('quotes', []) if isinstance(q, dict) and 'chunk_id' in q}
    missing = {}
    validation_issues = {}
    for dimension, check in checks:
        declared = check.get('evidence_refs', [])
        refs = [ref for ref in declared if isinstance(ref, str) and ref in available and ref not in quoted]
        if refs:
            missing.setdefault(dimension, []).extend(refs)
        if agent_id == 'clinical_agent':
            issues = source_scope_issues(row['drug_code'], dimension,
                [q for q in row.get('quotes', []) if q['chunk_id'] in declared], data.get('evidence', []),
                check.get('reason', '') + ' ' + check.get('next_action', ''))
        else:
            issues = [issue for field in ('claim_checks', 'risk_checks')
                      for value in (checked or {}).get(field, []) if value.get('dimension') == dimension
                      for issue in value.get('validation_issues', [])]
        if issues:
            validation_issues[dimension] = list(dict.fromkeys(issues))
    if not missing and not validation_issues:
        return None
    return {'drug_code': row['drug_code'],
            'missing_quote_refs': list(dict.fromkeys(ref for refs in missing.values() for ref in refs)),
            'dimensions': list(dict.fromkeys([*missing, *validation_issues])),
            'validation_issues': validation_issues, 'previous_output': copy.deepcopy(row)}


def collect_citation_repairs(agent_id, raw, data, unresolved, checked=None):
    """Supply the model's own unmodified assessment, not a server-downgraded row."""
    repairs = []
    checked_rows = {r['drug_code']: r for r in (checked or {}).get('drugs', [])}
    for row in raw.get('drugs', []) if isinstance(raw, dict) else []:
        if isinstance(row, dict) and row.get('drug_code') in unresolved:
            # Only canonical rows that passed parsing can become repair inputs.
            if checked is not None and row['drug_code'] not in checked_rows:
                continue
            repair = citation_repair(agent_id, row, data, checked_rows.get(row['drug_code']))
            if repair:
                repairs.append(repair)
    return repairs


def prepare_citation_repairs(agent_id, raw, data, unresolved):
    apply_citation_repairs(data, collect_citation_repairs(agent_id, raw, data, unresolved))


def apply_citation_repairs(data, repairs):
    data['citation_repairs'] = repairs
    if not repairs or {r['drug_code'] for r in repairs} != set(data['drugs']):
        return
    if any(r.get('validation_issues') for r in repairs):
        # A wrong passage/claim may need other retrieved passages for this drug.
        return
    # A citation-only repair needs the cited originals and patient facts, not
    # every other drug's retrieved passages. Keep every source the row/claim
    # references so the model can reselect spans or reject unsupported refs.
    def references(value):
        if isinstance(value, dict):
            refs = set(value.get('evidence_refs', []))
            refs.update(q['chunk_id'] for q in value.get('quotes', []))
            for child in value.values():
                refs.update(references(child))
            return refs
        if isinstance(value, list):
            return set().union(*(references(child) for child in value)) if value else set()
        return set()
    refs = references(repairs) | references(data.get('claims', []))
    data['evidence'] = [e for e in data['evidence'] if e['chunk_id'] in refs]
    data['evidence_groups'] = []
