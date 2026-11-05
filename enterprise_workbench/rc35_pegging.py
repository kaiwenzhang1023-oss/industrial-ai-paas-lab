"""Read-only reconciliation of persisted MRP demand allocations.

Order-level pegs are evidence of allocation, not evidence of physical supply.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

def number(value):
    try:
        n=Decimal(str(value))
        if not n.is_finite():raise ValueError('NON_FINITE')
        return n
    except (ValueError, InvalidOperation, TypeError):
        raise ValueError('INVALID_ALLOCATION_QUANTITY') from None

def trace_bom_lineage(snapshot, pegs):
    """Check that each persisted order-material assignment belongs to that
    order's frozen BOM ancestry. This proves structural lineage only, not
    supplier receipts, finite-capacity production or physical execution.
    """
    if not isinstance(snapshot, dict):
        raise ValueError('INVALID_SNAPSHOT')
    orders = snapshot.get('orders')
    bom = snapshot.get('bom')
    if not isinstance(orders,list) or not isinstance(bom,list) or len(bom)>20000:
        raise ValueError('INVALID_SNAPSHOT')
    roots={}
    for o in orders:
        oid=str(o['order_id'])
        if oid in roots:raise ValueError('DUPLICATE_ORDER')
        roots[oid]=str(o['product'])
    children=defaultdict(list)
    parents=defaultdict(set)
    for edge in bom:
        if not isinstance(edge,(list,tuple)) or len(edge)!=3:raise ValueError('INVALID_BOM_EDGE')
        parent,child,qty=edge
        parent,child=str(parent),str(child)
        if number(qty)<=0:raise ValueError('INVALID_BOM_QUANTITY')
        if parent==child:raise ValueError('CYCLIC_BOM')
        if child in parents and parent in parents[child]:raise ValueError('DUPLICATE_BOM_EDGE')
        parents[child].add(parent)
        children[parent].append(child)
    if any(len(ps)>1 for ps in parents.values()):raise ValueError('MULTI_PARENT_BOM_UNSUPPORTED')
    paths={}
    def walk(order,node,path):
        if node in path:raise ValueError('CYCLIC_BOM')
        branch=path+(node,)
        for child in children[node]:
            key=(order,child)
            if key in paths:raise ValueError('AMBIGUOUS_BOM_LINEAGE')
            paths[key]=list(branch+(child,))
            walk(order,child,branch)
    for oid,root in roots.items():walk(oid,root,())
    invalid=[]
    checks=[]
    seen=set()
    for peg in pegs:
        oid=str(peg['order_id']); material=str(peg['material'])
        key=(oid,material)
        if key not in seen:
            seen.add(key)
            path=paths.get(key)
            if not path:
                invalid.append({'order_id':oid,'material':material,'reason':'MISSING_ORDER_BOM_PATH'})
            else:
                checks.append({'order_id':oid,'material':material,'path':path,
                               'level':len(path)-1,'scope':'FROZEN_BOM_ANCESTRY'})
    return {'status':'PASS' if not invalid else 'MISMATCH',
            'paths':checks,'differences':invalid,
            'bom_lineage_verified':not invalid,
            'physical_supply_trace_verified':False}

def reconcile(lines, pegs, snapshot=None):
    if not isinstance(lines,list) or not isinstance(pegs,list) or len(lines)>20000 or len(pegs)>100000:
        raise ValueError('INVALID_ALLOCATION_INPUT')
    demand=defaultdict(Decimal)
    attributed=defaultdict(Decimal)
    seen=set()
    orders=defaultdict(lambda:defaultdict(Decimal))
    for row in lines:
        key=(str(row['material']),str(row['date']))
        if key in seen:raise ValueError('DUPLICATE_MRP_LINE')
        seen.add(key)
        demand[key]+=number(row['gross'])
    for row in pegs:
        key=(str(row['material']),str(row['date']))
        if key not in seen:raise ValueError('PEG_WITHOUT_MRP_LINE')
        gross=number(row['gross'])
        allocated=sum((number(row[k]) for k in ('from_stock','from_receipts','from_planned')),Decimal(0))
        if gross<0 or allocated<0 or gross!=allocated or any(number(row[k])<0 for k in ('from_stock','from_receipts','from_planned')):
            raise ValueError('INVALID_PEG_ALLOCATION')
        attributed[key]+=gross
        order=str(row['order_id'])
        orders[order]['gross']+=gross
        orders[order]['stock']+=number(row['from_stock'])
        orders[order]['receipts']+=number(row['from_receipts'])
        orders[order]['planned_unconfirmed']+=number(row['from_planned'])
    differences=[{'material':m,'date':d,'line_gross':str(g),'pegged_gross':str(attributed[m,d]),'difference':str(g-attributed[m,d])} for (m,d),g in sorted(demand.items()) if g!=attributed[m,d]]
    lineage=trace_bom_lineage(snapshot,pegs) if snapshot is not None else None
    return {'status':'PASS' if not differences and (lineage is None or lineage['status']=='PASS') else 'MISMATCH','line_count':len(lines),'peg_count':len(pegs),
        'differences':differences,'orders':[{'order_id':o,**{k:str(v) for k,v in fields.items()}} for o,fields in sorted(orders.items())],
        'scope':'PERSISTED_ALLOCATION_RECONCILIATION','physical_receipt_confirmed':False,
        'cross_level_chain_verified':False, 'bom_lineage':lineage}
