from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.erp.models import SalesOrder, OrderScope
from app.erp.adapter import from_legacy_row, from_v11_rows, select_orders, OrderNotConfirmed, OrderNotFound, read_legacy_order
from app.main import app

LEGACY=('SO-1','FG',Decimal('2.5'),date(2026,11,20),1,'CONFIRMED',2)

def test_legacy_order_contract():
    o=from_legacy_row(LEGACY)
    assert o.order_id=='SO-1' and o.lines[0].quantity==Decimal('2.5')
    assert o.source=='legacy' and o.version==2

def test_v11_multiline():
    o=from_v11_rows(('SO-2',date(2026,11,21),0,'CONFIRMED',1),[(1,'FG',2),(2,'PART',3)])
    assert len(o.lines)==2 and o.source=='v11'

def test_reject_duplicate_line_and_invalid_qty():
    with pytest.raises(ValidationError):
        from_v11_rows(('SO-2',date(2026,11,21),0,'CONFIRMED',1),[(1,'FG',2),(1,'PART',3)])
    with pytest.raises(ValidationError):
        from_legacy_row(('SO-1','FG',0,date(2026,11,20),1,'CONFIRMED',2))

@pytest.mark.parametrize('scope',[
    {'mode':'global','order_ids':['SO-1']},
    {'mode':'selected_orders','order_ids':[]},
    {'mode':'selected_orders','order_ids':['SO-1','SO-1']},
    {'mode':'selected_orders','order_ids':[' ']},
])
def test_scope_invalid(scope):
    with pytest.raises(ValidationError):OrderScope(**scope)

def test_scope_filter_and_fail_closed():
    o=from_legacy_row(LEGACY)
    draft=from_legacy_row(('SO-3','FG',1,date(2026,11,21),0,'DRAFT',1))
    assert [x.order_id for x in select_orders([draft,o],OrderScope(mode='global'))]==['SO-1']
    assert [x.order_id for x in select_orders([draft,o],OrderScope(mode='selected_orders',order_ids=['SO-1']))]==['SO-1']
    with pytest.raises(OrderNotFound):select_orders([o],OrderScope(mode='selected_orders',order_ids=['SO-404']))
    with pytest.raises(OrderNotConfirmed):select_orders([draft],OrderScope(mode='selected_orders',order_ids=['SO-3']))

class Cursor:
    def __init__(self,rows):self.rows=rows;self.sql='';self.params=None
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,params):self.sql=sql;self.params=params
    def fetchone(self):return self.rows[0] if self.rows else None
class Conn:
    def __init__(self,rows):self.cur=Cursor(rows)
    def cursor(self):return self.cur

def test_sql_parameterized_and_not_found():
    c=Conn([LEGACY]); assert read_legacy_order(c,"SO-1' OR TRUE --").order_id=='SO-1'
    assert c.cur.params==("SO-1' OR TRUE --",)
    with pytest.raises(OrderNotFound):read_legacy_order(Conn([]),'none')

def test_api_routes_present_and_no_v11_write_routes():
    schema = app.openapi()
    paths = {(path, (method.upper(),)) for path, operations in schema['paths'].items()
             for method in operations if method.lower() in {'get','post','put','patch','delete','options','head'}}
    assert ('/api/v1/erp/sales-orders', ('GET',)) in paths
    assert ('/api/v1/erp/sales-orders/{order_id}', ('GET',)) in paths
    assert not any(path.startswith('/api/v1/erp/') and method == 'POST'
                   for path, methods in paths for method in methods)

def test_public_read_only_guard(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY','1')
    r=TestClient(app).post('/api/v1/db/integrated-mrp/runs')
    assert r.status_code==403
    assert r.json()['detail']['code']=='PUBLIC_DEMO_READ_ONLY'
