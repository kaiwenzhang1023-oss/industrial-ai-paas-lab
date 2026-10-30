"""PostgreSQL repository. Requires DATABASE_URL and initialized schema.
Writes one MRP run, daily lines and pegs atomically; reads persisted source
records back into the pure planning engine. No silent JSON fallback.
"""
import hashlib, json, os, uuid
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from pathlib import Path
from app.domain.timephased import Item, Order
from app.domain.pegging import allocate

def connect(dsn=None):
    import psycopg
    url=dsn or os.environ.get('DATABASE_URL')
    if not url: raise RuntimeError('DATABASE_URL required for PostgreSQL repository')
    return psycopg.connect(url)

def seed(conn, path):
    """Upsert deterministic source data; no destructive TRUNCATE."""
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    with conn.transaction():
        with conn.cursor() as cur:
            for code,item in sorted(data['items'].items()):
                cur.execute('''INSERT INTO mock_erp.materials(material_id,make_buy,lead_days,safety_stock,moq,lot_multiple)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(material_id) DO UPDATE SET
                make_buy=EXCLUDED.make_buy,lead_days=EXCLUDED.lead_days,safety_stock=EXCLUDED.safety_stock,
                moq=EXCLUDED.moq,lot_multiple=EXCLUDED.lot_multiple''',
                (code,item['kind'],item.get('lead_days',0),item.get('safety','0'),item.get('moq','0'),item.get('lot','1')))
                cur.execute('''INSERT INTO mock_wms.inventory_balances(material_id,warehouse_id,lot_id,on_hand,reserved,blocked,snapshot_at)
                VALUES(%s,'WH-A','',%s,%s,%s,%s) ON CONFLICT(material_id,warehouse_id,lot_id)
                DO UPDATE SET on_hand=EXCLUDED.on_hand,reserved=EXCLUDED.reserved,blocked=EXCLUDED.blocked,
                snapshot_at=EXCLUDED.snapshot_at,version=mock_wms.inventory_balances.version + CASE WHEN (mock_wms.inventory_balances.on_hand,mock_wms.inventory_balances.reserved,mock_wms.inventory_balances.blocked,mock_wms.inventory_balances.snapshot_at) IS DISTINCT FROM (EXCLUDED.on_hand,EXCLUDED.reserved,EXCLUDED.blocked,EXCLUDED.snapshot_at) THEN 1 ELSE 0 END''',
                (code,item.get('on_hand','0'),item.get('reserved','0'),item.get('blocked','0'),data['as_of']+'T00:00:00+00:00'))
                for idx,(d,q) in enumerate(item.get('receipts',[])):
                    sid=f'SEED-{code}-{idx}'
                    cur.execute('''INSERT INTO mock_erp.supply_orders(supply_id,material_id,open_qty,arrival_date,status)
                    VALUES(%s,%s,%s,%s,'CONFIRMED') ON CONFLICT(supply_id) DO UPDATE SET
                    material_id=EXCLUDED.material_id,open_qty=EXCLUDED.open_qty,arrival_date=EXCLUDED.arrival_date,status=EXCLUDED.status''',(sid,code,q,d))
            for order in data['orders']:
                cur.execute('''INSERT INTO mock_erp.sales_orders(order_id,product_id,quantity,due_date,priority,status)
                VALUES(%s,%s,%s,%s,%s,'CONFIRMED') ON CONFLICT(order_id) DO UPDATE SET
                product_id=EXCLUDED.product_id,quantity=EXCLUDED.quantity,due_date=EXCLUDED.due_date,
                priority=EXCLUDED.priority,status='CONFIRMED',version=mock_erp.sales_orders.version + CASE WHEN (mock_erp.sales_orders.product_id,mock_erp.sales_orders.quantity,mock_erp.sales_orders.due_date,mock_erp.sales_orders.priority,mock_erp.sales_orders.status) IS DISTINCT FROM (EXCLUDED.product_id,EXCLUDED.quantity,EXCLUDED.due_date,EXCLUDED.priority,'CONFIRMED') THEN 1 ELSE 0 END''',
                (order['order_id'],order['product'],order['qty'],order['due'],order.get('priority',0)))
            cur.execute('''INSERT INTO mock_erp.bom_versions(bom_id,version,status,effective_from)
            VALUES('EM-100','V1','RELEASED','2026-01-01') ON CONFLICT DO NOTHING''')
            for idx,(parent,child,per) in enumerate(data['bom'],1):
                cur.execute('''INSERT INTO mock_erp.bom_items(bom_id,version,line_id,parent_id,component_id,qty_per)
                VALUES('EM-100','V1',%s,%s,%s,%s) ON CONFLICT(bom_id,version,line_id)
                DO UPDATE SET parent_id=EXCLUDED.parent_id,component_id=EXCLUDED.component_id,qty_per=EXCLUDED.qty_per''',(idx,parent,child,per))
    return len(data['orders']),len(data['items'])

