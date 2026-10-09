"""Build local-only, source-preserving scenarios and auditable cohort statistics."""
import argparse
import copy
import csv
import hashlib
import json
from collections import defaultdict, Counter
from pathlib import Path


def build(source, out):
    digest = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
    groups, stats = {}, defaultdict(lambda: {'source': set(), 'clsi': set(), 'rows': 0})
    selected_keys = []
    labels = {'Susceptible':'S','Intermediate':'I','Resistant':'R','S':'S','I':'I','R':'R'}
    total = 0
    with source.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            total += 1
            if row['organism'] != 'ESCHERICHIA COLI' or row['culture_description'] != 'URINE': continue
            key = tuple(row[k] for k in ('anon_id','pat_enc_csn_id_coded','order_proc_id_coded','organism'))
            drug = row['antibiotic']
            if not drug: continue
            token = hashlib.sha256('|'.join(key).encode()).hexdigest()
            value = stats[(token,drug)]
            value['rows'] += 1
            value['source'].add(labels.get(row.get('AST_pheno')))
            value['clsi'].add(labels.get(row.get('CLSI_2022_pheno')))
            if len(selected_keys) < 30 and key not in selected_keys and row.get('has_AST') and not any(row.get(k) for k in ('prelim_AST','mult_org_ast','neg_cx')):
                selected_keys.append(key); groups[key] = []
            if key in groups: groups[key].append(row)
    aggregates = defaultdict(Counter)
    for (_,drug), record in stats.items():
        count = aggregates[drug]
        count['records'] += 1; count['rows'] += record['rows']
        if len(record['source']) != 1 or len(record['clsi']) != 1:
            count['conflicting'] += 1
        elif None in record['clsi']:
            count['missing'] += 1
        elif None not in record['source'] and record['source'] != record['clsi']:
            count['conflicting'] += 1
        else:
            count[next(iter(record['clsi']))] += 1; count['denominator'] += 1
    background = [dict(source=source.name, source_sha256=digest, organism='ESCHERICHIA COLI', specimen='URINE',
        drug_code=drug, basis='CLSI_2022_pheno', scope='source dataset; not hospital antibiogram',
        grouping='one culture-organism-drug; conflicting/missing excluded from denominator',
        **{k: c[k] for k in ('S','I','R','denominator','missing','conflicting','records','rows')}) for drug,c in sorted(aggregates.items())]
    chosen = next((key for key,g in groups.items() if any(r['antibiotic']=='nitrofurantoin' and labels.get(r['CLSI_2022_pheno'])=='S' for r in g)), None)
    if chosen is None: raise ValueError('No qualifying urinary E. coli culture; do not manufacture source AST')
    ast=[]
    for r in groups[chosen]:
        ast.append(dict(drug_code=r['antibiotic'], reported_sir=labels.get(r.get('CLSI_2022_pheno')),
            method=r['AST_panel'], standard='CLSI', standard_version='2022',
            source=('CSV:CLSI_2022_pheno; dataset label, not recalculated' if labels.get(r.get('CLSI_2022_pheno')) else
                    'CSV:CLSI_2022_pheno selected but missing/unrecognized; AST_pheno preserved separately; do not infer from raw measurement'), interpretation_basis='CLSI_2022_pheno',
            source_phenotype=r.get('AST_pheno') or None, clsi_2022_phenotype=r.get('CLSI_2022_pheno') or None,
            raw_measurement={k:r.get(k,'') for k in ('AST_code','AST_panel','AST_inequality','AST_val1','AST_val2','enzyme_class','enzyme')}))
    timestamp='2026-10-05T09:00:00+08:00'
    base=dict(case_id='agent-complete', schema_version='1.0', is_synthetic=False, data_origin='hybrid',
        evidence_scope='reference', external_model_allowed=True, source='來源 AST＋人工編製臨床測試情境', created_at=timestamp,
        demographics=dict(age=45,sex='female',weight=60,weight_unit='kg'),
        encounter=dict(infection_site='lower urinary tract infection',severity='stable',context='排尿疼痛及頻尿兩天；無發燒、畏寒、側腰痛、嘔吐或陰道症狀。檢查無肋脊角壓痛，能正常口服。',observed_at=timestamp),
        clinical_history={'pregnancy':'not pregnant','immune_status':'not immunocompromised','urologic_history':'no catheter, obstruction or recent instrumentation','liver_history':'no known liver disease','urinalysis':'pyuria present','infection_source':'urinary tract','prior_antibiotic_exposure':'none in preceding three months'},
        vitals=dict(temperature_c=36.8,heart_rate_per_min=76,respiratory_rate_per_min=16,blood_pressure='118/72 mmHg',spo2_percent=98,observed_at=timestamp),
        renal=dict(creatinine=0.8,creatinine_unit='mg/dL',egfr=92,unit='mL/min/1.73m2',calculation_method='test-scenario value',crcl=84.1,crcl_unit='mL/min',crcl_calculation_method='Cockcroft-Gault using authored age 45, female, weight 60 kg and creatinine 0.8 mg/dL; not an observed measurement',dialysis_status='none',sampled_at=timestamp),
        allergies=dict(status='known_none',items=[]),medications=[],medication_history_status='reviewed_none',
        microbiology=dict(specimen='URINE',organism='ESCHERICHIA COLI',report_status='final'),ast_results=ast,
        rapid_identification=dict(method='MALDI-TOF',result='ESCHERICHIA COLI',observed_at=timestamp,source='authored test observation'),
        resistance_context=[r for r in background if r['drug_code'] in {a['drug_code'] for a in ast}],policy_refs=[],
        provenance=dict(source_system='local-microbiology-csv',source_file_sha256=digest,source_record_id=hashlib.sha256('|'.join(chosen).encode()).hexdigest(),
            adapter_version='agent-cases-2',simulated_fields=['demographics','encounter','renal','allergies','medications','medication_history_status','rapid_identification','clinical_history','vitals'],
            notes=['保留原始 AST；數值原始欄位未含單位時不冒稱 MIC。臨床資料為人工編製測試情境。']))
    cases=[base]
    renal=copy.deepcopy(base); renal['case_id']='agent-renal'; renal['renal'].update(creatinine=2.6,egfr=22,crcl=25.9,crcl_calculation_method='Cockcroft-Gault using authored age 45, female, weight 60 kg and creatinine 2.6 mg/dL; not an observed measurement'); cases.append(renal)
    allergy=copy.deepcopy(base); allergy['case_id']='agent-allergy'; allergy['allergies']={'status':'known_present','items':[{'drug_code':'nitrofurantoin','reaction':'anaphylaxis','severity':'severe'}]}; cases.append(allergy)
    interaction=copy.deepcopy(base); interaction['case_id']='agent-interaction'; interaction['medications']=[{'drug_code':'tizanidine','status':'active','observed_at':timestamp}]; interaction['medication_history_status']='reviewed_list'; cases.append(interaction)
    conflict=copy.deepcopy(base); conflict['case_id']='agent-ast-conflict'; target=copy.deepcopy(ast[0]); target['reported_sir']='R' if target['reported_sir']!='R' else 'S'; conflict['ast_results'].append(target); conflict['provenance']['simulated_fields'].append('ast_results.appended_conflicting_test_row'); cases.append(conflict)
    rapid=copy.deepcopy(base); rapid['case_id']='agent-rapid-only'; rapid['ast_results']=[]; rapid['microbiology']['report_status']='preliminary'; rapid['provenance']['simulated_fields'].append('microbiology.report_status'); cases.append(rapid)
    mismatch=copy.deepcopy(base); mismatch['case_id']='agent-evidence-mismatch'; mismatch['policy_refs']=['agent-unrelated-evidence']; cases.append(mismatch)
    missing=copy.deepcopy(base); missing['case_id']='agent-missing'; missing['allergies']={'status':'unknown','items':[]}; missing['renal']={}; missing['encounter']['infection_site']=None; cases.append(missing)
    out.mkdir(parents=True,exist_ok=True)
    for case in cases: (out/(case['case_id']+'.json')).write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf-8')
    revised=copy.deepcopy(renal); revised['renal']=copy.deepcopy(base['renal']); revised['provenance']['notes'].append('第二版測試情境：更新腎功能資料，舊 run 應保持原始快照。')
    (out/'agent-renal-revision.json').write_text(json.dumps(revised,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'resistance-statistics.json').write_text(json.dumps({'source_rows':total,'source_sha256':digest,'records':background},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'version':'agent-cases-2','cases':[c['case_id'] for c in cases],'source_sha256':digest,'revision':'agent-renal-revision.json'},indent=2),encoding='utf-8')
    print(json.dumps({'cases':len(cases),'ast_rows':len(ast),'background_drugs':len(background),'source_rows':total}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); build(args.source,args.out)
