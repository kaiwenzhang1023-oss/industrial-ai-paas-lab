"""RC3.5 read-only time-phased plan explanation and exception classification.

A positive MRP `net` is a replenishment requirement, not a stock-out.
Planned receipts are proposals, not confirmed receipts. This module never
claims finite-capacity feasibility or real supplier commitment.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


def dec(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('INVALID_MRP_NUMBER') from None
    if not n.is_finite():
        raise ValueError('INVALID_MRP_NUMBER')
    return n


def bucket_date(iso, granularity):
    day = date.fromisoformat(iso)
    if granularity == 'day':
        return day.isoformat()
    if granularity == 'week':
        return (day - timedelta(days=day.weekday())).isoformat()
    raise ValueError('INVALID_BUCKET_GRANULARITY')


def analyze(snapshot, lines, granularity='week', long_lead_days=14):
    """Derive day/week aggregates and order attribution from trusted PG snapshot.

    `sources` are source allocations, not a guaranteed end-to-end Pegging chain.
    Rows are netted globally and aggregated without adding opening balances.
    """
    if granularity not in ('day', 'week'):
        raise ValueError('INVALID_BUCKET_GRANULARITY')
    if not isinstance(snapshot, dict) or not isinstance(lines, list) or len(lines)>20000:
        raise ValueError('INVALID_MRP_INPUT')
    items = snapshot.get('items') or {}
    orders = {str(o['order_id']):o for o in snapshot.get('orders', [])}
    groups = defaultdict(lambda: {'gross':Decimal(0),'net':Decimal(0),
       'planned':Decimal(0),'confirmed_receipts':Decimal(0), 'sources':defaultdict(Decimal),
       'unconfirmed_shortfall':Decimal(0), 'lead_days':0,'kind':'', 'release_before_as_of':False})
    as_of = str(snapshot.get('as_of',''))
    for row in lines:
        material = str(row['material'])
        day = str(row['date'])
        key = (material,bucket_date(day,granularity))
        g = groups[key]
        item = items.get(material) or {}
        g['lead_days'] = int(item.get('lead_days',0))
        g['kind'] = str(item.get('kind',row.get('kind','')))
        for field in ('gross','net','planned'):
            g[field] += dec(row.get(field,0))
        g['confirmed_receipts'] += dec(row.get('receipts',0))
        for source in row.get('sources',[]):
            g['sources'][str(source['source'])] += dec(source['qty'])
        # This is a planning feasibility warning, NOT confirmed actual shortage.
        if dec(row.get('net',0))>0 and str(row.get('release','')) < as_of:
            g['release_before_as_of']=True
            g['unconfirmed_shortfall'] += dec(row['net'])
    result=[]
    for (material,day), g in sorted(groups.items()):
        related=[]
        for source,qty in sorted(g['sources'].items()):
            order=orders.get(source)
            related.append({'source':source,'qty':str(qty),
              'order_id':source if order else None,
              'order_due':str(order['due']) if order else None,
              'source_kind':'ORDER' if order else 'PLANNED_UPSTREAM'})
        if g['release_before_as_of']:
            severity='BLOCK'
            explanation='补货建议的计划释放日早于快照日期，存在无法按标准提前期执行的风险'
        elif g['net']>0 and g['lead_days']>=long_lead_days:
            severity='RISK'
            explanation='长交期物料需要计划补充，尚无供应商确认到货证据'
        elif g['net']>0:
            severity='REPLENISHMENT'
            explanation='存在净补货需求；不能据此认定实际缺料或停工'
        else:
            severity='COVERED'
            explanation='该时间桶无需新增净补货；不代表产能或供应履约已确认'
        result.append({'material':material,'bucket':day,'granularity':granularity,
            'gross':str(g['gross']),'net_replenishment':str(g['net']),
            'planned_receipts_unconfirmed':str(g['planned']),
            'confirmed_receipts':str(g['confirmed_receipts']),
            'lead_days':g['lead_days'],'lead_class':'LONG' if g['lead_days']>=long_lead_days else 'SHORT',
            'severity':severity,'reason':explanation,'source_allocations':related,
            'release_overdue_net':str(g['unconfirmed_shortfall'])})
    return {'granularity':granularity,'rows':result,'row_count':len(result),
      'semantics':{'net':'NET_REPLENISHMENT_NOT_SHORTAGE',
       'planned':'UNCONFIRMED_PLANNED_RECEIPT',
       'sources':'SOURCE_ALLOCATION_NOT_FULL_PEGGING',
       'capacity':'INFINITE_CAPACITY_NOT_MES_SCHEDULE'}}
