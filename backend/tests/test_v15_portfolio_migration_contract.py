"""Static contract checks; no database changes or Docker required."""
from pathlib import Path

def test_020_guarded_policy_creation():
    sql = (Path(__file__).resolve().parents[2] / 'database' / '020_v15_request_ledger_test.sql').read_text()
    assert "current_database() <> 'industrial_lab_v15_test'" in sql
    assert "WHERE polrelid='mcp_v15.request_ledger'::regclass" in sql
    assert 'IF NOT FOUND THEN' in sql
    assert 'existing policy differs; manual review required' in sql
    assert 'DROP POLICY' not in sql.upper()
    assert 'DROP TABLE' not in sql.upper()
