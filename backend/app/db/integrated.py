"""M2 integration: DB-only versioned MRP with atomic, reproducible JSONB results.

Uses a single REPEATABLE READ transaction and SHARE locks for all source reads.
No JSON fallback. Does not claim WMS reservation or production integration.
"""
import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from app.db.repository import SOURCE_TABLES
from app.domain.timephased import Item, Order
from app.domain.versioned_bom import BOMRevision
from app.domain.acceptance import run_acceptance

SOURCE_TABLES_V2 = SOURCE_TABLES + (
    'mock_erp.effective_bom_headers', 'mock_erp.effective_bom_components'
)

def canonical_hash(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), default=str).encode('utf-8')).hexdigest()

def read_integrated_sources(conn, as_of):
    """Caller owns a snapshot transaction and its locks."""
    with conn.cursor() as cur:
        cur.execute("SELECT order_id,product_id,quantity,due_date,priority,version FROM mock_erp.sales_orders WHERE status='CONFIRMED' ORDER BY due_date,priority DESC,order_id")
        rows=cur.fetchall()
        orders=[Order(r[0],r[1],r[2],r[3].isoformat(),r[4]) for r in rows]
        versions={'orders':[(r[0],int(r[5])) for r in rows]}
        cur.execute('''SELECT m.material_id,m.make_buy,m.lead_days,m.safety_stock,m.moq,m.lot_multiple,
            COALESCE(SUM(i.on_hand),0),COALESCE(SUM(i.reserved),0),COALESCE(SUM(i.blocked),0)
            FROM mock_erp.materials m LEFT JOIN mock_wms.inventory_balances i ON m.material_id=i.material_id
            GROUP BY m.material_id,m.make_buy,m.lead_days,m.safety_stock,m.moq,m.lot_multiple ORDER BY m.material_id''')
        item_rows=cur.fetchall()
        cur.execute('''SELECT material_id,supply_id,arrival_date,open_qty FROM mock_erp.supply_orders
                       WHERE status='CONFIRMED' AND open_qty>0 ORDER BY material_id,arrival_date,supply_id''')
        receipts={}; supply_ids={}; receipt_provenance={}
        for material,sid,arrival,qty in cur.fetchall():
            # Older receipts are carried forward as available supply at the planning horizon.
            day=max(arrival,date.fromisoformat(as_of)).isoformat()
            receipts.setdefault(material,[]).append((day,qty))
            supply_ids.setdefault(material,[]).append(sid)
            index=len(receipts[material])
            internal=f'RECEIPT:{material}:{index:06}@{day}'
            receipt_provenance[internal]={'source_system':'ERP','source_document_id':str(sid),
                'source_line_id':str(sid),'material_id':material,'effective_date':day}
        items={r[0]:Item(r[0],r[1],r[2],r[6],r[7],r[8],r[3],r[4],r[5],tuple(receipts.get(r[0],[]))) for r in item_rows}
        cur.execute('''SELECT parent_id,version,status,valid_from,valid_to_exclusive
                       FROM mock_erp.effective_bom_headers ORDER BY parent_id,version''')
        headers=cur.fetchall()
        cur.execute('''SELECT parent_id,version,line_no,component_id,qty_per
                       FROM mock_erp.effective_bom_components ORDER BY parent_id,version,line_no''')
        parts={}
        for parent,version,_,child,qty in cur.fetchall(): parts.setdefault((parent,version),[]).append((child,qty))
        revisions=[BOMRevision(parent,version,start.isoformat(),end.isoformat() if end else None,status,
                    tuple(parts.get((parent,version),[]))) for parent,version,status,start,end in headers]
        cur.execute('''SELECT material_id,warehouse_id,lot_id,version FROM mock_wms.inventory_balances
                       ORDER BY material_id,warehouse_id,lot_id''')
        versions['inventory']=[(a,b,c,int(d)) for a,b,c,d in cur.fetchall()]
        versions['supply_ids']=supply_ids
        versions['receipt_provenance']=receipt_provenance
        versions['bom']=[(r.parent,r.version,r.effective_from,r.effective_to,r.status) for r in revisions]
    if not orders or not revisions: raise ValueError('MISSING_DB_ORDERS_OR_BOM')
    return orders,items,revisions,versions

