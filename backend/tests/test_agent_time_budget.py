"""Virtual-clock schedules: no sleeping, model calls, or billable requests."""
import pytest
from app.agents import runtime_led as rt
from app.workflow import agent_led
from app.workflow.engine import execute
from app.workflow.time_budget import TimeBudget
from tests.test_agent_led import Docs, case, successful


def test_reservations_scale_to_explicit_short_deadline():
    budget=TimeBudget(0,480,rt.AGENTS)
    assert sum(budget.reservations)==pytest.approx(408)
    assert budget.reservations[-1]==pytest.approx(122.4)
    assert budget.call_timeout(357.6,5,180)==pytest.approx(122.4)


@pytest.mark.parametrize('repair_role',['case_agent','clinical_agent'])
def test_slow_search_and_repair_leave_full_audit_window(monkeypatch,repair_role):
    clock=[0.0];seen=[]
    monkeypatch.delenv('LLM_AGENT_LED_TIMEOUT_SECONDS',raising=False)
    monkeypatch.setattr(agent_led.time,'perf_counter',lambda:clock[0])
    class SlowDocs(Docs):
        def search(self,query,**kw):
            clock[0]+=30
            return super().search(query,**kw)
    def reply(self,agent,data,**kwargs):
        seen.append((agent.id,kwargs['timeout']))
        clock[0]+=kwargs['timeout']
        out=successful(self,agent,data,**kwargs)
        if agent.id==repair_role and sum(a==agent.id for a,_ in seen)==1:
            if repair_role=='clinical_agent': out['output']['drugs'][0].pop('status')
            else: out['output']['missing_fields']='invalid array'
        return out
    monkeypatch.setattr(rt.Provider,'complete',reply)
    run=execute(case(allergies={'status':'known_present','items':[{'drug_code':'other','severity':'mild'}]}),'multi-agent','mock',SlowDocs())
    assert seen[-1][0]=='evidence_audit' and seen[-1][1]==pytest.approx(180)
    assert len(seen)<=8 and clock[0]<=780
    assert run['budget']['reserved_role_seconds']['evidence_audit']==180
    assert any(r['status']=='budget_reserved' for r in run['retrievals'])


def test_provider_overrunning_stage_is_not_published_or_retried(monkeypatch):
    clock=[0.0]
    monkeypatch.setattr(agent_led.time,'perf_counter',lambda:clock[0])
    def reply(self,agent,data,**kwargs):
        out=successful(self,agent,data,**kwargs)
        if agent.id=='clinical_agent':clock[0]+=kwargs['timeout']+1
        return out
    monkeypatch.setattr(rt.Provider,'complete',reply)
    run=execute(case(),'multi-agent','mock',Docs())
    node=next(n for n in run['nodes'] if n['node_id']=='clinical_agent')
    assert node['output'] is None and len(node['attempts'])==1
    assert node['errors'][0]['code']=='AGENT_STAGE_TIMEOUT'
    assert not run['output']['candidates']
