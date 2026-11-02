"""Run with M1_TEST_DATABASE_URL pointing exclusively to industrial_lab_v15_test."""
import os,uuid
import pytest
psycopg = pytest.importorskip("psycopg")

@pytest.fixture
def db():
    url=os.getenv("M1_TEST_DATABASE_URL")
    if not url: pytest.skip("M1_TEST_DATABASE_URL absent")
    c=psycopg.connect(url,autocommit=False)
    with c.cursor() as cur:
        cur.execute("SELECT current_database(), current_setting('server_version_num')::integer")
        name,version=cur.fetchone()
        assert name=='industrial_lab_v15_test' and 160000<=version<170000
    c.rollback()
    try: yield c
    finally: c.rollback();c.close()

def test_schema_and_default_deny(db):
    with db.cursor() as c:
        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='mcp_v15'")
        assert set(r[0] for r in c.fetchall()) == {
            'principals','principal_permissions','resource_registry','resource_grants',
            'tool_call_state','tool_call_audit','request_ledger'
        }
        c.execute("SELECT mcp_v15.is_authorized('t','p','read','X','1')")
        assert c.fetchone()[0] is False

def test_authorization_lifecycle(db):
    t='test_'+uuid.uuid4().hex
    with db.cursor() as c:
        c.execute("INSERT INTO mcp_v15.principals VALUES (%s,'p','ACTIVE')",(t,))
        c.execute("INSERT INTO mcp_v15.principal_permissions(tenant_id,principal_id,permission) VALUES (%s,'p','read')",(t,))
        c.execute("INSERT INTO mcp_v15.resource_registry VALUES (%s,'ITEM','x','ACTIVE','hash',now())",(t,))
        c.execute("INSERT INTO mcp_v15.resource_grants(tenant_id,principal_id,resource_type,resource_id,permission) VALUES (%s,'p','ITEM','x','read')",(t,))
        c.execute("SELECT mcp_v15.is_authorized(%s,'p','read','ITEM','x')",(t,)); assert c.fetchone()[0]
        c.execute("SELECT mcp_v15.is_authorized(%s,'p','read','ITEM','x')",(t+'other',)); assert not c.fetchone()[0]
        c.execute("UPDATE mcp_v15.resource_grants SET revoked_at=now() WHERE tenant_id=%s",(t,))
        c.execute("SELECT mcp_v15.is_authorized(%s,'p','read','ITEM','x')",(t,)); assert not c.fetchone()[0]

def test_atomic_cas_and_append_only(db):
    call=uuid.uuid4();e1=uuid.uuid4();e2=uuid.uuid4();h='a'*64
    with db.cursor() as c:
        c.execute("SELECT mcp_v15.receive_call(%s,'t','p','test','1',%s,%s)",(call,h,e1))
        c.execute("SELECT mcp_v15.advance_call(%s,'RECEIVED',0,'AUTHORIZED',%s)",(call,e2)); assert c.fetchone()[0]
        c.execute("SELECT mcp_v15.advance_call(%s,'RECEIVED',0,'DENIED',%s)",(call,uuid.uuid4())); assert not c.fetchone()[0]
        c.execute("SELECT status,version FROM mcp_v15.tool_call_state WHERE call_id=%s",(call,)); assert c.fetchone()==('AUTHORIZED',1)
        c.execute("SELECT count(*) FROM mcp_v15.tool_call_audit WHERE call_id=%s",(call,)); assert c.fetchone()[0]==2
        c.execute('SAVEPOINT audit_guard')
        with pytest.raises(psycopg.Error): c.execute("DELETE FROM mcp_v15.tool_call_audit WHERE call_id=%s",(call,))
        c.execute('ROLLBACK TO SAVEPOINT audit_guard')
