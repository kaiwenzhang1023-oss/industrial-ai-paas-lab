import dataclasses
import pytest
from app.domain.mrp import calculate, procurement_total, MATERIALS, BOM, validate_bom

EXPECTED = {'ST-100':(100,40,40),'RT-100':(100,15,15),'BR-01':(200,0,0),'HS-01':(100,20,20),'SC-01':(40,30,30),'CW-01':(40,20,20),'RC-01':(15,10,10),'SH-01':(15,0,0)}
@pytest.mark.parametrize('code,expected',list(EXPECTED.items()))
def test_golden_rows(code,expected):
    r=calculate()[code]
    assert (r['gross'],r['net'],r['planned'])==expected

def test_procurement_amount(): assert procurement_total(calculate())==8700

def test_bom_lower_level_explosion():
    r=calculate()
    assert (r['SC-01']['gross'],r['CW-01']['gross'],r['RC-01']['gross'],r['SH-01']['gross'])==(40,40,15,15)

def test_late_supply_not_counted():
    r=calculate()
    assert r['HS-01']['timely_receipts']==10
    assert r['SC-01']['timely_receipts']==0

def test_timely_supply_counted():
    r=calculate()
    assert r['RT-100']['timely_receipts']==5
    assert r['CW-01']['timely_receipts']==5

def test_release_dates():
    r=calculate()
    assert r['HS-01']['release_date']=='2026-11-22'
    for code in ('SC-01','CW-01','RC-01'):
        assert r[code]['release_date']=='2026-11-22'
    assert r['ST-100']['release_date']=='2026-11-25'

def test_no_duplicate_supply_when_late():
    m=dict(MATERIALS)
    m['HS-01']=dataclasses.replace(m['HS-01'],receipts=(('2026-11-29',40),))
    assert calculate(materials=m)['HS-01']['net']==30

def test_reserved_blocked_inventory():
    m=dict(MATERIALS)
    m['BR-01']=dataclasses.replace(m['BR-01'],on_hand=220,reserved=10,blocked=20)
    assert calculate(materials=m)['BR-01']['net']==10

def test_moq_and_lot():
    m=dict(MATERIALS)
    m['HS-01']=dataclasses.replace(m['HS-01'],moq=25,lot=20)
    assert calculate(materials=m)['HS-01']['planned']==40

def test_cycle_rejected():
    with pytest.raises(ValueError,match='Cyclic'):
        validate_bom(BOM+(('SH-01','EM-100',1),))

def test_invalid_order_rejected():
    with pytest.raises(ValueError): calculate(order_qty=0)

def test_deterministic(): assert calculate()==calculate()
