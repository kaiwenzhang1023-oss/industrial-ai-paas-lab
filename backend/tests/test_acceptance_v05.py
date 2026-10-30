from decimal import Decimal as D
import pytest
from fastapi.testclient import TestClient
from app.domain.acceptance import run_acceptance
from app.domain.timephased import Item, Order
from app.domain.versioned_bom import BOMRevision
from app.main import app


def scenario():
    items={'FG':Item('FG','MAKE',lead_days=3),
           'ST':Item('ST','MAKE',lead_days=2,on_hand=D(60),receipts=(('2026-11-29',D(10)),)),
           'A':Item('A','BUY',on_hand=D(10)), 'B':Item('B','BUY')}
    rev=[BOMRevision('FG','v1','2026-01-01','2026-11-29','RELEASED',(('ST',1),)),
         BOMRevision('FG','v2','2026-11-29',None,'RELEASED',(('ST',2),)),
         BOMRevision('ST','old','2026-01-01','2026-11-26','RELEASED',(('A',1),)),
         BOMRevision('ST','new','2026-11-26',None,'RELEASED',(('B',1),))]
    orders=[Order('SO1','FG',D(100),'2026-11-30',1),Order('SO2','FG',D(20),'2026-12-03',5)]
    return orders,items,rev


def test_unified_golden_two_orders():
    data=run_acceptance(*scenario())
    st=[x for x in data['mrp_lines'] if x['material']=='ST' and D(x['gross'])>0]
    assert [(x['gross'],x['planned']) for x in st]==[('100','40'),('40','30')]
    assert {x['version'] for x in data['bom_selections'] if x['parent']=='FG'}=={'v1','v2'}
    assert data['pegging']['conservation_passed'] is True


def test_stable_hash_and_payload():
    first=run_acceptance(*scenario());second=run_acceptance(*scenario())
    assert first==second and len(first['result_hash'])==64


def test_future_receipt_not_allocated_to_earlier_order():
    result=run_acceptance(*scenario())
    rows=[r for r in result['pegging']['order_allocations'] if r['order_id']=='SO1' and r['material']=='ST']
    assert {r['supply_kind'] for r in rows}=={'STOCK','PLAN'}


def test_supply_ledger_conserves_all_lots():
    result=run_acceptance(*scenario())
    for row in result['pegging']['supply_ledger']:
        assert D(row['capacity'])==D(row['allocated'])+D(row['remaining'])


def test_moq_excess_reused_without_double_explosion():
    orders,items,revisions=scenario()
    items['ST']=Item('ST','MAKE',lead_days=2,moq=D(50),lot=D(10))
    orders=[Order('SO1','FG',D(20),'2026-11-30'),Order('SO2','FG',D(10),'2026-12-03')]
    result=run_acceptance(orders,items,revisions)
    lots=[p for p in result['plan_lots'] if p['material']=='ST']
    assert len(lots)==1 and lots[0]['quantity']=='50'
    children=[x for x in result['pegging']['plan_child_edges'] if x['parent_material']=='ST']
    assert sum(D(x['child_gross']) for x in children)==50


def test_missing_bom_fails_closed():
    orders,items,revisions=scenario()
    revisions=[r for r in revisions if not (r.parent=='ST' and r.version=='new')]
    with pytest.raises(ValueError,match='exactly one'):
        run_acceptance(orders,items,revisions)


def test_demo_api_contract():
    response=TestClient(app).get('/api/v1/acceptance/m2-02-05/demo')
    assert response.status_code==200
    body=response.json()
    assert body['simulation'] and body['storage']=='in_memory'
    assert body['pegging']['conservation_passed']
    assert len(body['result_hash'])==64
