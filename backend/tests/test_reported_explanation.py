from types import SimpleNamespace
from app.rules.reported import evaluate_ast


def test_missing_derived_label_does_not_claim_source_resistance():
    engine = SimpleNamespace(allowed_drugs=lambda: ['drug'], supports=lambda organism: True)
    result = evaluate_ast(engine, {'microbiology': {'report_status': 'final'}, 'ast_results': [{
        'drug_code': 'drug', 'interpretation_basis': 'CLSI_2022_pheno',
        'source_phenotype': 'Susceptible', 'clsi_2022_phenotype': None,
        'reported_sir': None, 'standard': 'CLSI', 'standard_version': '2022',
    }]})[0]
    assert result['eligible'] is False
    assert 'CLSI 2022 衍生判讀缺漏' in result['reason']
    assert '來源結果不是 S' not in result['reason']
