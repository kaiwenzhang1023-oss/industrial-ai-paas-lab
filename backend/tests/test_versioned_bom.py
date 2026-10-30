import pytest
from decimal import Decimal
from app.domain.timephased import Item,Order
from app.domain.versioned_bom import BOMRevision,select_revision,plan_versioned,validate_revisions

D=Decimal

def fixture():
    items={
        'FG':Item('FG','MAKE',lead_days=3),
        'ST':Item('ST','MAKE',lead_days=2,on_hand=D(60)),
        'A':Item('A','BUY',on_hand=D(10)),
        'B':Item('B','BUY',on_hand=D(10)),
    }
    rev=[BOMRevision('FG','v1','2026-01-01','2026-11-29','RELEASED',(('ST',1),)),
         BOMRevision('FG','v2','2026-11-29',None,'RELEASED',(('ST',2),)),
         BOMRevision('ST','v1','2026-01-01','2026-11-26','RELEASED',(('A',1),)),
         BOMRevision('ST','v2','2026-11-26',None,'RELEASED',(('B',1),))]
    return items,rev

def test_exclusive_boundary():
    _,r=fixture()
    assert select_revision('FG','2026-11-28',r).version=='v1'
    assert select_revision('FG','2026-11-29',r).version=='v2'

def test_draft_not_eligible():
    _,r=fixture();r.append(BOMRevision('FG','draft','2026-01-01',None,'DRAFT',(('ST',9),)))
    assert select_revision('FG','2026-11-29',r).version=='v2'

def test_gap_fail_closed():
    _,r=fixture()
    with pytest.raises(ValueError,match='exactly one'):select_revision('FG','2025-12-31',r)

def test_overlap_rejected():
    i,r=fixture();r.append(BOMRevision('FG','v3','2026-11-28',None,'RELEASED',(('ST',3),)))
    with pytest.raises(ValueError,match='overlapping'):validate_revisions(r,i)

def test_cycle_across_versions_rejected():
    i,r=fixture();r.append(BOMRevision('A','v1','2026-01-01',None,'RELEASED',(('FG',1),)))
    with pytest.raises(ValueError,match='cyclic'):validate_revisions(r,i)

def test_two_orders_use_different_fg_versions_and_shared_stock():
    i,r=fixture()
    orders=[Order('SO1','FG',D(100),'2026-11-30'),Order('SO2','FG',D(20),'2026-12-03')]
    result=plan_versioned(orders,i,r)
    st=[l for l in result.lines if l.material=='ST' and l.gross]
    assert [(x.date,x.gross,x.planned) for x in st]==[('2026-11-27',D(100),D(40)),('2026-11-30',D(40),D(40))]
    assert {(t.order_id,t.bom_version,t.gross) for t in result.traces if t.parent=='FG'}=={('SO1','v1',D(100)),('SO2','v2',D(40))}

def test_child_bom_selected_at_make_release_not_sales_due():
    i,r=fixture()
    result=plan_versioned([Order('SO1','FG',D(100),'2026-11-30'),Order('SO2','FG',D(20),'2026-12-03')],i,r)
    assert {(t.material,t.need_date,t.gross) for t in result.traces if t.parent=='ST'}=={('A','2026-11-25',D(40)),('B','2026-11-28',D(40))}

def test_missing_child_revision_fails_closed():
    i,r=fixture();i['ST']=Item('ST','MAKE',lead_days=2,on_hand=D(0));r=[x for x in r if not (x.parent=='ST' and x.version=='v2')]
    with pytest.raises(ValueError,match='exactly one'):plan_versioned([Order('SO2','FG',D(20),'2026-12-03')],i,r)

def test_repeatable():
    i,r=fixture();o=[Order('SO1','FG',D(100),'2026-11-30')]
    assert plan_versioned(o,i,r)==plan_versioned(o,i,r)

def test_no_unplanned_order_at_zero_net():
    i,r=fixture();i['ST']=Item('ST','MAKE',lead_days=2,on_hand=D(200))
    result=plan_versioned([Order('SO1','FG',D(100),'2026-11-30')],i,r)
    assert all(x.planned==0 for x in result.lines if x.material=='ST')
    assert not any(t.parent=='ST' for t in result.traces)

def test_bom_change_uses_consumption_date_not_due_date():
    i,r=fixture()
    # Due 11/30 but root release 11/27 => v1, not v2.
    x=plan_versioned([Order('SO1','FG',D(1),'2026-11-30')],i,r)
    assert next(t for t in x.traces if t.parent=='FG').bom_version=='v1'

def test_invalid_component_and_interval():
    i,r=fixture()
    with pytest.raises(ValueError,match='empty BOM interval'):
        validate_revisions([BOMRevision('FG','bad','2026-11-30','2026-11-30','RELEASED',(('ST',1),))],i)
    with pytest.raises(ValueError,match='invalid BOM component'):
        validate_revisions([BOMRevision('FG','bad','2026-01-01',None,'RELEASED',(('ST',0),))],i)
