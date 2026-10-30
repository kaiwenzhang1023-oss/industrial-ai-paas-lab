from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.domain.timephased import Item, Order, plan
from app.domain.pegging import allocate

D=Decimal

def test_make_lot_excess_explodes_into_child_and_pegs_balance():
    items={'ROOT':Item('ROOT','MAKE',lead_days=1),
           'SUB':Item('SUB','MAKE',lead_days=2,lot=D(10),on_hand=D(5)),
           'RAW':Item('RAW','BUY',lead_days=1)}
    orders=[Order('SO-A','ROOT',D(12),'2026-11-10')]
    bom=[('ROOT','SUB',1),('SUB','RAW',2)]
    lines,pegs=allocate(orders,items,bom)
    sub=next(l for l in lines if l.material=='SUB' and l.gross)
    raw=next(l for l in lines if l.material=='RAW' and l.gross)
    assert sub.net==D(7) and sub.planned==D(10)
    assert raw.gross==D(20)
    assert sum(p.gross for p in pegs if p.material=='RAW')==D(20)
    assert sum(p.gross for p in pegs if p.material=='SUB')==D(12)

def test_db_api_refuses_silent_json_fallback(monkeypatch):
    def fail(): raise RuntimeError('database offline')
    monkeypatch.setattr('app.main.db_connect',fail)
    client=TestClient(app)
    assert client.get('/api/v1/db/orders').status_code==503
    assert client.post('/api/v1/db/mrp/runs').status_code==503
    assert client.get('/api/v1/db/mrp/runs/unknown').status_code==503
    assert client.get('/api/v1/db/health').status_code==503

def test_db_run_not_found(monkeypatch):
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr('app.main.db_connect',lambda:Conn())
    def missing(conn,run_id):raise KeyError(run_id)
    monkeypatch.setattr('app.main.db_read_run',missing)
    assert TestClient(app).get('/api/v1/db/mrp/runs/missing').status_code==404
