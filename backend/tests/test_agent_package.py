"""Reproducible source provenance/denominator/8-scenario contract checks."""
import csv
import json
import xml.etree.ElementTree as ET
from scripts.build_agent_cases import build
from scripts.prepare_agent_references import label_sections
from app.schemas.case import Case


def test_who_lineage_normalization_retains_numbers_columns_and_line_boundaries():
    from scripts.link_who_source import extraction_comparison_text as norm
    assert norm('•I nfection\r\n• Urine\nreference (1) .')==norm('•Infection\n•Urine\nreference (1).')
    assert norm('1 2')!=norm('12')
    assert norm('a  b')!=norm('a b')
    assert norm('a\nb')!=norm('ab')
    assert norm('•No indication')!=norm('•Indication')


def test_who_link_requires_exact_extraction_and_explicit_apply(tmp_path,monkeypatch):
    import pytest
    from app.rag.service import DocumentService
    from scripts import link_who_source as script
    service=DocumentService(tmp_path/'db',retrieval_mode='lexical')
    original=service.import_document('full.txt',b'original WHO test artifact','WHO','2022')
    excerpt=service.import_document('part.md',b'correct excerpt','Chapter','2022')
    references=tmp_path/'references'
    references.mkdir()
    (references/'who-lower-uti.md').write_bytes(b'correct excerpt')
    (references/'manifest.json').write_text(json.dumps([{'filename':'who-lower-uti.md','original_sha256':original['content_hash']}]))
    monkeypatch.setattr(script,'extract_who_lower_uti',lambda path:'wrong extraction')
    with pytest.raises(ValueError,match='does not match'):
        script.link_who_source(service,references,apply=True)
    assert 'source_derivation' not in service.detail(excerpt['doc_id'])['metadata']
    monkeypatch.setattr(script,'extract_who_lower_uti',lambda path:'correct excerpt')
    assert script.link_who_source(service,references)['status']=='verified_preview'
    assert 'source_derivation' not in service.detail(excerpt['doc_id'])['metadata']
    assert script.link_who_source(service,references,apply=True)['status']=='applied'
    assert service.detail(excerpt['doc_id'])['metadata']['source_derivation']['original_hash']==original['content_hash']


def test_source_description_upgrade_preserves_clinical_edits_and_original_ast():
    import copy
    from scripts.upgrade_case_source_descriptions import upgrade_source_descriptions
    current={'case_id':'agent-complete','renal':{'egfr':42},
        'provenance':{'adapter_version':'agent-cases-1','source_file_sha256':'hash','source_record_id':'record'},
        'ast_results':[{'drug_code':'ertapenem','reported_sir':None,'interpretation_basis':'CLSI_2022_pheno',
                        'source_phenotype':'Susceptible','raw_measurement':{'AST_val1':'0.5'},'source':'CSV:CLSI_2022_pheno; dataset label, not recalculated'}]}
    package=copy.deepcopy(current)
    package['renal']['egfr']=92
    package['provenance']['adapter_version']='agent-cases-2'
    package['ast_results'][0]['source']='CLSI selected but missing; original report preserved'
    upgraded,status=upgrade_source_descriptions(current,package)
    assert status=='source_descriptions_updated' and upgraded['renal']==current['renal']
    assert upgraded['ast_results'][0]['reported_sir'] is None
    assert upgraded['ast_results'][0]['raw_measurement']==current['ast_results'][0]['raw_measurement']
    assert current['ast_results'][0]['source']=='CSV:CLSI_2022_pheno; dataset label, not recalculated'
    assert upgrade_source_descriptions(upgraded,package)==(None,'already_current')
    current['ast_results'][0]['source']='人工核對後修正的來源位置'
    assert upgrade_source_descriptions(current,package)==(None,'manual_source_modified_preserved')
    current['ast_results'][0]['raw_measurement']['AST_val1']='1'
    assert upgrade_source_descriptions(current,package)==(None,'ast_modified_preserved')
    current['provenance']['source_record_id']='other-record'
    assert upgrade_source_descriptions(current,package)==(None,'source_identity_mismatch')


