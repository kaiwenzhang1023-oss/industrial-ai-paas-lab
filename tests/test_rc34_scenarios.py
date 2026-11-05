"""RC3.4 isolated overlay contract: never mutate shared source objects."""
from decimal import Decimal
from app.domain.timephased import Item, Order
from app.db.repository import apply_scenario, SCENARIOS, _snapshot_hash
import pytest


def source():
    orders=[Order('SO-1','EM-100',Decimal('2'),'2026-11-25',1)]
    items={'EM-100':Item('EM-100','MAKE',lead_days=1),
           'BR-01':Item('BR-01','BUY',on_hand=Decimal('100'))}
    bom=[('EM-100','BR-01',Decimal('2'))]
    return orders,items,bom


def test_scenarios_are_isolated_and_distinct():
    o,i,b=source();original=_snapshot_hash('2026-10-29',o,i,b)
    variants={}
    for key in SCENARIOS:
        so,si,sb=apply_scenario(o,i,b,key)
        variants[key]=_snapshot_hash('2026-10-29',so,si,sb)
    assert len(set(variants.values()))==4
    assert _snapshot_hash('2026-10-29',o,i,b)==original
    assert i['BR-01'].on_hand==100 and b[0][2]==2


def test_delay_and_bom_anomaly_are_explicit():
    o,i,b=source()
    assert apply_scenario(o,i,b,'C')[0][0].due=='2026-12-02'
    assert apply_scenario(o,i,b,'D')[2][0][2]==4
    assert apply_scenario(o,i,b,'B')[1]['BR-01'].on_hand==0
    with pytest.raises(ValueError):apply_scenario(o,i,b,'INVALID')
