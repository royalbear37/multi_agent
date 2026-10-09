"""One explicitly selected live case. Saves the run and a compact local report."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import main

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--case',required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    result=main.start_run(main.RunBody(case_id=a.case,mode='multi-agent',provider_kind='live'))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':result['run_id'],'status':result['status'],'gate':result.get('gate_status'),'calls':result.get('agent_execution'),'errors':result.get('errors'),
        'drugs':[{'drug':x['drug_code'],'status':x['status'],'reason':x['reason']} for x in result.get('drug_assessments',[])]},ensure_ascii=False))
