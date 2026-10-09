"""Bounded role budgets and explicit truncation diagnostics; no external requests."""
import pytest
from app.agents import runtime_led as rt, runtime_v2 as legacy
from app.workflow.engine import execute
from tests.test_agent_led import case, Docs, successful

@pytest.mark.parametrize('role,expected', [('case_agent',6000),('synthesis_agent',16000),('evidence_audit',24000)])
def test_role_budget_is_sent_and_provider_finish_reason_retained(monkeypatch,role,expected):
    for key in ['LLM_AGENT_LED_MAX_OUTPUT_TOKENS','LLM_AGENT_SYNTHESIS_MAX_OUTPUT_TOKENS','LLM_AGENT_AUDIT_MAX_OUTPUT_TOKENS']:
        monkeypatch.delenv(key,raising=False)
    captured=[]
    def request(self,payload):
        captured.append(payload)
        return {'choices':[{'finish_reason':'length','message':{'content':'{}'}}],'usage':{'completion_tokens':expected}},0
    monkeypatch.setattr(legacy.OpenAICompatibleProvider,'_request',request)
    agent=next(a for a in rt.AGENTS if a.id==role)
    reply=rt.Provider('live',agent).complete(agent,{'evidence':[],'ast_results':[]},timeout=1)
    assert captured[0]['max_tokens']==expected
    assert reply['finish_reason']=='length' and reply['output'] is None
    assert reply['output_token_limit']==expected and reply['usage']['completion_tokens']==expected


def test_configured_budget_honored_and_legacy_cap_unchanged(monkeypatch):
    captured=[]
    monkeypatch.setattr(legacy.OpenAICompatibleProvider,'_request',lambda self,payload:(captured.append(payload) or {'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]},0))
    agent=next(a for a in rt.AGENTS if a.id=='synthesis_agent')
    monkeypatch.setenv(agent.output_tokens_setting,'6000')
    legacy.AgentProvider('live',agent).complete(agent,{},timeout=1)
    assert captured[-1]['max_tokens']==6000
    monkeypatch.setenv(agent.output_tokens_setting,'999999')
    legacy.AgentProvider('live',agent).complete(agent,{},timeout=1)
    assert captured[-1]['max_tokens']==24000
    monkeypatch.setenv('LLM_V2_MAX_OUTPUT_TOKENS','999999')
    old=legacy.AGENTS[0]
    legacy.AgentProvider('live',old).complete(old,{},timeout=1)
    assert captured[-1]['max_tokens']==8000


def test_truncation_does_not_retry_identical_budget_or_publish_partial_json(monkeypatch):
    def reply(self,agent,data,**kwargs):
        if agent.id=='synthesis_agent':
            assert 60 < kwargs['timeout'] <= 180
            return {'output':None,'finish_reason':'length','output_token_limit':16000,'usage':{'total_tokens':16000}}
        return successful(self,agent,data,**kwargs)
    monkeypatch.setattr(rt.Provider,'complete',reply)
    run=execute(case(),'multi-agent','mock',Docs())
    node=next(n for n in run['nodes'] if n['node_id']=='synthesis_agent')
    assert len(node['attempts'])==1 and node['errors'][0]['code']=='AGENT_OUTPUT_TRUNCATED'
    assert node['attempts'][0]['finish_reason']=='length'
    assert node['attempts'][0]['usage']['total_tokens']==16000
    assert run['agent_execution']['calls']==5 and not run['output']['candidates']
    assert next(n for n in run['nodes'] if n['node_id']=='evidence_audit')['status']=='not_applicable'
