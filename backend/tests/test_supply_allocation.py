from decimal import Decimal as D
import pytest
from app.domain.timephased import Item, Order
from app.domain.versioned_bom import BOMRevision
from app.domain.supply_allocation import plan_supply

def base():
    items={'FG':Item('FG','MAKE',lead_days=3),
           'ST':Item('ST','MAKE',lead_days=2,on_hand=D(60),receipts=(('2026-11-29',D(10)),)),
           'A':Item('A','BUY',on_hand=D(10)),
           'B':Item('B','BUY',on_hand=D(0))}
    rev=[BOMRevision('FG','v1','2026-01-01','2026-11-29','RELEASED',(('ST',1),)),
         BOMRevision('FG','v2','2026-11-29',None,'RELEASED',(('ST',2),)),
         BOMRevision('ST','old','2026-01-01','2026-11-26','RELEASED',(('A',1),)),
         BOMRevision('ST','new','2026-11-26',None,'RELEASED',(('B',1),))]
    orders=[Order('SO1','FG',D(100),'2026-11-30',1),Order('SO2','FG',D(20),'2026-12-03',5)]
    return orders,items,rev

def lines(r,mat):return [l for l in r.lines if l['material']==mat and l['gross']]

def test_versioned_multiorder_receipt_carry_and_downstream():
    o,i,v=base();r=plan_supply(o,i,v)
    st=lines(r,'ST')
    assert [(x['gross'],x['planned']) for x in st]==[(D(100),D(40)),(D(40),D(30))]
    assert [(x['need_date'],x['gross']) for x in lines(r,'A')]==[('2026-11-25',D(40))]
    assert [(x['need_date'],x['gross']) for x in lines(r,'B')]==[('2026-11-28',D(30))]
    assert {d.bom_version for d in r.demands if d.parent_material=='FG'}=={'v1','v2'}
    assert {d.parent_plan for d in r.demands if d.parent_material=='ST'}=={'PLAN:ST@2026-11-27','PLAN:ST@2026-11-30'}

def test_late_receipt_cannot_cover_earlier_demand():
    o,i,v=base();r=plan_supply(o,i,v)
    first=next(d for d in r.demands if d.material=='ST' and d.root_order=='SO1')
    alloc=[a for a in r.allocations if a.demand_id==first.demand_id]
    assert {(a.supply_kind,a.quantity) for a in alloc}=={('STOCK',D(60)),('PLAN',D(40))}

def test_receipt_carries_to_later_order():
    o,i,v=base();r=plan_supply(o,i,v)
    second=next(d for d in r.demands if d.material=='ST' and d.root_order=='SO2')
    assert {(a.supply_kind,a.quantity) for a in r.allocations if a.demand_id==second.demand_id}=={('RECEIPT',D(10)),('PLAN',D(30))}

def test_priority_tiebreak_and_no_double_stock():
    o,i,v=base();o=[Order('SOZ','FG',D(40),'2026-11-30',1),Order('SOA','FG',D(40),'2026-11-30',5)]
    r=plan_supply(o,i,v)
    a=next(d for d in r.demands if d.material=='ST' and d.root_order=='SOA')
    z=next(d for d in r.demands if d.material=='ST' and d.root_order=='SOZ')
    assert sum(x.quantity for x in r.allocations if x.demand_id==a.demand_id and x.supply_kind=='STOCK')==40
    assert sum(x.quantity for x in r.allocations if x.demand_id==z.demand_id and x.supply_kind=='STOCK')==20

def test_moq_excess_carries_without_double_explosion():
    o,i,v=base();i['ST']=Item('ST','MAKE',lead_days=2,moq=D(50),lot=D(10))
    o=[Order('SO1','FG',D(20),'2026-11-30'),Order('SO2','FG',D(10),'2026-12-03')]
    r=plan_supply(o,i,v)
    assert [(x['planned'],x['closing_supply']) for x in lines(r,'ST')]==[(D(50),D(30)),(D(0),D(10))]
    assert sum(d.qty for d in r.demands if d.parent_material=='ST')==D(50)
    assert len([p for p in r.plans if p.material=='ST'])==1
    second=next(d for d in r.demands if d.material=='ST' and d.root_order=='SO2')
    assert [(a.supply_kind,a.supply_id,a.quantity) for a in r.allocations if a.demand_id==second.demand_id]==[('PLAN','PLAN:ST@2026-11-27',D(20))]

def test_same_day_priority_and_id_tie():
    o,i,v=base();i['ST']=Item('ST','MAKE',lead_days=2,on_hand=D(10))
    o=[Order('Z','FG',D(10),'2026-11-30'),Order('A','FG',D(10),'2026-11-30')]
    r=plan_supply(o,i,v)
    a=next(d for d in r.demands if d.material=='ST' and d.root_order=='A')
    assert any(x.supply_kind=='STOCK' and x.quantity==10 for x in r.allocations if x.demand_id==a.demand_id)

def test_reserved_blocked_are_not_allocated():
    o,i,v=base();i['ST']=Item('ST','MAKE',lead_days=2,on_hand=D(60),reserved=D(20),blocked=D(10))
    r=plan_supply([o[0]],i,v)
    assert lines(r,'ST')[0]['planned']==70

def test_no_order_for_zero_shortage():
    o,i,v=base();i['ST']=Item('ST','MAKE',lead_days=2,on_hand=D(500))
    r=plan_supply(o,i,v)
    assert not any(p.material=='ST' for p in r.plans)
    assert not any(d.parent_material=='ST' for d in r.demands)

def test_moq_nonmultiple_rounding():
    o,i,v=base();i['ST']=Item('ST','MAKE',lead_days=2,moq=D(25),lot=D(10))
    # With 0 stock: MOQ 25 rounds up to 30.
    assert lines(plan_supply([Order('SO1','FG',D(1),'2026-11-30')],i,v),'ST')[0]['planned']==30

def test_repeatable():
    o,i,v=base();assert plan_supply(o,i,v)==plan_supply(o,i,v)

def test_missing_revision_fail_closed():
    o,i,v=base();v=[r for r in v if not (r.parent=='ST' and r.version=='new')]
    with pytest.raises(ValueError,match='exactly one'):plan_supply(o,i,v)

def test_invalid_supply_rejected():
    o,i,v=base();i['ST']=Item('ST','MAKE',lead_days=2,receipts=(('2026-11-19',D(1)),))
    with pytest.raises(ValueError,match='invalid receipt'):plan_supply(o,i,v)
