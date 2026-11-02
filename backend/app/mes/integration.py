"""V1.3 Batch B: immutable MRP->MES adapter and transactional MES simulation.
No writeback to ERP/MRP/WMS. Caller must supply a previously initialized V1.3 database.
"""
from __future__ import annotations
import hashlib
from decimal import Decimal
from app.db.integrated import read_integrated_run
from app.mes.core import (Operation, Routing, WorkOrderSpec, WorkOrder, Feedback, Status,
                          load_plan, capacity_plan, dec)


def make_specs(mrp, kinds, routings):
    if mrp['status'] != 'COMPLETED': raise ValueError('MRP_NOT_COMPLETED')
    specs=[]
    for lot in mrp['result'].get('plan_lots',[]):
        product=lot['material']
        if kinds.get(product) != 'MAKE': continue
        plan_id=lot['plan_id']
        if not plan_id or dec(lot['quantity']) <= 0: raise ValueError('INVALID_MRP_PLAN')
        version='V1'
        if (product,version) not in routings: raise ValueError('ROUTING_NOT_FOUND:'+product)
        work_id='MES-'+hashlib.sha256((mrp['run_id']+'|'+plan_id).encode()).hexdigest()[:24]
        specs.append(WorkOrderSpec(work_id,mrp['run_id'],plan_id,mrp['result_hash'],
                                   product,dec(lot['quantity']),lot['need_date'],version))
    if not specs: raise ValueError('NO_MAKE_PLANS')
    return specs


