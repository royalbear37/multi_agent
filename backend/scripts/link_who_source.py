"""Verify installed WHO excerpt against its original PDF, then record lineage.

Local only. No downloads, embeddings or model calls. Old runs stay unchanged.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_agent_references import extract_who_lower_uti


def extraction_comparison_text(text):
    """Accept only observed pypdf bullet/parenthetical punctuation spacing.

    Keep line order, numeric spacing and table columns. This verifies artifact
    lineage only; it is not a clinical or table-layout validation.
    """
    text=text.replace('\r\n','\n')
    text=re.sub(r'^• {1,2}', '•', text, flags=re.M)
    text=re.sub(r'^•([A-Z]) {1,2}', r'•\1', text, flags=re.M)
    return re.sub(r'\) (?=\.)', ')', text)


def link_who_source(service, references, *, apply=False):
    manifest=json.loads((references/'manifest.json').read_text(encoding='utf-8'))
    item=next(x for x in manifest if x['filename']=='who-lower-uti.md')
    excerpt=(references/'who-lower-uti.md').read_bytes()
    excerpt_hash=hashlib.sha256(excerpt).hexdigest()
    documents=service.list_documents()
    original=next((d for d in documents if d['content_hash']==item['original_sha256']), None)
    derived=next((d for d in documents if d['content_hash']==excerpt_hash), None)
    if not original or not derived:
        raise ValueError('Exact original PDF and excerpt must both be installed')
    original_path,_=service.source(original['doc_id'])
    derived_path,_=service.source(derived['doc_id'])
    if (hashlib.sha256(original_path.read_bytes()).hexdigest()!=item['original_sha256'] or
        hashlib.sha256(derived_path.read_bytes()).hexdigest()!=excerpt_hash):
        raise ValueError('Stored source bytes do not match verified hashes')
    expected=extract_who_lower_uti(original_path)
    if extraction_comparison_text(excerpt.decode('utf-8'))!=extraction_comparison_text(expected):
        raise ValueError('Excerpt does not match the original PDF extraction; not linked')
    if apply:
        service.register_source_derivation(derived['doc_id'], item['original_sha256'], excerpt_hash,
            'Verified lower-UTI extraction of original PDF pages 294–307. Normalized only CRLF/LF, 1–2 spaces after initial bullet/initial capital, and one space between closing parenthesis and period. Original excerpt unchanged; does not validate clinical meaning or table layout.')
    return dict(status='applied' if apply else 'verified_preview', original_doc_id=original['doc_id'],
        excerpt_doc_id=derived['doc_id'], source_document_id='sha256:'+item['original_sha256'],
        note='Same original artifact; multiple excerpts do not constitute independent evidence. Existing runs unchanged.')


if __name__=='__main__':
    from app import main
    parser=argparse.ArgumentParser()
    parser.add_argument('--references',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(link_who_source(main._documents(),args.references,apply=args.apply),ensure_ascii=False))
