"""Opt-in destructive-to-OWN-isolated-schema integration test. Never target production."""
import os
import uuid
import pytest
from psycopg.conninfo import conninfo_to_dict

@pytest.mark.integration
def test_pg16_idempotency_live_isolated():
    if os.getenv('V18_ALLOW_ISOLATED_PG16') != 'YES':
        pytest.skip('explicit PG16 opt-in required')
    dsn = os.getenv('V18_ISOLATED_PG16_DSN')
    if not dsn:
        pytest.skip('isolated test database DSN required')

    # Strict pre-connection identity validation.
    try:
        identity = conninfo_to_dict(dsn)
    except Exception:
        pytest.fail("V18_TEST_DSN_INVALID")

    actual_identity = (
        identity.get("host"),
        str(identity.get("port", "5432")),
        identity.get("dbname"),
        identity.get("user"),
    )

    expected_identity = (
        "127.0.0.1",
        "55433",
        "industrial_ai_v18_e06_acceptance",
        "v18_tester",
    )

    if actual_identity != expected_identity:
        pytest.fail("V18_TEST_DSN_IDENTITY_MISMATCH")
    import psycopg
    from app.mcp_v18.pg_ledger import PostgresLedger, DDL
    from app.mcp_v18.durable_ledger import LedgerConflict
    schema = 'v18_gate_' + uuid.uuid4().hex[:12]
    def connect():
        conn=psycopg.connect(dsn,connect_timeout=5)
        conn.execute('SET search_path TO ' + schema + ',public')
        return conn
    admin=psycopg.connect(dsn,connect_timeout=5)
    try:
        with admin.transaction():
            row=admin.execute('SELECT current_setting(\'server_version_num\')::int, current_database(), pg_is_in_recovery(), current_user').fetchone()
            assert 160000 <= row[0] < 170000, 'PG16_ONLY'
            assert row[1] in ('industrial_ai_v18_test', 'industrial_ai_v18_e06_acceptance'), 'TEST_DATABASE_ONLY'
            assert row[2] is False, 'READ_REPLICA_DENIED'
            assert row[3] == 'v18_tester', 'DATABASE_USER_IDENTITY_MISMATCH'
            admin.execute('CREATE SCHEMA ' + schema)
        with connect() as c:
            for stmt in DDL.strip().split(';'):
                if stmt.strip(): c.execute(stmt)
        ledger=PostgresLedger(connect)
        identity=('tenant-demo','principal-demo','request-1','mrp.get_run',{'run_id':'R1'})
        assert ledger.claim(*identity)['action']=='EXECUTE_ONCE'
        assert ledger.claim(*identity)['action']=='DO_NOT_REPLAY'
        ledger.complete(*identity,{'ok':True})
        assert ledger.claim(*identity)=={'action':'RETURN_CACHED','result':{'ok':True}}
        with pytest.raises(LedgerConflict):
            ledger.claim('tenant-demo','principal-demo','request-1','mrp.get_run',{'run_id':'OTHER'})
        assert ledger.inspect(*identity[:3])['action']=='RETURN_CACHED'
        with connect() as c:
            assert c.execute('SELECT count(*) FROM mcp_v18_events').fetchone()[0]>=4
    finally:
        try:
            with admin.transaction(): admin.execute('DROP SCHEMA IF EXISTS ' + schema + ' CASCADE')
        finally: admin.close()
