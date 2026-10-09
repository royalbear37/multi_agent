"""Create revisions for matching authored fixtures; change source descriptions only."""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.schemas.case import ASTResult


def upgrade_source_descriptions(current, package):
    old=current.get('provenance') or {}
    new=package.get('provenance') or {}
    if (current.get('case_id')!=package.get('case_id') or
        old.get('adapter_version') not in {'agent-cases-1','agent-cases-2'} or
        new.get('adapter_version')!='agent-cases-2' or
        not old.get('source_file_sha256') or old.get('source_file_sha256')!=new.get('source_file_sha256') or
        not old.get('source_record_id') or old.get('source_record_id')!=new.get('source_record_id')):
        return None,'source_identity_mismatch'
    before=[ASTResult.model_validate(row).model_dump(mode='json') for row in current.get('ast_results',[])]
    after=[ASTResult.model_validate(row).model_dump(mode='json') for row in package.get('ast_results',[])]
    values=lambda rows:[{k:v for k,v in row.items() if k!='source'} for row in rows]
    if values(before)!=values(after):
        return None,'ast_modified_preserved'
    changes=[i for i,(a,b) in enumerate(zip(before,after)) if a.get('source')!=b.get('source')]
    if not changes:
        return None,'already_current'
    known_old_sources={'CSV:CLSI_2022_pheno; dataset label, not recalculated',
                       'CSV:CLSI_2022_pheno (dataset-derived label; not recomputed)'}
    if any(before[index].get('source') not in known_old_sources for index in changes):
        return None,'manual_source_modified_preserved'
    result=copy.deepcopy(current)
    for index in changes:
        result['ast_results'][index]['source']=after[index]['source']
    result['provenance'].setdefault('notes',[]).append(
        '2026-10-07：僅更新 AST 來源描述，明示選定 CLSI 2022 判讀缺失；原始報告、類別、量測及臨床欄位均未變更。')
    return result,'source_descriptions_updated'


def upgrade_package(directory, apply=False):
    from app import main
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    rows=[]
    for cid in manifest['cases']:
        current=main.repo.get_case(cid)
        if not current:
            rows.append({'case_id':cid,'status':'not_installed'}); continue
        package=json.loads((directory/(cid+'.json')).read_text(encoding='utf-8'))
        value,status=upgrade_source_descriptions(current['case'],package)
        revision=current['revision']
        if value and apply:
            from app.adapters import normalize_case
            validated,warnings=normalize_case(value)
            try:
                revision=main.repo.upsert_case(validated.model_dump(mode='json'),value,warnings,
                    expected_revision=revision)['revision']
            except ValueError as exc:
                if str(exc)!='CASE_REVISION_CONFLICT': raise
                value=None
                status='concurrent_revision_preserved'
                revision=(main.repo.get_case(cid) or {}).get('revision')
        rows.append({'case_id':cid,'status':status,'applied':bool(value and apply),'revision':revision})
    report={'applied':apply,'cases':rows,'note':'No model calls. Historical run and case snapshots remain unchanged.'}
    (directory/'source-label-upgrade.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    upgrade_package(args.cases,args.apply)
