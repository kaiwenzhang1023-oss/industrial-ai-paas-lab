"""V1.6 API smoke tests; no live DB connection."""
import os
from fastapi.testclient import TestClient
from app.main import app

def test_metadata_routes(monkeypatch):
 monkeypatch.delenv("PORTFOLIO_READONLY_DATABASE_URL",raising=False)
 client=TestClient(app)
 for path in ("capabilities","mcp/tools","architecture","acceptance"):
  response=client.get("/api/v1/portfolio/"+path)
  assert response.status_code==200
  assert response.json()["version"]=="1.6"
 assert client.get("/api/v1/portfolio/mcp/tools").json()["live_invocation_enabled"] is False

def test_live_routes_fail_closed_without_reader(monkeypatch):
 monkeypatch.delenv("PORTFOLIO_READONLY_DATABASE_URL",raising=False)
 client=TestClient(app)
 for path in ("mes/work-orders","srm/requisitions","srm/exceptions","mapping/versions","mapping/executions"):
  response=client.get("/api/v1/portfolio/"+path)
  assert response.status_code==503
  assert response.json()["detail"]["code"]=="READONLY_READER_NOT_CONFIGURED"
 assert client.get("/api/v1/portfolio/mes/work-orders?limit=101").status_code==422

def test_public_post_denied(monkeypatch):
 monkeypatch.setenv("PUBLIC_READ_ONLY","1")
 client=TestClient(app)
 assert client.post("/api/v1/portfolio/mes/work-orders").status_code==403
