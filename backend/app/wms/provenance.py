"""Deterministic, *planning-only* attribution of aggregated STOCK usage to WMS rows.

Not an ATP promise, WMS reservation, physical pick or cross-warehouse feasibility proof.
"""
from decimal import Decimal


def allocate_stock_evidence(balances, pegging):
    """Return serializable, conserved lot-level evidence for STOCK allocations.

    Input balances are an as-read DB snapshot; callers must hold the same transaction
    snapshot used for MRP. Sort by warehouse/lot to make provenance deterministic.
    """
    pools = {}
    versions = {}
    for r in sorted(balances, key=lambda x: (x[0], x[1], x[2])):
        material, warehouse, lot, on_hand, reserved, blocked, snapshot_at, version = r
        available = Decimal(on_hand) - Decimal(reserved) - Decimal(blocked)
        if available < 0:
            raise ValueError('WMS_NEGATIVE_AVAILABLE')
        key = (str(material), str(warehouse), str(lot))
        if key in versions:
            raise ValueError('WMS_DUPLICATE_SOURCE')
        versions[key] = int(version)
        pools.setdefault(str(material), []).append([key, available, str(snapshot_at)])
    evidence = []
    for alloc in pegging['order_allocations']:
        if alloc['supply_kind'] != 'STOCK':
            continue
        material = str(alloc['material'])
        left = Decimal(str(alloc['allocated_qty']))
        for entry in pools.get(material, []):
            if left == 0:
                break
            key, available, snapshot_at = entry
            taken = min(left, available)
            if taken:
                evidence.append({'demand_id': alloc['demand_id'],
                    'supply_id': alloc['supply_id'], 'material_id': material,
                    'root_order_id': alloc.get('order_id'),
                    'warehouse_id': key[1], 'lot_id': key[2],
                    'allocated_qty': str(taken), 'source_version': versions[key],
                    'source_snapshot_at': snapshot_at,
                    'attribution_type': 'SIMULATED_PLANNING_ALLOCATION'})
                entry[1] -= taken
                left -= taken
        if left:
            raise ValueError('WMS_STOCK_PROVENANCE_INSUFFICIENT')
    by_demand = {}
    for row in evidence:
        k = (row['demand_id'], row['supply_id'])
        by_demand[k] = by_demand.get(k, Decimal(0)) + Decimal(row['allocated_qty'])
    for alloc in pegging['order_allocations']:
        if alloc['supply_kind'] == 'STOCK':
            k = (alloc['demand_id'], alloc['supply_id'])
            if by_demand.get(k, Decimal(0)) != Decimal(str(alloc['allocated_qty'])):
                raise AssertionError('WMS_STOCK_ATTRIBUTION_CONSERVATION')
    return evidence
