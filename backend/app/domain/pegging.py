"""Deterministic order-level supply pegging for the restricted V1 single-parent BOM.

Allocation order: need date ASC, priority DESC, order ID ASC. Earlier dated
receipts cannot satisfy earlier demand; excess planned lots carry forward.
This is a planning attribution, not WMS physical reservations.
"""
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from app.domain.timephased import plan

D = lambda x: Decimal(str(x))

@dataclass(frozen=True)
class Peg:
    material: str
    need_date: str
    order_id: str
    gross: Decimal
    from_stock: Decimal
    from_receipts: Decimal
    from_planned: Decimal
    planned_excess: Decimal = Decimal(0)


def allocate(orders, items, bom, as_of='2026-10-29'):
    """Return (daily MRP lines, order-level pegs).

    Supply allocations are per-demand, whereas planned orders are generated
    from the daily aggregate net requirements of the baseline engine.
    """
    lines = plan(orders, items, bom, as_of)
    by_material = defaultdict(list)
    for line in lines:
        by_material[line.material].append(line)
    roots = {o.order_id: o for o in orders}
    children = defaultdict(list)
    for parent, child, per in bom:
        children[parent].append((child,D(per)))
    # Build root demand then propagate MAKE planned-order attribution to children.
    demands = defaultdict(list)
    for o in orders:
        release = (date.fromisoformat(o.due)-timedelta(days=items[o.product].lead_days)).isoformat()
        for child, per in children[o.product]:
            demands[child].append((release,o.order_id,D(o.qty)*per))
    pegs=[]
    # Material processing order follows the baseline engine's topological order.
    seen=[]
    for line in lines:
        if line.material not in seen: seen.append(line.material)
    for material in seen:
        item=items[material]
        events=sorted(demands[material],key=lambda e:(e[0],-roots[e[1]].priority,e[1]))
        # Chronological supply pools; planned receipts are introduced only after
        # stock/confirmed receipts are allocated to each day's demands.
        stock=D(item.on_hand)-D(item.reserved)-D(item.blocked)
        confirmed=defaultdict(Decimal)
        for d,q in item.receipts: confirmed[d]+=D(q)
        confirmed_pool=Decimal(0)
        planned_pool=Decimal(0)
        planned_origin=defaultdict(Decimal)
        dates=sorted(set(e[0] for e in events)|set(confirmed)|{l.date for l in by_material[material]})
        for day in dates:
            confirmed_pool+=confirmed[day]
            daily=sorted((e for e in events if e[0]==day),key=lambda e:(-roots[e[1]].priority,e[1]))
            line=next((l for l in by_material[material] if l.date==day),None)
            if line and line.planned:
                planned_pool+=D(line.planned)
            for _,oid,qty in daily:
                remaining=qty
                from_stock=min(remaining,stock);stock-=from_stock;remaining-=from_stock
                from_receipts=min(remaining,confirmed_pool);confirmed_pool-=from_receipts;remaining-=from_receipts
                from_planned=min(remaining,planned_pool);planned_pool-=from_planned;remaining-=from_planned
                if remaining: raise AssertionError('MRP supply allocation deficit')
                pegs.append(Peg(material,day,oid,qty,from_stock,from_receipts,from_planned))
                if item.kind=='MAKE' and from_planned:
                    planned_origin[(day,oid)]+=from_planned
            if item.kind=='MAKE':
                # The baseline MRP explodes the FULL planned MAKE lot, including
                # surplus from MOQ / lot rounding. Attribute that surplus to the
                # last demand that caused the lot, while keeping surplus separate
                # from customer gross-demand pegs. This is planning attribution,
                # not a physical reservation of surplus finished components.
                if line and line.planned and daily:
                    attributed=sum((q for (d,_),q in planned_origin.items() if d==day), Decimal(0))
                    excess=D(line.planned)-attributed
                    if excess < 0: raise AssertionError('planned attribution exceeds lot')
                    if excess:
                        planned_origin[(day,daily[-1][1])]+=excess
                for (d,oid),qty in list(planned_origin.items()):
                    if d==day:
                        release=(date.fromisoformat(day)-timedelta(days=item.lead_days)).isoformat()
                        for child,per in children[material]: demands[child].append((release,oid,qty*per))
    return lines, pegs


def pegs_json(pegs):
    return [{k:(str(v) if isinstance(v,Decimal) else v) for k,v in asdict(p).items()} for p in pegs]
