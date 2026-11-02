from decimal import Decimal as D
import pytest
from app.mes.core import (Operation, Routing, WorkOrderSpec, Feedback, Status, load_plan, capacity_plan, canonical_hash)


def example():
    routing=Routing('EM-100','R1',(Operation('CUT',1,'WC-CUT',D('1'),D('.5')),Operation('ASSY',2,'WC-ASSY',D('0'),D('1'))))
    spec=WorkOrderSpec('WO-001','M2-RUN','PLAN-001','hash-immutable','EM-100',D('10'),'2026-11-26','R1')
    return load_plan([spec],{('EM-100','R1'):routing})[0]


def test_state_and_feedback_idempotency():
    o=example()
    with pytest.raises(ValueError,match='INVALID_STATUS_TRANSITION'): o.transition(Status.COMPLETED)
    o.transition(Status.RELEASED);o.transition(Status.IN_PROGRESS)
    e=Feedback('E1','CUT',D('10'),D('0'),'2026-11-21')
    assert o.record(e) is True
    assert o.record(e) is False
    with pytest.raises(ValueError,match='EVENT_ID_CONFLICT'): o.record(Feedback('E1','CUT',D('9'),D('1'),'2026-11-21'))
    assert o.record(Feedback('E2','ASSY',D('9'),D('1'),'2026-11-22')) is True
    o.transition(Status.COMPLETED)
    assert o.progress()['finished_good_qty']=='9'
    assert o.progress()['source_result_hash']=='hash-immutable'


def test_reject_upstream_and_overproduction():
    o=example();o.transition(Status.RELEASED);o.transition(Status.IN_PROGRESS)
    with pytest.raises(ValueError,match='UPSTREAM_OPERATION_INSUFFICIENT'):o.record(Feedback('E1','ASSY',D('1'),D('0'),'2026-11-21'))
    with pytest.raises(ValueError,match='WORK_ORDER_QUANTITY_EXCEEDED'):o.record(Feedback('E2','CUT',D('11'),D('0'),'2026-11-21'))


def test_finite_capacity_and_determinism():
    o=example()
    cap={('WC-CUT','2026-11-20'):D('4'),('WC-CUT','2026-11-21'):D('2'),('WC-ASSY','2026-11-21'):D('5'),('WC-ASSY','2026-11-22'):D('5')}
    a=capacity_plan([o],cap,'2026-11-20')
    b=capacity_plan([o],cap,'2026-11-20')
    assert a==b and canonical_hash(a)==canonical_hash(b)
    assert sum(D(x['hours']) for x in a['allocations'] if x['operation_id']=='CUT')==D('6')
    assert sum(D(x['hours']) for x in a['allocations'] if x['operation_id']=='ASSY')==D('10')
    assert all(D(x['hours'])>=0 for x in a['remaining_capacity'])


def test_capacity_fails_closed():
    with pytest.raises(ValueError,match='INSUFFICIENT_CAPACITY_HORIZON'):
        capacity_plan([example()],{('WC-CUT','2026-11-20'):D('1')},'2026-11-20')


def test_routing_contract_rejects_mismatch():
    o=example()
    spec=WorkOrderSpec('WO-002','M2-RUN','PLAN-001','hash','EM-100',D('1'),'2026-11-26','R2')
    with pytest.raises(ValueError,match='ROUTING_NOT_FOUND'):
        load_plan([spec],{('EM-100','R1'):o.routing})


def test_complete_requires_feedback():
    o=example();o.transition(Status.RELEASED);o.transition(Status.IN_PROGRESS)
    with pytest.raises(ValueError,match='INCOMPLETE_OPERATIONS'):o.transition(Status.COMPLETED)
