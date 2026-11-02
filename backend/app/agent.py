from __future__ import annotations
import hashlib, json, uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable
from app.agent_policy import authorize, ExecutionPolicy, GovernanceError, POLICY_VERSION

class AgentPolicyError(ValueError): pass
class AgentOutputError(ValueError): pass

TOOLS = {
 'order.read': ('order_id',),
 'bom.read': ('order_id',),
 'inventory.read': ('order_id',),
 'mrp.read': ('mrp_run_id',),
}
READ_ONLY = frozenset(TOOLS)

def canonical_hash(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str).encode()).hexdigest()

@dataclass(frozen=True)
class AgentContext:
 workflow_id: str
 order_id: str
 mrp_run_id: str
 workflow_version: int
 principal: str = 'recommendation-agent-v1'
 trace_id: str = ''

class ToolGateway:
 """Deny by default; optional audit sink records every tool decision."""
 def __init__(self, adapters: dict[str,Callable], max_calls=8, *, workflow_state='GENERATING_ADVICE', audit_sink=None):
  self.adapters=adapters
  self.max_calls=max_calls
  self.workflow_state=workflow_state
  self.audit_sink=audit_sink
  self.calls=[]
 def invoke(self, ctx:AgentContext, tool:str, args:dict):
  outcome='DENIED'; reason='TOOL_DENIED'; result=None
  try:
   try: authorize(ctx,tool,args,workflow_state=self.workflow_state)
   except GovernanceError as exc: raise AgentPolicyError(str(exc)) from exc
   if tool not in self.adapters: raise AgentPolicyError('TOOL_DENIED')
   if len(self.calls)>=self.max_calls: raise AgentPolicyError('TOOL_BUDGET_EXCEEDED')
   try: result=self.adapters[tool](**args)
   except Exception:
    outcome='ERROR'; reason='TOOL_ADAPTER_ERROR'
    raise
   outcome='ALLOWED'; reason='OK'
   self.calls.append({'tool':tool,'args_hash':canonical_hash(args),'result_hash':canonical_hash(result),
                      'policy_version':POLICY_VERSION})
   return result
  except AgentPolicyError as exc:
   reason=str(exc)
   raise
  finally:
   if self.audit_sink is not None:
    self.audit_sink({'workflow_id':ctx.workflow_id,'trace_id':ctx.trace_id,
                     'principal':ctx.principal,'tool':tool,'outcome':outcome,
                     'reason':reason,'args_hash':canonical_hash(args),
                     'result_hash':canonical_hash(result) if outcome=='ALLOWED' else None,
                     'policy_version':POLICY_VERSION})

def validate_draft(draft, facts):
 if not isinstance(draft,dict) or set(draft)!={'mrp_run_id','order_id','lines','summary','risk_flags'}:
  raise AgentOutputError('INVALID_DRAFT_SCHEMA')
 if draft['mrp_run_id']!=facts['mrp_run_id'] or draft['order_id']!=facts['order_id']:
  raise AgentOutputError('DRAFT_SCOPE_MISMATCH')
 if not isinstance(draft['lines'],list) or not isinstance(draft['summary'],str) or not isinstance(draft['risk_flags'],list):
  raise AgentOutputError('INVALID_DRAFT_FIELDS')
 expected={}
 for x in facts['lines']:
  if x['type']=='BUY' and Decimal(str(x['planned_qty']))>0:
   expected[str(x['material'])]=expected.get(str(x['material']),Decimal('0'))+Decimal(str(x['planned_qty']))
 found={}
 for line in draft['lines']:
  if not isinstance(line,dict) or set(line)!={'material','quantity','reason'}: raise AgentOutputError('INVALID_LINE_SCHEMA')
  material=line['material']
  if material in found or material not in expected or not isinstance(line['reason'],str): raise AgentOutputError('UNSUPPORTED_MATERIAL')
  try: qty=Decimal(str(line['quantity']))
  except Exception as exc: raise AgentOutputError('INVALID_QUANTITY') from exc
  if not qty.is_finite() or qty!=expected[material]: raise AgentOutputError('MRP_QUANTITY_MUTATION_DENIED')
  found[material]=qty
 if found!=expected: raise AgentOutputError('MISSING_BUY_LINE')
 return draft

def summarize_buy(facts):
 totals={}
 for x in facts['lines']:
  if x['type']=='BUY' and Decimal(str(x['planned_qty']))>0:
   m=str(x['material'])
   totals[m]=totals.get(m,Decimal('0'))+Decimal(str(x['planned_qty']))
 return totals

def deterministic_model(facts):
 """Offline contract model; not an LLM or a production recommendation."""
 return {'mrp_run_id':facts['mrp_run_id'],'order_id':facts['order_id'],
         'lines':[{'material':m,'quantity':str(q),
                   'reason':'MRP 全局运行汇总采购需求；不得视为单订单归属'}
                  for m,q in summarize_buy(facts).items()],
         'summary':'基于已持久化 MRP 全局运行结果生成待审核建议（非单订单归属；离线契约模型）',
         'risk_flags':['HUMAN_REVIEW_REQUIRED']}

def execute_agent(ctx, gateway, model=deterministic_model, *, policy=None):
 policy=policy or ExecutionPolicy()
 model_id='offline-contract-v1' if model is deterministic_model else 'external-injected'
 try: policy.check_model(model_id)
 except GovernanceError as exc: raise AgentPolicyError(str(exc)) from exc
 if gateway.max_calls > policy.max_tool_calls: gateway.max_calls=policy.max_tool_calls
 facts=gateway.invoke(ctx,'mrp.read',{'mrp_run_id':ctx.mrp_run_id})
 if facts.get('mrp_run_id')!=ctx.mrp_run_id or facts.get('order_id')!=ctx.order_id or facts.get('status')!='COMPLETED':
  raise AgentPolicyError('MRP_FACTS_NOT_VERIFIED')
 draft=validate_draft(model(facts),facts)
 try: policy.check_draft(draft)
 except GovernanceError as exc: raise AgentPolicyError(str(exc)) from exc
 return {'draft':draft,'facts_hash':canonical_hash(facts),'draft_hash':canonical_hash(draft),
         'tool_calls':gateway.calls.copy(),'model_id':model_id,'policy_version':policy.version}