def load_snapshot(conn,as_of='2026-10-29'):
    """Read only confirmed orders, released BOM, usable stock, confirmed supply."""
    with conn.cursor() as cur:
        cur.execute("SELECT order_id,product_id,quantity,due_date,priority FROM mock_erp.sales_orders WHERE status='CONFIRMED' ORDER BY due_date,priority DESC,order_id")
        orders=[Order(r[0],r[1],r[2],r[3].isoformat(),r[4]) for r in cur.fetchall()]
        cur.execute('''SELECT m.material_id,m.make_buy,m.lead_days,m.safety_stock,m.moq,m.lot_multiple,
        COALESCE(sum(i.on_hand),0),COALESCE(sum(i.reserved),0),COALESCE(sum(i.blocked),0)
        FROM mock_erp.materials m LEFT JOIN mock_wms.inventory_balances i ON i.material_id=m.material_id
        GROUP BY m.material_id,m.make_buy,m.lead_days,m.safety_stock,m.moq,m.lot_multiple''')
        itemrows=cur.fetchall()
        cur.execute("SELECT material_id,arrival_date,open_qty FROM mock_erp.supply_orders WHERE status='CONFIRMED' AND open_qty>0 AND arrival_date >= %s ORDER BY arrival_date,supply_id",(as_of,))
        receipts={}
        for code,d,q in cur.fetchall(): receipts.setdefault(code,[]).append((d.isoformat(),q))
        items={r[0]:Item(code=r[0],kind=r[1],lead_days=r[2],safety=r[3],moq=r[4],lot=r[5],on_hand=r[6],reserved=r[7],blocked=r[8],receipts=tuple(receipts.get(r[0],[]))) for r in itemrows}
        cur.execute("SELECT parent_id,component_id,qty_per FROM mock_erp.bom_items b JOIN mock_erp.bom_versions v USING(bom_id,version) WHERE v.status='RELEASED' AND v.effective_from<=%s AND (v.effective_to IS NULL OR v.effective_to >=%s) ORDER BY b.line_id",(as_of,as_of))
        bom=cur.fetchall()
    return orders,items,bom

# All source tables must be locked before the first snapshot read. SHARE locks
# conflict with concurrent INSERT/UPDATE/DELETE (ROW EXCLUSIVE), ensuring that
# the fingerprint and persisted plan refer to the same committed source state.
# This deliberately trades write throughput for a provable V0.1 consistency gate.
SOURCE_TABLES = (
    "mock_erp.sales_orders", "mock_erp.materials", "mock_erp.bom_versions",
    "mock_erp.bom_items", "mock_erp.supply_orders", "mock_wms.inventory_balances",
)

@dataclass(frozen=True)
class SnapshotEnvelope:
    as_of: str
    input_hash: str
    order_set_hash: str
    versions: dict


