"""Live independent audit of an actual WHO page that does not support adult cystitis."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pypdf import PdfReader
from app import main
from app.agents import runtime_led as runtime
from app.workflow.agent_led import facts_from, validate_output


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    case = main.repo.get_case('agent-complete')['case']
    page = PdfReader(root/'who_aware_antibiotic_book.pdf').pages[565].extract_text()
    evidence = {'chunk_id':'WHO-2022-physical-page-566','text':page,'document_title':'WHO AWaRe antibiotic book', 'document_version':'2022','location':{'page':566,'printed_page':550},'is_synthetic':False,'source_url':'https://www.who.int/publications/i/item/9789240062382'}
    data = dict(facts=facts_from(case),ast_results=case['ast_results'],drugs=['piperacillin_tazobactam'],evidence=[evidence],assessments={},claims=[{'drug_code':'piperacillin_tazobactam','status':'reviewable','reason':'此頁支持本例成人穩定下泌尿道感染使用 piperacillin/tazobactam','evidence_refs':[evidence['chunk_id']],'disagreements':[]}])
    data['facts'].pop('resistance_context',None)
    data['facts'] = {'demographics': {'age':45}, 'encounter':{'infection_site':'acute uncomplicated lower urinary tract infection (cystitis)'}, 'clinical_history':{'immune_status':'not immunocompromised'}}
    data['ast_results'] = []
    data['claims'] = [{'drug_code':'piperacillin_tazobactam', 'claim':'此原文支持成人急性非複雜性膀胱炎的治療選项。'}]
    agent = runtime.AGENTS[-1]; provider = runtime.Provider('live',agent); provider.check(case,data)
    reply = provider.complete(agent,data,timeout=60)
    output = validate_output(agent,reply['output'],data)
    report = dict(case_id=case['case_id'],model=provider.model,input=data,raw_output=reply['output'],output=output,usage=reply.get('usage'),passed=all(d['infection_match']=='unsupported' for d in output['drugs']))
    path=root/'data/local/agent_cases/live-who-566-negative.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'output':output,'usage':report['usage']},ensure_ascii=False))
    if not report['passed']: raise SystemExit('WHO 566 semantic negative audit failed')
