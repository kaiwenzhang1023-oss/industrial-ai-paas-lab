"""Real PostgreSQL integration tests; require TEST_DATABASE_URL.
Run against disposable database only: seed mutates source records.
"""
import os, pytest
from pathlib import Path
from app.db.repository import connect,seed,load_snapshot,calculate_and_save,read_run
from app.domain.pegging import allocate

pytestmark=pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'),reason='TEST_DATABASE_URL not set; PostgreSQL integration not run')
SEED=Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json'

@pytest.fixture
def db():
    with connect(os.environ['TEST_DATABASE_URL']) as conn:
        yield conn

def test_postgres_seed_roundtrip(db):
    seed(db,SEED)
    orders,items,bom=load_snapshot(db)
    assert len(orders)==2 and len(bom)==8
    assert items['ST-100'].on_hand==60
    assert items['HS-01'].receipts==(('2026-11-26',10),('2026-11-29',40))

def test_postgres_persisted_run_and_pegging(db):
    seed(db,SEED)
    result=calculate_and_save(db)
    persisted=read_run(db,result['run_id'])
    assert persisted['status']=='COMPLETED'
    assert len(persisted['lines'])==result['lines']
    assert len(persisted['pegs'])==result['pegs']
    assert all(float(p['gross'])==sum(float(p[k]) for k in ('from_stock','from_receipts','from_planned')) for p in persisted['pegs'])
    st=[p for p in persisted['pegs'] if p['material']=='ST-100']
    assert [(p['order_id'],p['from_stock'],p['from_planned']) for p in st]==[
        ('SO-2026-001','60.0000','40.0000'),('SO-2026-002','0.0000','20.0000')]

def test_postgres_run_input_hash_repeatable(db):
    seed(db,SEED)
    first=calculate_and_save(db)
    second=calculate_and_save(db)
    assert first['input_hash']==second['input_hash']


def test_postgres_snapshot_fence_persisted(db):
    seed(db,SEED)
    result=calculate_and_save(db)
    saved=read_run(db,result['run_id'])
    assert saved['snapshot']['as_of']=='2026-10-29'
    assert saved['snapshot']['source_versions']==result['snapshot_versions']
    assert result['isolation']=='REPEATABLE READ'


def test_postgres_snapshot_fence_rolls_back_on_duplicate_run_id(db):
    seed(db,SEED)
    from uuid import uuid4
    run_id='M20202-TEST-DUPLICATE-'+uuid4().hex[:12]
    first=calculate_and_save(db,run_id=run_id)
    import pytest
    with pytest.raises(Exception):
        calculate_and_save(db,run_id=run_id)
    assert read_run(db,first['run_id'])['status']=='COMPLETED'
