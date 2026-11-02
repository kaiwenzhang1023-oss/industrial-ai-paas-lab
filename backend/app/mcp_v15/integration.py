"""V1.5 read-only business adapters. Uses actual V1.4 persistence, no canned results."""
from app.db.integrated import read_integrated_run
from app.mes.integration import read_orders
from app.srm.service import list_requisitions
from app.mapping.engine import preview_b01
from app.mapping.contracts import B01_MAPPING_ID, B01_VERSION

class ResourceMissing(LookupError): pass

def execute(conn, name, args):
    if name == 'mrp.get_run':
        return read_integrated_run(conn,args['run_id'])
    if name == 'wms.get_inventory':
        # Query the persisted WMS source directly. This read-only MCP boundary
        # must not import the optional Pydantic-based WMS HTTP DTO layer.
        with conn.cursor() as cur:
            cur.execute("""SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0),
                COALESCE(SUM(blocked),0),COUNT(*),MAX(snapshot_at)
                FROM mock_wms.inventory_balances
                WHERE material_id=%s AND (%s::text IS NULL OR warehouse_id=%s)""",
                (args['material_id'],args.get('warehouse_id'),args.get('warehouse_id')))
            on_hand,reserved,blocked,count,snapshot=cur.fetchone()
        return {'material_id':args['material_id'],
                'warehouse_id':args.get('warehouse_id'),
                'on_hand':str(on_hand),'reserved':str(reserved),
                'blocked':str(blocked),'available':str(on_hand-reserved-blocked),
                'balance_rows':count,
                'latest_snapshot_at':snapshot.isoformat() if snapshot else None,
                'source':'postgresql'}
    if name == 'mes.get_work_order':
        # Read persisted work-order row, avoiding mutations and routing side effects.
        with conn.cursor() as cur:
            cur.execute("""SELECT work_order_id,source_run_id,source_plan_id,product_id,quantity,
                due_date,status,revision FROM mes_v13.work_orders WHERE work_order_id=%s""",(args['work_order_id'],))
            r=cur.fetchone()
        if r is None: raise ResourceMissing('MES_WORK_ORDER_NOT_FOUND')
        return dict(zip(('work_order_id','source_run_id','source_plan_id','product_id','quantity','due_date','status','revision'),
                        (x.isoformat() if hasattr(x,'isoformat') else str(x) if x.__class__.__name__=='Decimal' else x for x in r)))
    if name == 'srm.list_requisitions':
        # Source service is unfiltered; apply resource filter in SQL to prevent cross-resource disclosure.
        with conn.cursor() as cur:
            cur.execute("""SELECT pr_id,source_run_id,source_plan_id,material_id,quantity,uom,need_date,status
              FROM srm_v14.purchase_requisitions WHERE source_run_id=%s ORDER BY created_at DESC,pr_id LIMIT %s""",
              (args['run_id'],args.get('limit',50)))
            rows=cur.fetchall()
        return [dict(zip(('pr_id','source_run_id','source_plan_id','material_id','quantity','uom','need_date','status'),
                         (x.isoformat() if hasattr(x,'isoformat') else str(x) if x.__class__.__name__=='Decimal' else x for x in row))) for row in rows]
    if name == 'mapping.preview_b01':
        mrp=read_integrated_run(conn,args['run_id'])
        with conn.cursor() as cur:
            cur.execute('SELECT material_id,make_buy,uom FROM mock_erp.materials ORDER BY material_id')
            materials={r[0]:{'make_buy':r[1],'uom':r[2]} for r in cur.fetchall()}
        return preview_b01({'mapping_id':B01_MAPPING_ID,'mapping_version':B01_VERSION,
            'source_system':'MRP','source_object':'BUY_PLAN','target_system':'SRM',
            'target_object':'PR_CANDIDATE','source_result_hash':mrp['result_hash'],
            'mrp':mrp,'material_snapshot':materials})
    raise ValueError('UNKNOWN_TOOL')
