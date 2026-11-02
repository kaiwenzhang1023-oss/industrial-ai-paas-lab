"""M2-02-04: auditable supply provenance and cross-layer plan genealogy.

This is *planning* pegging, not a physical reservation. A MAKE lot is
exploded once in full; downstream demand belongs to that lot, not to an
arbitrarily selected sales order. All quantities use Decimal.
"""
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal

ZERO = Decimal(0)


def build_pegging_report(result, items, as_of='2026-11-20'):
    demands = {d.demand_id: d for d in result.demands}
    plans = {p.plan_id: p for p in result.plans}
    if len(demands) != len(result.demands) or len(plans) != len(result.plans):
        raise ValueError('duplicate demand or plan identifier')
    allocated = defaultdict(lambda: ZERO)
    by_supply = defaultdict(lambda: ZERO)
    supply_meta = {}
    order_rows = []
    for a in result.allocations:
        d = demands.get(a.demand_id)
        if d is None or a.material != d.material or a.need_date != d.need_date or a.root_order != d.root_order:
            raise ValueError('allocation/demand provenance mismatch')
        if a.quantity <= 0 or a.supply_kind not in ('STOCK','RECEIPT','PLAN'):
            raise ValueError('invalid allocation quantity or kind')
        if a.supply_kind == 'PLAN':
            p = plans.get(a.supply_id)
            if p is None or p.material != a.material or p.need_date > a.need_date:
                raise ValueError('invalid or future plan lot')
        elif a.supply_kind == 'STOCK':
            if a.supply_id != f'STOCK:{a.material}@{as_of}':
                raise ValueError('unknown stock lot')
        else:
            if not a.supply_id.startswith(f'RECEIPT:{a.material}:'):
                raise ValueError('invalid receipt provenance')
            receipt_day = a.supply_id.rsplit('@',1)[-1]
            if receipt_day > a.need_date:
                raise ValueError('future receipt allocated')
        key=(a.material,a.supply_kind,a.supply_id)
        allocated[a.demand_id] += a.quantity
        by_supply[key] += a.quantity
        supply_meta[key] = (a.material,a.supply_kind,a.supply_id)
        order_rows.append({'demand_id':a.demand_id,'order_id':a.root_order,
                           'material':a.material,'need_date':a.need_date,
                           'parent_plan':d.parent_plan,'parent_material':d.parent_material,
                           'bom_version':d.bom_version,'supply_kind':a.supply_kind,
                           'supply_id':a.supply_id,'allocated_qty':a.quantity})
    for d in result.demands:
        if allocated[d.demand_id] != d.qty:
            raise ValueError(f'demand conservation failed: {d.demand_id}')
        if d.parent_plan is not None and d.parent_plan not in plans:
            raise ValueError('orphaned child demand')
        if d.parent_plan is not None and d.root_order is not None:
            raise ValueError('fabricated order ownership on plan-child demand')

    # Receipt identity is an indexed source-row identity. Verify uniqueness
    # and source capacity against the original unaggregated receipt rows.
    capacity={}
    for material,item in items.items():
        opening=Decimal(str(item.on_hand))-Decimal(str(item.reserved))-Decimal(str(item.blocked))
        if opening < 0: raise ValueError('negative available inventory')
        capacity[(material,'STOCK',f'STOCK:{material}@{as_of}')]=opening
        for index,(day,qty) in enumerate(item.receipts,1):
            capacity[(material,'RECEIPT',f'RECEIPT:{material}:{index:06}@{day}')]=Decimal(str(qty))
    for p in result.plans:
        capacity[(p.material,'PLAN',p.plan_id)]=p.quantity
    for key,used in by_supply.items():
        if key not in capacity or used > capacity[key]:
            raise ValueError(f'supply conservation failed: {key}')
    supply_rows=[]
    for key in sorted(capacity):
        total=capacity[key];used=by_supply[key]
        if total < 0 or used < 0 or used > total:raise ValueError('invalid supply ledger')
        material,kind,source_id=key
        supply_rows.append({'material':material,'kind':kind,'source_id':source_id,
                            'capacity':total,'allocated':used,'remaining':total-used})

    # Link root order -> demand -> supply lot -> plan -> child demands.
    # This is a graph, not a proportional re-attribution of MAKE BOM costs.
    plan_children=defaultdict(list)
    for d in result.demands:
        if d.parent_plan:
            plan_children[d.parent_plan].append(d.demand_id)
    edges=[]
    for p in result.plans:
        for did in sorted(plan_children[p.plan_id]):
            d=demands[did]
            edges.append({'parent_plan_id':p.plan_id,'parent_material':p.material,
                          'plan_quantity':p.quantity,'plan_release_date':p.release_date,
                          'parent_bom_version':p.bom_version,'child_demand_id':did,
                          'child_material':d.material,'child_gross':d.qty,
                          'child_need_date':d.need_date})
    return {'order_allocations':order_rows,'supply_ledger':supply_rows,
            'plan_child_edges':edges,'demands':len(demands),
            'plans':len(plans),'conservation_passed':True,
            'attribution_policy':'plan_lot_genealogy_no_proportional_order_assignment'}


def report_as_jsonable(report):
    """Convert Decimal without float precision loss."""
    def convert(x):
        if isinstance(x,Decimal):return str(x)
        if isinstance(x,list):return [convert(y) for y in x]
        if isinstance(x,dict):return {k:convert(v) for k,v in x.items()}
        return x
    return convert(report)
