"""Verify/import versioned public references only; no cases or model calls."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))


def verified_files(bundle):
    bundle=bundle.resolve()
    items=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    result=[]
    for item in items:
        if item.get('document_kind')!='drug_label': raise ValueError('Only drug labels belong in this bundle')
        for name,expected in [(item['filename'],item['content_sha256']),(item['original_filename'],item['original_sha256'])]:
            path=(bundle/name).resolve()
            if not path.is_relative_to(bundle): raise ValueError('File outside bundle')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise ValueError('Hash mismatch: '+name)
        result.append((item,(bundle/item['filename']).read_bytes()))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,default=ROOT/'data/public_references/dailymed')
    p.add_argument('--verify-only',action='store_true')
    args=p.parse_args()
    verified=verified_files(args.bundle)
    if args.verify_only:
        print(json.dumps({'verified':len(verified),'imported':0,'model_calls':0}));return
    from app import main as api
    service=api._documents()
    documents=[]
    for item,content in verified:
        result=service.import_document(item['filename'],content,item['title'],item['version'],False,
            population=item['population'],source_url=item['source_url'],jurisdiction=item['jurisdiction'],document_kind='drug_label')
        documents.append({'title':item['title'],'doc_id':result['doc_id']})
    print(json.dumps({'verified':len(verified),'documents':documents,'model_calls':0,'next_step':'Rebuild reference vector index in the document library.'}))


if __name__=='__main__':main()
