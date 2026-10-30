from fastapi import FastAPI, HTTPException
from app.domain.mrp import calculate, procurement_total
app=FastAPI(title='Industrial AI PaaS Lab - M2-01 mock baseline',version='0.1.0')
@app.get('/health')
def health(): return {'status':'ok','phase':'M2-01'}
@app.get('/api/v1/orders')
def orders(): return [{'order_id':'SO-2026-001','product_id':'EM-100','quantity':100,'due_date':'2026-11-30','status':'CONFIRMED','version':1}]
@app.get('/api/v1/golden/evaluation')
def golden():
    result=calculate()
    return {'order_id':'SO-2026-001','rule_version':'GOLDEN-V1','materials':result,'procurement_amount_cny':str(procurement_total(result)),'simulation':True}
@app.get('/mock/erp/v1/orders/SO-2026-001')
def mock_erp_order(): return orders()[0]
@app.get('/mock/wms/v1/inventory')
def mock_wms_inventory():
    from app.domain.mrp import MATERIALS
    return [{'item_code':m.code,'qty_onhand':m.on_hand,'qty_allocated':m.reserved,'qty_frozen':m.blocked} for m in MATERIALS.values()]
@app.get('/mock/mes/v1/production-orders')
def mock_mes_orders(): return [{'production_order_id':'MO-DEMO-001','product_id':'EM-100','status':'PLANNED','simulation':True}]

from app.domain.seed_loader import load
from app.domain.timephased import plan, as_json
@app.get('/api/v1/mrp/multi-order')
def multi_order_mrp():
    data,orders,items=load()
    return {'as_of':data['as_of'],'orders':[o.order_id for o in orders],'lines':as_json(plan(orders,items,data['bom'],data['as_of'])),'simulation':True,'engine':'daily-shared-inventory-v1'}
@app.get('/mock/erp/v1/orders')
def erp_orders():
    data,_,_=load()
    return [{'so_no':x['order_id'],'sku':x['product'],'order_qty':x['qty'],'delivery_date':x['due'],'priority':x['priority']} for x in data['orders']]
@app.get('/mock/erp/v1/bom')
def erp_bom():
    data,_,_=load()
    return [{'parent_sku':p,'component_sku':c,'usage':q} for p,c,q in data['bom']]
@app.get('/mock/erp/v1/supplies')
def erp_supplies():
    data,_,_=load()
    return [{'item_code':k,'arrival_date':d,'open_qty':q} for k,x in data['items'].items() for d,q in x.get('receipts',[])]
@app.get('/mock/wms/v1/inventory-v2')
def wms_inventory_v2():
    data,_,_=load()
    return [{'item_code':k,'qty_onhand':x.get('on_hand','0'),'qty_allocated':x.get('reserved','0'),'qty_frozen':x.get('blocked','0'),'warehouse':'WH-A'} for k,x in data['items'].items()]
@app.get('/mock/mes/v1/production-orders-v2')
def mes_orders_v2():
    return [{'mo_no':'MO-DEMO-001','sku':'EM-100','state':'PLANNED','simulation':True}]


# V0.4 database-first endpoints. No fallback to JSON on database errors.
from fastapi import Query
from fastapi.responses import JSONResponse
from app.db.repository import connect as db_connect, load_snapshot as db_load_snapshot, calculate_and_save as db_calculate_and_save, read_run as db_read_run
from app.domain.pegging import allocate as db_allocate, pegs_json
from app.domain.timephased import as_json as mrp_as_json
from datetime import date as Date

@app.get('/api/v1/db/health')
def database_health():
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                cur.fetchone()
        return {'status':'ok','storage':'postgresql'}
    except Exception:
        raise HTTPException(status_code=503, detail={'code':'DATABASE_UNAVAILABLE','message':'PostgreSQL is unavailable'})

@app.get('/api/v1/db/orders')
def database_orders():
    try:
        with db_connect() as conn:
            orders, _, _ = db_load_snapshot(conn)
        return {'source':'postgresql','orders':[{'order_id':o.order_id,'product_id':o.product,'quantity':str(o.qty),'due_date':o.due,'priority':o.priority} for o in orders]}
    except Exception:
        raise HTTPException(status_code=503,detail={'code':'DATABASE_UNAVAILABLE'})

@app.post('/api/v1/db/mrp/runs',status_code=201)
def create_database_mrp_run(as_of:Date=Query(default=Date(2026,10,29))):
    try:
        with db_connect() as conn:
            result=db_calculate_and_save(conn,as_of.isoformat())
        return {'source':'postgresql',**result}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail={'code':'MRP_VALIDATION_ERROR','message':str(exc)})
    except Exception:
        raise HTTPException(status_code=503,detail={'code':'DATABASE_OR_PERSISTENCE_ERROR'})

@app.get('/api/v1/db/mrp/runs/{run_id}')
def get_database_mrp_run(run_id:str):
    try:
        with db_connect() as conn:
            return {'source':'postgresql',**db_read_run(conn,run_id)}
    except KeyError:
        raise HTTPException(status_code=404,detail={'code':'RUN_NOT_FOUND'})
    except Exception:
        raise HTTPException(status_code=503,detail={'code':'DATABASE_UNAVAILABLE'})

