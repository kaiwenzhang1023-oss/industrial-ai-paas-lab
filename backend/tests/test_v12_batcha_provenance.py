from decimal import Decimal
import pytest
from app.wms.provenance import allocate_stock_evidence


def row(material,warehouse,lot,on_hand,reserved=0,blocked=0,version=1):
    return (material,warehouse,lot,Decimal(on_hand),Decimal(reserved),Decimal(blocked),
            '2026-10-29 00:00:00+00:00',version)


def pegging(*qtys):
    return {'order_allocations':[{'supply_kind':'STOCK','material':'BR-01',
      'allocated_qty':str(q),'demand_id':f'D{i}','supply_id':'STOCK:BR-01@2026-11-20',
      'order_id':'SO-2026-001'} for i,q in enumerate(qtys)]}


def test_multisite_deterministic():
    rows=[row('BR-01','WH-B','LOT-2','9'),row('BR-01','WH-A','LOT-1','5')]
    a=allocate_stock_evidence(rows,pegging(8))
    assert [(x['warehouse_id'],x['lot_id'],x['allocated_qty']) for x in a] == [
        ('WH-A','LOT-1','5'),('WH-B','LOT-2','3')]
    assert allocate_stock_evidence(list(reversed(rows)),pegging(8))==a


def test_reserved_and_blocked_not_allocated():
    a=allocate_stock_evidence([row('BR-01','WH-A','','10','3','2')],pegging(5))
    assert a[0]['allocated_qty']=='5'


def test_insufficient_stock_fails_closed():
    with pytest.raises(ValueError,match='WMS_STOCK_PROVENANCE_INSUFFICIENT'):
        allocate_stock_evidence([row('BR-01','WH-A','','4')],pegging(5))


def test_no_stock_allocation_no_evidence():
    assert allocate_stock_evidence([],{'order_allocations':[]})==[]


def test_duplicate_balance_key_rejected():
    r=row('BR-01','WH-A','','4')
    with pytest.raises(ValueError,match='WMS_DUPLICATE_SOURCE'):
        allocate_stock_evidence([r,r],pegging(1))


def test_multiple_demands_do_not_reuse_same_stock():
    a=allocate_stock_evidence([row('BR-01','WH-A','','10')],pegging(7,3))
    assert sum(Decimal(x['allocated_qty']) for x in a)==Decimal('10')


def test_negative_available_rejected():
    with pytest.raises(ValueError,match='WMS_NEGATIVE_AVAILABLE'):
        allocate_stock_evidence([row('BR-01','WH-A','','2','3')],pegging(1))
