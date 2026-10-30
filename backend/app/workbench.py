"""M4 V0.1 workbench read models and explicit, controlled demo actions.

No mock success fallback: these endpoints always read/write PostgreSQL.
"""
from datetime import date
import os
import secrets
from fastapi import Header
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.db.repository import connect
from app.workflow.runtime import create, read, dispatch, WorkflowConflict, WorkflowNotFound
from app.workflow.scheduler import durable_mrp_runner
from app.agent import generate_and_persist, AgentPolicyError, AgentOutputError

router = APIRouter(prefix='/api/v1/workbench', tags=['M4 Workbench'])

def records(cur):
    columns=[d.name for d in cur.description]
    return [{k:(str(v) if isinstance(v,(Decimal,date)) else v) for k,v in zip(columns,row)} for row in cur.fetchall()]

def require_operator(x_operator_key: str | None = Header(default=None)):
    """Public cloud is read-only unless an operator key is configured.

    Local demo remains writable only with DEMO_WRITE_ENABLED=1.
    """
    if os.getenv('DEMO_WRITE_ENABLED') != '1':
        raise HTTPException(403, detail={'code':'DEMO_WRITE_DISABLED'})
    expected = os.getenv('DEMO_OPERATOR_KEY')
    if expected and not secrets.compare_digest(x_operator_key or '', expected):
        raise HTTPException(403, detail={'code':'OPERATOR_KEY_REQUIRED'})


def db_error(exc):
    if isinstance(exc,WorkflowNotFound): raise HTTPException(404,detail={'code':'WORKFLOW_NOT_FOUND'}) from exc
    if isinstance(exc,(WorkflowConflict,AgentPolicyError,AgentOutputError)): raise HTTPException(409,detail={'code':str(exc)}) from exc
    if isinstance(exc,ValueError): raise HTTPException(422,detail={'code':str(exc)}) from exc
    raise HTTPException(503,detail={'code':'WORKBENCH_DATABASE_UNAVAILABLE'}) from exc

@router.get('/snapshot')
def snapshot():
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT order_id,product_id,quantity,due_date,priority,status FROM mock_erp.sales_orders ORDER BY order_id LIMIT 100')
                orders=records(cur)
                cur.execute('SELECT material_id,make_buy,lead_days,uom FROM mock_erp.materials ORDER BY material_id LIMIT 200')
                materials=records(cur)
                cur.execute('''SELECT c.parent_id,c.version,c.line_no,c.component_id,c.qty_per,h.status,h.valid_from,h.valid_to_exclusive FROM mock_erp.effective_bom_components c JOIN mock_erp.effective_bom_headers h ON c.parent_id=h.parent_id AND c.version=h.version ORDER BY c.parent_id,c.version,c.line_no LIMIT 300''')
                bom=records(cur)
                cur.execute('SELECT material_id,warehouse_id,on_hand,reserved,blocked,snapshot_at FROM mock_wms.inventory_balances ORDER BY material_id LIMIT 200')
                inventory=records(cur)
                cur.execute('SELECT instance_id AS workflow_id,order_id,state,version,mrp_run_id,updated_at FROM platform.workflow_instances ORDER BY updated_at DESC LIMIT 60')
                workflows=records(cur)
                cur.execute('''SELECT r.run_id,r.status,p.snapshot_as_of FROM platform.requirement_runs r LEFT JOIN platform.integrated_mrp_payloads p ON p.run_id=r.run_id ORDER BY r.created_at DESC,r.run_id DESC LIMIT 30''')
                runs=records(cur)
                cur.execute('SELECT draft_id,workflow_id,mrp_run_id,status,model_id,draft,created_at FROM platform.agent_drafts ORDER BY draft_id DESC LIMIT 60')
                drafts=records(cur)
                cur.execute('SELECT audit_id,workflow_id,tool_name,outcome,reason_code,policy_version,created_at FROM platform.agent_tool_audit ORDER BY audit_id DESC LIMIT 100')
                tool_audit=records(cur)
        return {'source':'postgresql','simulation':True,'write_enabled':os.getenv('DEMO_WRITE_ENABLED')=='1' and not bool(os.getenv('DEMO_OPERATOR_KEY')),'orders':orders,'materials':materials,'bom':bom,'inventory':inventory,'workflows':workflows,'runs':runs,'drafts':drafts,'tool_audit':tool_audit}
    except Exception as exc: db_error(exc)

@router.get('/workflows/{workflow_id}/history')
def workflow_history(workflow_id:str):
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT audit_id,event_id,from_state,to_state,version,recorded_at FROM platform.workflow_audit WHERE instance_id=%s ORDER BY audit_id',(workflow_id,))
                transitions=records(cur)
                cur.execute('SELECT message_id,event_id,topic,status,attempts,created_at,delivered_at,last_error,next_attempt_at FROM platform.workflow_outbox WHERE instance_id=%s ORDER BY message_id',(workflow_id,))
                outbox=records(cur)
        return {'workflow_id':workflow_id,'transitions':transitions,'outbox':outbox}
    except Exception as exc: db_error(exc)

class NewWorkflow(BaseModel):
    order_id: str = Field(min_length=1,max_length=80)

@router.post('/workflows',status_code=201)
def new_workflow(body:NewWorkflow, _:None=Depends(require_operator)):
    try:
        with connect() as conn:
            conn.autocommit=True
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM mock_erp.sales_orders WHERE order_id=%s AND status='CONFIRMED'",(body.order_id,))
                if cur.fetchone() is None: raise ValueError('ORDER_NOT_CONFIRMED')
            return create(conn,body.order_id)
    except Exception as exc: db_error(exc)

class Advance(BaseModel):
    expected_version: int = Field(ge=0)
    as_of: date = date(2026,11,20)