# M2-02-05: unified, explicitly in-memory business acceptance endpoint.
# This endpoint is not evidence of PostgreSQL persistence.
@app.get('/api/v1/acceptance/m2-02-05/demo')
def acceptance_demo():
    from decimal import Decimal
    from app.domain.timephased import Item, Order
    from app.domain.versioned_bom import BOMRevision
    from app.domain.acceptance import run_acceptance
    D = Decimal
    items = {'FG':Item('FG','MAKE',lead_days=3),
             'ST':Item('ST','MAKE',lead_days=2,on_hand=D(60),receipts=(('2026-11-29',D(10)),)),
             'A':Item('A','BUY',on_hand=D(10)), 'B':Item('B','BUY')}
    revisions = [BOMRevision('FG','v1','2026-01-01','2026-11-29','RELEASED',(('ST',1),)),
                 BOMRevision('FG','v2','2026-11-29',None,'RELEASED',(('ST',2),)),
                 BOMRevision('ST','old','2026-01-01','2026-11-26','RELEASED',(('A',1),)),
                 BOMRevision('ST','new','2026-11-26',None,'RELEASED',(('B',1),))]
    orders = [Order('SO1','FG',D(100),'2026-11-30',1),
              Order('SO2','FG',D(20),'2026-12-03',5)]
    return run_acceptance(orders,items,revisions)

# M2 integration: explicitly database-backed versioned BOM + Pegging.
from app.db.integrated import run_integrated, read_integrated_run
@app.post('/api/v1/db/integrated-mrp/runs',status_code=201)
def create_integrated_mrp_run(as_of:Date=Query(default=Date(2026,11,20))):
    try:
        with db_connect() as conn:
            return run_integrated(conn,as_of.isoformat())
    except ValueError as exc:
        raise HTTPException(status_code=422,detail={'code':'MRP_VALIDATION_ERROR','message':str(exc)})
    except Exception:
        raise HTTPException(status_code=503,detail={'code':'DATABASE_OR_PERSISTENCE_ERROR'})

@app.get('/api/v1/db/integrated-mrp/runs/{run_id}')
def get_integrated_mrp_run(run_id:str):
    try:
        with db_connect() as conn:
            return read_integrated_run(conn,run_id)
    except KeyError:
        raise HTTPException(status_code=404,detail={'code':'RUN_NOT_FOUND'})
    except ValueError as exc:
        raise HTTPException(status_code=409,detail={'code':str(exc)})
    except Exception:
        raise HTTPException(status_code=503,detail={'code':'DATABASE_UNAVAILABLE'})

# M3-01: PostgreSQL-only workflow endpoints (no implicit MRP execution).
from pydantic import BaseModel, Field
from app.workflow.runtime import create as wf_create,read as wf_read,dispatch as wf_dispatch,WorkflowConflict,WorkflowNotFound
class WorkflowCreateRequest(BaseModel):
    order_id: str = Field(min_length=1)
class WorkflowEventRequest(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    expected_version: int | None = Field(default=None,ge=0)
@app.post('/api/v1/workflows',status_code=201)
def workflow_create(body:WorkflowCreateRequest):
    try:
        with db_connect() as conn:
            conn.autocommit=True
            return wf_create(conn,body.order_id)
    except Exception: raise HTTPException(503,detail={'code':'WORKFLOW_STORAGE_ERROR'})
@app.get('/api/v1/workflows/{workflow_id}')
def workflow_read(workflow_id:str):
    try:
        with db_connect() as conn:
            conn.autocommit=True
            return wf_read(conn,workflow_id)
    except WorkflowNotFound: raise HTTPException(404,detail={'code':'WORKFLOW_NOT_FOUND'})
    except Exception: raise HTTPException(503,detail={'code':'WORKFLOW_STORAGE_ERROR'})
@app.post('/api/v1/workflows/{workflow_id}/events')
def workflow_event(workflow_id:str,body:WorkflowEventRequest):
    try:
        with db_connect() as conn:
            conn.autocommit=True
            return wf_dispatch(conn,workflow_id,body.event_id,body.event_type,body.payload,body.expected_version)
    except WorkflowNotFound: raise HTTPException(404,detail={'code':'WORKFLOW_NOT_FOUND'})
    except WorkflowConflict as exc: raise HTTPException(409,detail={'code':str(exc)})
    except ValueError as exc: raise HTTPException(422,detail={'code':str(exc)})
    except Exception: raise HTTPException(503,detail={'code':'WORKFLOW_STORAGE_ERROR'})

# M4 V0.1: database-backed web workbench, without changing legacy API contracts.
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles
from fastapi.responses import RedirectResponse as _RedirectResponse
from app.workbench import router as _workbench_router
app.include_router(_workbench_router)
_workbench_dir = _Path(__file__).resolve().parent / 'web'
app.mount('/workbench', _StaticFiles(directory=str(_workbench_dir), html=True), name='workbench')
@app.get('/app',include_in_schema=False)
def workbench_redirect():
    return _RedirectResponse('/workbench/')

# V1.0 public-cloud perimeter: legacy M2/M3 POST endpoints must not bypass
# the workbench operator guard. Public deployments are strictly read-only.
import os as _v1_os
from fastapi.responses import JSONResponse as _V1JSONResponse
@app.middleware('http')
async def v1_public_readonly(request, call_next):
    if _v1_os.getenv('PUBLIC_READ_ONLY') == '1' and request.method.upper() not in ('GET','HEAD','OPTIONS'):
        return _V1JSONResponse(status_code=403,content={'detail':{'code':'PUBLIC_DEMO_READ_ONLY'}})
    return await call_next(request)
