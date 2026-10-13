"""Bound independent audit input without removing claims or fabricating evidence."""
import copy
import json
from app.agents.limits import AgentLedLimits


def fit_audit_context(data, limit=None):
    if limit is None:
        limit = AgentLedLimits.from_env().audit_input_chars
    result = copy.deepcopy(data)
    sources = {e['chunk_id']:e for e in result['evidence']}
    pools = []
    for claim in result['claims']:
        dimensions = claim.get('claims', []) + claim.get('risk_claims', [])
        pools.extend([list(dict.fromkeys(c.get('evidence_refs', []))) for c in dimensions])
        pools.append(list(dict.fromkeys(claim.get('evidence_refs', []))))
    order = list(dict.fromkeys(ref for i in range(max(map(len, pools), default=0)) for pool in pools for ref in pool[i:i+1]))
    # Claims/facts are immutable. Sources shared between drugs occur only once.
    result['evidence'] = []
    groups = []
    for claim in result['claims']:
        refs = list(dict.fromkeys(claim.get('evidence_refs', []) + [ref for c in claim.get('claims', []) + claim.get('risk_claims', []) for ref in c.get('evidence_refs', [])]))
        groups.append({'stage':'audit','drug_code':claim['drug_code'],'requested_refs':refs,
                       'evidence_refs':[], 'omitted_refs':refs, 'retrieval_status':'ok',
                       'retrieved_count':len([r for r in refs if r in sources]),'selected_count':0,'omitted_count':len(refs)})
    result['evidence_groups'] = groups

    def update_groups():
        selected = {e['chunk_id'] for e in result['evidence']}
        for group in groups:
            group['evidence_refs'] = [r for r in group['requested_refs'] if r in selected]
            group['omitted_refs'] = [r for r in group['requested_refs'] if r not in selected]
            group['selected_count'] = len(group['evidence_refs'])
            group['omitted_count'] = len(group['omitted_refs'])

    for ref in order:
        if ref not in sources:
            continue
        result['evidence'].append(sources[ref])
        update_groups()
        if len(json.dumps(result, ensure_ascii=False)) > limit:
            result['evidence'].pop()
            update_groups()
    return result
