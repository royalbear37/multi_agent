"""Bounded-memory cohort reader. Patient rows and generated cases stay local."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.rules.reported import phenotype
from app.schemas.case import Case

REQUIRED = {'anon_id', 'pat_enc_csn_id_coded', 'order_proc_id_coded', 'culture_description',
            'organism', 'antibiotic', 'AST_pheno', 'CLSI_2022_pheno', 'AST_panel',
            'neg_cx', 'mult_org_ast', 'has_AST', 'prelim_AST'}
SITES = {'URINE': ('urinary tract infection', '模擬情境：排尿疼痛、頻尿，無發燒或側腰痛；未由培養部位推定真實診斷。'),
         'BLOOD': ('bloodstream infection', '模擬情境：發燒與寒顫，需評估感染來源；未由血液培養推定真實菌血症。'),
         'RESPIRATORY_TRACT': ('pneumonia', '模擬情境：發燒、咳嗽與新發肺部浸潤；症狀及影像均為補寫。')}
SCENARIO_ORGANISMS = {'ESCHERICHIA COLI', 'KLEBSIELLA PNEUMONIAE', 'STAPHYLOCOCCUS AUREUS', 'PSEUDOMONAS AERUGINOSA'}
DEMO_CONTEXT = (' Demo 範圍：依所列模擬感染情境分析來源藥敏與引用。'
                '既往病史、免疫狀態、詳細生命徵象及額外影像未提供，保留為未知與展示限制；'
                '不代表正常、陰性或已完成臨床確診。')


def group_key(row):
    return tuple(row.get(k, '').strip() for k in ('anon_id', 'pat_enc_csn_id_coded', 'order_proc_id_coded', 'organism'))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError('CSV missing required columns: ' + ', '.join(sorted(REQUIRED - set(reader.fieldnames or []))))
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Malformed CSV row; no partial import was installed')
            yield {k: v.strip() for k, v in row.items()}


def ast_row(row):
    # AST_val1 may be a disk diameter or MIC; no units are supplied by this file.
    # Keep exact strings instead of incorrectly labelling all numeric values MIC.
    label = phenotype(row.get('CLSI_2022_pheno'))
    return {'drug_code': row['antibiotic'], 'reported_sir': label if label in {'S','I','R'} else None,
            'method': row.get('AST_panel'), 'standard': 'CLSI', 'standard_version': '2022',
            'source': 'CSV:CLSI_2022_pheno (dataset-derived label; not recomputed)',
            'interpretation_basis': 'CLSI_2022_pheno',
            'source_phenotype': row.get('AST_pheno') or None,
            'clsi_2022_phenotype': row.get('CLSI_2022_pheno') or None,
            'raw_measurement': {k: row.get(k, '') for k in ('AST_code','AST_panel','AST_inequality','AST_val1','AST_val2','enzyme_class','enzyme')}}


def build_case(key, group, digest, policy_ref, index):
    first = group[0]
    site, context = SITES[first['culture_description']]
    nonfinal = any(r.get('prelim_AST') or r.get('mult_org_ast') or r.get('neg_cx') for r in group)
    now = datetime.now(timezone.utc).isoformat()
    value = {'case_id': f'cohort-{digest[:8]}-{index:03}', 'created_at': now,
             'is_synthetic': False, 'data_origin': 'hybrid', 'evidence_scope': 'reference',
             'source': '來源藥敏＋模擬臨床情境；不是真實完整病歷',
             'demographics': {'age': 55, 'sex': 'female', 'weight': 65, 'weight_unit': 'kg'},
             'encounter': {'infection_site': site, 'severity': 'stable', 'context': context + DEMO_CONTEXT},
             'renal': {'egfr': 90, 'unit': 'mL/min/1.73m2', 'dialysis_status': 'none'},
             'allergies': {'status': 'known_none', 'items': []},
             'microbiology': {'specimen': first['culture_description'], 'organism': first['organism'],
                              'report_status': 'needs_review' if nonfinal else 'final'},
             'ast_results': [ast_row(r) for r in group if r.get('antibiotic')],
             'policy_refs': [policy_ref] if policy_ref else [],
             'provenance': {'source_system': 'local-microbiology-csv', 'source_file_sha256': digest,
                            'adapter_version': 'microbiology-1.0', 'imported_at': now,
                            'source_record_id': hashlib.sha256('|'.join(key).encode()).hexdigest(),
                            'simulated_fields': ['demographics', 'encounter', 'renal', 'allergies', 'medications'],
                            'notes': ['菌種、檢體、AST 與報告旗標來自 CSV；其他臨床內容為模擬。',
                                      '未使用來源病人 ID、就醫 ID 或偏移日期作為模擬病歷資訊。',
                                      '未提供測量單位，原始測量字串僅供核對；不重新判讀 MIC。']}}
    # An explicitly simulated medication gives the reviewer treatment context.
    first_s = next((r['antibiotic'] for r in group if phenotype(r.get('CLSI_2022_pheno')) == phenotype(r.get('AST_pheno')) == 'S'), None)
    if first_s:
        value['medications'] = [{'drug_code': first_s, 'status': 'current (simulated)'}]
    return Case.model_validate(value).model_dump(mode='json')


def prepare(path, out, policy_ref, per_site=4):
    path, out = Path(path), Path(out)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    counts = {k: Counter() for k in ('organism','antibiotic','culture_description','AST_panel','AST_pheno','CLSI_2022_pheno','prelim_AST','mult_org_ast')}
    selected, quotas = {}, Counter()
    total = 0
    for row in rows(path):
        total += 1
        for column, counter in counts.items():
            counter[row.get(column, '')] += 1
        site = row.get('culture_description')
        if (site in SITES and quotas[site] < per_site and row['organism'] in SCENARIO_ORGANISMS
                and row['has_AST'] and not any(row.get(k) for k in ('prelim_AST','mult_org_ast','neg_cx'))
                and phenotype(row['AST_pheno']) == phenotype(row['CLSI_2022_pheno']) == 'S'):
            key = group_key(row)
            if key not in selected:
                selected[key] = []
                quotas[site] += 1
    # A second streaming pass gathers complete groups even if rows aren't adjacent.
    for row in rows(path):
        key = group_key(row)
        if key in selected:
            selected[key].append(row)
            if len(selected[key]) > 2000:
                raise ValueError('Selected culture exceeds 2000 rows; resolve isolate grouping before import')
    catalog = {'source_sha256': digest, 'rows': total,
               'organisms': sorted(k for k in counts['organism'] if k),
               'antibiotics': sorted(k for k in counts['antibiotic'] if k)}
    cases = [build_case(key, group, digest, policy_ref, i) for i, (key, group) in enumerate(selected.items(), 1)]
    # Add paired allergy/renal scenarios from the same observed AST, explicitly labelled.
    import copy
    for base in cases[:3]:
        variant = copy.deepcopy(base)
        variant['case_id'] += '-allergy'
        drug = next((a['drug_code'] for a in base['ast_results'] if a['reported_sir'] == 'S' and phenotype(a['source_phenotype']) == 'S'), None)
        if not drug:
            continue
        variant['allergies'] = {'status': 'known_present', 'items': [{'drug_code': drug, 'reaction': '模擬：蕁麻疹', 'severity': 'moderate'}]}
        variant['renal']['egfr'] = 35
        variant['encounter']['context'] += ' 配對情境另加入藥品過敏與腎功能下降，供比較排除理由；不自動推算調整方案。'
        cases.append(Case.model_validate(variant).model_dump(mode='json'))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'profile.json').write_text(json.dumps({'rows': total, 'source_sha256': digest, 'counts': counts, 'cases': len(cases)}, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'rows': total, 'organisms': len(catalog['organisms']), 'antibiotics': len(catalog['antibiotics']), 'cases': len(cases), 'source_sha256': digest}
