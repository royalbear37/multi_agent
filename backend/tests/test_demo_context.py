import copy
from scripts.update_demo_context import update
from app.adapters.microbiology import DEMO_CONTEXT


def test_context_update_is_idempotent_and_preserves_source_and_user_edits():
    source = {'data_origin': 'hybrid', 'encounter': {'context': '模擬情境：原內容'},
              'provenance': {'source_system': 'local-microbiology-csv', 'simulated_fields': ['encounter']},
              'ast_results': [{'drug_code': 'test', 'reported_sir': 'R'}]}
    original = copy.deepcopy(source)
    assert update(source)
    assert source['encounter']['context'] == original['encounter']['context'] + DEMO_CONTEXT
    assert source['ast_results'] == original['ast_results']
    assert not update(source)
    source['encounter']['context'] = '使用者另寫的真實紀錄'
    assert not update(source)
    source['data_origin'] = 'deidentified'
    assert not update(source)
