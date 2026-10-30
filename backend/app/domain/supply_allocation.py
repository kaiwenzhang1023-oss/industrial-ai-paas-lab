"""V0.1: deterministic supply-lot allocation with effective BOM and provenance.

Planning attribution only, NOT a WMS reservation. Planned MAKE lots explode in
full exactly once; their downstream requirements retain the plan-lot provenance.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from app.domain.versioned_bom import validate_revisions, select_revision

D = lambda n: Decimal(str(n))

@dataclass(frozen=True)
class Allocation:
    material: str
    need_date: str
    demand_id: str
    root_order: str | None
    gross: Decimal
    supply_kind: str
    supply_id: str
    quantity: Decimal

@dataclass(frozen=True)
class Demand:
    demand_id: str
    material: str
    need_date: str
    qty: Decimal
    root_order: str | None
    priority: int
    parent_plan: str | None
    parent_material: str
    bom_version: str

@dataclass(frozen=True)
class PlanLot:
    plan_id: str
    material: str
    need_date: str
    release_date: str
    quantity: Decimal
    bom_version: str | None

@dataclass
class AllocationResult:
    lines: list
    demands: list
    allocations: list
    plans: list
    selections: list


def plan_supply(orders, items, revisions, as_of='2026-11-20'):
    """Net inventory by day; allocate stock/receipts/plans to each demand.

    Within a day priority is descending then root order ID then demand ID.
    Opening inventory and dated receipts are separate, auditable supply lots.
    Excess planned supply carries to later dates and is never re-exploded.
    """
    date.fromisoformat(as_of)
    edges = validate_revisions(revisions, items)
    order_ids = [o.order_id for o in orders]
    if len(set(order_ids)) != len(order_ids): raise ValueError('duplicate sales order')
    depth = defaultdict(int)
    roots = {o.product for o in orders}
    for root in roots:
        if root not in items: raise ValueError('unknown root')
    def walk(node, d):
        for child in edges[node]:
            depth[child] = max(depth[child], d + 1)
            walk(child, d + 1)
    for root in roots: walk(root, 0)
    demands = defaultdict(list)
    all_demands = []; allocations = []; plans = []; selections = []; lines = []
    seq = 0
    def explode(parent, release, quantity, root_order, priority, parent_plan):
        nonlocal seq
        rev = select_revision(parent, release, revisions)
        selections.append((parent, release, rev.version, parent_plan or root_order))
        for child, per in rev.components:
            seq += 1
            record = Demand(f'D{seq:06}', child, release, D(quantity)*D(per), root_order,
                            priority, parent_plan, parent, rev.version)
            demands[child].append(record)
            all_demands.append(record)
        return rev.version
    for o in sorted(orders, key=lambda x:(x.due, -x.priority, x.order_id)):
        if D(o.qty)<=0 or o.due < as_of: raise ValueError('invalid order')
        release=(date.fromisoformat(o.due)-timedelta(days=items[o.product].lead_days)).isoformat()
        if release<as_of: raise ValueError('root release before horizon')
        explode(o.product, release, o.qty, o.order_id, o.priority, None)
    for material in sorted(depth, key=lambda m:(depth[m],m)):
        item = items[material]
        if item.kind not in ('MAKE','BUY'): raise ValueError('invalid item kind')
        if item.lead_days<0 or any(D(x)<0 for x in (item.on_hand,item.reserved,item.blocked,item.safety,item.moq)) or D(item.lot)<=0 or D(item.reserved)+D(item.blocked)>D(item.on_hand):
            raise ValueError('invalid inventory or policy')
        # Pools are consumed in chronological receipt order; never future stock.
        pools=[]
        initial=D(item.on_hand)-D(item.reserved)-D(item.blocked)
        if initial: pools.append(['STOCK',f'STOCK:{material}@{as_of}',initial])
        incoming=defaultdict(list)
        for index,(day,qty) in enumerate(item.receipts, start=1):
            date.fromisoformat(day)
            if day<as_of or D(qty)<0: raise ValueError('invalid receipt')
            if D(qty):
                # Each upstream receipt row has a distinct, stable identity.
                incoming[day].append((f'RECEIPT:{material}:{index:06}@{day}',D(qty)))
        days=sorted(set(incoming)|{d.need_date for d in demands[material]})
        for day in days:
            for receipt_id,receipt_qty in incoming.get(day,[]):
                pools.append(['RECEIPT',receipt_id,receipt_qty])
            todays=sorted((d for d in demands[material] if d.need_date==day),
                          key=lambda d:(-d.priority, d.root_order or '',d.demand_id))
            gross=sum((d.qty for d in todays),Decimal(0))
            before=sum((p[2] for p in pools),Decimal(0))
            short=max(Decimal(0),gross+D(item.safety)-before) if todays else Decimal(0)
            planned=Decimal(0)
            if short:
                planned=(max(short,D(item.moq))/D(item.lot)).to_integral_value(rounding=ROUND_CEILING)*D(item.lot)
            release=(date.fromisoformat(day)-timedelta(days=item.lead_days)).isoformat()
            plan_id=None
            if planned:
                if release<as_of: raise ValueError(f'planned release before horizon: {material} {release}')
                plan_id=f'PLAN:{material}@{day}'
                pools.append(['PLAN',plan_id,planned])
            for demand in todays:
                left=demand.qty
                for pool in pools:
                    if not left: break
                    taken=min(left,pool[2]); pool[2]-=taken; left-=taken
                    if taken:
                        allocations.append(Allocation(material,day,demand.demand_id,demand.root_order,
                                                      demand.qty,pool[0],pool[1],taken))
                if left: raise AssertionError('unallocated demand')
            closing=sum((p[2] for p in pools),Decimal(0))
            lines.append({'material':material,'need_date':day,'gross':gross,'opening_supply':before,
                          'net':short,'planned':planned,'closing_supply':closing,'release_date':release if planned else None})
            if planned:
                version=None
                if item.kind=='MAKE':
                    # Complete lot, including MOQ excess, is required for component procurement.
                    # Downstream root attribution is NOT fabricated; it points to plan_id.
                    version=explode(material,release,planned,None,0,plan_id)
                plans.append(PlanLot(plan_id,material,day,release,planned,version))
    # Demand-level conservation, including multiple sources for one demand.
    grouped=defaultdict(Decimal)
    for a in allocations: grouped[a.demand_id]+=a.quantity
    for d in all_demands:
        if grouped[d.demand_id]!=d.qty: raise AssertionError(f'peg mismatch {d.demand_id}')
    return AllocationResult(lines,all_demands,allocations,plans,selections)
