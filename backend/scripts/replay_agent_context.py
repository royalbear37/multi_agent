"""Replay saved retrievals and completed replies locally, with mock remaining roles."""
import argparse,copy,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.agents import runtime_led as rt
from app.workflow.engine import execute
from app.agents.contracts_led import ASTItem

def replay(saved):
    sources={e['chunk_id']:e for e in saved['evidence_snapshots']}
    completed={n['node_id']:n['output'] for n in saved['nodes'] if n.get('output') and n.get('agent_id') and n['status'] in ['completed','needs_confirmation']}
    class RecordedDocs:
        def search_agent_context(self,query,**kwargs):
            r=next(r for r in saved['retrievals'] if r['query']==query and r['stage']==kwargs.get('stage') and r.get('drug_code')==kwargs.get('drug_code'))
            rows=[]
            for cid in r['chunk_ids']:
                e=copy.deepcopy(sources[cid]);e.pop('context_for',None)
                if cid not in r.get('primary_ids',r['chunk_ids']): e['context_for']='saved-neighbor'
                rows.append(e)
            return {'status':r['status'],'evidence':rows,'warnings':r.get('warnings',[]),'retrieval_method':'recorded-local-replay'}
    original=rt.Provider.complete
    inputs={}
    def complete(self,agent,data,**kwargs):
        inputs[agent.id]=copy.deepcopy(data)
        if agent.id in completed:
            output=copy.deepcopy(completed[agent.id])
            if agent.id=='ast_agent':
                output['drugs']=[{k:v for k,v in row.items() if k in ASTItem.model_fields} for row in output['drugs']]
            return {'output':output,'usage':None}
        return original(self,agent,data,**kwargs)
    with patch.object(rt.Provider,'complete',complete):
        result=execute(saved['case_snapshot'],'multi-agent','mock',RecordedDocs())
    for data in inputs.values():
        assert len(json.dumps(data,ensure_ascii=False))<=180000
        assert data['ast_results']==saved['case_snapshot']['ast_results']
        for e in data['evidence']:
            if 'text' in e: assert e['text']==sources[e['chunk_id']]['text']
    assert len(inputs)==6, result['errors']
    return {'validation_kind':'offline replay; three saved replies, remaining roles MOCK; no clinical validation',
        'saved_run_id':saved['run_id'],'version':rt.VERSION,'external_calls':0,
        'input_characters':{k:len(json.dumps(v,ensure_ascii=False)) for k,v in inputs.items()},
        'source_counts':{k:len(v['evidence']) for k,v in inputs.items()},
        'errors':result['errors'],'calls_to_local_stub':result['agent_execution']['calls'],
        'raw_ast_and_selected_source_text_preserved':True,'evidence_selection':result['evidence_selection']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); report=replay(json.loads(args.run.read_text(encoding='utf-8-sig')))
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
