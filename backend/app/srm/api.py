"""V1.4 Batch A SRM HTTP API: guarded writes and persisted reads."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from app.db.repository import connect
from app.workbench import require_w3_operator
from app.srm import service as svc
router=APIRouter(prefix='/api/v1/srm',tags=['V1.4 SRM simulation'])
class Supplier(BaseModel):
    supplier_id:str=Field(min_length=1)
    code:str=Field(min_length=1)
    name:str=Field(min_length=1)
    expected_revision:int|None=None
class SupplierItem(BaseModel):
    supplier_id:str
    material_id:str
    moq:Decimal=Field(ge=0)
    lead_days:int=Field(ge=0)
    capacity:Decimal|None=None
class ImportRun(BaseModel): run_id:str=Field(min_length=1)
class PO(BaseModel):
    po_id:str=Field(min_length=1)
    supplier_id:str
    pr_id:str
class Transition(BaseModel):
    status:str
    expected_revision:int=Field(ge=0)
class Schedule(BaseModel):
    schedule_id:str
    po_line_id:str
    confirmed_qty:Decimal=Field(gt=0)
    promised_date:date
class Confirmation(BaseModel):
    po_id:str
    confirmation_id:str
    schedules:list[Schedule]
    expected_revision:int=Field(ge=0)
def run(fn):
    try:
        with connect() as conn: return fn(conn)
    except svc.SRMError as e:
        code=str(e)
        raise HTTPException(409 if any(x in code for x in ('CONFLICT','STALE','ALREADY')) else 422,detail={'code':code}) from e
    except Exception as e:
        raise HTTPException(503,detail={'code':'SRM_STORAGE_UNAVAILABLE'}) from e
@router.get('/requisitions')
def requisitions(): return run(svc.list_requisitions)
@router.get('/exceptions')
def exceptions(): return run(svc.list_exceptions)
@router.post('/suppliers',status_code=201)
def supplier(body:Supplier,_=Depends(require_w3_operator)): return run(lambda c:svc.supplier_upsert(c,**body.model_dump()))
@router.post('/supplier-items',status_code=201)
def item(body:SupplierItem,_=Depends(require_w3_operator)): return run(lambda c:svc.supplier_item(c,**body.model_dump()))
@router.post('/requisitions/import-mrp',status_code=201)
def import_run(body:ImportRun,_=Depends(require_w3_operator)): return run(lambda c:svc.import_mrp(c,body.run_id))
@router.post('/purchase-orders',status_code=201)
def po(body:PO,_=Depends(require_w3_operator)): return run(lambda c:svc.create_po(c,**body.model_dump()))
@router.post('/purchase-orders/{po_id}/transition')
def transition(po_id:str,body:Transition,_=Depends(require_w3_operator)): return run(lambda c:svc.transition(c,po_id,body.status,body.expected_revision))
@router.post('/confirmations',status_code=201)
def confirm(body:Confirmation,_=Depends(require_w3_operator)): return run(lambda c:svc.confirm(c,body.po_id,body.confirmation_id,[x.model_dump(mode='json') for x in body.schedules],body.expected_revision))
