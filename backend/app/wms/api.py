"""V1.2 WMS read-only API: balance snapshots, not stock reservations."""
from fastapi import APIRouter, HTTPException, Query
from app.db.repository import connect
from .adapter import list_balances, summarize
from .models import InventoryBalance, InventorySummary

router=APIRouter(prefix='/api/v1/wms',tags=['WMS V1.2 read-only'])

@router.get('/inventory-balances',response_model=list[InventoryBalance])
def get_balances(material_id: str | None = Query(default=None,min_length=1),
                 warehouse_id: str | None = Query(default=None,min_length=1),
                 limit: int = Query(default=50,ge=1,le=100),
                 offset: int = Query(default=0,ge=0)):
    try:
        with connect() as conn:
            return list_balances(conn,material_id,warehouse_id,limit,offset)
    except Exception as exc:
        raise HTTPException(503,detail={'code':'WMS_DATABASE_UNAVAILABLE'}) from exc

@router.get('/inventory-summary',response_model=InventorySummary)
def get_summary(material_id: str = Query(min_length=1),
                warehouse_id: str | None = Query(default=None,min_length=1)):
    try:
        with connect() as conn:
            return summarize(conn,material_id,warehouse_id)
    except Exception as exc:
        raise HTTPException(503,detail={'code':'WMS_DATABASE_UNAVAILABLE'}) from exc
