from decimal import Decimal as D
import pytest
from dataclasses import replace
from app.domain.timephased import Item, Order
from app.domain.versioned_bom import BOMRevision
from app.domain.supply_allocation import plan_supply
from app.domain.pegging_report import build_pegging_report,report_as_jsonable


def sample(moq=D(0), lot=D(1)):
    items={'FG':Item('FG','MAKE',lead_days=3),
           'ST':Item('ST','MAKE',lead_days=2,on_hand=D(0),moq=moq,lot=lot),
           'A':Item('A','BUY',on_hand=D(0))}
    revisions=[BOMRevision('FG','v1','2026-01-01',None,'RELEASED',(('ST',1),)),
               BOMRevision('ST','v1','2026-01-01',None,'RELEASED',(('A',2),))]
    orders=[Order('SO1','FG',D(20),'2026-11-30'),Order('SO2','FG',D(10),'2026-12-03')]
    return orders,items,revisions

def test_moq_plan_reused_by_later_order_and_exploded_once():
    o,i,v=sample(D(50),D(10));r=plan_supply(o,i,v)
    report=build_pegging_report(r,i)
    st=[x for x in report['order_allocations'] if x['material']=='ST']
    assert [(x['order_id'],x['supply_id'],x['allocated_qty']) for x in st]==[
        ('SO1','PLAN:ST@2026-11-27',D(20)),('SO2','PLAN:ST@2026-11-27',D(10))]
    ledger=next(x for x in report['supply_ledger'] if x['source_id']=='PLAN:ST@2026-11-27')
    assert (ledger['capacity'],ledger['allocated'],ledger['remaining'])==(D(50),D(30),D(20))
    assert sum(x['child_gross'] for x in report['plan_child_edges'] if x['parent_material']=='ST')==D(100)
    assert all(x['order_id'] is None for x in report['order_allocations'] if x['material']=='A')

def test_distinct_same_day_receipts_have_unique_source_ids():
    o,i,v=sample();i['ST']=Item('ST','MAKE',lead_days=2,receipts=(('2026-11-26',D(7)),('2026-11-26',D(8))))
    r=plan_supply(o[:1],i,v); report=build_pegging_report(r,i)
    receipt=[x for x in report['supply_ledger'] if x['material']=='ST' and x['kind']=='RECEIPT']
    assert len(receipt)==2 and len({x['source_id'] for x in receipt})==2
    assert sum(x['allocated'] for x in receipt)==D(15)

def test_future_receipt_does_not_cover_earlier_order():
    o,i,v=sample();i['ST']=Item('ST','MAKE',lead_days=2,receipts=(('2026-11-29',D(10)),))
    r=plan_supply(o,i,v);report=build_pegging_report(r,i)
    first=[x for x in report['order_allocations'] if x['order_id']=='SO1' and x['material']=='ST']
    assert all(x['supply_kind']!='RECEIPT' for x in first)
    second=[x for x in report['order_allocations'] if x['order_id']=='SO2' and x['material']=='ST']
    assert any(x['supply_kind']=='RECEIPT' and x['allocated_qty']==10 for x in second)

def test_reject_fabricated_overallocation():
    o,i,v=sample();r=plan_supply(o,i,v)
    r.allocations[0]=replace(r.allocations[0],quantity=r.allocations[0].quantity+D(1))
    with pytest.raises(ValueError,match='demand conservation'):build_pegging_report(r,i)

def test_reject_fabricated_source_capacity():
    o,i,v=sample();r=plan_supply(o,i,v)
    p=next(p for p in r.plans if p.material=='ST')
    r.plans[r.plans.index(p)]=replace(p,quantity=D(1))
    with pytest.raises(ValueError,match='supply conservation'):build_pegging_report(r,i)

def test_reject_orphan_plan_genealogy():
    o,i,v=sample();r=plan_supply(o,i,v)
    d=next(d for d in r.demands if d.parent_plan)
    r.demands[r.demands.index(d)]=replace(d,parent_plan='PLAN:UNKNOWN')
    with pytest.raises(ValueError,match='orphaned'):build_pegging_report(r,i)

def test_reject_fake_root_on_child_plan():
    o,i,v=sample();r=plan_supply(o,i,v)
    d=next(d for d in r.demands if d.parent_plan)
    r.demands[r.demands.index(d)]=replace(d,root_order='SO1')
    with pytest.raises(ValueError,match='provenance mismatch|fabricated'):build_pegging_report(r,i)

def test_report_repeatability_and_decimal_serialization():
    o,i,v=sample(D(25),D(10));a=report_as_jsonable(build_pegging_report(plan_supply(o,i,v),i))
    b=report_as_jsonable(build_pegging_report(plan_supply(o,i,v),i))
    assert a==b and a['conservation_passed']
    assert all(isinstance(x['capacity'],str) for x in a['supply_ledger'])

def test_stock_reserved_and_blocked_conservation():
    o,i,v=sample();i['ST']=Item('ST','MAKE',lead_days=2,on_hand=D(30),reserved=D(10),blocked=D(5))
    r=plan_supply(o,i,v);report=build_pegging_report(r,i)
    stock=next(x for x in report['supply_ledger'] if x['kind']=='STOCK' and x['material']=='ST')
    assert stock['capacity']==15 and stock['allocated']==15 and stock['remaining']==0

def test_no_duplicate_receipt_reuse_across_orders():
    o,i,v=sample();i['ST']=Item('ST','MAKE',lead_days=2,receipts=(('2026-11-26',D(5)),))
    report=build_pegging_report(plan_supply(o,i,v),i)
    receipt=next(x for x in report['supply_ledger'] if x['kind']=='RECEIPT' and x['material']=='ST')
    assert receipt['allocated']==5 and receipt['remaining']==0
