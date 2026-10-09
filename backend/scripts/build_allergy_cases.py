"""Paired authored allergy histories; preserve the base case's original AST."""
import argparse
import copy
import json
from pathlib import Path


def paired_cases(base):
    item = {'drug_code':'amoxicillin','label_source':'人工測試情境：既有過敏標籤',
            'verification_status':'unverified'}
    variants = [
        ('unverified', {}, ['具體反應、時間及評估來源缺漏可見', '未確認不得推定無過敏']),
        ('severe', {'reaction':'anaphylaxis','severity':'severe','occurred_at':'測試情境：2024 年',
                   'verification_status':'confirmed','verification_source':'人工編製的專科評估情境，非真實醫療紀錄',
                   'verification_note':'測試設定為已有嚴重過敏評估紀錄',
                   'verified_by':'authored-test-reviewer','verified_at':'2026-10-06T09:00:00+08:00'},
         ['嚴重反應不得被 AST 敏感覆蓋', '逐藥判斷，不可任意擴大整類禁忌']),
        ('intolerance', {'reaction':'nausea only','severity':'not recorded'},
         ['辨識紀錄需要釐清', '不得自動確診免疫性過敏或自動解除標籤']),
        ('conflicting', {'reaction':'anaphylaxis','severity':'severe','verification_status':'conflicting',
                        'verification_source':'人工測試：舊反應紀錄與後續評估互相矛盾',
                        'verification_note':'後續紀錄稱已排除，與原始嚴重反應紀錄不一致，需人工核對'},
         ['同時保留嚴重反應與後續矛盾紀錄', '提出具體核對事項，不自行取代原始紀錄']),
    ]
    cases, expectations = [], []
    for name, changes, checks in variants:
        value = copy.deepcopy(base)
        value['case_id'] = 'agent-allergy-pair-' + name
        value['allergies'] = {'status':'known_present','items':[{**item, **changes}]}
        provenance = value.setdefault('provenance', {})
        provenance.setdefault('simulated_fields', [])
        if 'allergies' not in provenance['simulated_fields']:
            provenance['simulated_fields'].append('allergies')
        provenance.setdefault('notes', []).append('過敏配對測試：人工補寫過敏資訊，其餘病例與原始 AST 不變；研究動機為過敏標籤觀察性研究，不是研究中的真實個案。')
        if not value.get('is_synthetic'):
            value['data_origin'] = 'hybrid'
        cases.append(value)
        expectations.append({'case_id':value['case_id'],'checks':checks,'clinical_grading':'requires expert adjudication'})
    return cases, expectations


def build(base_path, out):
    cases, expectations = paired_cases(json.loads(base_path.read_text(encoding='utf-8')))
    out.mkdir(parents=True, exist_ok=True)
    for value in cases:
        (out / (value['case_id'] + '.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'version':'allergy-pairs-1',
        'base_case':str(base_path),'cases':[c['case_id'] for c in cases],
        'modes':['rule-only','rag-only','single-agent','multi-agent'],
        'expectations':expectations},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cases':len(cases),'out':str(out)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    build(args.base,args.out)
