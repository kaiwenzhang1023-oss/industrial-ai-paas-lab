from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.workbench import require_operator
import pytest
from fastapi import HTTPException


def test_cloud_readonly_default(monkeypatch):
    monkeypatch.delenv('DEMO_WRITE_ENABLED',raising=False)
    monkeypatch.delenv('DEMO_OPERATOR_KEY',raising=False)
    response=TestClient(app).post('/api/v1/workbench/workflows',json={'order_id':'SO-2026-001'})
    assert response.status_code==403
    assert response.json()['detail']['code']=='DEMO_WRITE_DISABLED'


def test_operator_key(monkeypatch):
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','private')
    with pytest.raises(HTTPException) as exc:
        require_operator('wrong')
    assert exc.value.status_code==403
    require_operator('private')


def test_v1_static_provenance_and_receipt_contract():
    root=Path(__file__).resolve().parents[2]
    js=(root/'backend/app/web/app.js').read_text(encoding='utf-8')
    assert 'd.provenance' in js
    assert '已分配供给量' in js
    assert 'd.pegs.map' not in js
    assert (root/'database/012_outbox_receipts.sql').is_file()
    assert 'PUBLIC_READ_ONLY=1' in (root/'Dockerfile').read_text()


def test_public_cloud_perimeter_blocks_legacy_mutations(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY','1')
    response=TestClient(app).post('/api/v1/db/mrp/runs')
    assert response.status_code==403
    assert response.json()['detail']['code']=='PUBLIC_DEMO_READ_ONLY'
    monkeypatch.delenv('PUBLIC_READ_ONLY',raising=False)
