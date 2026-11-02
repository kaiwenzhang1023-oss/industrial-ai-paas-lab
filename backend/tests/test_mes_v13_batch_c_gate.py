"""Batch C pure reliability gates; PG16 checks are separate and must be run by operator."""
from decimal import Decimal as D
import pytest
from app.mes.core import Routing, Operation, WorkOrderSpec, WorkOrder, Feedback, Status, capacity_plan
from app.mes.integration import make_specs

ROUTING=Routing('EM-100','V1',(
    Operation('ASSEMBLY',1,'WC-A',D('1'),D('0.5')),
    Operation('TEST',2,'WC-T',D('0.5'),D('0.25'))))

def order(id='WO-1',quantity='10'):
    spec=WorkOrderSpec(id,'M2-run','P-1','hash','EM-100',D(quantity),'2026-12-01','V1')
    return WorkOrder(spec,ROUTING)

def active():
    w=order();w.transition(Status.RELEASED);w.transition(Status.IN_PROGRESS);return w

def test_no_early_completion():
    w=active();w.record(Feedback('a','ASSEMBLY',D(10),D(0),'2026-11-25'))
    w.record(Feedback('b','TEST',D(1),D(0),'2026-11-25'))
    with pytest.raises(ValueError,match='INCOMPLETE_OPERATIONS'):
        w.transition(Status.COMPLETED)

def test_completed_full_quantity():
    w=active();w.record(Feedback('a','ASSEMBLY',D(10),D(0),'2026-11-25'))
    w.record(Feedback('b','TEST',D(9),D(1),'2026-11-25'))
    w.transition(Status.COMPLETED)
    assert w.status == Status.COMPLETED

def test_feedback_idempotency_and_conflict():
    w=active();event=Feedback('a','ASSEMBLY',D(10),D(0),'2026-11-25')
    assert w.record(event) is True
    assert w.record(event) is False
    with pytest.raises(ValueError,match='EVENT_ID_CONFLICT'):
        w.record(Feedback('a','ASSEMBLY',D(9),D(1),'2026-11-25'))
    assert len(w.feedback)==1

def test_upstream_and_quantity_fences():
    w=active()
    with pytest.raises(ValueError,match='UPSTREAM_OPERATION_INSUFFICIENT'):
        w.record(Feedback('b','TEST',D(1),D(0),'2026-11-25'))
    with pytest.raises(ValueError,match='WORK_ORDER_QUANTITY_EXCEEDED'):
        w.record(Feedback('a','ASSEMBLY',D(11),D(0),'2026-11-25'))

def test_shared_capacity_never_overallocated():
    a,b=order('WO-1'),order('WO-2')
    caps={(c,d):D('8') for c in ('WC-A','WC-T') for d in ('2026-11-25','2026-11-26','2026-11-27')}
    result=capacity_plan([a,b],caps,'2026-11-25')
    for (center,day),limit in caps.items():
        used=sum((D(x['hours']) for x in result['allocations'] if (x['work_center'],x['day'])==(center,day)),D(0))
        assert used<=limit

def test_capacity_horizon_failure():
    with pytest.raises(ValueError,match='INSUFFICIENT_CAPACITY_HORIZON'):
        capacity_plan([order()],{('WC-A','2026-11-25'):D('1')},'2026-11-25')

def test_make_plan_deterministic_and_fail_closed():
    mrp={'run_id':'M2-run','status':'COMPLETED','result_hash':'h','result':{'plan_lots':[
        {'plan_id':'p','material':'EM-100','quantity':'10','need_date':'2026-12-01'}]}}
    r={('EM-100','V1'):ROUTING}
    assert make_specs(mrp,{'EM-100':'MAKE'},r)==make_specs(mrp,{'EM-100':'MAKE'},r)
    with pytest.raises(ValueError,match='ROUTING_NOT_FOUND'):
        make_specs(mrp,{'EM-100':'MAKE'}, {})
