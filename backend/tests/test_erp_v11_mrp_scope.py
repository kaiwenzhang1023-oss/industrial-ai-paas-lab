"""W2 stage 2: selected-order DB read contract; no live database required."""
from datetime import date
from decimal import Decimal
import pytest
from app.db.integrated import read_integrated_sources, canonical_hash
from app.erp.models import OrderScope
from app.erp.adapter import OrderNotFound, OrderNotConfirmed

class Cursor:
    def __init__(self, rows): self.rows=rows; self.last=''; self.params=None
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self, sql, params=None):self.last=sql; self.params=params
    def fetchall(self):
        if 'FROM mock_erp.sales_orders' in self.last:return self.rows
        if 'FROM mock_erp.materials' in self.last:return [('FG','MAKE',1,Decimal(0),Decimal(1),Decimal(1),Decimal(0),Decimal(0),Decimal(0))]
        if 'FROM mock_erp.supply_orders' in self.last:return []
        if 'FROM mock_erp.effective_bom_headers' in self.last:return [('FG','V1','RELEASED',date(2026,1,1),None)]
        if 'FROM mock_erp.effective_bom_components' in self.last:return []
        if 'FROM mock_wms.inventory_balances' in self.last:return []
        raise AssertionError(self.last)
class Conn:
    def __init__(self,rows):self.cur=Cursor(rows)
    def cursor(self):return self.cur

def test_selected_orders_filters_at_sql_source():
    c=Conn([('SO-1','FG',Decimal(2),date(2026,11,30),1,1,'CONFIRMED')])
    orders,_,_,versions=read_integrated_sources(c,'2026-11-20',OrderScope(mode='selected_orders',order_ids=['SO-1']))
    assert [o.order_id for o in orders]==['SO-1']
    assert versions['v11_order_scope']=={'mode':'selected_orders','order_ids':['SO-1']}

def test_selected_missing_order_fails_closed():
    with pytest.raises(OrderNotFound):
        read_integrated_sources(Conn([]),'2026-11-20',OrderScope(mode='selected_orders',order_ids=['SO-X']))

def test_selected_unconfirmed_order_fails_closed():
    with pytest.raises(OrderNotConfirmed):
        read_integrated_sources(Conn([('SO-1','FG',Decimal(2),date(2026,11,30),1,1,'DRAFT')]),'2026-11-20',OrderScope(mode='selected_orders',order_ids=['SO-1']))

def test_scope_hash_differs_by_selection():
    a=canonical_hash({'versions':{'v11_order_scope':{'mode':'selected_orders','order_ids':['SO-1']}}})
    b=canonical_hash({'versions':{'v11_order_scope':{'mode':'selected_orders','order_ids':['SO-2']}}})
    assert a!=b