def run_integrated(conn,as_of='2026-11-20',run_id=None):
    from psycopg.types.json import Jsonb
    date.fromisoformat(as_of)
    if conn.info.transaction_status.name != 'IDLE':
        raise RuntimeError('SNAPSHOT_REQUIRES_IDLE_CONNECTION')
    run_id=run_id or 'M2-' + uuid.uuid4().hex[:20]
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cur.execute("SET LOCAL lock_timeout = '5s'")
            for table in SOURCE_TABLES_V2:
                cur.execute(f'LOCK TABLE {table} IN SHARE MODE')
        orders,items,revisions,versions=read_integrated_sources(conn,as_of)
        input_hash=canonical_hash({'as_of':as_of,'orders':[vars(o) for o in orders],
                                   'items':{k:vars(v) for k,v in sorted(items.items())},
                                   'revisions':[vars(r) for r in revisions], 'versions':versions})
        result=run_acceptance(orders,items,revisions,as_of)
        result['simulation']=True
        result['storage']='postgresql'
        result['source_snapshot_hash']=input_hash
        # Keep the source identity in the immutable persisted result, not only in source_versions.
        provenance=versions['receipt_provenance']
        for row in result['pegging']['order_allocations']:
            if row['supply_kind']=='RECEIPT':
                if row['supply_id'] not in provenance: raise ValueError('MISSING_RECEIPT_PROVENANCE')
                row['source_ref']=provenance[row['supply_id']]
        for row in result['pegging']['supply_ledger']:
            if row['kind']=='RECEIPT':
                if row['source_id'] not in provenance: raise ValueError('MISSING_RECEIPT_PROVENANCE')
                row['source_ref']=provenance[row['source_id']]
        result_hash=canonical_hash(result)
        order_hash=canonical_hash(sorted(o.order_id for o in orders))
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO platform.requirement_runs
                 (run_id,order_set_hash,input_hash,rule_version,status)
                 VALUES(%s,%s,%s,'M2-INTEGRATED-V1','COMPLETED')''',
                 (run_id,order_hash,input_hash))
            cur.execute('''INSERT INTO platform.integrated_mrp_payloads
                 (run_id,snapshot_as_of,engine,source_versions,result_json,result_hash)
                 VALUES(%s,%s,%s,%s,%s,%s)''',
                 (run_id,as_of,'effective_bom_supply_allocation_v1',Jsonb(versions),Jsonb(result),result_hash))
            persist_pegging_rows(cur,run_id,result)
    return {'run_id':run_id,'input_hash':input_hash,'result_hash':result_hash,
            'storage':'postgresql','snapshot_as_of':as_of,
            'orders':len(orders),'mrp_lines':len(result['mrp_lines'])}

def read_integrated_run(conn,run_id):
    with conn.cursor() as cur:
        cur.execute('''SELECT r.input_hash,r.status,p.snapshot_as_of,p.source_versions,p.result_json,p.result_hash
            FROM platform.requirement_runs r JOIN platform.integrated_mrp_payloads p USING(run_id)
            WHERE run_id=%s''',(run_id,))
        row=cur.fetchone()
    if row is None: raise KeyError(run_id)
    payload=row[4]
    if canonical_hash(payload)!=row[5]:
        raise ValueError('PERSISTED_RESULT_HASH_MISMATCH')
    return {'run_id':run_id,'input_hash':row[0],'status':row[1],
            'snapshot_as_of':row[2].isoformat(),'source_versions':row[3],
            'result_hash':row[5],'result':payload,'storage':'postgresql'}

def seed_effective_bom(conn):
    """Idempotent bootstrap from legacy BOM lines, only if effective BOM is empty.
    This is a demo migration; never overwrite curated effective BOM revisions.
    """
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM mock_erp.effective_bom_headers')
            if cur.fetchone()[0]: return 0
            cur.execute('''SELECT DISTINCT parent_id FROM mock_erp.bom_items ORDER BY parent_id''')
            parents=[r[0] for r in cur.fetchall()]
            for parent in parents:
                cur.execute('''INSERT INTO mock_erp.effective_bom_headers
                    (parent_id,version,status,valid_from) VALUES(%s,'V1','RELEASED','2026-01-01')''',(parent,))
                cur.execute('''SELECT component_id,qty_per FROM mock_erp.bom_items
                    WHERE parent_id=%s ORDER BY line_id''',(parent,))
                for n,(child,qty) in enumerate(cur.fetchall(),1):
                    cur.execute('''INSERT INTO mock_erp.effective_bom_components
                        (parent_id,version,line_no,component_id,qty_per) VALUES(%s,'V1',%s,%s,%s)''',
                        (parent,n,child,qty))
    return len(parents)


def persist_pegging_rows(cur,run_id,result):
    """Insert normalized, run-scoped genealogy rows in the same transaction.

    Never use a derived receipt sequence as an external business identifier.
    This helper intentionally fails closed if provenance is incomplete.
    """
    from psycopg.types.json import Jsonb
    report=result['pegging']
    for row in report['supply_ledger']:
        ref=row.get('source_ref')
        if row['kind']=='RECEIPT' and not ref: raise ValueError('MISSING_RECEIPT_PROVENANCE')
        cur.execute("""INSERT INTO platform.mrp_supply_sources
            (run_id,supply_id,material_id,supply_kind,source_system,source_document_id,source_line_id,
             capacity_qty,allocated_qty,remaining_qty)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run_id,row['source_id'],row['material'],row['kind'],
             ref['source_system'] if ref else 'PLANNER',
             ref['source_document_id'] if ref else row['source_id'],
             ref['source_line_id'] if ref else row['source_id'],
             row['capacity'],row['allocated'],row['remaining']))
    for row in report['order_allocations']:
        cur.execute("""INSERT INTO platform.mrp_demand_allocations
            (run_id,demand_id,supply_id,material_id,root_order_id,need_date,allocated_qty,
             parent_plan_id,bom_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run_id,row['demand_id'],row['supply_id'],row['material'],row['order_id'],
             row['need_date'],row['allocated_qty'],row['parent_plan'],row['bom_version']))
    for row in report['plan_child_edges']:
        cur.execute("""INSERT INTO platform.mrp_plan_child_edges
            (run_id,parent_plan_id,child_demand_id,parent_material,child_material,
             bom_version,child_need_date,child_gross_qty)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run_id,row['parent_plan_id'],row['child_demand_id'],row['parent_material'],
             row['child_material'],row['parent_bom_version'],row['child_need_date'],row['child_gross']))
