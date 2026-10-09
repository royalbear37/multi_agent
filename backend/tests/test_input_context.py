import copy
import json

from app.agents import runtime_led as rt
from app.workflow.engine import execute
from app.workflow.input_context import compact_sources, assessment_source_refs
from tests.test_agent_led import case, Docs, successful


def test_metadata_compaction_preserves_source_meaning_permissions_and_snapshot():
    source = {'chunk_id':'e1','doc_id':'d1','text':'Original source text',
        'location':{'page':566,'section':'Warnings'},'population':'pediatric',
        'document_kind':'drug_label','document_version':'v1','is_synthetic':False,
        'external_model_allowed':False,'source_document_id':'original-who',
        'source_location':{'page':566},'source_derivation':'redundant storage detail '*10000}
    before=copy.deepcopy(source)
    result=compact_sources([source])[0]
    assert result['text']==source['text'] and result['location']==source['location']
    assert result['population']=='pediatric' and not result['external_model_allowed']
    assert result['source_document_id']=='original-who'
    assert len(json.dumps(result))<1000 and source==before
    result['location']['page']=1
    assert source['location']['page']==566


def test_synthesis_ref_collection_keeps_nested_risk_refs():
    value={'drugs':[{'quotes':[{'chunk_id':'quote','quote':'some text'}],
        'risk_details':{'renal':{'evidence_refs':['renal']}},'evidence_refs':['top']}]}
    assert assessment_source_refs(value)=={'quote','renal','top'}


def test_full_flow_does_not_count_storage_metadata_or_unused_catalog_as_context(monkeypatch):
    class MetadataDocs(Docs):
        def search(self,query,**kwargs):
            base=super().search(query,**kwargs)['evidence'][0]
            base['source_derivation']='storage metadata '*15000
            return {'status':'ok','evidence':[base]+[
                {**base,'chunk_id':f'unused-{i}','text':'Unselected source',
                 'document_title':'Long document title '*100} for i in range(200)]}
    inputs={}
    def reply(self,agent,data,**kw):
        inputs[agent.id]=copy.deepcopy(data)
        assert len(json.dumps(data,ensure_ascii=False))<180000
        return successful(self,agent,data,**kw)
    monkeypatch.setattr(rt.Provider,'complete',reply)
    result=execute(case(),'multi-agent','mock',MetadataDocs())
    assert result['agent_execution']['calls']==6 and not result['errors']
    assert [e['chunk_id'] for e in inputs['synthesis_agent']['evidence']]==['e1']
    assert len(result['evidence_snapshots'])==201
    assert result['evidence_snapshots'][0]['source_derivation']
    assert inputs['evidence_audit']['evidence'][0]['text']==result['evidence_snapshots'][0]['text']
