"""Record explicit human decisions without upgrading the system's assessments."""
import copy


def validate_drug_decisions(run, decisions, role):
    if run.get('decision_basis') != 'agent':
        raise ValueError('逐藥醫師決策僅適用 Agent 主導分析')
    if role not in {'doctor', 'physician', 'pharmacist'}:
        raise ValueError('請選擇醫師或藥師角色記錄逐藥決策')
    rows = {r['drug_code']: r for r in run.get('drug_assessments', [])}
    if not decisions:
        raise ValueError('請至少選擇一項藥品的決定')
    seen, result = set(), []
    for item in decisions:
        code = item['drug_code']
        if code not in rows or code in seen:
            raise ValueError('藥品須來自本次逐藥評估，且不能重複')
        seen.add(code)
        if item['decision'] in {'adopt', 'conditional'} and item['acknowledged_warnings'] is not True:
            raise ValueError('採用前請確認已閱讀系統警示')
        if item['decision'] == 'conditional' and not item['conditions'].strip():
            raise ValueError('有條件採用須填寫使用條件')
        result.append({**copy.deepcopy(item), 'system_assessment': copy.deepcopy(rows[code])})
    return result
