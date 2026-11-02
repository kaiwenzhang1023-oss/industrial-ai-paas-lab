"""M1-02: production-shaped in-memory MRP, simulated PG readback, and no-write gates.
No PostgreSQL connections, schema migrations, or SRM import calls are made.
"""
import ast
import copy
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from app.db.integrated import canonical_hash, read_integrated_run
from app.domain.acceptance import run_acceptance
from app.domain.timephased import Item, Order
from app.domain.versioned_bom import BOMRevision
from app.mapping import preview_b01, B01_MAPPING_ID, B01_VERSION
from app.srm.service import normalize_buy, stable


def production_shaped_request():
    """Use the real time-phased MRP/acceptance implementation, not hand-made lots."""
    orders = [Order('SO-M102', 'EM-100', Decimal('100'), '2026-11-30', 1)]
    items = {
        'EM-100': Item('EM-100', 'MAKE', lead_days=2),
        'BR-01': Item('BR-01', 'BUY', lead_days=4, moq=Decimal('10'), lot=Decimal('10')),
        'ST-100': Item('ST-100', 'MAKE', lead_days=2),
        'CW-01': Item('CW-01', 'BUY', lead_days=3),
    }
    revisions = [
        BOMRevision('EM-100','V1','2026-01-01',None,'RELEASED',(('BR-01',2),('ST-100',1))),
        BOMRevision('ST-100','V1','2026-01-01',None,'RELEASED',(('CW-01',1),)),
    ]
    result = run_acceptance(orders,items,revisions,'2026-11-20')
    # Simulate the same JSONB result payload shape as run_integrated (which
    # overwrites the in-memory result hash and stores a canonical result hash).
    result['simulation'] = True
    result['storage'] = 'postgresql'
    result['source_snapshot_hash'] = 'input-sha256-placeholder'
    result_hash = canonical_hash(result)
    mrp = {'run_id':'M2-M102-REAL-ENGINE','status':'COMPLETED',
           'result_hash':result_hash,'input_hash':'input-sha256-placeholder',
           'result':result,'source_versions':{},'snapshot_as_of':'2026-11-20',
           'storage':'postgresql'}
    materials = {k:{'make_buy':v.kind,'uom':'PCS'} for k,v in items.items()}
    return {'mapping_id':B01_MAPPING_ID,'mapping_version':B01_VERSION,
            'source_system':'MRP','source_object':'BUY_PLAN',
            'target_system':'SRM','target_object':'PR_CANDIDATE',
            'source_result_hash':result_hash,'mrp':mrp,'material_snapshot':materials}


class FakeCursor:
    def __init__(self, row): self.row=row; self.queries=[]
    def execute(self, sql, params=None): self.queries.append((sql,params))
    def fetchone(self): return self.row
    def __enter__(self): return self
    def __exit__(self,*args): return False
class FakeConnection:
    def __init__(self,row): self.cursor_instance=FakeCursor(row)
    def cursor(self): return self.cursor_instance


def test_actual_mrp_engine_to_srm_candidate_field_by_field():
    req=production_shaped_request()
    lots=req['mrp']['result']['plan_lots']
    assert lots and any(x['material']=='BR-01' for x in lots)
    assert any(x['material']=='ST-100' for x in lots)
    original=copy.deepcopy(req)
    out=preview_b01(req)
    assert out['status']=='VALID',out
    assert req==original
    expected=normalize_buy(req['mrp'],{k:v['make_buy'] for k,v in req['material_snapshot'].items()})
    assert len(out['candidate_payloads'])==len(expected)
    assert len(expected)>=2
    for plan in expected:
        row=next(x for x in out['candidate_payloads'] if x['source_plan_id']==plan['source_plan_id'])
        assert row['pr_id']==stable('PR',{'run':req['mrp']['run_id'],'plan':plan['source_plan_id']})
        for k in ('source_run_id','source_result_hash','source_plan_id','material_id','bom_version'):
            assert row[k]==plan[k]
        assert Decimal(row['quantity'])==plan['quantity']
        assert row['need_date']==plan['need_date'].isoformat()
        assert row['release_date']==plan['release_date'].isoformat()
        assert row['uom']==req['material_snapshot'][plan['material_id']]['uom']
        assert 'status' not in row and 'created_at' not in row


