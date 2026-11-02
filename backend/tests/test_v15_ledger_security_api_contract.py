"""C4.4 static contract: ledger access is function-mediated and additive."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_forward_migration_is_test_only_and_does_not_destroy_history():
    sql=(ROOT/'database/025_v15_request_ledger_security_api_TEST_ONLY.sql').read_text()
    assert "current_database() <> 'industrial_lab_v15_test'" in sql
    assert 'ALTER FUNCTION mcp_v15.ledger_claim' in sql
    assert 'OWNER TO mcp_v15_ledger_owner_test' in sql
    assert 'GRANT EXECUTE ON FUNCTION mcp_v15.ledger_claim' in sql
    assert 'GRANT EXECUTE ON FUNCTION mcp_v15.ledger_finish' in sql
    assert 'REVOKE CREATE ON SCHEMA mcp_v15 FROM mcp_v15_ledger_owner_test' in sql
    assert 'DROP TABLE' not in sql.upper()
    assert 'TRUNCATE' not in sql.upper()
    assert 'DELETE FROM mcp_v15.request_ledger' not in sql.upper()

def test_runtime_has_no_direct_ledger_dml_in_python():
    source=(ROOT/'backend/app/mcp_v15/idempotency.py').read_text()
    assert 'INSERT INTO mcp_v15.request_ledger' not in source
    assert 'UPDATE mcp_v15.request_ledger' not in source
    assert 'SELECT action,response_json FROM mcp_v15.ledger_claim' in source
    assert 'mcp_v15.ledger_finish' in source
    assert "state in ('IN_PROGRESS','UNKNOWN')" in source

def test_recovery_uses_operator_api_not_direct_table_scan():
    source=(ROOT/'backend/app/mcp_v17/recovery.py').read_text()
    assert 'SET LOCAL ROLE mcp_v15_ledger_operator_test' in source
    assert 'mcp_v15.ledger_inspect_stale' in source
    assert 'FROM mcp_v15.request_ledger' not in source
