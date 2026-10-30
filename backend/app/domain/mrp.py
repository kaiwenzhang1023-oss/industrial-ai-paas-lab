"""Deterministic, single-order EM-100 golden scenario calculator.
Not a general multi-order time-phased MRP engine.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from math import ceil

@dataclass(frozen=True)
class Material:
    code: str
    kind: str
    parent: str
    qty_per: int
    on_hand: int
    reserved: int
    blocked: int
    receipts: tuple[tuple[str,int], ...]
    moq: int
    lot: int
    lead_days: int
    need_date: str
    unit_price: Decimal = Decimal('0')

BOM = (
    ('EM-100','ST-100',1),('EM-100','RT-100',1),
    ('EM-100','BR-01',2),('EM-100','HS-01',1),
    ('ST-100','SC-01',1),('ST-100','CW-01',1),
    ('RT-100','RC-01',1),('RT-100','SH-01',1),
)
MATERIALS = {
 'ST-100': Material('ST-100','MAKE','EM-100',1,60,0,0,(),0,1,2,'2026-11-27'),
 'RT-100': Material('RT-100','MAKE','EM-100',1,80,0,0,(('2026-11-26',5),),0,1,2,'2026-11-27'),
 'BR-01': Material('BR-01','BUY','EM-100',2,250,0,0,(),10,10,4,'2026-11-27'),
 'HS-01': Material('HS-01','BUY','EM-100',1,70,0,0,(('2026-11-26',10),('2026-11-29',40)),10,10,5,'2026-11-27',Decimal('100')),
 'SC-01': Material('SC-01','BUY','ST-100',1,10,0,0,(('2026-11-27',15),),10,10,3,'2026-11-25',Decimal('120')),
 'CW-01': Material('CW-01','BUY','ST-100',1,15,0,0,(('2026-11-24',5),),10,10,3,'2026-11-25',Decimal('80')),
 'RC-01': Material('RC-01','BUY','RT-100',1,5,0,0,(),10,10,3,'2026-11-25',Decimal('150')),
 'SH-01': Material('SH-01','BUY','RT-100',1,15,0,0,(),10,10,3,'2026-11-25'),
}

def validate_bom(edges):
    children = {}
    for parent, child, qty in edges:
        if qty <= 0: raise ValueError('BOM quantity must be positive')
        children.setdefault(parent, []).append(child)
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting: raise ValueError('Cyclic BOM')
        if node in visited: return
        visiting.add(node)
        for child in children.get(node, []): visit(child)
        visiting.remove(node)
        visited.add(node)
    for node in children: visit(node)

def calculate(order_qty=100, materials=None, bom=BOM):
    validate_bom(bom)
    if order_qty <= 0: raise ValueError('Invalid order quantity')
    materials = MATERIALS if materials is None else materials
    result = {}
    def explode(parent, planned_qty):
        for p, code, per in bom:
            if p != parent: continue
            m = materials[code]
            gross = planned_qty * per
            if min(m.on_hand,m.reserved,m.blocked,m.moq,m.lot,m.lead_days) < 0 or m.lot <= 0 or m.reserved+m.blocked > m.on_hand:
                raise ValueError('Invalid material quantities')
            available = m.on_hand-m.reserved-m.blocked
            timely = sum(q for d,q in m.receipts if d <= m.need_date)
            if timely < 0: raise ValueError('Invalid receipts')
            net = max(0,gross-available-timely)
            planned = ceil(max(net,m.moq)/m.lot)*m.lot if net else 0
            release = (date.fromisoformat(m.need_date)-timedelta(days=m.lead_days)).isoformat()
            result[code] = {'gross':gross,'available':available,'timely_receipts':timely,'net':net,'planned':planned,'need_date':m.need_date,'release_date':release,'kind':m.kind}
            if m.kind == 'MAKE' and planned: explode(code,planned)
    explode('EM-100',order_qty)
    return result

def procurement_total(result, materials=None):
    materials = MATERIALS if materials is None else materials
    return sum((materials[k].unit_price*v['planned'] for k,v in result.items() if v['kind']=='BUY'), Decimal('0'))
