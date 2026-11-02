"""V1.4 Batch A: PostgreSQL-only SRM; never mutates upstream MRP/WMS/MES."""
from __future__ import annotations
import hashlib, json
from datetime import date
from decimal import Decimal

class SRMError(ValueError): pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def stable(prefix,value): return prefix+'-'+digest(value)[:24]
def qty(v):
    d=Decimal(str(v))
    if not d.is_finite() or d<=0 or d.as_tuple().exponent < -4 or d>Decimal('99999999999999.9999'): raise SRMError('INVALID_QUANTITY')
    return d

def audit(cur,kind,entity,action,payload):
    from psycopg.types.json import Jsonb
    cur.execute('INSERT INTO srm_v14.audit(entity_type,entity_id,action,payload) VALUES(%s,%s,%s,%s)',(kind,entity,action,Jsonb(payload)))

def supplier_upsert(conn,supplier_id,code,name,expected_revision=None):
    if not all([supplier_id.strip(),code.strip(),name.strip()]): raise SRMError('INVALID_SUPPLIER')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT revision FROM srm_v14.suppliers WHERE supplier_id=%s FOR UPDATE',(supplier_id,))
            row=cur.fetchone()
            if row:
                if expected_revision is None or row[0]!=expected_revision: raise SRMError('STALE_REVISION')
                cur.execute('UPDATE srm_v14.suppliers SET code=%s,name=%s,revision=revision+1 WHERE supplier_id=%s',(code,name,supplier_id))
                rev=row[0]+1
            else:
                if expected_revision not in (None,0): raise SRMError('STALE_REVISION')
                cur.execute('INSERT INTO srm_v14.suppliers(supplier_id,code,name) VALUES(%s,%s,%s)',(supplier_id,code,name)); rev=0
            audit(cur,'SUPPLIER',supplier_id,'UPSERT',{'revision':rev,'code':code})
    return {'supplier_id':supplier_id,'revision':rev}

def supplier_item(conn,supplier_id,material_id,moq='0',lead_days=0,capacity=None):
    m=Decimal(str(moq)); c=Decimal(str(capacity)) if capacity is not None else None
    if not m.is_finite() or m<0 or (c is not None and (not c.is_finite() or c<=0)) or lead_days<0: raise SRMError('INVALID_SUPPLIER_ITEM')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('INSERT INTO srm_v14.supplier_items(supplier_id,material_id,moq,lead_days,capacity) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(supplier_id,material_id) DO UPDATE SET moq=EXCLUDED.moq,lead_days=EXCLUDED.lead_days,capacity=EXCLUDED.capacity',(supplier_id,material_id,m,lead_days,c))
            audit(cur,'SUPPLIER_ITEM',supplier_id+':'+material_id,'UPSERT',{'moq':str(m),'lead_days':lead_days})
    return {'supplier_id':supplier_id,'material_id':material_id}

def normalize_buy(mrp,kinds):
    if mrp['status']!='COMPLETED': raise SRMError('MRP_NOT_COMPLETED')
    seen=set(); result=[]
    for lot in mrp['result'].get('plan_lots',[]):
        material=lot['material']; kind=kinds.get(material)
        if kind is None: raise SRMError('UNKNOWN_MATERIAL:'+material)
        if kind!='BUY': continue
        plan=lot['plan_id']
        if not plan or plan in seen: raise SRMError('DUPLICATE_PLAN_ID')
        seen.add(plan)
        try:
            q=qty(lot['quantity']); need=date.fromisoformat(lot['need_date']); release=date.fromisoformat(lot['release_date'])
        except (KeyError,TypeError,ValueError) as e: raise SRMError('INVALID_BUY_PLAN') from e
        result.append({'source_run_id':mrp['run_id'],'source_result_hash':mrp['result_hash'],'source_plan_id':plan,'material_id':material,'quantity':q,'need_date':need,'release_date':release,'bom_version':lot.get('bom_version')})
    if not result: raise SRMError('NO_BUY_PLANS')
    return result

