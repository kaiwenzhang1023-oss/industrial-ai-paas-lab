"""Effective-dated, RELEASED-only BOM selection for simplified MTO MRP.

Validity is [effective_from, effective_to) (end exclusive). Component
consumption at parent release selects the parent BOM. Each MAKE planned
release selects its own BOM at its own release date. Shared material stock
is netted once across all orders; root products are MTO (not stocked).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from app.domain.timephased import Line

D = lambda x: Decimal(str(x))

@dataclass(frozen=True)
class BOMRevision:
    parent: str
    version: str
    effective_from: str
    effective_to: str | None
    status: str
    components: tuple  # (component_code, qty_per)

@dataclass(frozen=True)
class DemandTrace:
    material: str
    need_date: str
    order_id: str
    gross: Decimal
    parent: str
    bom_version: str
    parent_release: str

@dataclass
class VersionedResult:
    lines: list
    traces: list
    selections: list


def select_revision(parent, on_date, revisions):
    eligible = [r for r in revisions if r.parent == parent and r.status == 'RELEASED'
                and r.effective_from <= on_date
                and (r.effective_to is None or on_date < r.effective_to)]
    if len(eligible) != 1:
        raise ValueError(f'expected exactly one RELEASED BOM for {parent} on {on_date}; got {len(eligible)}')
    return eligible[0]


def validate_revisions(revisions, items):
    grouped = defaultdict(list)
    edges = defaultdict(set)
    for r in revisions:
        if r.parent not in items or not r.version or r.status not in ('DRAFT', 'RELEASED'):
            raise ValueError('invalid BOM header')
        date.fromisoformat(r.effective_from)
        if r.effective_to is not None:
            date.fromisoformat(r.effective_to)
            if r.effective_to <= r.effective_from: raise ValueError('empty BOM interval')
        if not r.components: raise ValueError('empty BOM')
        seen=set()
        for child,per in r.components:
            if child not in items or D(per)<=0 or child==r.parent or child in seen:
                raise ValueError('invalid BOM component')
            seen.add(child)
            if r.status=='RELEASED': edges[r.parent].add(child)
        if r.status=='RELEASED': grouped[r.parent].append(r)
    for parent,rs in grouped.items():
        for i,a in enumerate(rs):
            for b in rs[i+1:]:
                if a.effective_from < (b.effective_to or '9999-12-31') and b.effective_from < (a.effective_to or '9999-12-31'):
                    raise ValueError(f'overlapping RELEASED BOM for {parent}')
    visited=set(); visiting=set()
    def visit(n):
        if n in visiting: raise ValueError('cyclic BOM across versions')
        if n in visited:return
        visiting.add(n)
        for c in edges[n]: visit(c)
        visiting.remove(n);visited.add(n)
    for n in items:visit(n)
    return edges


def plan_versioned(orders, items, revisions, as_of='2026-11-20'):
    edges=validate_revisions(revisions,items)
    roots={o.product for o in orders}
    if any(root not in items for root in roots):raise ValueError('missing root product')
    # Shared component with multiple parents is supported; depth is the maximum
    # topological depth, ensuring every parent is processed before the child.
    depth=defaultdict(int)
    def visit(n,d):
        for c in edges[n]:
            depth[c]=max(depth[c],d+1)
            visit(c,d+1)
    for root in roots:visit(root,0)
    demand=defaultdict(lambda:defaultdict(list))
    traces=[]; selections=[]
    def explode(parent, on_date, qty, oid):
        rev=select_revision(parent,on_date,revisions)
        selections.append({'parent':parent,'need_date':on_date,'version':rev.version,'order_id':oid})
        for child,per in rev.components:
            amount=D(qty)*D(per)
            demand[child][on_date].append((oid,amount))
            traces.append(DemandTrace(child,on_date,oid,amount,parent,rev.version,on_date))
    for o in sorted(orders,key=lambda o:(o.due,-o.priority,o.order_id)):
        if D(o.qty)<=0 or o.due<as_of:raise ValueError('invalid order')
        release=(date.fromisoformat(o.due)-timedelta(days=items[o.product].lead_days)).isoformat()
        if release<as_of:raise ValueError('root release before planning horizon')
        explode(o.product,release,D(o.qty),o.order_id)
    lines=[]
    for code in sorted(depth,key=lambda c:(depth[c],c)):
        item=items[code]
        if item.kind not in ('BUY','MAKE'):raise ValueError('invalid material kind')
        opening=D(item.on_hand)-D(item.reserved)-D(item.blocked)
        if opening<0 or item.lot<=0 or item.lead_days<0:raise ValueError('invalid planning policy')
        supplies=defaultdict(Decimal)
        for day,qty in item.receipts:
            if day<as_of or D(qty)<0:raise ValueError('invalid supply')
            supplies[day]+=D(qty)
        for day in sorted(set(demand[code])|set(supplies)):
            gross=sum((qty for _,qty in demand[code].get(day,[])),Decimal(0))
            receipt=supplies[day]
            net=max(Decimal(0),D(item.safety)-(opening+receipt-gross))
            planned=(max(net,D(item.moq))/D(item.lot)).to_integral_value(rounding=ROUND_CEILING)*D(item.lot) if net else Decimal(0)
            closing=opening+receipt+planned-gross
            release=(date.fromisoformat(day)-timedelta(days=item.lead_days)).isoformat()
            if planned and release<as_of:raise ValueError(f'planned release before horizon: {code} {release}')
            lines.append(Line(code,day,gross,opening,receipt,net,planned,closing,release,item.kind,sorted(demand[code].get(day,[]))))
            if planned and item.kind=='MAKE':
                # Planned lot may exceed net requirement. Attribution to order
                # is intentionally NOT invented; PLAN:<material>@<day> is an
                # auditable supply source, not an order-level peg.
                explode(code,release,planned,f'PLAN:{code}@{day}')
            opening=closing
    return VersionedResult(lines,traces,selections)
