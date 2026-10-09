"""Offline source-scope replay; never changes stored runs or calls a provider."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.workflow.risk_details import validate_risk_details


def replay(path):
    raw=path.read_bytes()
    run=json.loads(raw.decode('utf-8-sig'))
    node=next(n for n in run['nodes'] if n.get('agent_id')=='clinical_agent')
    checks=[]
    for original in node['output']['drugs']:
        row=copy.deepcopy(original)
        validate_risk_details(row,node['input'])
        for dimension,detail in row['risk_details'].items():
            before=original['risk_details'][dimension]
            checks.append(dict(drug_code=row['drug_code'],dimension=dimension,
                before=before['status'],after=detail['status'],
                new_issues=[s for s in detail['validation_issues'] if s not in before.get('validation_issues',[])],
                evidence_refs=detail['evidence_refs']))
    assert path.read_bytes()==raw
    return dict(run_id=run['run_id'],source_sha256=hashlib.sha256(raw).hexdigest(),
        source_unchanged=True,model_calls=0,scope='necessary source-scope checks, not independent semantic verification',
        checked_dimensions=len(checks),changed_to_unknown=sum(c['before']!='unknown' and c['after']=='unknown' for c in checks),
        checks=checks)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.run.resolve()==a.out.resolve():p.error('output must differ from the original run')
    report=replay(a.run)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}))