def test_source_upgrade_cannot_replace_a_newer_revision(tmp_path):
    import pytest
    from app.repositories import SQLiteRepository
    repo=SQLiteRepository(tmp_path/'upgrade.db')
    old={'case_id':'case','source':'original'}
    repo.upsert_case(old,old,[])
    current={**old,'source':'manual correction'}
    repo.upsert_case(current,current,[],expected_revision=1)
    with pytest.raises(ValueError,match='CASE_REVISION_CONFLICT'):
        repo.upsert_case({**old,'source':'stale package'},{},[],expected_revision=1)
    assert repo.get_case('case')['case']==current
    assert len(repo.list_revisions('case'))==2


def test_authored_history_upgrade_preserves_edits_and_rejects_changed_medications():
    import copy
    from scripts.install_agent_package import upgrade_authored_medication_history
    current={'case_id':'agent-complete','medications':[], 'renal':{'egfr':42},
        'provenance':{'adapter_version':'agent-cases-1','source_file_sha256':'hash','simulated_fields':['medications']}}
    package=copy.deepcopy(current)
    package['renal']={'egfr':92}
    package['provenance']['adapter_version']='agent-cases-2'
    package['medication_history_status']='reviewed_none'
    upgraded=upgrade_authored_medication_history(current,package)
    assert upgraded['renal']==current['renal'] and upgraded['medication_history_status']=='reviewed_none'
    assert 'medication_history_status' not in current
    assert upgrade_authored_medication_history(upgraded,package) is None
    current['medications']=[{'drug_code':'new'}]
    assert upgrade_authored_medication_history(current,package) is None
    current['medications']=[]
    current['provenance']['source_file_sha256']='different'
    assert upgrade_authored_medication_history(current,package) is None


def test_package_preserves_source_and_has_eight_distinct_scenarios(tmp_path):
    base = dict(anon_id='not-exported', pat_enc_csn_id_coded='enc', order_proc_id_coded='order', organism='ESCHERICHIA COLI', culture_description='URINE', antibiotic='nitrofurantoin', has_AST='1', prelim_AST='', mult_org_ast='', neg_cx='', AST_pheno='Susceptible', CLSI_2022_pheno='S', AST_panel='panel')
    rows = [base, base.copy(), {**base, 'order_proc_id_coded':'conflict','CLSI_2022_pheno':'R'}, {**base, 'order_proc_id_coded':'missing','CLSI_2022_pheno':''}]
    source = tmp_path/'source.csv'
    with source.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=base); writer.writeheader(); writer.writerows(rows)
    output = tmp_path/'out'; build(source, output)
    cases = {c: json.loads((output/(c+'.json')).read_text(encoding='utf-8')) for c in json.loads((output/'manifest.json').read_text())['cases']}
    assert len(cases) == 8
    for value in cases.values():
        Case.model_validate(value)
        assert value['data_origin'] == 'hybrid' and value['provenance']['simulated_fields']
        assert 'not-exported' not in json.dumps(value)
    original = cases['agent-complete']['ast_results']
    assert len(original) == 2 and original[0]['source_phenotype'] == 'Susceptible'
    for name in ('agent-renal','agent-allergy','agent-interaction','agent-evidence-mismatch','agent-missing'):
        assert cases[name]['ast_results'] == original
    assert cases['agent-ast-conflict']['ast_results'][:-1] == original
    assert cases['agent-rapid-only']['ast_results'] == []
    assert cases['agent-allergy']['allergies']['items'][0]['reaction'] == 'anaphylaxis'
    assert cases['agent-interaction']['medications'][0]['status'] == 'active'
    assert cases['agent-missing']['renal'] == {}
    stats = json.loads((output/'resistance-statistics.json').read_text())['records'][0]
    assert (stats['records'],stats['rows'],stats['denominator'],stats['S'],stats['conflicting'],stats['missing']) == (3,4,1,1,1,1)


def test_label_extraction_preserves_child_headings_and_table_labels():
    tree = ET.fromstring('''<document xmlns="urn:hl7-org:v3"><component><structuredBody><component><section><title>WARNINGS</title><text>Parent context</text><component><section><title>Renal impairment</title><text>Table 1: renal categories<table><caption>Renal risk</caption></table></text></section></component></section></component></structuredBody></component></document>''')
    sections = label_sections(tree)
    assert len(sections) == 2 and 'WARNINGS / Renal impairment' in sections[1] and 'Renal risk' in sections[1]