@router.post('/workflows/{workflow_id}/advance')
def advance(workflow_id:str,body:Advance, _:None=Depends(require_operator)):
    """Explicit demo step; never performs purchase approval or ERP write."""
    try:
        with connect() as conn:
            conn.autocommit=True
            current=read(conn,workflow_id)
            if current['version']!=body.expected_version: raise WorkflowConflict('STALE_WORKFLOW_VERSION')
            state=current['state']
            if state=='CREATED':
                return dispatch(conn,workflow_id,f'UI:{workflow_id}:START','START',{},expected_version=body.expected_version)
            if state=='VALIDATING':
                # This is an explicit operator demonstration action, not a real ERP validation service.
                return dispatch(conn,workflow_id,f'UI:{workflow_id}:VALIDATED','VALIDATION_PASSED',{},expected_version=body.expected_version)
            if state=='CALCULATING':
                run_id=durable_mrp_runner(conn,workflow_id,current['order_id'],body.as_of.isoformat())
                result=dispatch(conn,workflow_id,f'UI:{workflow_id}:MRP:{run_id}','MRP_COMPLETED',{'mrp_run_id':run_id},expected_version=body.expected_version)
                # Expose the persisted run identifier in the API response; dispatch's
                # generic transition envelope intentionally does not contain it.
                return {**result,'mrp_run_id':read(conn,workflow_id)['mrp_run_id']}
            if state=='GENERATING_ADVICE':
                return generate_and_persist(conn,workflow_id)
            raise WorkflowConflict('NO_DEMO_ADVANCE_FROM:'+state)
    except Exception as exc: db_error(exc)


@router.get('/mrp/{run_id}/details')
def mrp_details(run_id: str):
    # Read persisted M2 integrated MRP; never recompute.
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT r.run_id,r.status,r.rule_version,p.snapshot_as_of,p.result_hash,p.source_versions,p.result_json
                    FROM platform.requirement_runs r LEFT JOIN platform.integrated_mrp_payloads p ON p.run_id=r.run_id
                    WHERE r.run_id=%s''',(run_id,))
                runs=records(cur)
                if not runs: raise WorkflowNotFound('MRP_RUN_NOT_FOUND')
                persisted=runs[0].pop('result_json',None)
                cur.execute('SELECT material_id,make_buy FROM mock_erp.materials')
                kinds=dict(cur.fetchall())
                lines=[{'material_id':r.get('material'),'make_buy':kinds.get(r.get('material')),
                    'need_date':r.get('need_date'),'gross':r.get('gross'),'net':r.get('net'),
                    'planned':r.get('planned'),'projected_balance':r.get('closing_supply')}
                    for r in (persisted or {}).get('mrp_lines',[])]
                cur.execute('''SELECT material_id,need_date,order_id,gross,from_stock,from_receipts,from_planned
                    FROM platform.requirement_pegs WHERE run_id=%s ORDER BY need_date,material_id,order_id''',(run_id,))
                pegs=records(cur)
                cur.execute('''SELECT material_id,root_order_id,need_date,supply_id,allocated_qty,parent_plan_id,bom_version
                    FROM platform.mrp_demand_allocations WHERE run_id=%s ORDER BY allocation_id LIMIT 500''',(run_id,))
                allocations=records(cur)
                cur.execute("""SELECT a.material_id,a.root_order_id,a.need_date,s.supply_kind,
                    SUM(a.allocated_qty) AS allocated_qty
                    FROM platform.mrp_demand_allocations a
                    JOIN platform.mrp_supply_sources s ON s.run_id=a.run_id AND s.supply_id=a.supply_id
                    WHERE a.run_id=%s
                    GROUP BY a.material_id,a.root_order_id,a.need_date,s.supply_kind
                    ORDER BY a.need_date,a.material_id,a.root_order_id,s.supply_kind""",(run_id,))
                provenance=records(cur)
                cur.execute('''SELECT parent_material,child_material,bom_version,child_need_date,child_gross_qty,parent_plan_id
                    FROM platform.mrp_plan_child_edges WHERE run_id=%s ORDER BY parent_material,child_material LIMIT 500''',(run_id,))
                edges=records(cur)
                cur.execute('''SELECT supply_id,material_id,supply_kind,source_system,source_document_id,capacity_qty,allocated_qty,remaining_qty
                    FROM platform.mrp_supply_sources WHERE run_id=%s ORDER BY material_id,supply_id LIMIT 500''',(run_id,))
                supplies=records(cur)
        return {'run':runs[0],'lines':lines,'pegs':pegs,'allocations':allocations,'bom_edges':edges,'supplies':supplies, 'provenance':provenance, 'provenance_source':'platform.mrp_demand_allocations',
                'legacy_pegs_available':bool(pegs), 'scope':'ALL_CONFIRMED_ORDERS','read_only':True}
    except WorkflowNotFound: raise HTTPException(404,detail={'code':'MRP_RUN_NOT_FOUND'})
    except Exception as exc: db_error(exc)

@router.get('/outbox/summary')
def outbox_summary():
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT status,count(*) AS count FROM platform.workflow_outbox GROUP BY status ORDER BY status''')
                counts=records(cur)
                cur.execute('''SELECT message_id,instance_id AS workflow_id,event_id,status,attempts,delivered_at,last_error,next_attempt_at
                    FROM platform.workflow_outbox ORDER BY message_id DESC LIMIT 100''')
                messages=records(cur)
        return {'counts':counts,'messages':messages,'delivery_mode':'EXPLICIT_WORKER_ONLY',
                'note':'PENDING is persisted, not delivered; background worker is not started by web server'}
    except Exception as exc: db_error(exc)
