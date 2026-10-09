"""Validate source links and uncertainty; do not infer pharmacological suitability."""
from __future__ import annotations
from .source_scope import source_scope_issues


DIMENSIONS = {'allergy': ('allergies', '過敏'), 'renal': ('renal', '腎功能'),
              'interactions': ('medications', '交互作用')}


def fact_value(facts, path):
    value = facts
    for part in path.split('.'):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def has_fact(value):
    if isinstance(value, dict):
        return any(has_fact(item) for item in value.values())
    return value is not None and value != ''


def validate_risk_details(row, data):
    details = row.get('risk_details')
    if not details:
        if data.get('risk_details_required'):
            row['status'] = 'unknown'
            row['reason'] += '；未提供分項風險評估，需重新分析。'
        return
    facts = data.get('facts', {})
    references = {q['chunk_id'] for q in row.get('quotes', [])}
    research = {e['chunk_id'] for e in data.get('evidence', []) if e.get('document_kind') == 'research_article'}
    for dimension, (root, label) in DIMENSIONS.items():
        item = details[dimension]
        failures = []
        paths = item['fact_refs']
        if not paths or not any(p == root or p.startswith(root+'.') for p in paths):
            failures.append('缺少對應病例欄位')
        if any(not has_fact(fact_value(facts, p)) for p in paths):
            failures.append('引用的病例資料未提供')
        refs = item['evidence_refs']
        if not refs or not set(refs) <= references or set(refs) & research:
            failures.append('缺少已核對的指引／標示引文')
        failures.extend(source_scope_issues(row['drug_code'],dimension,
            [q for q in row.get('quotes',[]) if q['chunk_id'] in refs],data.get('evidence',[]),
            item['reason']+' '+item['next_action']))
        if item['missing_fields']:
            failures.append('仍有關鍵資料待確認')
        if dimension == 'allergy' and (facts.get('allergies') or {}).get('status') == 'unknown':
            failures.append('病例過敏狀態未知')
        if dimension == 'interactions' and facts.get('medication_history_status') not in {'reviewed_none','reviewed_list'}:
            failures.append('用藥清單完整性尚未確認，空清單不代表確認無用藥')
        if item['status'] == 'caution' and not item['next_action'].strip():
            failures.append('注意事項未說明下一步')
        if failures:
            item['status'] = 'unknown'
            item['reason'] += '；' + '；'.join(failures)
            if not item['next_action'].strip():
                item['next_action'] = f'補充{label}病例資料或核對相關文件後重新分析'
        item['validation_issues'] = failures
        row[dimension] = item['reason']
    states = {d['status'] for d in details.values()}
    derived = ('unknown' if 'unknown' in states else 'avoid' if 'avoid' in states
               else 'caution' if 'caution' in states else 'no_identified_risk')
    # Earlier quote/prescription validation must never be relaxed by detail rows.
    if row['status'] == 'unknown' or row.get('citation_validation', {}).get('invalid_count'):
        return
    if row['status'] == 'avoid' and derived != 'avoid':
        row['status'] = 'unknown'
        row['reason'] += '；整體不建議與分項風險結論不一致。'
    elif row['status'] == 'caution' and derived == 'no_identified_risk':
        row['status'] = 'unknown'
        row['reason'] += '；注意事項未對應到分項評估。'
    else:
        row['status'] = derived


def caution_ready(row):
    details = row.get('risk_details') if row else None
    return bool(row and row.get('status') == 'caution' and details and
        all(item['status'] in {'no_identified_risk', 'caution'} and not item.get('validation_issues') and
            not item.get('missing_fields') and (item['status'] != 'caution' or item.get('next_action', '').strip())
            for item in details.values()))
