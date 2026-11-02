"""M1-01 security hardening: existing Docker PG16 isolated TEST DB only.
No migrations, no role creation, no writes outside test DB. Each test rolls back.
"""
import os
import threading
import uuid

import pytest

psycopg = pytest.importorskip('psycopg')

DB_NAME = 'industrial_lab_v15_test'


def connect():
    url = os.environ.get('M1_TEST_DATABASE_URL')
    if not url:
        pytest.fail('M1_TEST_DATABASE_URL is required; tests must not silently skip')
    conn = psycopg.connect(url, autocommit=False, connect_timeout=8)
    with conn.cursor() as cur:
        cur.execute('SELECT current_database(), current_setting(\'server_version_num\')::int')
        name, version = cur.fetchone()
        assert name == DB_NAME and 160000 <= version < 170000, (name, version)
    conn.rollback()
    return conn


@pytest.fixture
def db():
    c = connect()
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def test_default_deny_tenant_and_resource_lifecycle(db):
    tenant = 'm101h_' + uuid.uuid4().hex
    with db.cursor() as c:
        c.execute('SELECT mcp_v15.is_authorized(%s,%s,%s,%s,%s)', (tenant, 'u', 'read', 'PART', 'x'))
        assert c.fetchone()[0] is False
        c.execute('INSERT INTO mcp_v15.principals VALUES (%s, %s, %s)', (tenant, 'u', 'ACTIVE'))
        c.execute('INSERT INTO mcp_v15.principal_permissions(tenant_id,principal_id,permission) VALUES (%s,%s,%s)', (tenant,'u','read'))
        c.execute('INSERT INTO mcp_v15.resource_registry VALUES (%s,%s,%s,%s,%s,now())', (tenant,'PART','x','ACTIVE','test'))
        c.execute('INSERT INTO mcp_v15.resource_grants(tenant_id,principal_id,resource_type,resource_id,permission) VALUES (%s,%s,%s,%s,%s)', (tenant,'u','PART','x','read'))
        def allowed(t, principal='u', perm='read', r='x'):
            c.execute('SELECT mcp_v15.is_authorized(%s,%s,%s,%s,%s)', (t,principal,perm,'PART',r))
            return c.fetchone()[0]
        assert allowed(tenant)
        assert not allowed(tenant + '_other')
        assert not allowed(tenant, principal='other')
        assert not allowed(tenant, perm='write')
        assert not allowed(tenant, r='other')
        c.execute("UPDATE mcp_v15.resource_registry SET status='STALE' WHERE tenant_id=%s", (tenant,))
        assert not allowed(tenant)
        c.execute("UPDATE mcp_v15.resource_registry SET status='ACTIVE' WHERE tenant_id=%s", (tenant,))
        c.execute("UPDATE mcp_v15.resource_grants SET expires_at=now()-interval '1 second' WHERE tenant_id=%s", (tenant,))
        assert not allowed(tenant)
        c.execute("UPDATE mcp_v15.resource_grants SET expires_at=NULL, revoked_at=now() WHERE tenant_id=%s", (tenant,))
        assert not allowed(tenant)
        c.execute("UPDATE mcp_v15.resource_grants SET revoked_at=NULL WHERE tenant_id=%s", (tenant,))
        c.execute("UPDATE mcp_v15.principal_permissions SET revoked_at=now() WHERE tenant_id=%s", (tenant,))
        assert not allowed(tenant)
        c.execute("UPDATE mcp_v15.principal_permissions SET revoked_at=NULL WHERE tenant_id=%s", (tenant,))
        c.execute("UPDATE mcp_v15.principals SET status='DISABLED' WHERE tenant_id=%s", (tenant,))
        assert not allowed(tenant)


