"""RC2 public read-only middleware regression; no database access required."""
from fastapi.testclient import TestClient
from app.main import app

def test_v14_public_readonly_blocks_all_mutating_verbs(monkeypatch):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    monkeypatch.setenv("DEMO_WRITE_ENABLED", "0")
    with TestClient(app) as client:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = client.request(method, "/api/v1/srm/requisitions/import-mrp", json={"run_id": "RC2-NEVER-WRITE"})
            assert response.status_code == 403, (method, response.text)
            assert response.json()["detail"]["code"] == "PUBLIC_DEMO_READ_ONLY"
