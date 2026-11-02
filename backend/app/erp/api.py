"""V1.1 read-only ERP endpoints backed by the existing V1.0 schema.

Write routes are intentionally NOT registered until isolated Neon branch
migration, operator authentication and auditing have passed their gates.
"""
from fastapi import APIRouter, HTTPException, Query
from app.db.repository import connect
from .adapter import read_legacy_orders, read_legacy_order, OrderNotFound
from .models import SalesOrder

router = APIRouter(prefix='/api/v1/erp',tags=['ERP V1.1 read-only'])

@router.get('/sales-orders',response_model=list[SalesOrder])
def list_sales_orders(status: str | None = None,
                      limit: int = Query(default=50,ge=1,le=100),
                      offset: int = Query(default=0,ge=0)):
    if status is not None and status not in ('DRAFT','CONFIRMED','CANCELLED'):
        raise HTTPException(422,detail={'code':'INVALID_ORDER_STATUS'})
    try:
        with connect() as conn:
            return read_legacy_orders(conn,status,limit,offset)
    except Exception:
        raise HTTPException(503,detail={'code':'DATABASE_UNAVAILABLE'})

@router.get('/sales-orders/{order_id}',response_model=SalesOrder)
def get_sales_order(order_id: str):
    try:
        with connect() as conn:
            return read_legacy_order(conn,order_id)
    except OrderNotFound:
        raise HTTPException(404,detail={'code':'ORDER_NOT_FOUND'})
    except Exception:
        raise HTTPException(503,detail={'code':'DATABASE_UNAVAILABLE'})