def load_routings(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT product_id,routing_version,operation_id,sequence,work_center,setup_hours,hours_per_unit
          FROM mes_v13.routings ORDER BY product_id,routing_version,sequence""")
        rows=cur.fetchall()
    grouped={}
    for p,v,oid,seq,center,setup,unit in rows:
        grouped.setdefault((p,v),[]).append(Operation(oid,seq,center,setup,unit))
    return {key:Routing(key[0],key[1],tuple(ops)) for key,ops in grouped.items()}


def create_from_mrp(conn, run_id):
    """Idempotent creation; lock referenced MRP rows, never recompute or mutate them."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT run_id FROM platform.requirement_runs WHERE run_id=%s FOR SHARE',(run_id,))
            if not cur.fetchone(): raise ValueError('MRP_RUN_NOT_FOUND')
        mrp=read_integrated_run(conn,run_id)  # persisted canonical hash check
        with conn.cursor() as cur:
            cur.execute('SELECT material_id,make_buy FROM mock_erp.materials')
            kinds=dict(cur.fetchall())
        routings=load_routings(conn)
        specs=make_specs(mrp,kinds,routings)
        orders=load_plan(specs,routings)
        with conn.cursor() as cur:
            for wo in orders:
                s=wo.spec
                cur.execute("""INSERT INTO mes_v13.work_orders
                 (work_order_id,source_run_id,source_plan_id,source_result_hash,product_id,quantity,due_date,routing_version)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(work_order_id) DO NOTHING""",
                 (s.work_order_id,s.source_run_id,s.source_plan_id,s.source_result_hash,s.product_id,s.quantity,s.due_date,s.routing_version))
                cur.execute("""SELECT source_run_id,source_plan_id,source_result_hash,product_id,quantity,due_date,routing_version
                 FROM mes_v13.work_orders WHERE work_order_id=%s""",(s.work_order_id,))
                existing=cur.fetchone()
                if existing!=(s.source_run_id,s.source_plan_id,s.source_result_hash,s.product_id,s.quantity,__import__('datetime').date.fromisoformat(s.due_date),s.routing_version):
                    raise ValueError('MES_WORK_ORDER_ID_CONFLICT')
    return {'source_run_id':run_id,'source_result_hash':mrp['result_hash'],
            'work_order_ids':[x.spec.work_order_id for x in orders],'count':len(orders),'simulation':True}


def read_orders(conn,limit=100):
    with conn.cursor() as cur:
        cur.execute("""SELECT work_order_id,source_run_id,source_plan_id,source_result_hash,product_id,
         quantity,due_date,routing_version,status,revision FROM mes_v13.work_orders
         ORDER BY created_at DESC,work_order_id LIMIT %s""",(limit,))
        rows=cur.fetchall()
    keys=['work_order_id','source_run_id','source_plan_id','source_result_hash','product_id','quantity','due_date','routing_version','status','revision']
    return [{k:(v.isoformat() if hasattr(v,'isoformat') else str(v) if isinstance(v,Decimal) else v) for k,v in zip(keys,row)} for row in rows]


def reconstruct(conn,work_id,lock=False):
    with conn.cursor() as cur:
        cur.execute("""SELECT work_order_id,source_run_id,source_plan_id,source_result_hash,product_id,
         quantity,due_date,routing_version,status,revision FROM mes_v13.work_orders WHERE work_order_id=%s"""+(' FOR UPDATE' if lock else ''),(work_id,))
        r=cur.fetchone()
        if not r: raise ValueError('MES_WORK_ORDER_NOT_FOUND')
        cur.execute("""SELECT event_id,operation_id,good_qty,scrap_qty,event_date FROM mes_v13.feedback_events
          WHERE work_order_id=%s ORDER BY recorded_at,event_id""",(work_id,))
        events=cur.fetchall()
    spec=WorkOrderSpec(r[0],r[1],r[2],r[3],r[4],r[5],r[6].isoformat(),r[7])
    routing=load_routings(conn).get((r[4],r[7]))
    if not routing: raise ValueError('ROUTING_NOT_FOUND')
    wo=WorkOrder(spec,routing,Status(r[8]))
    wo.feedback={e[0]:Feedback(e[0],e[1],e[2],e[3],e[4].isoformat()) for e in events}
    return wo,r[9]


def transition(conn,work_id,new_status,expected_revision):
    from psycopg.types.json import Jsonb
    with conn.transaction():
        wo,revision=reconstruct(conn,work_id,True)
        if revision!=expected_revision: raise ValueError('STALE_MES_REVISION')
        wo.transition(Status(new_status))
        with conn.cursor() as cur:
            cur.execute('UPDATE mes_v13.work_orders SET status=%s,revision=revision+1 WHERE work_order_id=%s',
                        (wo.status.value,work_id))
            cur.execute('INSERT INTO mes_v13.audit(work_order_id,event_type,detail) VALUES(%s,%s,%s)',
                        (work_id,'TRANSITION',Jsonb({'to':wo.status.value,'from_revision':revision})))
    return {**wo.progress(),'revision':revision+1}


def feedback(conn,work_id,event,expected_revision):
    from psycopg.types.json import Jsonb
    with conn.transaction():
        wo,revision=reconstruct(conn,work_id,True)
        old=wo.feedback.get(event.event_id)
        if old is not None:
            if old!=event: raise ValueError('EVENT_ID_CONFLICT')
            return {**wo.progress(),'revision':revision,'idempotent':True}
        if revision!=expected_revision: raise ValueError('STALE_MES_REVISION')
        wo.record(event)
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO mes_v13.feedback_events
                (event_id,work_order_id,operation_id,good_qty,scrap_qty,event_date) VALUES(%s,%s,%s,%s,%s,%s)""",
                (event.event_id,work_id,event.operation_id,event.good_qty,event.scrap_qty,event.event_date))
            cur.execute('UPDATE mes_v13.work_orders SET revision=revision+1 WHERE work_order_id=%s',(work_id,))
            cur.execute('INSERT INTO mes_v13.audit(work_order_id,event_type,detail) VALUES(%s,%s,%s)',
                        (work_id,'FEEDBACK',Jsonb({'event_id':event.event_id,'operation_id':event.operation_id})))
    return {**wo.progress(),'revision':revision+1,'idempotent':False}


def plan_capacity(conn,work_ids,daily_capacity,start_date):
    # Caller-provided daily capacity: planning-only; persisted allocations are replaced atomically.
    with conn.transaction():
        orders=[reconstruct(conn,wid,True)[0] for wid in sorted(set(work_ids))]
        result=capacity_plan(orders,{(r['work_center'],r['day']):dec(r['hours']) for r in daily_capacity},start_date)
        with conn.cursor() as cur:
            # Fail closed when a separate persisted plan already occupies a requested
            # capacity bucket. The caller's capacity is not an additive entitlement.
            requested = {(r['work_center'], r['day']) for r in daily_capacity}
            cur.execute('SELECT work_order_id,work_center,day FROM mes_v13.capacity_allocations FOR UPDATE')
            for existing_id, center, day in cur.fetchall():
                if existing_id not in set(work_ids) and (center,day.isoformat()) in requested:
                    raise ValueError('EXTERNAL_CAPACITY_RESERVATION_CONFLICT')
            for wid in sorted(set(work_ids)):
                cur.execute('DELETE FROM mes_v13.capacity_allocations WHERE work_order_id=%s',(wid,))
            for r in result['allocations']:
                cur.execute("""INSERT INTO mes_v13.capacity_allocations
                    (work_order_id,operation_id,work_center,day,hours) VALUES(%s,%s,%s,%s,%s)""",
                    (r['work_order_id'],r['operation_id'],r['work_center'],r['day'],r['hours']))
    return result
