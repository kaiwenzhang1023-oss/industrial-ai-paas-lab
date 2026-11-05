"""Version B RC4: bounded, side-effect-free what-if and live RC8 JS comparison.

The trusted Version A source is the frozen unmodified RC8 engine. The result
is *never* obtained from browser-submitted values or the Version B planner.
"""
from __future__ import annotations
import copy
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from app.domain.timephased import Item, Order, as_json, plan
from g3.core import (ADAPTER, ENGINE, IncompatibleSnapshot, compare,
                     digest_file, load_reference, snapshot_hash)


class PolicyRejected(ValueError):
    pass


@dataclass(frozen=True)
class Change:
    kind: Literal['receipt', 'stock', 'due']
    target: str
    quantity: str | None = None
    date: str | None = None


def _qty(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise PolicyRejected('INVALID_DECIMAL_QUANTITY') from None
    if not d.is_finite() or d < 0 or d > Decimal('100000000'):
        raise PolicyRejected('QUANTITY_OUT_OF_RANGE')
    return d


def _make_models(snapshot):
    items = {}
    for name, value in snapshot['items'].items():
        items[name] = Item(
            code=name, kind=value['kind'], lead_days=int(value['lead_days']),
            on_hand=_qty(value['on_hand']), reserved=_qty(value['reserved']),
            blocked=_qty(value['blocked']), safety=_qty(value['safety']),
            moq=_qty(value['moq']), lot=_qty(value['lot']),
            receipts=tuple((day, _qty(qty)) for day, qty in value['receipts'])
        )
    orders = [Order(order_id=o['order_id'], product=o['product'],
                    qty=_qty(o['qty']), due=o['due'], priority=int(o['priority']))
              for o in snapshot['orders']]
    return orders, items, snapshot['bom']


def what_if(snapshot, change: Change):
    """Compute two immutable plans; never writes database or changes approval."""
    if change.kind not in ('receipt', 'stock', 'due'):
        raise PolicyRejected('UNSUPPORTED_WHAT_IF_KIND')
    before = copy.deepcopy(snapshot)
    after = copy.deepcopy(snapshot)
    if change.kind in ('stock', 'receipt'):
        if change.target not in after['items']:
            raise PolicyRejected('UNKNOWN_MATERIAL')
        quantity = _qty(change.quantity)
        item = after['items'][change.target]
        if change.kind == 'stock':
            if quantity < _qty(item['reserved']) + _qty(item['blocked']):
                raise PolicyRejected('STOCK_BELOW_RESERVED_AND_BLOCKED')
            item['on_hand'] = str(quantity)
        else:
            from datetime import date
            try:
                d = date.fromisoformat(str(change.date))
                asof = date.fromisoformat(str(snapshot['as_of']))
            except ValueError:
                raise PolicyRejected('INVALID_RECEIPT_DATE') from None
            if d < asof:
                raise PolicyRejected('RECEIPT_BEFORE_AS_OF')
            item['receipts'].append([d.isoformat(), str(quantity)])
    else:
        from datetime import date
        try:
            day = date.fromisoformat(str(change.date))
            asof = date.fromisoformat(str(snapshot['as_of']))
        except ValueError:
            raise PolicyRejected('INVALID_DUE_DATE') from None
        if day < asof:
            raise PolicyRejected('DUE_BEFORE_AS_OF')
        target = next((o for o in after['orders'] if o['order_id'] == change.target), None)
        if target is None:
            raise PolicyRejected('UNKNOWN_ORDER')
        target['due'] = day.isoformat()
    try:
        a_o, a_i, a_b = _make_models(before)
        b_o, b_i, b_b = _make_models(after)
        baseline = as_json(plan(a_o, a_i, a_b, before['as_of']))
        candidate = as_json(plan(b_o, b_i, b_b, after['as_of']))
    except (ValueError, KeyError, TypeError) as exc:
        raise PolicyRejected('PLANNER_POLICY_REJECTED') from exc
    # Reuse independent comparison's field attribution; both here are B planner
    # what-if branches, never mislabel this as a cross-engine A/B proof.
    metrics = {}
    for label, rows in (('baseline', baseline), ('candidate', candidate)):
        metrics[label] = {'lines': len(rows), **{k: str(sum(Decimal(r[k]) for r in rows))
                             for k in ('gross', 'net', 'planned')}}
    delta = {k: str(Decimal(metrics['candidate'][k]) - Decimal(metrics['baseline'][k]))
             for k in ('gross', 'net', 'planned')}
    return {
        'simulation': True, 'external_execution': False,
        'side_effect': 'NONE', 'source': 'PERSISTED_RUN_SNAPSHOT_COPY',
        'baseline_snapshot_sha256': snapshot_hash(before),
        'candidate_snapshot_sha256': snapshot_hash(after),
        'change': {'kind': change.kind, 'target': change.target,
                   'quantity': change.quantity, 'date': change.date},
        'baseline': metrics['baseline'], 'candidate': metrics['candidate'],
        'delta': delta, 'changed': any(Decimal(v) != 0 for v in delta.values()),
    }


def native_a_live(snapshot, *, node_executable=None, timeout_seconds=8):
    """Execute the frozen A engine in a trusted subprocess. No B-engine fallback.

    Runtime is optional in production, mandatory to claim DYNAMIC_NATIVE_A.
    """
    reference = load_reference()  # fail closed on source/adapter drift
    if reference['source_engine_sha256'] != digest_file(ENGINE):
        raise RuntimeError('FROZEN_A_ENGINE_HASH_MISMATCH')
    if reference['source_adapter_sha256'] != digest_file(ADAPTER):
        raise RuntimeError('FROZEN_A_ADAPTER_HASH_MISMATCH')
    raw = json.dumps(snapshot, default=str, sort_keys=True, ensure_ascii=False)
    if len(raw.encode('utf-8')) > 800000:
        raise PolicyRejected('SNAPSHOT_SIZE_LIMIT')
    node = node_executable or shutil.which('node')
    if not node or not Path(node).is_file():
        raise RuntimeError('NODE_RUNTIME_UNAVAILABLE')
    try:
        proc = subprocess.run([str(node), str(ADAPTER)], input=raw,
                   capture_output=True, text=True, encoding='utf-8',
                   timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('NATIVE_A_PROCESS_FAILED') from None
    if proc.returncode != 0 or len(proc.stdout) > 4000000:
        raise IncompatibleSnapshot('NATIVE_A_POLICY_INCOMPATIBLE')
    try:
        response = json.loads(proc.stdout)
        if response['engine'] != 'VERSION_A_RC8_NATIVE_JS_PLAN_BUCKETS':
            raise ValueError('ENGINE_PROVENANCE_MISMATCH')
        lines = response['lines']
        if not isinstance(lines, list) or len(lines) > 20000:
            raise ValueError('INVALID_NATIVE_A_RESULT')
    except (ValueError, KeyError, TypeError):
        raise RuntimeError('NATIVE_A_INVALID_OUTPUT') from None
    return lines


def dynamic_comparison(snapshot, persisted_run, *, node_executable=None):
    lines = native_a_live(snapshot, node_executable=node_executable)
    result = compare(lines, persisted_run['lines'])
    result.update({
        'comparison_mode': 'LIVE_NATIVE_VERSION_A_RC8_JS_VS_PERSISTED_B_PG16',
        'a_engine_sha256': digest_file(ENGINE),
        'a_adapter_sha256': digest_file(ADAPTER),
        'a_input_hash': snapshot_hash(snapshot),
        'b_input_hash': snapshot_hash(snapshot),
        'independent_a_execution_this_request': True,
        'verified_reference': False,  # dynamic, not pinned seed reference
        'a_result_untrusted': False,
        'b_source': 'PERSISTED_POSTGRESQL',
        'external_execution': False,
    })
    return result
