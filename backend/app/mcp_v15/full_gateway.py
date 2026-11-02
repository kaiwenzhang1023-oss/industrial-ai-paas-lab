"""Test-gated MCP orchestration, trusted HMAC claims, read-only adapters, durable audit.

This is an in-process gateway, NOT a network MCP server. Authentication secrets and
business DB connections must be held only by a trusted host; never exposed to callers.
"""
import base64, hashlib, hmac, json, time, uuid
from dataclasses import dataclass
from .integration import execute

SPECS={
 'mrp.get_run':('MRP_RUN','run_id',{'run_id'}),
 'wms.get_inventory':('MATERIAL','material_id',{'material_id','warehouse_id'}),
 'mes.get_work_order':('MES_WORK_ORDER','work_order_id',{'work_order_id'}),
 'srm.list_requisitions':('MRP_RUN','run_id',{'run_id','limit'}),
 'mapping.preview_b01':('MRP_RUN','run_id',{'run_id'}),
}
class Rejected(ValueError): pass

def canonical(obj):
 return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def _unb64(s): return base64.urlsafe_b64decode(s+'='*((-len(s))%4))

@dataclass(frozen=True)
class VerifiedIdentity:
 tenant: str
 principal: str
 expires: int

def issue_test_token(secret,tenant,principal,expires):
 if len(secret)<32 or not tenant or not principal: raise Rejected('INVALID_TOKEN_INPUT')
 payload=_b64(canonical({'tenant':tenant,'principal':principal,'exp':int(expires)}).encode())
 return payload+'.'+_b64(hmac.new(secret.encode(),payload.encode(),hashlib.sha256).digest())

def verify_token(secret,token,now=None):
 if not isinstance(secret,str) or len(secret)<32 or not isinstance(token,str) or len(token)>4096: raise Rejected('UNTRUSTED_IDENTITY')
 try:
  payload,sig=token.split('.')
  mac=hmac.new(secret.encode(),payload.encode(),hashlib.sha256).digest()
  if not hmac.compare_digest(mac,_unb64(sig)): raise Rejected('BAD_SIGNATURE')
  data=json.loads(_unb64(payload))
  if set(data)!={'tenant','principal','exp'} or not isinstance(data['exp'],int) or isinstance(data['exp'],bool): raise Rejected('BAD_CLAIMS')
  if not all(isinstance(data[k],str) and 0<len(data[k])<=128 for k in ('tenant','principal')): raise Rejected('BAD_CLAIMS')
  if data['exp']<=int(time.time() if now is None else now): raise Rejected('TOKEN_EXPIRED')
  return VerifiedIdentity(data['tenant'],data['principal'],data['exp'])
 except Rejected: raise
 except (ValueError,TypeError,UnicodeError,KeyError): raise Rejected('INVALID_TOKEN') from None

def validate(tool,args):
 if tool not in SPECS: raise Rejected('UNKNOWN_TOOL')
 if not isinstance(args,dict): raise Rejected('ARGUMENTS_NOT_OBJECT')
 typ,key,allowed=SPECS[tool]
 if set(args)-allowed or key not in args: raise Rejected('INVALID_ARGUMENT_SCHEMA')
 if not isinstance(args[key],str) or not (1<=len(args[key])<=128): raise Rejected('INVALID_RESOURCE_ID')
 if any(not isinstance(v,str) or not 1<=len(v)<=128 for k,v in args.items() if k not in ('limit',)): raise Rejected('INVALID_ARGUMENT_SCHEMA')
 if 'limit' in args and (type(args['limit']) is not int or not 1<=args['limit']<=100): raise Rejected('INVALID_LIMIT')
 canonical(args)
 return typ,args[key]

