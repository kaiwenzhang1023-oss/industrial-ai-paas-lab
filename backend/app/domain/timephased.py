"""Deterministic daily-bucket, shared-inventory, multi-order simplified MRP.
One inventory pool per material; allocation is global and chronological.
Production is infinite capacity, fixed calendar-day lead times.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

@dataclass(frozen=True)
class Item:
    code: str
    kind: str  # MAKE or BUY
    lead_days: int = 0
    on_hand: Decimal = Decimal(0)
    reserved: Decimal = Decimal(0)
    blocked: Decimal = Decimal(0)
    safety: Decimal = Decimal(0)
    moq: Decimal = Decimal(0)
    lot: Decimal = Decimal(1)
    receipts: tuple = ()  # (ISO date, qty) of unallocated confirmed supply

@dataclass(frozen=True)
class Order:
    order_id: str
    product: str
    qty: Decimal
    due: str
    priority: int = 0

@dataclass
class Line:
    material: str
    date: str
    gross: Decimal
    opening: Decimal
    receipts: Decimal
    net: Decimal
    planned: Decimal
    closing: Decimal
    release: str
    kind: str
    sources: list = field(default_factory=list)

def plan(orders, items, bom, as_of='2026-10-29'):
    """Global demand netting by day. Children explode from MAKE planned releases.
    Receipts on the same day are usable; initial stock exists at as_of.
    Gross demand is aggregated per item/day before netting; source allocations
    are documented by stable priority, but not pegged per order in this MVP.
    """
    edges=defaultdict(list)
    for parent, child, per in bom:
        per=Decimal(str(per))
        if per<=0 or child not in items: raise ValueError('invalid BOM')
        edges[parent].append((child,per))
    def check(n,stack):
        if n in stack: raise ValueError('cyclic BOM')
        for c,_ in edges[n]: check(c,stack|{n})
    for o in orders: check(o.product,set())
    demands=defaultdict(lambda:defaultdict(list))
    for o in sorted(orders,key=lambda x:(x.due,-x.priority,x.order_id)):
        if Decimal(str(o.qty))<=0: raise ValueError('order quantity must be positive')
        if date.fromisoformat(o.due)<date.fromisoformat(as_of): raise ValueError('past due order')
        # Finished goods root is assembled to order, so its gross requirement
        # explodes at the assembly release date. Finished goods stock is out of scope.
        if o.product not in items: raise ValueError('missing product')
        root=items[o.product]
        release=(date.fromisoformat(o.due)-timedelta(days=root.lead_days)).isoformat()
        for c,per in edges[o.product]: demands[c][release].append((o.order_id,Decimal(str(o.qty))*per))
    # Process MAKE layers from upper to lower. BOM is acyclic and each node has
    # at most one parent in this MVP; prevent accidental double-counting.
    parents=defaultdict(set)
    for p,children in edges.items():
        for c,_ in children: parents[c].add(p)
    if any(len(v)>1 for v in parents.values()): raise ValueError('multi-parent BOM unsupported in V1')
    depth={}
    def walk(n,d):
        for c,_ in edges[n]:
            depth[c]=d+1; walk(c,d+1)
    for o in orders: walk(o.product,0)
    lines=[]
    for code in sorted(depth,key=lambda x:(depth[x],x)):
        item=items[code]
        if item.kind not in ('BUY','MAKE'): raise ValueError('invalid kind')
        nums=[item.on_hand,item.reserved,item.blocked,item.safety,item.moq,item.lot]
        if any(Decimal(str(n))<0 for n in nums) or item.lot<=0 or item.reserved+item.blocked>item.on_hand or item.lead_days<0:
            raise ValueError('invalid inventory or planning policy')
        supply=defaultdict(Decimal)
        for d,q in item.receipts:
            if Decimal(str(q))<0 or d<as_of: raise ValueError('invalid receipt')
            supply[d]+=Decimal(str(q))
        dates=sorted(set(demands[code])|set(supply))
        opening=item.on_hand-item.reserved-item.blocked
        for d in dates:
            gross=sum((v for _,v in demands[code].get(d,[])),Decimal(0))
            receipt=supply[d]
            net=max(Decimal(0),item.safety-(opening+receipt-gross))
            if net:
                min_order=max(net,item.moq)
                planned=(min_order/item.lot).to_integral_value(rounding='ROUND_CEILING')*item.lot
            else: planned=Decimal(0)
            closing=opening+receipt+planned-gross
            release=(date.fromisoformat(d)-timedelta(days=item.lead_days)).isoformat()
            line=Line(code,d,gross,opening,receipt,net,planned,closing,release,item.kind,sorted(demands[code].get(d,[]),key=lambda z:z[0]))
            lines.append(line)
            if planned and item.kind=='MAKE':
                for child,per in edges[code]: demands[child][release].append((f'PLAN:{code}@{d}',planned*per))
            opening=closing
    # Items with no demand are intentionally not planned for safety-stock replenishment.
    return lines

def as_json(lines):
    from dataclasses import asdict
    return [{k: ([{'source':s,'qty':str(q)} for s,q in v] if k=='sources' else str(v) if isinstance(v,Decimal) else v)
             for k,v in asdict(line).items()} for line in lines]