def test_pg16_readback_contract_without_database_connection():
    req=production_shaped_request(); mrp=req['mrp']
    row=(mrp['input_hash'],mrp['status'],date.fromisoformat(mrp['snapshot_as_of']),
         mrp['source_versions'],mrp['result'],mrp['result_hash'])
    fake=FakeConnection(row)
    req['mrp']=read_integrated_run(fake,mrp['run_id'])
    assert preview_b01(req)['status']=='VALID'
    assert len(fake.cursor_instance.queries)==1
    assert 'SELECT' in fake.cursor_instance.queries[0][0].upper()
    assert fake.cursor_instance.queries[0][1]==(mrp['run_id'],)
    bad=list(row); bad[4]=dict(mrp['result'],simulation=False)
    with pytest.raises(ValueError,match='PERSISTED_RESULT_HASH_MISMATCH'):
        read_integrated_run(FakeConnection(tuple(bad)),mrp['run_id'])


@pytest.mark.parametrize('mutate',[
    lambda r:r['mrp'].update(status='RUNNING'),
    lambda r:r['mrp']['result'].update(plan_lots=None),
    lambda r:r['mrp']['result']['plan_lots'].append(dict(r['mrp']['result']['plan_lots'][0])),
    lambda r:r['mrp']['result']['plan_lots'][0].update(quantity='0'),
    lambda r:r['mrp']['result']['plan_lots'][0].update(quantity='NaN'),
    lambda r:r['mrp']['result']['plan_lots'][0].update(quantity='1.00001'),
    lambda r:r['mrp']['result']['plan_lots'][0].update(quantity='100000000000000'),
    lambda r:r['mrp']['result']['plan_lots'][0].update(need_date='2026-02-30'),
    lambda r:r['mrp']['result']['plan_lots'][0].update(release_date='not-a-date'),
    lambda r:r['mrp']['result']['plan_lots'][0].update(material='UNKNOWN'),
    lambda r:r['material_snapshot']['BR-01'].update(uom=''),
    lambda r:r['material_snapshot']['BR-01'].update(make_buy='UNKNOWN'),
    lambda r:r.update(source_result_hash='0'*64),
    lambda r:r.update(mapping_version='missing'),
    lambda r:r.update(mapping_status='DRAFT'),
    lambda r:r.update(rules=[{'op':'PYTHON'}]),
    lambda r:r.update(source_system='ERP'),
    lambda r:r['mrp'].pop('result_hash'),
])
def test_invalid_input_fail_closed_no_partial_candidates(mutate):
    req=production_shaped_request()
    mutate(req)
    result=preview_b01(req)
    assert result['status']=='REJECTED',result
    assert result['candidate_payloads']==[]
    assert result['mapping_result_hash'] is None
    assert result['errors'] and all('code' in x and 'path' in x for x in result['errors'])


def test_repeat_determinism_and_material_snapshot_provenance():
    req=production_shaped_request()
    a=preview_b01(req);b=preview_b01(copy.deepcopy(req))
    assert a==b and a['status']=='VALID'
    changed=copy.deepcopy(req)
    changed['material_snapshot']['BR-01']['uom']='BOX'
    c=preview_b01(changed)
    assert c['status']=='VALID' and c['mapping_result_hash']!=a['mapping_result_hash']


def test_no_database_or_network_calls_from_preview():
    req=production_shaped_request()
    with patch('app.srm.service.import_mrp',side_effect=AssertionError('SRM WRITE CALLED')), \
         patch('app.db.repository.connect',side_effect=AssertionError('DB CONNECT CALLED')):
        assert preview_b01(req)['status']=='VALID'


def test_mapping_source_ast_no_sql_or_dynamic_execution():
    root=Path(__file__).resolve().parents[2]
    module_dir=root/'backend/app/mapping'
    for f in module_dir.glob('*.py'):
        tree=ast.parse(f.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=([node.module] if isinstance(node,ast.ImportFrom) else [x.name for x in node.names])
                assert not any(x and x.split('.')[0] in {'psycopg','sqlalchemy','requests','httpx','subprocess','socket'} for x in names),(f,names)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                assert node.func.id not in {'eval','exec','compile','open'},(f,node.func.id)
    assert not any((root/'database').glob('016*mapping*.sql'))
