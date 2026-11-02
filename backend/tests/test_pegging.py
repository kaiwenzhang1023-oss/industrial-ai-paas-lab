from decimal import Decimal
from app.domain.seed_loader import load
from app.domain.pegging import allocate
from app.domain.timephased import Item,Order

def sample():
    data,orders,items=load()
    return allocate(orders,items,data['bom'],data['as_of'])

def test_all_pegs_balance():
    _,pegs=sample()
    assert pegs
    for p in pegs: assert p.gross==p.from_stock+p.from_receipts+p.from_planned

def test_order_level_shared_inventory():
    _,pegs=sample()
    st=[p for p in pegs if p.material=='ST-100']
    assert [(p.order_id,p.gross,p.from_stock,p.from_planned) for p in st]==[
        ('SO-2026-001',Decimal(100),Decimal(60),Decimal(40)),
        ('SO-2026-002',Decimal(20),Decimal(0),Decimal(20))]

def test_late_supply_not_used_early():
    _,pegs=sample()
    hs=[p for p in pegs if p.material=='HS-01']
    assert [(p.from_stock,p.from_receipts,p.from_planned) for p in hs]==[
        (Decimal(70),Decimal(10),Decimal(20)),(Decimal(0),Decimal(20),Decimal(0))]

def test_make_pegs_propagate_order_identity():
    _,pegs=sample()
    sc=[p for p in pegs if p.material=='SC-01']
    assert [(p.order_id,p.gross) for p in sc]==[
        ('SO-2026-001',Decimal(40)),('SO-2026-002',Decimal(20))]

def test_same_day_priority():
    items={'FG':Item('FG','MAKE',lead_days=0),'C':Item('C','BUY',on_hand=Decimal(5))}
    orders=[Order('LOW','FG',Decimal(5),'2026-11-01',0),Order('HIGH','FG',Decimal(5),'2026-11-01',9)]
    _,pegs=allocate(orders,items,[('FG','C',1)])
    assert [(p.order_id,p.from_stock,p.from_planned) for p in pegs]==[
        ('HIGH',Decimal(5),Decimal(0)),('LOW',Decimal(0),Decimal(5))]

def test_stable_order_id_tiebreak():
    items={'FG':Item('FG','MAKE'),'C':Item('C','BUY',on_hand=Decimal(1))}
    orders=[Order('B','FG',Decimal(1),'2026-11-01'),Order('A','FG',Decimal(1),'2026-11-01')]
    _,pegs=allocate(orders,items,[('FG','C',1)])
    assert pegs[0].order_id=='A' and pegs[0].from_stock==1

def test_deterministic():
    assert sample()==sample()
