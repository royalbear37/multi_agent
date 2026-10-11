"""Record explicit human decisions without upgrading the system's assessments."""
import copy
import re


def drug_identity(code):
    return re.sub(r'[\s_+/／＋–—-]+', '_', code.strip().casefold())


def validate_drug_decisions(run, decisions, role):
    if run.get('decision_basis') != 'agent':
        raise ValueError('逐藥醫師決策僅適用 Agent 主導分析')
    if role not in {'doctor', 'physician', 'pharmacist'}:
        raise ValueError('請選擇醫師或藥師角色記錄逐藥決策')
    rows = {r['drug_code']: r for r in run.get('drug_assessments', [])}
    if not decisions:
        raise ValueError('請至少選擇一項藥品的決定')
    aliases = {drug_identity(code): code for code in rows}
    seen, result = set(), []
    for item in decisions:
        identity = drug_identity(item['drug_code'])
        code = aliases.get(identity, item['drug_code'].strip())
        if identity in seen:
            raise ValueError('藥品不能重複')
        if code not in rows and item.get('outside_analysis') is not True:
            raise ValueError('未經本次評估的藥品須明示為醫師自行新增')
        seen.add(identity)
        if item['decision'] in {'adopt', 'conditional'} and item['acknowledged_warnings'] is not True:
            raise ValueError('採用前請確認已閱讀系統警示')
        if item['decision'] == 'conditional' and not item['conditions'].strip():
            raise ValueError('有條件採用須填寫使用條件')
        result.append({**copy.deepcopy(item), 'drug_code': code,
                       'outside_analysis': code not in rows,
                       'selection_origin': 'physician_added' if code not in rows else 'analysis',
                       'system_assessment': copy.deepcopy(rows.get(code)),
                       'warnings': ['醫師自行新增；此名稱未對應本次藥品評估，請核對是否為既有藥品別名並另行確認藥敏、風險及引用'] if code not in rows else []})
    return result
