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
    path.write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('14 fixed synthetic cases written; independent expectations preserved.')
