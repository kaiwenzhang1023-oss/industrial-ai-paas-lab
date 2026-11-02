"""Static contract checks: NOT a replacement for real PostgreSQL integration."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA=(ROOT/'database/schema.sql').read_text()
REPO=(ROOT/'backend/app/db/repository.py').read_text()
API=(ROOT/'backend/app/main.py').read_text()

def test_schema_separates_authorities():
    for schema in ('mock_erp','mock_wms','mock_mes','platform','audit'):
        assert f'CREATE SCHEMA IF NOT EXISTS {schema}' in SCHEMA

def test_persistence_has_run_and_pegging_tables():
    migration=(ROOT/'database/003_v03.sql').read_text()
    assert 'platform.requirement_runs' in SCHEMA
    assert 'platform.material_requirements' in SCHEMA
    assert 'platform.requirement_pegs' in migration

def test_repository_uses_parameterized_sql():
    assert 'cur.execute(' in REPO
    assert '%s' in REPO
    assert 'with conn.transaction()' in REPO

def test_db_api_no_json_fallback():
    assert '/api/v1/db/mrp/runs' in API
    assert 'db_calculate_and_save' in API
    assert 'DATABASE_OR_PERSISTENCE_ERROR' in API

def test_contract_has_idempotency_key():
    assert 'idempotency_key text UNIQUE NOT NULL' in SCHEMA
    assert 'request_hash text NOT NULL' in SCHEMA
