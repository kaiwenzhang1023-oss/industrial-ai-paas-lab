"""Pure adapter checks; database integration remains a Batch C gate."""
from decimal import Decimal
import pytest
from app.mes.integration import make_specs
from app.mes.core import Routing, Operation, load_plan, capacity_plan

ROUTING=Routing('EM-100','V1',(
    Operation('ASSEMBLY',1,'WC-A',Decimal('1'),Decimal('0.5')),
    Operation('TEST',2,'WC-T',Decimal('0.5'),Decimal('0.25')),
))

def mrp():
    return {'run_id':'M2-test','status':'COMPLETED','result_hash':'abc123',
            'result':{'plan_lots':[
                {'plan_id':'P-1','material':'EM-100','quantity':'10','need_date':'2026-11-30'},
                {'plan_id':'P-2','material':'BR-01','quantity':'20','need_date':'2026-11-29'}]}}

def test_make_only_and_stable_identity():
    a=make_specs(mrp(),{'EM-100':'MAKE','BR-01':'BUY'},{('EM-100','V1'):ROUTING})
    b=make_specs(mrp(),{'EM-100':'MAKE','BR-01':'BUY'},{('EM-100','V1'):ROUTING})
    assert a==b and len(a)==1 and a[0].source_plan_id=='P-1'
    assert a[0].source_result_hash=='abc123'

def test_missing_routing_fails_closed():
    with pytest.raises(ValueError,match='ROUTING_NOT_FOUND'):
        make_specs(mrp(),{'EM-100':'MAKE'}, {})

def test_buy_only_rejected():
    with pytest.raises(ValueError,match='NO_MAKE_PLANS'):
        make_specs(mrp(),{'EM-100':'BUY','BR-01':'BUY'}, {})

def test_invalid_plan_rejected():
    value=mrp();value['result']['plan_lots'][0]['quantity']='0'
    with pytest.raises(ValueError,match='INVALID_MRP_PLAN'):
        make_specs(value,{'EM-100':'MAKE'},{('EM-100','V1'):ROUTING})

def test_capacity_from_imported_spec():
    specs=make_specs(mrp(),{'EM-100':'MAKE','BR-01':'BUY'},{('EM-100','V1'):ROUTING})
    wo=load_plan(specs,{('EM-100','V1'):ROUTING})
    capacity={(center,day):Decimal('12') for center in ('WC-A','WC-T') for day in ('2026-11-20','2026-11-21')}
    result=capacity_plan(wo,capacity,'2026-11-20')
    assert result['planning_only'] is True
    assert len(result['allocations'])==2
