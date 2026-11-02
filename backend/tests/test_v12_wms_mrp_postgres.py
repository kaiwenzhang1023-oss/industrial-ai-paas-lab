"""V1.2 FINAL candidate: actual PG read/write/readback, WMS evidence and API contract.
Run only against local industrial_lab_v12_test. Never production or Neon.
"""
import os
from collections import defaultdict
from pathlib import Path
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.db.repository import connect, seed
from app.db.integrated import run_integrated, read_integrated_run, canonical_hash, seed_effective_bom
from app.db.v12_test_guard import require_v12_test_url

pytestmark = pytest.mark.integration

@pytest.fixture
def dburl():
    url = os.getenv('TEST_DATABASE_URL')
    if not url: pytest.fail('TEST_DATABASE_URL required; no skip for final gate')
    require_v12_test_url(url)
    with connect(url) as db:
        with db.cursor() as cur:
            cur.execute('SELECT current_database(), current_user, inet_server_port()')
            name, user, _ = cur.fetchone()
            assert (name, user) == ('industrial_lab_v12_test', 'lab')
    # Seed explicitly: this test module must pass when executed alone or first.
    # The seed and effective-BOM bootstrap are idempotent on the isolated DB.
    root = Path(__file__).resolve().parents[2]
    with connect(url) as db:
        seed(db, root / 'datasets/seed/multi_order.json')
        seed_effective_bom(db)
    return url

def test_v12_new_run_persisted_wms_conservation_and_workbench(dburl, monkeypatch):
    with connect(dburl) as db:
        created = run_integrated(db, '2026-11-20')
        stored = read_integrated_run(db, created['run_id'])
    result = stored['result']
    assert stored['status'] == 'COMPLETED'
    assert stored['result_hash'] == created['result_hash'] == canonical_hash(result)
    assert stored['input_hash'] == created['input_hash']
    assert result['storage'] == 'postgresql'
    assert result['wms_stock_attribution_contract'] == 'V12-PLANNING-ONLY-V1'
    evidence = result['wms_stock_attribution']
    assert evidence, 'WMS evidence must not be empty for seeded scenario'
    expected = defaultdict(Decimal)
    for alloc in result['pegging']['order_allocations']:
        if alloc['supply_kind'] == 'STOCK':
            expected[(alloc['demand_id'], alloc['supply_id'])] += Decimal(str(alloc['allocated_qty']))
    actual = defaultdict(Decimal)
    for e in evidence:
        assert e['attribution_type'] == 'SIMULATED_PLANNING_ALLOCATION'
        assert e['warehouse_id'] and e['material_id'] and e['source_version'] >= 1
        assert Decimal(e['allocated_qty']) > 0
        actual[(e['demand_id'],e['supply_id'])] += Decimal(e['allocated_qty'])
    assert dict(actual) == dict(expected), 'WMS stock evidence conservation failed'
    import app.workbench as wb
    monkeypatch.setattr(wb, 'connect', lambda: connect(dburl))
    from app.main import app
    response = TestClient(app).get(f"/api/v1/workbench/mrp/{created['run_id']}/details")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['read_only'] is True
    assert body['wms_attribution_contract'] == 'V12-PLANNING-ONLY-V1'
    assert body['wms_stock_attribution'] == evidence
    assert body['run']['status'] == 'COMPLETED'
    print(f"V12_FINAL_EVIDENCE run_id={created['run_id']} wms_rows={len(evidence)} result_hash={created['result_hash']}")

def test_v12_repeatability_of_persisted_wms_evidence(dburl):
    with connect(dburl) as db:
        a = run_integrated(db, '2026-11-20')
        b = run_integrated(db, '2026-11-20')
        ra = read_integrated_run(db, a['run_id'])
        rb = read_integrated_run(db, b['run_id'])
    assert a['input_hash'] == b['input_hash']
    assert a['result_hash'] == b['result_hash']
    assert ra['result']['wms_stock_attribution'] == rb['result']['wms_stock_attribution']