def import_mrp(conn,run_id):
    from app.db.integrated import read_integrated_run
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT run_id FROM platform.requirement_runs WHERE run_id=%s FOR SHARE',(run_id,))
            if not cur.fetchone(): raise SRMError('MRP_RUN_NOT_FOUND')
            mrp=read_integrated_run(conn,run_id)
            cur.execute('SELECT material_id,make_buy,uom FROM mock_erp.materials')
            items={r[0]:(r[1],r[2]) for r in cur.fetchall()}
            plans=normalize_buy(mrp,{k:v[0] for k,v in items.items()})
            ids=[]
            for x in plans:
                pr=stable('PR',{'run':run_id,'plan':x['source_plan_id']})
                expected=(x['source_result_hash'],x['material_id'],x['quantity'],items[x['material_id']][1],x['need_date'],x['release_date'],x['bom_version'])
                cur.execute('INSERT INTO srm_v14.purchase_requisitions(pr_id,source_run_id,source_result_hash,source_plan_id,material_id,quantity,uom,need_date,release_date,bom_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_run_id,source_plan_id) DO NOTHING',(pr,run_id,x['source_result_hash'],x['source_plan_id'],x['material_id'],x['quantity'],items[x['material_id']][1],x['need_date'],x['release_date'],x['bom_version']))
                inserted=cur.rowcount
                cur.execute('SELECT pr_id,source_result_hash,material_id,quantity,uom,need_date,release_date,bom_version FROM srm_v14.purchase_requisitions WHERE source_run_id=%s AND source_plan_id=%s',(run_id,x['source_plan_id']))
                row=cur.fetchone()
                if row!=(pr,*expected): raise SRMError('BUY_SOURCE_CONFLICT')
                if inserted: audit(cur,'PR',pr,'IMPORT',{'source_run_id':run_id,'source_plan_id':x['source_plan_id'],'source_result_hash':x['source_result_hash']})
                ids.append(pr)
    return {'run_id':run_id,'result_hash':mrp['result_hash'],'pr_ids':ids,'count':len(ids),'simulation':True}

def create_po(conn,po_id,supplier_id,pr_id):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT material_id,quantity,need_date,status FROM srm_v14.purchase_requisitions WHERE pr_id=%s FOR UPDATE',(pr_id,))
            pr=cur.fetchone()
            if not pr: raise SRMError('PR_NOT_FOUND')
            if pr[3]!='OPEN': raise SRMError('PR_ALREADY_ORDERED')
            cur.execute('SELECT 1 FROM srm_v14.supplier_items WHERE supplier_id=%s AND material_id=%s',(supplier_id,pr[0]))
            if not cur.fetchone(): raise SRMError('SUPPLIER_ITEM_NOT_FOUND')
            cur.execute('INSERT INTO srm_v14.purchase_orders(po_id,supplier_id) VALUES(%s,%s)',(po_id,supplier_id))
            line=stable('POL',{'po':po_id,'pr':pr_id})
            cur.execute('INSERT INTO srm_v14.purchase_order_lines(po_line_id,po_id,pr_id,material_id,ordered_qty,required_date) VALUES(%s,%s,%s,%s,%s,%s)',(line,po_id,pr_id,pr[0],pr[1],pr[2]))
            cur.execute("UPDATE srm_v14.purchase_requisitions SET status='ORDERED' WHERE pr_id=%s",(pr_id,))
            audit(cur,'PO',po_id,'CREATE',{'pr_id':pr_id,'po_line_id':line})
    return {'po_id':po_id,'po_line_id':line,'status':'DRAFT','revision':0}