class FullGateway:
 """Dedicated runtime DB connection and separate trusted read-only business connection.

 Release switch is per-instance; default is deny. No HTTP request may control it.
 Runtime connection must have role mcp_v15_runtime_test (SET LOCAL ROLE) for each transaction.
 """
 def __init__(self,secret,release_enabled=False,clock=None):
  if not isinstance(secret,str) or len(secret)<32: raise ValueError('SECRET_TOO_SHORT')
  self._secret=secret; self._release=bool(release_enabled); self._clock=clock or time.time

 def invoke(self,runtime_conn,business_conn,token,tool,args,deadline_seconds=10):
  identity=verify_token(self._secret,token,self._clock())
  resource_type,resource_id=validate(tool,args)
  if type(deadline_seconds) not in (int,float) or not 0<deadline_seconds<=30: raise Rejected('INVALID_DEADLINE')
  digest=hashlib.sha256(canonical(args).encode()).hexdigest()
  call=uuid.uuid4(); event=uuid.uuid4()
  status='DENIED'; reason='RELEASE_DISABLED'; result=None
  # In each transaction SET LOCAL ROLE ensures low privilege, even if connection is pooled.
  with runtime_conn.transaction():
   with runtime_conn.cursor() as cur:
    cur.execute('SET LOCAL ROLE mcp_v15_runtime_test')
    cur.execute('SELECT mcp_v15.runtime_receive(%s,%s,%s,%s,%s,%s,%s)',
      (call,identity.tenant,identity.principal,tool,'1.0',digest,event))
    cur.execute('SELECT mcp_v15.authorize_runtime(%s,%s,%s,%s,%s)',
      (identity.tenant,identity.principal,'read',resource_type,resource_id))
    allowed=bool(cur.fetchone()[0])
    if not allowed: reason='RESOURCE_DENIED'
    elif self._release: status='AUTHORIZED'; reason=None
    cur.execute('SELECT mcp_v15.runtime_advance(%s,%s,%s,%s,%s)',(call,'RECEIVED',0,status,uuid.uuid4()))
    if cur.fetchone()[0] is not True: raise RuntimeError('AUDIT_CAS_FAILED')
  if status=='DENIED': return {'call_id':str(call),'status':status,'error_code':reason}
  with runtime_conn.transaction():
   with runtime_conn.cursor() as cur:
    cur.execute('SET LOCAL ROLE mcp_v15_runtime_test')
    cur.execute('SELECT mcp_v15.runtime_advance(%s,%s,%s,%s,%s)',(call,'AUTHORIZED',1,'RUNNING',uuid.uuid4()))
    if cur.fetchone()[0] is not True: raise RuntimeError('RUNNING_CAS_FAILED')
  started=self._clock()
  try:
   # Business connection is trusted and separate; transaction explicitly read-only.
   with business_conn.transaction():
    with business_conn.cursor() as cur:
     cur.execute('SET TRANSACTION READ ONLY')
     cur.execute('SET LOCAL ROLE mcp_v15_business_reader_test')
     cur.execute('SELECT set_config(%s,%s,true)',('statement_timeout',str(int(deadline_seconds*1000))))
    result=execute(business_conn,tool,args)
   if self._clock()-started>deadline_seconds: raise TimeoutError('DEADLINE_EXCEEDED')
   status='COMPLETED'; reason=None
  except Exception as exc:
   status='TIMED_OUT' if isinstance(exc,TimeoutError) or getattr(exc,'sqlstate',None)=='57014' else 'FAILED'
   reason='DEADLINE_EXCEEDED' if status=='TIMED_OUT' else 'BUSINESS_EXECUTION_FAILED'
   result=None
  with runtime_conn.transaction():
   with runtime_conn.cursor() as cur:
    cur.execute('SET LOCAL ROLE mcp_v15_runtime_test')
    cur.execute('SELECT mcp_v15.runtime_advance(%s,%s,%s,%s,%s)',(call,'RUNNING',2,status,uuid.uuid4()))
    if cur.fetchone()[0] is not True: raise RuntimeError('TERMINAL_CAS_FAILED')
  response={'call_id':str(call),'status':status}
  if status=='COMPLETED': response['result']=result
  else: response['error_code']=reason
  return response
