"""One-shot, manual-only bootstrap for *dedicated* Version B preview database.
Never run at import/startup and never connect to a prior V1.8 shared DB.
Usage: python -m preview_cloud.bootstrap (prompts for DSN via getpass)
"""
from __future__ import annotations
import getpass
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
SQL=(ROOT/'database'/'schema.sql',ROOT/'database'/'003_v03.sql',
     ROOT/'database'/'004_snapshot_fence.sql',
     ROOT/'enterprise_workbench'/'migrations'/'rc2_001.sql',
     ROOT/'enterprise_workbench'/'migrations'/'rc2_002.sql',
     ROOT/'enterprise_workbench'/'migrations'/'rc3_001.sql')


def main():
    import psycopg
    expected='industrial_v19b_preview'
    dsn=getpass.getpass('Neon VERSION B isolated preview connection URL (hidden): ').strip()
    if not dsn:raise SystemExit('HOLD: DSN was not supplied')
    parts=urlsplit(dsn)
    if parts.scheme not in ('postgresql','postgres') or parts.path.lstrip('/')!=expected:
        raise SystemExit('HOLD: database name not exactly '+expected)
    if not (parts.hostname or '').endswith('.neon.tech'):
        raise SystemExit('HOLD: only Neon endpoint accepted')
    if parts.query.find('sslmode=require')<0 and parts.query.find('sslmode=verify-full')<0:
        raise SystemExit('HOLD: sslmode=require or verify-full needed in DSN')
    print('TARGET_DATABASE_VERIFIED='+expected)
    print('MIGRATION_COUNT='+str(len(SQL)))
    with psycopg.connect(dsn) as conn:
        name=conn.execute('select current_database()').fetchone()[0]
        if name!=expected:raise SystemExit('HOLD: connected database mismatch')
        with conn.transaction():
            for p in SQL:
                print('APPLY='+str(p.relative_to(ROOT)))
                conn.execute(p.read_text(encoding='utf-8'))
        from app.db.repository import seed
        n=seed(conn,ROOT/'datasets'/'seed'/'multi_order.json')
        print('SEED_ORDERS_ITEMS='+repr(n))
        row=conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='version_b_rc2'").fetchone()
        if row[0]!=9:raise SystemExit('HOLD: expected nine Version B tables, got '+str(row[0]))
        print('VERSION_B_TABLES=9')
    print('NEON_PREVIEW_BOOTSTRAP=PASS')

if __name__=='__main__':main()
