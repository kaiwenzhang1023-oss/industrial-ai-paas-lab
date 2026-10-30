from decimal import Decimal as D
from dataclasses import replace
import pytest
from app.domain.seed_loader import load
from app.domain.timephased import plan

def fixture():
    data,orders,items=load()
    return data,orders,items

def lines_for(lines,code): return [l for l in lines if l.material==code and l.gross>0]

def test_shared_stock_two_orders():
    d,orders,items=fixture(); lines=plan(orders,items,d['bom'],d['as_of'])
    stator=lines_for(lines,'ST-100')
    assert [(x.date,x.gross,x.planned) for x in stator]==[('2026-11-27',D(100),D(40)),('2026-11-30',D(20),D(20))]
    assert sum(x.planned for x in stator)==60  # not 40+0 or 40+20 with duplicated initial stock

def test_child_explosion_uses_make_release_date():
    d,o,i=fixture(); lines=plan(o,i,d['bom'],d['as_of'])
    assert [(x.date,x.gross) for x in lines_for(lines,'SC-01')]==[('2026-11-25',D(40)),('2026-11-28',D(20))]

def test_late_receipt_only_helps_later():
    d,o,i=fixture(); lines=plan(o,i,d['bom'],d['as_of'])
    hs=lines_for(lines,'HS-01')
    assert hs[0].date=='2026-11-27' and hs[0].opening==80 and hs[0].planned==20
    assert hs[1].date=='2026-11-30' and hs[1].planned==0

def test_stock_not_double_allocated():
    d,o,i=fixture(); lines=plan(o,i,d['bom'],d['as_of'])
    rt=lines_for(lines,'RT-100')
    assert [x.planned for x in rt]==[15,20]

def test_moq_lot_rounding():
    d,o,i=fixture(); i['HS-01']=replace(i['HS-01'],moq=D(23),lot=D(10))
    hs=lines_for(plan(o,i,d['bom'],d['as_of']),'HS-01')
    assert hs[0].planned==30

def test_invalid_inventory():
    d,o,i=fixture(); i['HS-01']=replace(i['HS-01'],reserved=D(80))
    with pytest.raises(ValueError): plan(o,i,d['bom'],d['as_of'])

def test_cycle():
    d,o,i=fixture()
    with pytest.raises(ValueError,match='cyclic'): plan(o,i,d['bom']+[('SC-01','EM-100',1)],d['as_of'])

def test_repeatability():
    d,o,i=fixture(); assert plan(o,i,d['bom'],d['as_of'])==plan(o,i,d['bom'],d['as_of'])

def test_order_input_order_independent():
    d,o,i=fixture(); assert plan(o,i,d['bom'],d['as_of'])==plan(list(reversed(o)),i,d['bom'],d['as_of'])
