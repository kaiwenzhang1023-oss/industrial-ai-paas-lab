"""V1.8 demo extension: deterministic, read-only, distinct from persisted MRP."""
from app.portfolio_demo_extension import golden_mrp_demo, capabilities

def test_golden_contract():
    r=golden_mrp_demo()
    assert r['simulation'] and r['not_persisted'] and r['not_platform_pegging']
    assert r['result']['purchase_amount_cny']=='8700'
    assert len(r['result']['lines'])==8
    assert r['snapshot']['database_run_id'] is None
    assert len(r['snapshot']['fingerprint_sha256'])==64
    assert r['procurement_suggestions']

def test_reproducible():
    assert golden_mrp_demo()==golden_mrp_demo()

def test_readonly_capability(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY','1')
    monkeypatch.setenv('DEMO_WRITE_ENABLED','0')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','anything')
    assert capabilities()['operator_execution_available'] is False

def test_operator_requires_all_flags(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY','0')
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','test-only')
    assert capabilities()['operator_execution_available'] is True
