"""Optional LIVE Neon PG18 reader gate. No credentials stored or printed.
Run only with an isolated dev branch URL in PORTFOLIO_READONLY_DATABASE_URL.
Never point this tool at production. Does not modify any database objects.
"""
import os
import sys
from urllib.parse import urlsplit

EXPECTED_USER = "portfolio_v16_api_limited"
SOURCES = [
    "mes_v13.work_orders", "srm_v14.purchase_requisitions",
    "srm_v14.supply_exceptions", "mapping_v14.public_versions",
    "mapping_v14.public_executions",
]


def main():
    dsn = os.environ.get("PORTFOLIO_READONLY_DATABASE_URL", "")
    if not dsn:
        print("BLOCKED: PORTFOLIO_READONLY_DATABASE_URL not configured")
        return 2
    parts = urlsplit(dsn)
    if parts.username != EXPECTED_USER or not parts.hostname or not parts.hostname.endswith(".neon.tech"):
        print("BLOCKED: expected dedicated Neon reader login")
        return 2
    # The host alone cannot prove branch identity; operator must check Neon UI.
    if os.environ.get("V16_DEV_BRANCH_CONFIRMED") != "dev-v1-6-backend-pg18":
        print("BLOCKED: explicit dev branch confirmation required")
        return 2
    import psycopg
    try:
        with psycopg.connect(dsn, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT current_user, session_user, current_setting('server_version_num')::int")
                user, session, version = cur.fetchone()
                if user != EXPECTED_USER or session != EXPECTED_USER or version // 10000 != 18:
                    raise RuntimeError("identity or server version mismatch")
                cur.execute("""SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                                      rolreplication, rolbypassrls,
                                      pg_has_role(oid,'neon_superuser','MEMBER')
                               FROM pg_roles WHERE rolname=current_user""")
                attrs = cur.fetchone()
                if not attrs or attrs[0] is not True or any(attrs[1:]):
                    raise RuntimeError("privileged login detected")
                for schema in ("mes_v13", "srm_v14", "mapping_v14"):
                    cur.execute("SELECT has_schema_privilege(current_user, %s, 'CREATE')", (schema,))
                    if cur.fetchone()[0]:
                        raise RuntimeError("unexpected schema CREATE privilege")
                for table in SOURCES:
                    cur.execute("SELECT has_table_privilege(current_user, %s, 'SELECT')", (table,))
                    if cur.fetchone()[0] is not True:
                        raise RuntimeError("read permission denied for " + table)
                cur.execute("SELECT has_table_privilege(current_user, 'mapping_v14.mapping_versions', 'SELECT')")
                if cur.fetchone()[0]:
                    raise RuntimeError("mapping base table unexpectedly readable")
                cur.execute("SELECT has_table_privilege(current_user, 'mes_v13.work_orders', 'INSERT')")
                if cur.fetchone()[0]:
                    raise RuntimeError("MES write privilege unexpectedly granted")
                for table in SOURCES:
                    cur.execute("SELECT count(*) FROM (SELECT 1 FROM " + table + " LIMIT 1) AS probe")
            conn.rollback()
        print("PASS: PG18 live reader identity, 5 reads, privilege boundaries")
        return 0
    except Exception as exc:
        # Do not print exception strings: some drivers include DSN details.
        print("FAIL: live reader gate failed (inspect local secure logs)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
