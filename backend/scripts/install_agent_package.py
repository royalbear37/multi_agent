"""Install generated local cases and public references, without model calls."""
import argparse
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import main


def upgrade_authored_medication_history(current, package):
    """Upgrade only matching authored history; preserve all other current fields."""
    provenance=current.get('provenance') or {}
    supplied=package.get('provenance') or {}
    if (provenance.get('adapter_version') != 'agent-cases-1' or
        supplied.get('adapter_version') != 'agent-cases-2' or
        current.get('case_id') != package.get('case_id') or
        not provenance.get('source_file_sha256') or
        provenance.get('source_file_sha256') != supplied.get('source_file_sha256') or
        'medications' not in provenance.get('simulated_fields',[]) or
        current.get('medications') != package.get('medications') or
        current.get('medication_history_status','unknown') != 'unknown'):
        return None
    value=copy.deepcopy(current)
    value['medication_history_status']=package['medication_history_status']
    value['provenance'].setdefault('simulated_fields',[]).append('medication_history_status')
    value['provenance'].setdefault('notes',[]).append('agent-cases-2：依相同人工情境的用藥清單補記完整性；保留其餘病例內容及歷史版本，非新增實際病人觀察。')
    return value


def install(cases, references, supersede=False, upgrade_history=False):
    manifest=json.loads((references/'manifest.json').read_text(encoding='utf-8'))
    svc=main._documents()
    documents=[]
    previous = json.loads((cases/'installed.json').read_text(encoding='utf-8')).get('documents', []) if supersede and (cases/'installed.json').exists() else []
    for item in manifest:
        result=svc.import_document(item['filename'],(references/item['filename']).read_bytes(),item['title'],item['version'],item['is_synthetic'],
            population=item['population'],policy_refs=item.get('policy_refs'),source_url=item.get('source_url'),
            jurisdiction=item.get('jurisdiction'),document_kind=item.get('document_kind','reference'),
            study_design=item.get('study_design','not_recorded'))
        documents.append({'title':item['title'],'doc_id':result['doc_id']})
    current_ids = {d['doc_id'] for d in documents}
    for old in previous:
        if old['doc_id'] not in current_ids and any(d['title'] == old['title'] for d in documents):
            svc.delete_document(old['doc_id'])
    package=json.loads((cases/'manifest.json').read_text(encoding='utf-8'))
    upgraded=[]
    for cid in package['cases']:
        payload=json.loads((cases/(cid+'.json')).read_text(encoding='utf-8'))
        current=main.repo.get_case(cid)
        if not current: main.import_case(main.ImportBody(payload=payload))
        elif upgrade_history:
            updated=upgrade_authored_medication_history(current['case'],payload)
            if updated:
                record=main.create_revision(cid,main.ImportBody(payload=updated))
                upgraded.append({'case_id':cid,'revision':record['revision']})
    report={'cases':package['cases'],'documents':documents,'upgraded_history':upgraded,
        'note':'No models called; existing cases preserved except explicitly requested, matching authored medication-history metadata revisions.'}
    (cases/'installed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cases':len(package['cases']),'documents':len(documents)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--cases',type=Path,required=True); p.add_argument('--references',type=Path,required=True)
    p.add_argument('--supersede-package-documents',action='store_true',help='Replace only documents recorded by the previous package install; run snapshots remain intact.')
    p.add_argument('--upgrade-authored-medication-history',action='store_true',help='Create revisions only for unchanged, matching authored package medication histories; retain all other current fields.')
    args=p.parse_args(); install(args.cases,args.references,args.supersede_package_documents,args.upgrade_authored_medication_history)
