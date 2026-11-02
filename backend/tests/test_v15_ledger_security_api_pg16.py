"""C4.4 live PG16 integration. Requires 025 migration on isolated V15 TEST DB."""
import os
import uuid
import pytest

psycopg=pytest.importorskip('psycopg')
from app.mcp_v15.idempotency import claim,finish,RequestConflict
from app.mcp_v17.recovery import inspect_stale

@pytest.fixture
def conn():
    dsn=os.getenv('M1_TEST_DATABASE_URL')
    if not dsn: pytest.skip('M1_TEST_DATABASE_URL not configured')
    c=psycopg.connect(dsn,autocommit=True,connect_timeout=8)
    db,ver=c.execute("SELECT current_database(),current_setting('server_version_num')::int").fetchone()
    assert db=='industrial_lab_v15_test' and 160000<=ver<170000
    try: yield c
    finally: c.close()

def test_runtime_claim_finish_cache_conflict_and_no_table_access(conn):
    request='C44-PY-'+uuid.uuid4().hex
    identity=('c44-py-tenant','c44-py-principal',request,'mrp.get_run',{'run_id':'EM-100'})
    assert claim(conn,*identity)==('NEW',None)
    assert claim(conn,*identity)==('IN_PROGRESS',None)
    finish(conn,*identity[:4],identity[4],{'status':'COMPLETED','result':{'run_id':'EM-100'}})
    state,cached=claim(conn,*identity)
    assert state=='DONE' and cached=={'status':'COMPLETED','result':{'run_id':'EM-100'}}
    with pytest.raises(RequestConflict):
        claim(conn,*identity[:4],{'run_id':'OTHER'})
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE mcp_v15_runtime_test')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute('SELECT * FROM mcp_v15.request_ledger LIMIT 1')

def test_recovery_uses_operator_only_function(conn):
    rows=inspect_stale(conn,threshold=1,limit=10)
    assert isinstance(rows,list)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE mcp_v15_ledger_operator_test')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute('SELECT * FROM mcp_v15.request_ledger LIMIT 1')
