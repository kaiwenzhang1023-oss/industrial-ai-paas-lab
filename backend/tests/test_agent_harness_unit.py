import pytest
from app.agent import AgentContext, ToolGateway, AgentPolicyError, AgentOutputError, execute_agent, deterministic_model, validate_draft

FACTS={'mrp_run_id':'R1','order_id':'SO1','status':'COMPLETED','lines':[{'material':'HS','planned_qty':'10','type':'BUY'},{'material':'HS','planned_qty':'5','type':'BUY'},{'material':'ST','planned_qty':'20','type':'MAKE'}]}
CTX=AgentContext('WF1','SO1','R1',3)
def gateway(): return ToolGateway({'mrp.read':lambda mrp_run_id:FACTS})
def test_offline_agent_contract():
 result=execute_agent(CTX,gateway())
 assert result['draft']['lines'][0]['quantity']=='15'
 assert result['tool_calls'][0]['tool']=='mrp.read'
def test_denies_unregistered_and_write_tools():
 for tool in ['erp.purchase_request.create','shell.exec','inventory.write']:
  with pytest.raises(AgentPolicyError): gateway().invoke(CTX,tool,{'order_id':'SO1'})
def test_denies_cross_run_and_invalid_args():
 with pytest.raises(AgentPolicyError): gateway().invoke(CTX,'mrp.read',{'mrp_run_id':'OTHER'})
 with pytest.raises(AgentPolicyError): gateway().invoke(CTX,'mrp.read',{'mrp_run_id':'R1','extra':1})
def test_rejects_mrp_mutation_and_omission():
 draft=deterministic_model(FACTS)
 draft['lines'][0]['quantity']='16'
 with pytest.raises(AgentOutputError): validate_draft(draft,FACTS)
 draft=deterministic_model(FACTS)
 draft['lines']=[]
 with pytest.raises(AgentOutputError): validate_draft(draft,FACTS)
def test_rejects_bad_scope_and_unverified_facts():
 with pytest.raises(AgentPolicyError): execute_agent(CTX,ToolGateway({'mrp.read':lambda mrp_run_id:{**FACTS,'status':'FAILED'}}))
def test_tool_budget():
 g=ToolGateway({'mrp.read':lambda mrp_run_id:FACTS},max_calls=1)
 g.invoke(CTX,'mrp.read',{'mrp_run_id':'R1'})
 with pytest.raises(AgentPolicyError):g.invoke(CTX,'mrp.read',{'mrp_run_id':'R1'})
