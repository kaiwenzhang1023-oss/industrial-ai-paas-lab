import copy
import json
from pathlib import Path
import pytest
from app.mapping import preview_b01
from app.srm.service import normalize_buy, stable

@pytest.fixture
def b01_request():
    return json.loads((Path(__file__).parent/'fixtures/em100_b01.json').read_text())

def test_buy_only_and_compatible(b01_request):
    result=preview_b01(b01_request)
    assert result['status']=='VALID', result
    assert len(result['candidate_payloads'])==1
    candidate=result['candidate_payloads'][0]
    existing=normalize_buy(b01_request['mrp'],{k:v['make_buy'] for k,v in b01_request['material_snapshot'].items()})[0]
    assert candidate['pr_id']==stable('PR',{'run':existing['source_run_id'],'plan':existing['source_plan_id']})
    for key in ('source_run_id','source_result_hash','source_plan_id','material_id','need_date','release_date','bom_version'):
        assert candidate[key]==existing[key] or (hasattr(existing[key],'isoformat') and candidate[key]==existing[key].isoformat())
    assert candidate['quantity']==str(existing['quantity'])
    assert candidate['uom']=='PCS'
    assert 'status' not in candidate and 'created_at' not in candidate

def test_determinism_and_input_not_mutated(b01_request):
    before=copy.deepcopy(b01_request)
    assert preview_b01(b01_request)==preview_b01(b01_request)
    assert b01_request==before

def test_bad_hash_rejected(b01_request):
    b01_request['source_result_hash']='different'
    result=preview_b01(b01_request)
    assert result['status']=='REJECTED' and result['errors'][0]['code']=='SOURCE_FINGERPRINT_MISMATCH'

def test_bad_buy_atomic(b01_request):
    b01_request['mrp']['result']['plan_lots'].append({'plan_id':'bad','material':'BR-01','quantity':'0','need_date':'2026-12-15','release_date':'2026-12-11'})
    result=preview_b01(b01_request)
    assert result['status']=='REJECTED' and result['candidate_payloads']==[]

def test_unknown_material(b01_request):
    b01_request['mrp']['result']['plan_lots'][0]['material']='UNKNOWN'
    assert preview_b01(b01_request)['status']=='REJECTED'

def test_make_only_rejected(b01_request):
    b01_request['mrp']['result']['plan_lots']=b01_request['mrp']['result']['plan_lots'][1:]
    assert preview_b01(b01_request)['status']=='REJECTED'

def test_unpublished_rejected(b01_request):
    b01_request['mapping_status']='DRAFT'
    assert preview_b01(b01_request)['errors'][0]['code']=='MAPPING_VERSION_NOT_PUBLISHED'

def test_runtime_rules_forbidden(b01_request):
    b01_request['rules']=[]
    assert preview_b01(b01_request)['status']=='REJECTED'

def test_extra_fields_not_leaked(b01_request):
    b01_request['mrp']['result']['plan_lots'][0]['unexpected']='ignored'
    assert 'unexpected' not in preview_b01(b01_request)['candidate_payloads'][0]
