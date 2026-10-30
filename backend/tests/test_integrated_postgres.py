"""Real database integration tests; never counted as passed when TEST_DATABASE_URL missing.
Requires initialized, isolated PostgreSQL test DB. Database is mutated.
"""
import os
import pytest
from app.db.repository import connect, seed
from app.db.integrated import seed_effective_bom,run_integrated,read_integrated_run
from pathlib import Path

@pytest.fixture
def testdb():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required: REAL DB TEST NOT EXECUTED')
    if 'industrial_lab_test' not in url:
        pytest.fail('TEST_DATABASE_URL must identify isolated industrial_lab_test database')
    with connect(url) as conn:
        yield conn

@pytest.mark.integration
def test_real_seed_run_readback(testdb):
    root=Path(__file__).resolve().parents[2]
    seed(testdb,root/'datasets/seed/multi_order.json')
    seed_effective_bom(testdb)
    created=run_integrated(testdb,'2026-11-20')
    read=read_integrated_run(testdb,created['run_id'])
    assert read['input_hash']==created['input_hash']
    assert read['result_hash']==created['result_hash']
    assert read['result']['pegging']['conservation_passed'] is True
    assert read['result']['storage']=='postgresql'

@pytest.mark.integration
def test_real_repeatable_hash(testdb):
    root=Path(__file__).resolve().parents[2]
    seed(testdb,root/'datasets/seed/multi_order.json')
    seed_effective_bom(testdb)
    a=run_integrated(testdb,'2026-11-20')
    b=run_integrated(testdb,'2026-11-20')
    assert a['input_hash']==b['input_hash']
    assert a['result_hash']==b['result_hash']
