"""V1.3 Batch A: deterministic, planning-only MES simulation.

No ERP/MRP/WMS writes, no machine control. Time units are decimal hours.
Work centers use daily buckets, no calendar/shift assumptions beyond supplied capacity.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json


def dec(value):
    v = Decimal(str(value))
    if not v.is_finite():
        raise ValueError('NON_FINITE_QUANTITY')
    return v


class Status(str, Enum):
    PLANNED = 'PLANNED'
    RELEASED = 'RELEASED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


ALLOWED = {
    Status.PLANNED: {Status.RELEASED, Status.CANCELLED},
    Status.RELEASED: {Status.IN_PROGRESS, Status.CANCELLED},
    Status.IN_PROGRESS: {Status.COMPLETED},
    Status.COMPLETED: set(),
    Status.CANCELLED: set(),
}


@dataclass(frozen=True)
class Operation:
    operation_id: str
    sequence: int
    work_center: str
    setup_hours: Decimal
    hours_per_unit: Decimal

    def __post_init__(self):
        if not self.operation_id or not self.work_center or self.sequence < 1:
            raise ValueError('INVALID_OPERATION')
        if dec(self.setup_hours) < 0 or dec(self.hours_per_unit) <= 0:
            raise ValueError('INVALID_STANDARD_TIME')


@dataclass(frozen=True)
class Routing:
    product_id: str
    version: str
    operations: tuple[Operation, ...]

    def __post_init__(self):
        seq = [x.sequence for x in self.operations]
        ids = [x.operation_id for x in self.operations]
        if not self.product_id or not self.version or not seq or len(seq) != len(set(seq)) or len(ids) != len(set(ids)):
            raise ValueError('INVALID_ROUTING')
        if seq != sorted(seq):
            raise ValueError('ROUTING_SEQUENCE_NOT_SORTED')


@dataclass(frozen=True)
class WorkOrderSpec:
    work_order_id: str
    source_run_id: str
    source_plan_id: str
    source_result_hash: str
    product_id: str
    quantity: Decimal
    due_date: str
    routing_version: str

    def __post_init__(self):
        date.fromisoformat(self.due_date)
        if not all((self.work_order_id,self.source_run_id,self.source_plan_id,self.source_result_hash,self.product_id,self.routing_version)) or dec(self.quantity) <= 0:
            raise ValueError('INVALID_WORK_ORDER')


@dataclass(frozen=True)
class Feedback:
    event_id: str
    operation_id: str
    good_qty: Decimal
    scrap_qty: Decimal
    event_date: str

    def __post_init__(self):
        date.fromisoformat(self.event_date)
        if not self.event_id or not self.operation_id or dec(self.good_qty) < 0 or dec(self.scrap_qty) < 0 or dec(self.good_qty)+dec(self.scrap_qty) <= 0:
            raise ValueError('INVALID_FEEDBACK')


@dataclass
class WorkOrder:
    spec: WorkOrderSpec
    routing: Routing
    status: Status = Status.PLANNED
    feedback: dict[str, Feedback] = field(default_factory=dict)

    def __post_init__(self):
        if self.spec.product_id != self.routing.product_id or self.spec.routing_version != self.routing.version:
            raise ValueError('ROUTING_VERSION_MISMATCH')

    def transition(self, new_status: Status):
        new_status = Status(new_status)
        if new_status not in ALLOWED[self.status]:
            raise ValueError('INVALID_STATUS_TRANSITION')
        if new_status == Status.COMPLETED and not self.is_complete():
            raise ValueError('INCOMPLETE_OPERATIONS')
        self.status = new_status

    def record(self, event: Feedback):
        if self.status != Status.IN_PROGRESS:
            raise ValueError('WORK_ORDER_NOT_IN_PROGRESS')
        old = self.feedback.get(event.event_id)
        if old is not None:
            if old != event:
                raise ValueError('EVENT_ID_CONFLICT')
            return False
        ops = {x.operation_id: x for x in self.routing.operations}
        if event.operation_id not in ops:
            raise ValueError('UNKNOWN_OPERATION')
        index = [x.operation_id for x in self.routing.operations].index(event.operation_id)
        if index:
            prior = self.routing.operations[index-1].operation_id
            if self.completed_good(prior) < dec(event.good_qty)+dec(event.scrap_qty)+self.completed_good(event.operation_id)+self.completed_scrap(event.operation_id):
                raise ValueError('UPSTREAM_OPERATION_INSUFFICIENT')
        else:
            if self.completed_good(event.operation_id)+self.completed_scrap(event.operation_id)+dec(event.good_qty)+dec(event.scrap_qty) > dec(self.spec.quantity):
                raise ValueError('WORK_ORDER_QUANTITY_EXCEEDED')
        self.feedback[event.event_id] = event
        return True

    def completed_good(self, operation_id):
        return sum((dec(e.good_qty) for e in self.feedback.values() if e.operation_id == operation_id), Decimal(0))

    def completed_scrap(self, operation_id):
        return sum((dec(e.scrap_qty) for e in self.feedback.values() if e.operation_id == operation_id), Decimal(0))

    def is_complete(self):
        return (all(self.completed_good(o.operation_id)+self.completed_scrap(o.operation_id) > 0 for o in self.routing.operations)
                and self.completed_good(self.routing.operations[-1].operation_id) > 0
                and self.completed_good(self.routing.operations[-1].operation_id)
                    + self.completed_scrap(self.routing.operations[-1].operation_id) == dec(self.spec.quantity))

    def progress(self):
        last = self.routing.operations[-1].operation_id
        return {'work_order_id': self.spec.work_order_id, 'source_run_id':self.spec.source_run_id,
                'source_result_hash':self.spec.source_result_hash,
                'status':self.status.value,'planned_qty':str(dec(self.spec.quantity)),
                'finished_good_qty':str(self.completed_good(last)),
                'finished_scrap_qty':str(self.completed_scrap(last)),
                'remaining_qty':str(max(Decimal(0),dec(self.spec.quantity)-self.completed_good(last)-self.completed_scrap(last))),
                'feedback_events':len(self.feedback)}


def load_plan(specs: list[WorkOrderSpec], routings: dict[tuple[str,str], Routing]):
    """Validated MRP->MES contract. Caller must verify persisted MRP hash upstream."""
    result = []
    seen = set()
    for spec in sorted(specs,key=lambda x:x.work_order_id):
        if spec.work_order_id in seen: raise ValueError('DUPLICATE_WORK_ORDER_ID')
        seen.add(spec.work_order_id)
        key=(spec.product_id,spec.routing_version)
        if key not in routings: raise ValueError('ROUTING_NOT_FOUND')
        result.append(WorkOrder(spec,routings[key]))
    return result


def capacity_plan(orders: list[WorkOrder], daily_capacity: dict[tuple[str,str],Decimal], start_date: str):
    """Forward finite capacity allocation per work center, in stable order.

    Each operation is scheduled after the preceding operation's finish day.
    A single operation may be split across days. No partial batch execution semantics.
    """
    start = date.fromisoformat(start_date)
    capacities = {(center,date.fromisoformat(day)):dec(v) for (center,day),v in daily_capacity.items()}
    if any(v<0 for v in capacities.values()): raise ValueError('NEGATIVE_CAPACITY')
    remaining = dict(capacities)
    allocations=[]
    for order in sorted(orders,key=lambda x:(x.spec.due_date,x.spec.work_order_id)):
        earliest = start
        for op in order.routing.operations:
            hours = dec(op.setup_hours)+dec(op.hours_per_unit)*dec(order.spec.quantity)
            candidate_days=sorted(d for (c,d) in capacities if c==op.work_center and d>=earliest)
            if not candidate_days: raise ValueError('INSUFFICIENT_CAPACITY_HORIZON')
            end = None
            for day in candidate_days:
                use=min(hours,remaining[(op.work_center,day)])
                if use:
                    allocations.append({'work_order_id':order.spec.work_order_id,'operation_id':op.operation_id,
                        'work_center':op.work_center,'day':day.isoformat(),'hours':str(use)})
                    remaining[(op.work_center,day)]-=use
                    hours-=use
                    end=day
                if hours==0: break
            if hours: raise ValueError('INSUFFICIENT_CAPACITY_HORIZON')
            earliest=end  # same-day downstream operations allowed in daily-bucket simulation
    return {'allocations':allocations,'remaining_capacity':[
        {'work_center':c,'day':d.isoformat(),'hours':str(v)} for (c,d),v in sorted(remaining.items())],
        'planning_only':True}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str).encode()).hexdigest()
