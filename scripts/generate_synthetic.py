"""Reproduce fixed synthetic input cases; expected answers are authored separately."""
import copy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'data'/'synthetic'
base=json.loads((folder/'case-01-complete.json').read_text(encoding='utf-8-sig'))
for path in sorted(folder.glob('case-*.json')):
    number=int(path.name.split('-')[1])
    case=copy.deepcopy(base)
    case['case_id']=path.stem
    case['created_at']=f'2026-01-{number:02}T00:00:00+00:00'
    if number==2: case['renal']={}
    elif number==3: case['allergies']={'status':'unknown','items':[]}
    elif number==4: case['allergies']={'status':'known_present','items':[{'drug_code':'DEMO_DRUG_A','reaction':'DEMO_REACTION','severity':'demo-severe'}]}
    elif number==5: case['resistance_context_ref']=['DEMO_RESISTANCE_HIGH']
    elif number==6: case['ast_results'][0]['unit']=None
    elif number==7: case['ast_results'][0]['standard_version']=None
    elif number==8: case['ast_results'][0]['reported_sir']='R'
    elif number==9:
        case['ast_results']=[]
        case['rapid_identification']={'method':'synthetic MALDI-TOF','result':'DEMO_ORGANISM_A','observed_at':case['created_at'],'source':'synthetic-fixture'}
    elif number==10: case['policy_refs']=['NO_SUCH_POLICY']
    elif number==11: case['microbiology']['organism']='DEMO_UNSUPPORTED'
    elif number==14: case['policy_refs']=['demo-conflicting-policy']
    elif number==15:
        # A complete, interactive success fixture.  Every value is fictional
        # and intentionally uses the demo rule vocabulary only.
        stamp='2026-01-15T00:00:00+00:00'
        case.update({
            'source': 'synthetic-interactive-demo',
            'created_at': stamp,
            'demographics': {'age': 56, 'sex': 'F', 'weight': 64, 'weight_unit': 'kg'},
            'encounter': {'infection_site': 'demo-site-urinary', 'severity': 'demo-moderate', 'context': 'demo-inpatient', 'observed_at': stamp},
            'renal': {'creatinine': 1.0, 'creatinine_unit': 'demo-mg/dL', 'egfr': 75, 'unit': 'mL/min/1.73m2', 'calculation_method': 'demo-equation', 'dialysis_status': 'none', 'sampled_at': stamp},
            'allergies': {'status': 'known_none', 'items': []},
            'microbiology': {'specimen': 'demo-urine', 'organism': 'DEMO_ORGANISM_A', 'collected_at': stamp, 'report_status': 'final'},
            'ast_results': [
                {'drug_code': 'DEMO_DRUG_A', 'mic': 1, 'comparator': '=', 'unit': 'demo-unit', 'reported_sir': 'S', 'method': 'demo', 'standard': 'DEMO', 'standard_version': '1', 'source': 'synthetic'},
                {'drug_code': 'DEMO_DRUG_B', 'mic': 2, 'comparator': '=', 'unit': 'demo-unit', 'reported_sir': 'S', 'method': 'demo', 'standard': 'DEMO', 'standard_version': '1', 'source': 'synthetic'},
            ],
            'rapid_identification': {'method': 'synthetic MALDI-TOF', 'result': 'DEMO_ORGANISM_A', 'observed_at': stamp, 'source': 'synthetic-fixture'},
            'medications': [
                {'drug_code': 'DEMO_MEDICATION_BASELINE', 'status': 'active', 'observed_at': stamp},
                {'drug_code': 'DEMO_DRUG_C', 'status': 'held', 'observed_at': stamp},
            ],
            'resistance_context_ref': ['demo-resistance-v1'],
            'policy_refs': ['demo-policy-v1'],
            'provenance': {'source_system': 'synthetic-interactive-seed', 'imported_at': stamp, 'adapter_version': 'canonical-1', 'source_record_id': 'interactive-15'},
        })
    elif number==16:
        # A second complete fixture exercises a different renal value,
        # medication list, rapid result and two-source AST report.
        stamp='2026-01-16T00:00:00+00:00'
        case.update({
            'source': 'synthetic-interactive-demo',
            'created_at': stamp,
            'demographics': {'age': 68, 'sex': 'M', 'weight': 82, 'weight_unit': 'kg'},
            'encounter': {'infection_site': 'demo-site-respiratory', 'severity': 'demo-stable', 'context': 'demo-observation', 'observed_at': stamp},
            'renal': {'creatinine': 1.3, 'creatinine_unit': 'demo-mg/dL', 'egfr': 52, 'unit': 'mL/min/1.73m2', 'calculation_method': 'demo-equation', 'dialysis_status': 'none', 'sampled_at': stamp},
            'allergies': {'status': 'known_none', 'items': []},
            'microbiology': {'specimen': 'demo-respiratory', 'organism': 'DEMO_ORGANISM_A', 'collected_at': stamp, 'report_status': 'final'},
            'ast_results': [
                {'drug_code': 'DEMO_DRUG_A', 'mic': 0.5, 'comparator': '=', 'unit': 'demo-unit', 'reported_sir': 'S', 'method': 'demo', 'standard': 'DEMO', 'standard_version': '1', 'source': 'synthetic'},
                {'drug_code': 'DEMO_DRUG_B', 'mic': 4, 'comparator': '=', 'unit': 'demo-unit', 'reported_sir': 'S', 'method': 'demo', 'standard': 'DEMO', 'standard_version': '1', 'source': 'synthetic'},
            ],
            'rapid_identification': {'method': 'synthetic MALDI-TOF', 'result': 'DEMO_ORGANISM_A', 'observed_at': stamp, 'source': 'synthetic-fixture'},
            'medications': [
                {'drug_code': 'DEMO_MEDICATION_SUPPORTIVE', 'status': 'active', 'observed_at': stamp},
                {'drug_code': 'DEMO_DRUG_B', 'status': 'home-medication', 'observed_at': stamp},
            ],
            'resistance_context_ref': ['demo-resistance-v1'],
            'policy_refs': ['demo-policy-v1'],
            'provenance': {'source_system': 'synthetic-interactive-seed', 'imported_at': stamp, 'adapter_version': 'canonical-1', 'source_record_id': 'interactive-16'},
        })
    path.write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('16 fixed synthetic cases written; independent expectations preserved.')
