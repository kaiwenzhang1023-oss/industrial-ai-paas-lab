"""V1.3 MES API. Writes require existing operator-key policy; read endpoints remain read-only."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.db.repository import connect
from app.workbench import require_w3_operator
from app.mes import integration as svc
from app.mes.core import Feedback
router=APIRouter(prefix='/api/v1/mes',tags=['V1.3 MES simulation'])

class ImportRun(BaseModel):
    run_id:str=Field(min_length=1,max_length=100)
class ChangeStatus(BaseModel):
    status:str
    expected_revision:int=Field(ge=0)
class AddFeedback(BaseModel):
    event_id:str=Field(min_length=1,max_length=120)
    operation_id:str
    good_qty:Decimal=Field(ge=0)
    scrap_qty:Decimal=Field(ge=0)
    event_date:date
    expected_revision:int=Field(ge=0)
class CapacityRow(BaseModel):
    work_center:str
    day:date
    hours:Decimal=Field(ge=0)
class CapacityRequest(BaseModel):
    work_order_ids:list[str]
    start_date:date
    daily_capacity:list[CapacityRow]

def guarded(fn):
    try:
        with connect() as conn:
            return fn(conn)
    except ValueError as exc:
        code=str(exc)
        raise HTTPException(409 if 'CONFLICT' in code or 'STALE' in code else 422,detail={'code':code}) from exc
    except Exception as exc:
        raise HTTPException(503,detail={'code':'MES_STORAGE_UNAVAILABLE'}) from exc

@router.get('/work-orders')
def list_orders():return guarded(svc.read_orders)
@router.get('/work-orders/{work_id}')
def details(work_id:str):
    def read(conn):
        wo,revision=svc.reconstruct(conn,work_id)
        return {'progress':wo.progress(),'revision':revision,'routing':[vars(x) for x in wo.routing.operations],
                'events':[vars(x) for x in wo.feedback.values()],'simulation':True}
    return guarded(read)
@router.post('/import-mrp',status_code=201)
def import_mrp(body:ImportRun,_=Depends(require_w3_operator)):
    return guarded(lambda conn:svc.create_from_mrp(conn,body.run_id))
@router.post('/work-orders/{work_id}/transition')
def change(work_id:str,body:ChangeStatus,_=Depends(require_w3_operator)):
    return guarded(lambda conn:svc.transition(conn,work_id,body.status,body.expected_revision))
@router.post('/work-orders/{work_id}/feedback')
def record(work_id:str,body:AddFeedback,_=Depends(require_w3_operator)):
    e=Feedback(body.event_id,body.operation_id,body.good_qty,body.scrap_qty,body.event_date.isoformat())
    return guarded(lambda conn:svc.feedback(conn,work_id,e,body.expected_revision))
@router.post('/capacity-plan')
def capacity(body:CapacityRequest,_=Depends(require_w3_operator)):
    rows=[{'work_center':r.work_center,'day':r.day.isoformat(),'hours':str(r.hours)} for r in body.daily_capacity]
    return guarded(lambda conn:svc.plan_capacity(conn,body.work_order_ids,rows,body.start_date.isoformat()))
