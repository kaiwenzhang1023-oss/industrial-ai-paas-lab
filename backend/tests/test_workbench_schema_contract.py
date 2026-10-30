"""Static M4 read-model contract: snapshot_as_of belongs to M2 integrated payloads."""
from pathlib import Path

def test_workbench_run_snapshot_uses_integrated_payload_contract():
    root = Path(__file__).resolve().parents[2]
    schema = (root / 'database/schema.sql').read_text(encoding='utf-8')
    integration = (root / 'database/006_m2_integration.sql').read_text(encoding='utf-8')
    source = (root / 'backend/app/workbench.py').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS platform.requirement_runs' in schema
    assert 'CREATE TABLE IF NOT EXISTS platform.integrated_mrp_payloads' in integration
    assert 'snapshot_as_of date NOT NULL' in integration
    assert 'LEFT JOIN platform.integrated_mrp_payloads p ON p.run_id=r.run_id' in source
    assert 'SELECT run_id,status,snapshot_as_of FROM platform.requirement_runs' not in source
