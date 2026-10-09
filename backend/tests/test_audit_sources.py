import copy
import pytest
from app.workflow.audit_sources import validate_audit_sources, named_drug
from app.agents.contracts_led import AuditReport
from app.agents.citation_spans import selection_schema


def fixture(drug='tetracycline'):
    quote='Tetracycline reference text for a source-linkage test, not clinical guidance.'
    row=dict(drug_code=drug,verdict='supported',basis='mixed',reason='保存來源支持',
             quotes=[dict(chunk_id='label',quote=quote)],
             ast_check=dict(assessment='resistant',claim_assessment='resistant',category_source_refs=['ast_results.0.clsi_2022_phenotype']))
    data=dict(audit_sources_required=True,ast_results=[dict(drug_code=drug,interpretation_basis='CLSI_2022_pheno',
         clsi_2022_phenotype='R',source_phenotype='Resistant')],
         evidence=[dict(chunk_id='label',document_title='DailyMed '+drug,document_kind='drug_label',text=quote)])
    return row,dict(claim='本例來源判讀為抗藥',evidence_refs=['label']),data


def test_v9_other_drug_who_excerpt_cannot_support_tetracycline_avoid():
    row,claim,data=fixture()
    row['quotes'][0]['quote']='Amoxicillin is listed in this fictional guideline excerpt.'
    data['evidence'][0].update(document_title='WHO lower UTI',document_kind='guideline')
    validate_audit_sources(row,claim,data)
    assert row['ast_check_validation']['status']=='confirmed'
    assert row['verdict']=='uncertain'
    assert any('未辨識本藥' in s for s in row['provenance_issues'])


def test_v9_dailymed_cannot_be_attributed_to_who_even_with_valid_ast_refs():
    row,claim,data=fixture('levofloxacin')
    row['quotes'][0]['quote']='Levofloxacin source text for this test.'
    claim['claim']='WHO與DailyMed支持此項判斷'
    validate_audit_sources(row,claim,data)
    assert row['verdict']=='uncertain'
    assert any('歸因WHO' in s for s in row['provenance_issues'])


@pytest.mark.parametrize('mutation',['missing','wrong_drug','wrong_category','wrong_basis','raw_measurement','false_unknown','false_untested'])
def test_definite_ast_claim_requires_its_own_selected_category(mutation):
    row,claim,data=fixture()
    if mutation=='missing': row['ast_check']=None
    if mutation=='wrong_drug': data['ast_results'][0]['drug_code']='other'
    if mutation=='wrong_category': row['ast_check']['assessment']='susceptible'
    if mutation=='wrong_basis': row['ast_check']['category_source_refs']=['ast_results.0.source_phenotype']
    if mutation=='raw_measurement': row['ast_check']['category_source_refs']=['ast_results.0.raw_measurement.AST_val1']
    if mutation=='false_unknown': row['ast_check'].update(assessment='unknown',category_source_refs=[])
    if mutation=='false_untested': row['ast_check'].update(assessment='untested',category_source_refs=[])
    validate_audit_sources(row,claim,data)
    assert row['verdict']=='uncertain'
    assert row['ast_check_validation']['status']=='unconfirmed'


def test_valid_label_and_category_do_not_automatically_upgrade_uncertain_verdict():
    row,claim,data=fixture()
    row['verdict']='uncertain'
    row['quotes'][0]['quote']='This product has warnings requiring review.'
    validate_audit_sources(row,claim,data)
    assert row['ast_check_validation']['status']=='confirmed'
    assert row['provenance_issues']==[]
    assert row['verdict']=='uncertain'


@pytest.mark.parametrize('tested',[True,False])
def test_missing_category_or_untested_is_not_claimed_susceptible(tested):
    row,claim,data=fixture()
    row['ast_check'].update(assessment='unknown' if tested else 'untested',category_source_refs=[])
    row['ast_check']['claim_assessment']=row['ast_check']['assessment']
    if tested: data['ast_results'][0]['clsi_2022_phenotype']=None
    else: data['ast_results']=[]
    validate_audit_sources(row,claim,data)
    assert row['ast_check_validation']['status']=='confirmed'


def test_legacy_results_remain_readable_and_new_wire_requires_ast_check():
    row,claim,data=fixture(); row['ast_check']=None
    before=copy.deepcopy(row); data['audit_sources_required']=False
    validate_audit_sources(row,claim,data)
    assert row==before
    schema=selection_schema(AuditReport)['$defs']['AuditItem']
    assert 'ast_check' in schema['required']
    assert schema['properties']['ast_check']=={'$ref':'#/$defs/ASTCheck'}
    assert not named_drug('tetracycline','oxytetracycline')
    assert named_drug('amoxicillin_clavulanate','amoxicillin + clavulanate')
    assert named_drug('amoxicillin_clavulanate','Amoxicillin+clavulanic acid')
    assert named_drug('amoxicillin_clavulanate','AMOXICILLIN AND CLAVULANATE POTASSIUM')
    assert named_drug('trimethoprim_sulfamethoxazole','Sulfamethoxazole+trimethoprim')
    assert not named_drug('amoxicillin_clavulanate','Amoxicillin alone is listed. In another paragraph, clavulanate is discussed as a separate compound.')


def test_risk_only_label_cannot_supply_drug_name_for_another_claim_quote():
    row,claim,data=fixture()
    row['quotes'].append({'chunk_id':'who','quote':'Amoxicillin adult chapter in this test.'})
    data['evidence'].append({'chunk_id':'who','document_title':'WHO book','document_kind':'guideline'})
    claim['evidence_refs']=['who']
    validate_audit_sources(row,claim,data)
    assert row['verdict']=='uncertain'
    assert any('未辨識本藥' in s for s in row['provenance_issues'])


def test_unknown_source_cannot_confirm_a_susceptible_assertion():
    row,claim,data=fixture()
    data['ast_results'][0]['clsi_2022_phenotype']=None
    row['ast_check'].update(assessment='unknown',claim_assessment='susceptible',category_source_refs=[])
    claim['claim']='本例菌株敏感'
    validate_audit_sources(row,claim,data)
    assert row['ast_check_validation']['source_status']=='confirmed'
    assert row['ast_check_validation']['claim_status']=='unconfirmed'
    assert row['verdict']=='uncertain'
