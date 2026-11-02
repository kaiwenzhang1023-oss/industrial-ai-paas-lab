"""M1-03 static/contract gates without live PG16."""
import ast
from pathlib import Path
import pytest
from app.mapping.errors import MappingFailure
from app.mapping.fingerprints import sha256
from app.mapping.contracts import B01_MAPPING_ID,B01_VERSION

ROOT=Path(__file__).resolve().parents[3]

def test_mapping_persistence_only_mapping_schema():
    src=(ROOT/'backend/app/mapping/persistence.py').read_text()
    assert 'srm_v14.' not in src and 'mock_erp.' not in src
    assert 'platform.' not in src and 'mock_mes.' not in src
    assert 'import_mrp(' not in src
    tree=ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str):
            if any(x in n.value.upper() for x in ('TRUNCATE ','DELETE FROM ','UPDATE SRM_','INSERT INTO SRM_')):
                pytest.fail('Forbidden business SQL')

def test_ddl_is_additive_and_isolated():
    sql=(ROOT/'database/016_v14_mapping_batch_b.sql').read_text()
    assert 'CREATE SCHEMA IF NOT EXISTS mapping_v14' in sql
    for table in ('mapping_versions','execution_runs','execution_errors','audit_events'):
        assert 'CREATE TABLE IF NOT EXISTS mapping_v14.'+table in sql
    for business in ('srm_v14.','mock_erp.','mock_wms.','platform.','mes_v13.'):
        assert business not in sql
    assert 'MAPPING_IMMUTABLE_RECORD' in sql
    assert 'public_executions' in sql

def test_ledger_hash_distinguishes_payload():
    a={'execution_id':'e1','request':{'source_result_hash':'A'}}
    b={'execution_id':'e1','request':{'source_result_hash':'B'}}
    assert sha256(a)!=sha256(b)

def test_replay_and_idempotency_implemented():
    src=(ROOT/'backend/app/mapping/persistence.py').read_text()
    assert 'pg_advisory_xact_lock' in src
    assert 'EXECUTION_IDEMPOTENCY_CONFLICT' in src
    assert 'replay_preview' in src
    assert 'SOURCE_FINGERPRINT_MISMATCH' in src
    assert 'INSERT INTO mapping_v14.audit_events' in src
