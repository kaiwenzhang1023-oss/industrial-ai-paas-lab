import pytest
from app.agent import AgentContext, ToolGateway, AgentPolicyError, execute_agent, deterministic_model
from app.agent_policy import ExecutionPolicy, POLICY_VERSION

CTX=AgentContext('WF1','SO1','RUN1',3,trace_id='TRACE1')
FACTS={'mrp_run_id':'RUN1','order_id':'SO1','status':'COMPLETED',
       'lines':[{'material':'HS','planned_qty':'20','type':'BUY'}]}

def test_read_policy_and_version():
    g=ToolGateway({'mrp.read':lambda mrp_run_id:FACTS})
    out=execute_agent(CTX,g)
    assert out['policy_version']==POLICY_VERSION
    assert out['tool_calls'][0]['policy_version']==POLICY_VERSION

def test_deny_wrong_workflow_state():
    g=ToolGateway({'mrp.read':lambda mrp_run_id:FACTS},workflow_state='WAITING_REVIEW')
    with pytest.raises(AgentPolicyError,match='WORKFLOW_STATE_DENIED'):
        g.invoke(CTX,'mrp.read',{'mrp_run_id':'RUN1'})

def test_deny_unapproved_model_before_tool_read():
    g=ToolGateway({'mrp.read':lambda mrp_run_id:FACTS})
    with pytest.raises(AgentPolicyError,match='MODEL_NOT_APPROVED'):
        execute_agent(CTX,g,model=lambda facts:deterministic_model(facts))
    assert not g.calls

def test_audit_denied_and_allowed_hash_only():
    events=[]
    g=ToolGateway({'mrp.read':lambda mrp_run_id:FACTS},audit_sink=events.append)
    with pytest.raises(AgentPolicyError):g.invoke(CTX,'erp.purchase_request.create',{'order_id':'SO1'})
    g.invoke(CTX,'mrp.read',{'mrp_run_id':'RUN1'})
    assert [e['outcome'] for e in events]==['DENIED','ALLOWED']
    assert all('args' not in e and 'result' not in e for e in events)
    assert events[1]['result_hash'] and events[0]['result_hash'] is None

def test_adapter_error_audited():
    events=[]
    def broken(mrp_run_id):raise RuntimeError('adapter down')
    g=ToolGateway({'mrp.read':broken},audit_sink=events.append)
    with pytest.raises(RuntimeError,match='adapter down'):
        g.invoke(CTX,'mrp.read',{'mrp_run_id':'RUN1'})
    assert events[0]['outcome']=='ERROR'

def test_budget_and_scope_audited():
    events=[]
    g=ToolGateway({'mrp.read':lambda mrp_run_id:FACTS},max_calls=1,audit_sink=events.append)
    with pytest.raises(AgentPolicyError,match='CROSS_RUN_READ_DENIED'):
        g.invoke(CTX,'mrp.read',{'mrp_run_id':'OTHER'})
    g.invoke(CTX,'mrp.read',{'mrp_run_id':'RUN1'})
    with pytest.raises(AgentPolicyError,match='TOOL_BUDGET_EXCEEDED'):
        g.invoke(CTX,'mrp.read',{'mrp_run_id':'RUN1'})
    assert [e['outcome'] for e in events]==['DENIED','ALLOWED','DENIED']

def test_human_review_flag_required():
    def model(facts):
        d=deterministic_model(facts)
        d['risk_flags']=[]
        return d
    with pytest.raises(AgentPolicyError,match='HUMAN_REVIEW_FLAG_REQUIRED'):
        execute_agent(CTX,ToolGateway({'mrp.read':lambda mrp_run_id:FACTS}),model=model,
                      policy=ExecutionPolicy(allowed_models=frozenset({'external-injected'})))

@pytest.mark.integration
def test_pg_governance_audit_and_workflow_integration():
    import os
    if not os.getenv('TEST_DATABASE_URL'): pytest.skip('TEST_DATABASE_URL required')
    from pathlib import Path
    from app.db.repository import connect, seed
    from app.db.integrated import seed_effective_bom
    from app.workflow.runtime import create,dispatch
    from app.workflow.scheduler import durable_mrp_runner
    from app.agent import generate_and_persist
    with connect(os.environ['TEST_DATABASE_URL']) as db:
        db.autocommit=True
        seed(db,Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json')
        seed_effective_bom(db)
        wid=create(db,'SO-2026-001')['workflow_id']
        dispatch(db,wid,'v02-start-'+wid,'START',{})
        dispatch(db,wid,'v02-valid-'+wid,'VALIDATION_PASSED',{})
        run_id=durable_mrp_runner(db,wid,'SO-2026-001','2026-11-20')
        dispatch(db,wid,'v02-mrp-'+wid,'MRP_COMPLETED',{'mrp_run_id':run_id})
        out=generate_and_persist(db,wid)
        assert out['workflow']['state']=='WAITING_REVIEW'
        with db.cursor() as cur:
            cur.execute('SELECT outcome,tool_name,policy_version,args_hash,result_hash FROM platform.agent_tool_audit WHERE workflow_id=%s',(wid,))
            rows=cur.fetchall()
            assert len(rows)==1 and rows[0][:3]==('ALLOWED','mrp.read',POLICY_VERSION)
            assert rows[0][3] and rows[0][4]
