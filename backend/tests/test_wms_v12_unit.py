"""W2 contract tests; no real DB required."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.wms import api, adapter
from app.wms.models import InventoryBalance

client=TestClient(app)

class FakeCursor:
    def __init__(self,rows): self.rows=rows; self.sql=''; self.params=None
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params): self.sql=sql; self.params=params
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0]
class FakeConn:
    def __init__(self,rows): self.cur=FakeCursor(rows)
    def cursor(self): return self.cur
    def __enter__(self): return self
    def __exit__(self,*args): return False

TS=datetime(2026,11,20,tzinfo=timezone.utc)

def test_balance_decimal_and_no_double_deduction():
    b=InventoryBalance(material_id='A',warehouse_id='WH-A',lot_id='',
      on_hand=Decimal('10.1000'),reserved=Decimal('2.0000'),blocked=Decimal('1.1000'),
      snapshot_at=TS,version=2)
    assert b.available==Decimal('7.0000')

def test_balance_api_queries_db_and_keeps_warehouse_lot(monkeypatch):
    fake=FakeConn([('A','WH-B','LOT-1',Decimal(10),Decimal(2),Decimal(1),TS,3)])
    monkeypatch.setattr(api,'connect',lambda:fake)
    r=client.get('/api/v1/wms/inventory-balances?material_id=A&warehouse_id=WH-B&limit=5&offset=0')
    assert r.status_code==200
    assert r.json()[0]['available']=='7'
    assert r.json()[0]['lot_id']=='LOT-1'
    assert 'ORDER BY material_id,warehouse_id,lot_id' in fake.cur.sql
    assert fake.cur.params==('A','A','WH-B','WH-B',5,0)

def test_summary_api_aggregates_with_decimal(monkeypatch):
    fake=FakeConn([(Decimal(100),Decimal(20),Decimal(5),2,TS)])
    monkeypatch.setattr(api,'connect',lambda:fake)
    r=client.get('/api/v1/wms/inventory-summary?material_id=A')
    assert r.status_code==200
    assert r.json()['available']=='75'
    assert r.json()['balance_rows']==2

def test_wms_api_readonly_and_pagination_validation():
    paths=app.openapi()['paths']
    for path in ('/api/v1/wms/inventory-balances','/api/v1/wms/inventory-summary'):
        assert set(paths[path])=={'get'}
    assert client.get('/api/v1/wms/inventory-balances?limit=101').status_code==422
    assert client.get('/api/v1/wms/inventory-summary').status_code==422

def test_wms_db_error_no_mock_fallback(monkeypatch):
    def broken(): raise RuntimeError('database offline')
    monkeypatch.setattr(api,'connect',broken)
    r=client.get('/api/v1/wms/inventory-balances')
    assert r.status_code==503
    assert r.json()['detail']['code']=='WMS_DATABASE_UNAVAILABLE'