def _snapshot_hash(as_of, orders, items, bom):
    payload = {'as_of': as_of, 'orders': [vars(o) for o in orders],
               'items': {k: vars(v) for k, v in sorted(items.items())},
               'bom': bom}
    encoded = json.dumps(payload, sort_keys=True, default=str,
                         separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _read_versions(conn):
    # Source revisions are diagnostic only: the locking transaction is the
    # actual fence. Include row identities and versions to detect changed sets.
    with conn.cursor() as cur:
        cur.execute('SELECT order_id,version FROM mock_erp.sales_orders ORDER BY order_id')
        orders = [[str(a), int(b)] for a,b in cur.fetchall()]
        cur.execute('SELECT material_id,warehouse_id,lot_id,version FROM mock_wms.inventory_balances ORDER BY material_id,warehouse_id,lot_id')
        inventory = [[str(a),str(b),str(c),int(d)] for a,b,c,d in cur.fetchall()]
    return {'orders': orders, 'inventory': inventory}


def calculate_and_save(conn, as_of='2026-10-29', run_id=None):
    # Requires a fresh connection / no existing transaction. psycopg transaction
    # context commits the plan and releases source locks atomically.
    if conn.info.transaction_status.name != 'IDLE':
        raise RuntimeError('SNAPSHOT_REQUIRES_IDLE_CONNECTION')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cur.execute("SET LOCAL lock_timeout = '5s'")
            for table in SOURCE_TABLES:
                cur.execute(f'LOCK TABLE {table} IN SHARE MODE')
        orders, items, bom = load_snapshot(conn, as_of)
        versions = _read_versions(conn)
        input_hash = _snapshot_hash(as_of, orders, items, bom)
        order_hash = hashlib.sha256('|'.join(sorted(o.order_id for o in orders)).encode()).hexdigest()
        lines, pegs = allocate(orders, items, bom, as_of)
        run_id = run_id or 'MRP-' + uuid.uuid4().hex[:16]
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO platform.requirement_runs
                (run_id,order_set_hash,input_hash,rule_version,status)
                VALUES(%s,%s,%s,'MRP-V0.3','COMPLETED')''',
                (run_id,order_hash,input_hash))
            for l in lines:
                cur.execute('''INSERT INTO platform.material_requirements
                    (run_id,material_id,need_date,gross,net,planned,projected_balance)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                    (run_id,l.material,l.date,l.gross,l.net,l.planned,l.closing))
            for p in pegs:
                cur.execute('''INSERT INTO platform.requirement_pegs
                    (run_id,material_id,need_date,order_id,gross,from_stock,from_receipts,from_planned)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (run_id,p.material,p.need_date,p.order_id,p.gross,
                     p.from_stock,p.from_receipts,p.from_planned))
            cur.execute('''INSERT INTO platform.run_snapshot_fences
                (run_id,as_of,source_versions) VALUES(%s,%s,%s::jsonb)''',
                (run_id,as_of,json.dumps(versions,sort_keys=True)))
    return {'run_id':run_id,'input_hash':input_hash,
            'lines':len(lines),'pegs':len(pegs),'snapshot_versions':versions,
            'isolation':'REPEATABLE READ','source_fence':'SHARE TABLE LOCK'}

def read_run(conn,run_id):
    with conn.cursor() as cur:
        cur.execute('SELECT input_hash,rule_version,status FROM platform.requirement_runs WHERE run_id=%s',(run_id,))
        header=cur.fetchone()
        if header is None: raise KeyError(run_id)
        cur.execute('SELECT material_id,need_date,gross,net,planned,projected_balance FROM platform.material_requirements WHERE run_id=%s ORDER BY need_date,material_id',(run_id,))
        lines=[{'material':r[0],'date':r[1].isoformat(),'gross':str(r[2]),'net':str(r[3]),'planned':str(r[4]),'closing':str(r[5])} for r in cur.fetchall()]
        cur.execute('SELECT material_id,need_date,order_id,gross,from_stock,from_receipts,from_planned FROM platform.requirement_pegs WHERE run_id=%s ORDER BY need_date,material_id,order_id',(run_id,))
        pegs=[{'material':r[0],'date':r[1].isoformat(),'order_id':r[2],'gross':str(r[3]),'from_stock':str(r[4]),'from_receipts':str(r[5]),'from_planned':str(r[6])} for r in cur.fetchall()]
        cur.execute('SELECT as_of,source_versions FROM platform.run_snapshot_fences WHERE run_id=%s',(run_id,))
        fence=cur.fetchone()
    return {'run_id':run_id,'input_hash':header[0],'rule_version':header[1],
            'status':header[2],'lines':lines,'pegs':pegs,
            'snapshot': {'as_of':fence[0].isoformat(),'source_versions':fence[1]} if fence else None}
