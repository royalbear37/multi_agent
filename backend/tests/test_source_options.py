import copy
from app.agents.source_options import ast_source_options, bind_source_options
from app.agents.citation_spans import selection_schema
from app.agents.contracts_led import ASTReport, SynthesisReport
from app.agents import runtime_led as rt
from app.agents.runtime_v2 import AgentProvider


def test_options_preserve_missing_selected_category_and_cannot_infer_from_mic():
    rows=[dict(drug_code='ertapenem',interpretation_basis='CLSI_2022_pheno',
               clsi_2022_phenotype=None,source_phenotype='Susceptible',reported_sir=None,
               mic=None,raw_measurement={'AST_val1':'<=0.5'},source='long source explanation')]
    saved=copy.deepcopy(rows)
    options=ast_source_options(rows)
    assert options[0]['selected_value'] is None
    assert options[0]['selected_field']=='ast_results.0.clsi_2022_phenotype'
    assert options[0]['categorical_fields']==[{'ref':'ast_results.0.source_phenotype','value':'Susceptible'}]
    wire=bind_source_options(selection_schema(ASTReport),options,[])
    assert wire['$defs']['ASTItem']['properties']['category_source_refs']['items']['enum']==['ast_results.0.source_phenotype']
    assert rows==saved


def test_ast_wire_explicit_options_do_not_replace_the_models_choice(monkeypatch):
    data=dict(facts={},ast_results=[dict(drug_code='a',reported_sir='S')],evidence=[],drugs=['a'],assessments={},claims=[])
    def fake(self,agent,wire,**kw):
        assert wire['ast_category_sources'][0]['selected_field']=='ast_results.0.reported_sir'
        assert wire['ast_category_sources'][0]['selected_value']=='S'
        assert agent.output_type.model_json_schema()['$defs']['ASTItem']['properties']['category_source_refs']['items']['enum']==['ast_results.0.reported_sir']
        return {'output':{'rapid_assessment':'unknown','resistance_assessment':'unknown','drugs':[{'drug_code':'a','assessment':'susceptible','reason':'test','category_source_refs':['invalid source description']}]}}
    monkeypatch.setattr(AgentProvider,'complete',fake)
    result=rt.Provider('live',rt.AGENTS[1]).complete(rt.AGENTS[1],data,timeout=1)
    assert result['output']['drugs']==[] and result['wire_errors']
    assert 'ast_category_sources' not in data


def test_reference_enums_are_local_to_each_call_and_do_not_change_canonical_schema():
    canonical=SynthesisReport.model_json_schema()
    wire=bind_source_options(selection_schema(SynthesisReport),[],['E1','E2'])
    assert wire['$defs']['Decision']['properties']['evidence_refs']['items']['enum']==['E1','E2']
    empty=bind_source_options(selection_schema(SynthesisReport),[],[])
    assert empty['$defs']['Decision']['properties']['evidence_refs']['maxItems']==0
    assert SynthesisReport.model_json_schema()==canonical