def postgres_mrp_adapter(conn):
 """Reads persisted M2 run; material lines are scoped to the workflow order."""
 from app.db.integrated import read_integrated_run
 def read_mrp(mrp_run_id):
  run=read_integrated_run(conn,mrp_run_id)
  return run
 return read_mrp

def _read_scoped_mrp_facts(conn, ctx, mrp_run_id):
 """Actual database-backed tool adapter; every invocation goes through ToolGateway."""
 from app.db.integrated import read_integrated_run
 if mrp_run_id != ctx.mrp_run_id:
  raise AgentPolicyError('CROSS_RUN_READ_DENIED')
 run=read_integrated_run(conn,mrp_run_id)
 mrp_rows=run['result']['mrp_lines']
 if not isinstance(mrp_rows,list): raise AgentPolicyError('MRP_LINES_SCHEMA_INVALID')
 material_ids={row['material'] for row in mrp_rows}
 with conn.cursor() as cur:
  cur.execute('SELECT material_id,make_buy FROM mock_erp.materials WHERE material_id = ANY(%s)',(sorted(material_ids),))
  kinds=dict(cur.fetchall())
 if material_ids-set(kinds): raise AgentPolicyError('MRP_MATERIAL_NOT_FOUND')
 if any(kinds[m] not in ('BUY','MAKE') for m in material_ids): raise AgentPolicyError('MRP_MATERIAL_KIND_INVALID')
 lines=[{'material':row['material'],'planned_qty':row['planned'],'type':kinds[row['material']]} for row in mrp_rows]
 # The M2 result may aggregate multiple orders; never imply per-order pegging.
 return {'mrp_run_id':mrp_run_id,'order_id':ctx.order_id,'status':run['status'],'lines':lines}

def generate_and_persist(conn,workflow_id,model=deterministic_model):
 """V0.3: audited DB fact read, draft and state transition in ONE transaction.

 The transaction also covers workflow inbox/audit/outbox. On any failure all
 successful-path tool audit and draft writes roll back together. Rejections
 before the transaction are not recorded here; see the documented limitation.
 """
 from app.workflow.runtime import read,dispatch_in_transaction,WorkflowConflict
 from psycopg.types.json import Jsonb
 if conn.info.transaction_status.name!='IDLE': raise RuntimeError('AGENT_REQUIRES_IDLE_CONNECTION')
 state=read(conn,workflow_id)
 if state['state']!='GENERATING_ADVICE': raise AgentPolicyError('WORKFLOW_NOT_GENERATING_ADVICE')
 if not state['mrp_run_id']: raise AgentPolicyError('MRP_RUN_ID_MISSING')
 ctx=AgentContext(workflow_id,state['order_id'],state['mrp_run_id'],state['version'])
 with conn.transaction():
  with conn.cursor() as cur:
   cur.execute('SELECT state,version,mrp_run_id,order_id FROM platform.workflow_instances WHERE instance_id=%s FOR UPDATE',(workflow_id,))
   locked=cur.fetchone()
   if locked!=('GENERATING_ADVICE',ctx.workflow_version,ctx.mrp_run_id,ctx.order_id):
    raise WorkflowConflict('STALE_AGENT_CONTEXT')
  def audit_sink(event):
   # Insert in the SAME transaction; no nested independent commit.
   with conn.cursor() as cur:
    cur.execute("""INSERT INTO platform.agent_tool_audit
      (workflow_id,trace_id,principal,tool_name,policy_version,outcome,reason_code,args_hash,result_hash)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (event['workflow_id'],event['trace_id'],event['principal'],event['tool'],
       event['policy_version'],event['outcome'],event['reason'],event['args_hash'],event['result_hash']))
  gateway=ToolGateway({'mrp.read':lambda mrp_run_id:_read_scoped_mrp_facts(conn,ctx,mrp_run_id)},
                      workflow_state=state['state'],audit_sink=audit_sink)
  result=execute_agent(ctx,gateway,model)
  with conn.cursor() as cur:
   cur.execute("""INSERT INTO platform.agent_drafts(workflow_id,mrp_run_id,workflow_version,model_id,facts_hash,draft_hash,draft,tool_trace)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (workflow_id,workflow_version) DO NOTHING RETURNING draft_id""",
               (workflow_id,ctx.mrp_run_id,ctx.workflow_version,result['model_id'],result['facts_hash'],result['draft_hash'],Jsonb(result['draft']),Jsonb(result['tool_calls'])))
   if cur.fetchone() is None:
    cur.execute('SELECT draft_hash FROM platform.agent_drafts WHERE workflow_id=%s AND workflow_version=%s',(workflow_id,ctx.workflow_version))
    existing=cur.fetchone()
    if not existing or existing[0]!=result['draft_hash']: raise WorkflowConflict('AGENT_DRAFT_HASH_CONFLICT')
  event_id=f'AGENT:{workflow_id}:{ctx.workflow_version}:ADVICE_DRAFTED'
  transition=dispatch_in_transaction(conn,workflow_id,event_id,'ADVICE_DRAFTED',
                                     {'draft_hash':result['draft_hash']},expected_version=ctx.workflow_version)
 return {'workflow':transition,**result}