def test_audit_append_only_update_delete_and_atomic_rollback(db):
    call, event = uuid.uuid4(), uuid.uuid4()
    with db.cursor() as c:
        c.execute('SELECT mcp_v15.receive_call(%s,%s,%s,%s,%s,%s,%s)', (call,'test','p','test','1','b'*64,event))
        for statement in ('UPDATE mcp_v15.tool_call_audit SET outcome=\'changed\' WHERE call_id=%s',
                          'DELETE FROM mcp_v15.tool_call_audit WHERE call_id=%s'):
            c.execute('SAVEPOINT audit_probe')
            with pytest.raises(psycopg.Error):
                c.execute(statement, (call,))
            c.execute('ROLLBACK TO SAVEPOINT audit_probe')
        c.execute('SELECT count(*) FROM mcp_v15.tool_call_audit WHERE call_id=%s', (call,))
        assert c.fetchone()[0] == 1
        c.execute('SAVEPOINT invalid_transition')
        with pytest.raises(psycopg.Error):
            c.execute('SELECT mcp_v15.advance_call(%s,%s,%s,%s,%s)', (call,'RECEIVED',0,'COMPLETED',uuid.uuid4()))
        c.execute('ROLLBACK TO SAVEPOINT invalid_transition')
        c.execute('SELECT status,version FROM mcp_v15.tool_call_state WHERE call_id=%s', (call,))
        assert c.fetchone() == ('RECEIVED',0)
        c.execute('SELECT count(*) FROM mcp_v15.tool_call_audit WHERE call_id=%s', (call,))
        assert c.fetchone()[0] == 1


def test_public_not_granted_governance_access(db):
    # ACL grantee=0 denotes PUBLIC; do not confuse it with a database role.
    with db.cursor() as c:
        c.execute("""SELECT count(*) FROM pg_namespace n,
                    LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) acl
                    WHERE n.nspname='mcp_v15' AND acl.grantee=0""")
        assert c.fetchone()[0] == 0
        c.execute("""SELECT count(*) FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace,
                    LATERAL aclexplode(coalesce(r.relacl,acldefault('r',r.relowner))) acl
                    WHERE n.nspname='mcp_v15' AND r.relkind IN ('r','p','v','m') AND acl.grantee=0""")
        assert c.fetchone()[0] == 0
        c.execute("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
                    LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
                    WHERE n.nspname='mcp_v15' AND acl.grantee=0""")
        assert c.fetchone()[0] == 0


def test_two_connections_cas_exactly_one_winner():
    # Setup is committed in isolated test DB to let independent sessions race.
    # Always remove setup records in finally. Does not modify frozen V1.4 DB.
    call, event = uuid.uuid4(), uuid.uuid4()
    seed = connect()
    try:
        with seed.cursor() as cur:
            cur.execute('SELECT mcp_v15.receive_call(%s,%s,%s,%s,%s,%s,%s)', (call,'test','p','test','1','c'*64,event))
        seed.commit()
        barrier = threading.Barrier(2)
        results = []
        errors = []
        def worker():
            conn = None
            try:
                conn = connect()
                barrier.wait(timeout=10)
                with conn.cursor() as cur:
                    cur.execute('SELECT mcp_v15.advance_call(%s,%s,%s,%s,%s)', (call,'RECEIVED',0,'AUTHORIZED',uuid.uuid4()))
                    result = cur.fetchone()[0]
                conn.commit()
                results.append(result)
            except Exception as exc:
                errors.append(repr(exc))
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=20)
        assert all(not t.is_alive() for t in threads), 'CAS worker timed out'
        assert not errors, errors
        assert sorted(results) == [False, True], results
        with seed.cursor() as cur:
            cur.execute('SELECT status,version FROM mcp_v15.tool_call_state WHERE call_id=%s', (call,))
            assert cur.fetchone() == ('AUTHORIZED',1)
            cur.execute('SELECT event_type FROM mcp_v15.tool_call_audit WHERE call_id=%s ORDER BY occurred_at,event_type', (call,))
            assert sorted(r[0] for r in cur.fetchall()) == ['AUTHORIZED','RECEIVED']
        seed.rollback()
    finally:
        # Audit is append-only, so do not attempt to delete committed test evidence.
        # Persistent test evidence is intentionally retained and clearly namespaced by call UUID.
        seed.close()
