"""M2-02-05: unified, deterministic acceptance runner for versioned MRP.

This is an in-memory business acceptance path, NOT database integration.
"""
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json
from app.domain.supply_allocation import plan_supply
from app.domain.pegging_report import build_pegging_report, report_as_jsonable


def run_acceptance(orders, items, revisions, as_of='2026-11-20'):
    result = plan_supply(orders, items, revisions, as_of)
    report = build_pegging_report(result, items, as_of)
    # Assert both demand and source capacity conservation in one business gate.
    used = defaultdict(lambda: Decimal(0))
    for row in report['order_allocations']:
        used[row['demand_id']] += row['allocated_qty']
    for demand in result.demands:
        if used[demand.demand_id] != demand.qty:
            raise AssertionError('demand conservation')
    for row in report['supply_ledger']:
        if row['capacity'] != row['allocated'] + row['remaining']:
            raise AssertionError('supply conservation')
    if any(row['remaining'] < 0 for row in report['supply_ledger']):
        raise AssertionError('negative remaining')
    payload = report_as_jsonable({
        'as_of': as_of,
        'orders': [dict(order_id=o.order_id, product=o.product, qty=str(o.qty),
                        due=o.due, priority=o.priority) for o in orders],
        'mrp_lines': result.lines,
        'plan_lots': [vars(p) for p in result.plans],
        'bom_selections': [dict(parent=p, release_date=d, version=v, provenance=source)
                           for p,d,v,source in result.selections],
        'pegging': report,
        'simulation': True,
        'storage': 'in_memory',
        'engine': 'effective_bom_supply_allocation_v1',
    })
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    payload['result_hash'] = sha256(canonical.encode()).hexdigest()
    return payload
