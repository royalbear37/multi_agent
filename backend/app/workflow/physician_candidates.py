"""A physician's selection list, separate from AI verification and recommendations."""
import copy
import re


def identity(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def physician_selection(run):
    result = []
    case = run.get('case_snapshot') or {}
    for row in run.get('drug_assessments', []):
        excluded = []
        ast = row.get('ast') or {}
        if ast.get('assessment') == 'resistant' and ast.get('source_validation', {}).get('status') == 'confirmed':
            excluded.append('本例藥敏來源已核對為抗藥；另列不建議項目供醫師查看')
        for item in (case.get('allergies') or {}).get('items', []):
            if identity(item.get('drug_code')) != identity(row['drug_code']):
                continue
            if item.get('verification_status') in {'ruled_out', 'conflicting'}:
                continue
            if item.get('severity') in {'severe', '嚴重', '重度'} or 'anaphylaxis' in str(item.get('reaction', '')).lower():
                excluded.append('病例記錄本藥嚴重過敏反應；另列不建議項目供醫師查看')
        if row.get('status') == 'avoid' and (row.get('audit') or {}).get('verdict') == 'supported':
            excluded.append(row.get('reason') or '避用理由已通過独立核對')
        result.append({
            'drug_code':row['drug_code'], 'eligible':not excluded,
            'verification_status':'complete' if row.get('status') == 'reviewable' else 'incomplete',
            'exclusion_reasons':excluded,
            'reason':row.get('reason') or '供醫師依原始資料審閱',
            'evidence_refs':copy.deepcopy(row.get('evidence_refs', [])),
            'warnings':copy.deepcopy(row.get('blockers', [])),
            'ast_available':row.get('ast_available', False),
        })
    return result


def add_physician_candidates(run):
    if run.get('decision_basis') != 'agent':
        return run
    selections = physician_selection(run)
    run['physician_selection_version'] = 'physician-selection-1'
    run['physician_candidates'] = [r for r in selections if r['eligible']]
    run['physician_excluded'] = [r for r in selections if not r['eligible']]
    run['physician_review_status'] = 'available' if selections else 'no_drug_assessments'
    return run
