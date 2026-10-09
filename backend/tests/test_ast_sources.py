import pytest
from app.workflow.ast_sources import validate_ast_sources
from app.adapters.microbiology import ast_row


@pytest.mark.parametrize('ref',['ast_results.0.raw_measurement.AST_val1','ast_results.0.mic',
    'ast_results.0.source_phenotype','ast_results.0.clsi_2022_phenotype','ast_results.0.reported_sir'])
def test_v7_missing_clsi_cannot_be_replaced_by_raw_measurement_or_original_label(ref):
    source=ast_row({'antibiotic':'ertapenem','AST_pheno':'Susceptible','CLSI_2022_pheno':'',
        'AST_panel':'broth_microdilution','AST_val1':'0.5','AST_inequality':'<='})
    assert source['reported_sir'] is None and source['source_phenotype']=='Susceptible'
    assert 'missing/unrecognized' in source['source']
    row={'drug_code':'ertapenem','assessment':'susceptible','reason':'待核對', 'category_source_refs':[ref]}
    validate_ast_sources(row,{'ast_sources_required':True,'ast_results':[source]})
    assert row['assessment']=='unknown'


@pytest.mark.parametrize('basis,field,value,state',[
    ('CLSI_2022_pheno','clsi_2022_phenotype','S','susceptible'),
    ('source_report','source_phenotype','Resistant','resistant'),
    ('legacy','reported_sir','I','intermediate')])
def test_explicit_category_source_is_preserved(basis,field,value,state):
    source={'drug_code':'a','interpretation_basis':basis,field:value}
    row={'drug_code':'a','assessment':state,'reason':'依明示類別','category_source_refs':[f'ast_results.0.{field}']}
    validate_ast_sources(row,{'ast_sources_required':True,'ast_results':[source]})
    assert row['assessment']==state
    assert row['category_sources'][0]['value']==value


def test_cannot_borrow_other_drug_or_change_resistant_to_susceptible():
    for drug,label in [('other','S'),('a','R')]:
        row={'drug_code':'a','assessment':'susceptible','reason':'測試','category_source_refs':['ast_results.0.reported_sir']}
        validate_ast_sources(row,{'ast_sources_required':True,'ast_results':[{'drug_code':drug,'reported_sir':label}]})
        assert row['assessment']=='unknown'


@pytest.mark.parametrize('basis',['legacy',None])
def test_legacy_basis_cannot_use_a_different_original_report_category(basis):
    row={'drug_code':'a','assessment':'susceptible','reason':'incorrect original report substitution',
         'category_source_refs':['ast_results.0.source_phenotype']}
    validate_ast_sources(row,{'ast_sources_required':True,'ast_results':[{'drug_code':'a',
        'interpretation_basis':basis,'reported_sir':'R','source_phenotype':'Susceptible'}]})
    assert row['assessment']=='unknown'
    assert row['source_validation']['status']=='unconfirmed'


def test_original_clsi_disagreement_can_be_traced_without_recalculation():
    row={'drug_code':'a','assessment':'conflicting','reason':'來源不一致',
         'category_source_refs':['ast_results.0.source_phenotype','ast_results.0.clsi_2022_phenotype']}
    validate_ast_sources(row,{'ast_sources_required':True,'ast_results':[{'drug_code':'a',
        'interpretation_basis':'CLSI_2022_pheno','source_phenotype':'Susceptible','clsi_2022_phenotype':'R'}]})
    assert row['assessment']=='conflicting' and len(row['category_sources'])==2


@pytest.mark.parametrize('selected,comparison,refs,expected',[
    ('S','Susceptible',['clsi_2022_phenotype','source_phenotype'],'susceptible'),
    ('S','Susceptible',['source_phenotype'],'unknown'),
    (None,'Susceptible',['source_phenotype'],'unknown'),
    ('R','Susceptible',['clsi_2022_phenotype','source_phenotype'],'unknown'),
])
def test_v9_matching_comparison_source_does_not_invalidate_present_selected_basis(selected,comparison,refs,expected):
    row={'drug_code':'a','assessment':'susceptible','reason':'模型來源判讀',
         'category_source_refs':['ast_results.0.'+field for field in refs]}
    validate_ast_sources(row,{'ast_sources_required':True,'ast_results':[{'drug_code':'a',
        'interpretation_basis':'CLSI_2022_pheno','clsi_2022_phenotype':selected,'source_phenotype':comparison}]})
    assert row['assessment']==expected
