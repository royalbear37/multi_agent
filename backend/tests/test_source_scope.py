"""Regression excerpts represent source-linkage cases, not clinical advice."""
import copy
import pytest
from app.workflow.source_scope import source_scope_issues, label_identity_issue
from app.workflow.risk_details import validate_risk_details
from app.workflow.claim_checks import validate_claim_checks


def label(drug, heading=None, text=''):
    return dict(chunk_id='e',document_kind='drug_label',document_title='DailyMed '+drug,
        location={'heading_path':[heading or drug.upper()+' TABLET','Selected section']},text=text)


@pytest.mark.parametrize('dimension',['infection','allergy','renal','interactions'])
def test_imipenem_short_title_cannot_hide_recarbrio_product_scope(dimension):
    e=label('imipenem','RECARBRIO (IMIPENEM ANHYDROUS, CILASTATIN, AND RELEBACTAM ANHYDROUS) INJECTION')
    q=[dict(chunk_id='e',quote='Imipenem combination labeling: allergy, renal and drug interactions.')]
    assert any('複方' in s for s in source_scope_issues('imipenem',dimension,q,[e]))


def test_same_ingredient_form_and_exact_combination_are_not_wrong_products():
    assert label_identity_issue('nitrofurantoin',label('nitrofurantoin','NITROFURANTOIN (MONOHYDRATE/MACROCRYSTALS) CAPSULE')) is None
    assert label_identity_issue('imipenem_cilastatin_relebactam',label('imipenem_cilastatin_relebactam','RECARBRIO (IMIPENEM ANHYDROUS, CILASTATIN, AND RELEBACTAM ANHYDROUS) INJECTION')) is None
    assert label_identity_issue('amoxicillin_clavulanate',label('amoxicillin_clavulanate','AMOXICILLIN AND CLAVULANATE POTASSIUM TABLET')) is None


def test_who_plazomicin_table_is_not_imipenem_renal_evidence():
    q=[dict(chunk_id='e',quote='Table 47.2 Plazomicin suggested doses. Adjust doses in renal impairment.')]
    e=dict(chunk_id='e',document_kind='reference',document_title='WHO book')
    assert any('未辨識本藥' in s for s in source_scope_issues('imipenem','renal',q,[e]))


def test_other_drug_topic_cannot_borrow_identity_from_a_different_quote():
    quotes=[dict(chunk_id='one',quote='Meropenem is described for complicated infection.'),
            dict(chunk_id='two',quote='Aztreonam requires renal dose adjustment.')]
    evidence=[dict(chunk_id=k,document_kind='reference',document_title='Reference') for k in ['one','two']]
    assert any('風險面向' in s for s in source_scope_issues('meropenem','renal',quotes,evidence))
    quotes[0]['quote']='Meropenem renal dose adjustment requires individual review.'
    assert not source_scope_issues('meropenem','renal',quotes[:1],evidence)


@pytest.mark.parametrize('text',[
    'Probenecid decreases renal tubular secretion. Tell patients before changing dosage of diabetes medication.',
    'Geriatric use: excreted by the kidney; take care in dose selection. Patients with hepatic impairment were studied.',
    'Elderly patients may have decreased renal function; monitor and make dosage adjustments accordingly.',
    'No alteration in renal laboratory parameters was observed after administration.',
    'No adjustment in renal function was observed after administration.',
])
def test_unrelated_dose_words_and_geriatric_monitoring_cannot_establish_no_renal_adjustment(text):
    assert any('劑量調整依據' in s for s in source_scope_issues('ampicillin','renal',[dict(chunk_id='e',quote=text)],[label('ampicillin')],'正常腎功能無需調整劑量'))


@pytest.mark.parametrize('statement',['避免與 valproic acid 合用','valproic acid 與 meropenem 併用應避免','丙戊酸（valproic acid）與 meropenem 併用應避免','避免 valproic acid'])
def test_selected_interaction_must_name_the_medicine_in_next_action(statement):
    q=[dict(chunk_id='e',quote='In vitro tests show meropenem synergy with aminoglycoside antibacterial drugs.')]
    issues=source_scope_issues('meropenem','interactions',q,[label('meropenem')],statement)
    assert any('valproic acid' in s for s in issues)
    assert not source_scope_issues('meropenem','interactions',[dict(chunk_id='e',quote='Interaction: coadministration with valproic acid requires review.')],[label('meropenem')],'避免與 valproic acid 合用')


@pytest.mark.parametrize('text',[
    'Renal Impairment: dosage adjustment is required for severe impairment (GFR less than 30 mL/min).',
    'No alteration of dosage is necessary for patients over 65 with normal renal function.',
    'Meropenem dosage alteration is not required in patients with renal impairment.',
    'Meropenem dosage modifications are not required in patients with renal impairment.',
])
def test_real_dosing_passage_is_not_rejected_as_missing_source(text):
    assert not source_scope_issues('ciprofloxacin','renal',[dict(chunk_id='e',quote=text)],[label('ciprofloxacin')],'無需調整劑量')


def test_allergy_and_in_vitro_mutagenesis_are_not_interaction_passages():
    q=[dict(chunk_id='e',quote='Aztreonam hypersensitivity warning. In vitro mutagenesis testing in animals.')]
    assert any('風險面向' in s for s in source_scope_issues('aztreonam','interactions',q,[label('aztreonam')]))


def test_clinical_failure_is_per_dimension_and_valid_other_drug_is_preserved():
    row=dict(drug_code='meropenem',status='no_identified_risk',reason='初評',quotes=[dict(chunk_id='e',quote='Allergy warning. Renal dose adjustment. In vitro synergy with aminoglycosides.')],
        risk_details={d:dict(status='no_identified_risk',reason='已核對',next_action='',fact_refs=[p],evidence_refs=['e'],missing_fields=[])
            for d,p in [('allergy','allergies.status'),('renal','renal.egfr'),('interactions','medications')]})
    data=dict(facts={'allergies':{'status':'known_none'},'renal':{'egfr':90},'medications':[],'medication_history_status':'reviewed_none'},evidence=[label('meropenem')])
    valid=copy.deepcopy(row);validate_risk_details(valid,data)
    assert valid['status']=='no_identified_risk'
    row['risk_details']['interactions']['next_action']='避免與 valproic acid 合用'
    validate_risk_details(row,data)
    assert row['status']=='unknown' and row['risk_details']['interactions']['validation_issues']
    assert row['risk_details']['allergy']['status']=='no_identified_risk'
    assert valid['status']=='no_identified_risk'


def test_audit_supported_verdict_cannot_bypass_source_scope_failure():
    dims=['infection','ast','allergy','renal','interactions']
    claims=[dict(dimension=d,statement='待核對',fact_refs=[],evidence_refs=['e'] if d!='ast' else []) for d in dims]
    claims[3]['statement']='腎功能正常無需調整'
    row=dict(drug_code='ertapenem',basis='mixed',verdict='supported',ast_check_validation={'status':'confirmed'},
        quotes=[dict(chunk_id='e',quote='Ertapenem adult infection. Allergy warning. Drug interactions. Elderly renal monitoring and dose selection.')],
        claim_checks=[dict(dimension=d,verdict='supported',reason='聲稱支持',fact_refs=[],evidence_refs=['e'] if d!='ast' else [],infection_match='supported',population_match='supported',drug_match='supported') for d in dims])
    validate_claim_checks(row,{'claims':claims},{'evidence':[label('ertapenem')],'facts':{}})
    assert row['verdict']=='uncertain'
    assert row['claim_checks'][0]['verdict']=='supported'
    assert row['claim_checks'][3]['verdict']=='uncertain'
