"""Preserve validated rows and repair only incomplete rows within the call budget."""
import copy
from pydantic import ValidationError


def validate_partial(agent, raw, data, validate):
    if agent.id=='case_agent': return validate(agent,raw,data), [], []
    if not isinstance(raw,dict) or not isinstance(raw.get('drugs'),list):
        return None, ['report: expected object with drugs array'], list(data['drugs'])
    envelope=agent.output_type.model_validate({**raw,'drugs':[]}).model_dump(mode='json')
    result={**envelope,'drugs':[]}; diagnostics=[]; unresolved=[]
    expected=set(data['drugs']); seen=set()
    counts={str(r.get('drug_code')):sum(isinstance(x,dict) and x.get('drug_code')==r.get('drug_code') for x in raw['drugs']) for r in raw['drugs'] if isinstance(r,dict)}
    for row in raw['drugs']:
        drug=row.get('drug_code') if isinstance(row,dict) else None
        if not isinstance(drug,str) or counts.get(drug)!=1:
            diagnostics.append('drugs: missing or duplicate drug_code'); continue
        if drug not in expected and agent.id!='evidence_agent':
            diagnostics.append('drugs: unexpected drug_code'); continue
        subset={**data,'drugs':[drug] if drug in expected else [],
                'claims':[c for c in data.get('claims',[]) if c['drug_code']==drug]}
        one={**envelope,'issues':[i for i in envelope.get('issues',[]) if i.get('drug_code') in (None,drug)],'drugs':[row]}
        try:
            checked_report=validate(agent,one,subset)
            checked=checked_report['drugs'][0]
            result['issues'].extend(i for i in checked_report.get('issues',[]) if i not in result['issues'])
            result['drugs'].append(checked); seen.add(drug)
            problems=[]
            # A supported assertion without selected evidence is repairable;
            # honest uncertainty or absent retrieved sources is not retried.
            asserted=row.get('status') in {'supported','no_identified_risk','caution','avoid'} or row.get('verdict')=='supported'
            if agent.id in {'evidence_agent','clinical_agent','evidence_audit'} and asserted and row.get('basis')!='case_fact' and not row.get('quotes') and data.get('evidence'):
                problems.append('quotes: select supplied chunk_id/span_ids or explicitly report uncertainty')
            if checked.get('citation_validation',{}).get('invalid_count') or checked.get('reference_validation',{}).get('invalid_refs'):
                problems.append('references: select identifiers and spans supplied in this call')
            if agent.id=='synthesis_agent' and (len(row.get('claims',[]))!=5 or {c['dimension'] for c in row.get('claims',[])}!={'infection','ast','allergy','renal','interactions'}):
                problems.append('claims: provide each of the five dimensions exactly once')
            if agent.id=='evidence_audit' and not checked.get('claim_checks_complete'):
                problems.append('claim_checks: independently check each supplied dimension exactly once')
            if problems:
                unresolved.append(drug); diagnostics.extend(f'{drug}: {p}' for p in problems)
        except (ValidationError,ValueError,TypeError,KeyError) as exc:
            diagnostics.append(f'{drug}: '+type(exc).__name__); unresolved.append(drug)
    for drug in expected-seen:
        unresolved.append(drug); diagnostics.append(f'{drug}: missing valid drug row')
    result['issues']=[i for i in result['issues'] if i.get('drug_code') is None or i.get('drug_code') in seen]
    return result, diagnostics, list(dict.fromkeys(unresolved))


def merge_partial(previous, current):
    if previous is None: return copy.deepcopy(current)
    if current is None: return previous
    rows={r['drug_code']:r for r in previous.get('drugs',[])}
    rows.update({r['drug_code']:r for r in current.get('drugs',[])})
    result={**previous,'drugs':list(rows.values())}
    # Both sets of valid report-level issues remain attributable to the role.
    replaced={r['drug_code'] for r in current.get('drugs',[])}
    kept=[i for i in previous.get('issues',[]) if i.get('drug_code') not in replaced]
    result['issues']=kept+[i for i in current.get('issues',[]) if i not in kept]
    result['findings']=previous.get('findings',[])+[x for x in current.get('findings',[]) if x not in previous.get('findings',[])]
    return result