def transition(conn,po_id,status,expected_revision):
    allowed={'DRAFT':{'ISSUED','CANCELLED'},'ISSUED':{'CANCELLED','REJECTED'},'PARTIALLY_CONFIRMED':{'CANCELLED'},'CONFIRMED':{'CANCELLED'}}
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT status,revision FROM srm_v14.purchase_orders WHERE po_id=%s FOR UPDATE',(po_id,)); row=cur.fetchone()
            if not row: raise SRMError('PO_NOT_FOUND')
            if row[1]!=expected_revision: raise SRMError('STALE_REVISION')
            if status not in allowed.get(row[0],set()): raise SRMError('INVALID_PO_TRANSITION')
            cur.execute('UPDATE srm_v14.purchase_orders SET status=%s,revision=revision+1 WHERE po_id=%s',(status,po_id))
            audit(cur,'PO',po_id,'TRANSITION',{'from':row[0],'to':status})
    return {'po_id':po_id,'status':status,'revision':expected_revision+1}

def confirm(conn,po_id,confirmation_id,schedules,expected_revision):
    if not schedules: raise SRMError('EMPTY_CONFIRMATION')
    normalized=[]; seen=set()
    for s in schedules:
        sid=s['schedule_id']; line=s['po_line_id']
        if not sid or sid in seen: raise SRMError('DUPLICATE_SCHEDULE')
        seen.add(sid)
        normalized.append({'schedule_id':sid,'po_line_id':line,'confirmed_qty':str(qty(s['confirmed_qty'])),'promised_date':date.fromisoformat(str(s['promised_date'])).isoformat()})
    event_hash=digest({'po_id':po_id,'schedules':sorted(normalized,key=lambda x:x['schedule_id'])})
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT status,revision FROM srm_v14.purchase_orders WHERE po_id=%s FOR UPDATE',(po_id,)); po=cur.fetchone()
            if not po: raise SRMError('PO_NOT_FOUND')
            cur.execute('SELECT po_id,event_hash FROM srm_v14.supplier_confirmations WHERE confirmation_id=%s',(confirmation_id,)); existing=cur.fetchone()
            if existing:
                if existing[0]!=po_id or existing[1]!=event_hash: raise SRMError('CONFIRMATION_ID_CONFLICT')
                return {'po_id':po_id,'confirmation_id':confirmation_id,'status':po[0],'revision':po[1],'idempotent':True}
            if po[1]!=expected_revision: raise SRMError('STALE_REVISION')
            if po[0] not in ('ISSUED','PARTIALLY_CONFIRMED'): raise SRMError('PO_NOT_CONFIRMABLE')
            cur.execute('SELECT po_line_id,ordered_qty,required_date FROM srm_v14.purchase_order_lines WHERE po_id=%s',(po_id,)); lines={r[0]:(r[1],r[2]) for r in cur.fetchall()}
            if not lines or any(s['po_line_id'] not in lines for s in normalized): raise SRMError('FOREIGN_PO_LINE')
            cur.execute('SELECT s.po_line_id,COALESCE(SUM(s.confirmed_qty),0) FROM srm_v14.supplier_confirmation_schedules s JOIN srm_v14.supplier_confirmations c USING(confirmation_id) WHERE c.po_id=%s GROUP BY s.po_line_id',(po_id,)); totals={r[0]:r[1] for r in cur.fetchall()}
            for s in normalized: totals[s['po_line_id']]=totals.get(s['po_line_id'],Decimal(0))+Decimal(s['confirmed_qty'])
            if any(totals.get(k,Decimal(0))>v[0] for k,v in lines.items()): raise SRMError('CONFIRMED_QTY_EXCEEDS_ORDER')
            cur.execute('INSERT INTO srm_v14.supplier_confirmations(confirmation_id,po_id,event_hash) VALUES(%s,%s,%s)',(confirmation_id,po_id,event_hash))
            for s in normalized:
                cur.execute('INSERT INTO srm_v14.supplier_confirmation_schedules(schedule_id,confirmation_id,po_line_id,confirmed_qty,promised_date) VALUES(%s,%s,%s,%s,%s)',(s['schedule_id'],confirmation_id,s['po_line_id'],s['confirmed_qty'],s['promised_date']))
            for line,(ordered,required) in lines.items():
                cur.execute('SELECT s.confirmed_qty,s.promised_date FROM srm_v14.supplier_confirmation_schedules s JOIN srm_v14.supplier_confirmations c USING(confirmation_id) WHERE c.po_id=%s AND s.po_line_id=%s',(po_id,line))
                parts=cur.fetchall(); late=[(q,(d-required).days) for q,d in parts if d>required]
                risk=sum((q for q,days in late),Decimal(0)); days=max((d for q,d in late),default=0)
                eid=stable('EXC',{'line':line,'type':'DELIVERY_DELAY'})
                cur.execute('SELECT risk_qty,late_days,evidence_hash FROM srm_v14.supply_exceptions WHERE po_line_id=%s AND exception_type=%s FOR UPDATE',(line,'DELIVERY_DELAY'))
                previous=cur.fetchone()
                if risk:
                    evidence=digest(sorted((str(q),d.isoformat()) for q,d in parts))
                    if previous is None or previous!=(risk,days,evidence):
                        cur.execute('INSERT INTO srm_v14.supply_exceptions(exception_id,po_line_id,exception_type,risk_qty,late_days,evidence_hash) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(po_line_id,exception_type) DO UPDATE SET risk_qty=EXCLUDED.risk_qty,late_days=EXCLUDED.late_days,evidence_hash=EXCLUDED.evidence_hash',(eid,line,'DELIVERY_DELAY',risk,days,evidence))
                        audit(cur,'SUPPLY_EXCEPTION',eid,'OPEN' if previous is None else 'UPDATE',{'po_id':po_id,'po_line_id':line,'before':None if previous is None else {'risk_qty':str(previous[0]),'late_days':previous[1],'evidence_hash':previous[2]},'after':{'risk_qty':str(risk),'late_days':days,'evidence_hash':evidence}})
                elif previous is not None:
                    cur.execute('DELETE FROM srm_v14.supply_exceptions WHERE po_line_id=%s AND exception_type=%s',(line,'DELIVERY_DELAY'))
                    audit(cur,'SUPPLY_EXCEPTION',eid,'RESOLVE',{'po_id':po_id,'po_line_id':line,'before':{'risk_qty':str(previous[0]),'late_days':previous[1],'evidence_hash':previous[2]}})
            new_status='CONFIRMED' if all(totals.get(k,Decimal(0))==v[0] for k,v in lines.items()) else 'PARTIALLY_CONFIRMED'
            cur.execute('UPDATE srm_v14.purchase_orders SET status=%s,revision=revision+1 WHERE po_id=%s',(new_status,po_id))
            audit(cur,'CONFIRMATION',confirmation_id,'CONFIRM',{'po_id':po_id,'schedules':normalized,'status':new_status})
    return {'po_id':po_id,'confirmation_id':confirmation_id,'status':new_status,'revision':expected_revision+1,'idempotent':False}

def list_requisitions(conn,limit=100):
    with conn.cursor() as cur:
        cur.execute('SELECT pr_id,source_run_id,source_plan_id,material_id,quantity,uom,need_date,status FROM srm_v14.purchase_requisitions ORDER BY created_at DESC,pr_id LIMIT %s',(limit,))
        return [dict(zip(['pr_id','source_run_id','source_plan_id','material_id','quantity','uom','need_date','status'],[str(x) if isinstance(x,(Decimal,date)) else x for x in row])) for row in cur.fetchall()]

def list_exceptions(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT exception_id,po_line_id,exception_type,risk_qty,late_days,status FROM srm_v14.supply_exceptions ORDER BY exception_id')
        return [dict(zip(['exception_id','po_line_id','exception_type','risk_qty','late_days','status'],[str(x) if isinstance(x,Decimal) else x for x in row])) for row in cur.fetchall()]
