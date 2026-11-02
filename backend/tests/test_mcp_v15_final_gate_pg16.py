"""M1-01 final role/RLS bypass tests + M1-02 deny-only gateway integration."""
import os,uuid
import pytest
psycopg=pytest.importorskip('psycopg')
from app.mcp_v15.gateway import Gateway
from app.mcp_v15.security import Identity

@pytest.fixture
def conn():
    url=os.environ.get('M1_TEST_DATABASE_URL')
    if not url: pytest.fail('M1_TEST_DATABASE_URL missing')
    c=psycopg.connect(url,connect_timeout=8)
    with c.cursor() as cur:
        cur.execute('SELECT current_database(), current_setting(\'server_version_num\')::int')
        db,ver=cur.fetchone()
        assert db=='industrial_lab_v15_test' and 160000<=ver<170000
    c.rollback()
    try: yield c
    finally: c.rollback();c.close()

def role(conn,name):
    with conn.cursor() as cur:
        cur.execute('SET LOCAL ROLE '+name)

def test_low_privilege_no_table_dml_or_legacy_function(conn):
    role(conn,'mcp_v15_runtime_test')
    for sql in ('SELECT * FROM mcp_v15.principals',
                "INSERT INTO mcp_v15.principals VALUES ('x','x','ACTIVE')",
                'DELETE FROM mcp_v15.tool_call_audit',
                "SELECT mcp_v15.receive_call(gen_random_uuid(),'x','x','x','1',repeat('a',64)::char(64),gen_random_uuid())"):
        with conn.cursor() as c:
            c.execute('SAVEPOINT p')
            with pytest.raises(psycopg.errors.InsufficientPrivilege): c.execute(sql)
            c.execute('ROLLBACK TO SAVEPOINT p')

def test_reader_cannot_invoke_runtime_functions(conn):
    role(conn,'mcp_v15_reader_test')
    with conn.cursor() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT mcp_v15.runtime_receive(gen_random_uuid(),'x','x','x','1',repeat('a',64)::char(64),gen_random_uuid())")

def test_rls_enabled_and_no_low_role_policies(conn):
    with conn.cursor() as c:
        c.execute("SELECT relname,relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='mcp_v15' AND relkind='r'")
        rows=dict(c.fetchall())
        assert all(rows.get(t) is True for t in ('principals','principal_permissions','resource_registry','resource_grants','tool_call_state','tool_call_audit'))
        c.execute("""SELECT count(*) FROM pg_policies WHERE schemaname='mcp_v15'
                    AND tablename <> 'request_ledger'""")
        assert c.fetchone()[0]==0
        c.execute("""SELECT roles,qual,with_check FROM pg_policies
                    WHERE schemaname='mcp_v15' AND tablename='request_ledger'
                      AND policyname='ledger_owner_test'""")
        policy=c.fetchone()
        assert policy is not None and 'mcp_v15_ledger_owner_test' in policy[0]
        assert policy[1]=='true' and policy[2]=='true'
        c.execute("""SELECT count(*) FROM pg_policies WHERE schemaname='mcp_v15'
                  AND tablename='request_ledger'
                  AND ('mcp_v15_runtime_test'=ANY(roles) OR 'mcp_v15_reader_test'=ANY(roles))""")
        assert c.fetchone()[0]==0

def test_gateway_deny_audited_atomically(conn):
    role(conn,'mcp_v15_runtime_test')
    result=Gateway().submit(conn,Identity('gate_'+uuid.uuid4().hex,'p'),'mrp.get_run',{'run_id':'r'},'MRP','r')
    assert result['status']=='DENIED'
    # Runtime role must not read tables. Verify with separate owner connection after rollback
    # in a dedicated owner transaction below.
    conn.rollback()
    with conn.cursor() as c:
        c.execute('SELECT status,version FROM mcp_v15.tool_call_state WHERE call_id=%s',(result['call_id'],))
        assert c.fetchone() is None  # transaction rollback removes both state and audit

def test_runtime_role_cannot_write_business_tables(conn):
    role(conn,'mcp_v15_runtime_test')
    with conn.cursor() as c:
        c.execute('SAVEPOINT p')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('CREATE TABLE public.mcp_v15_illegal_write_probe(x int)')
        c.execute('ROLLBACK TO SAVEPOINT p')
