"""Version B RC1 same-origin RC8 UX integration boundary.

This module serves a frozen static UI and exposes an explicit capabilities contract.
It does not claim browser simulations are PostgreSQL transactions.
"""
from pathlib import Path
from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
CAPABILITIES = {
    "edition": "Version B",
    "candidate": "RC4_G4_CANDIDATE",
    "ui_baseline": "Version A V1.9.1 RC8",
    "ui_execution": "RC8_BROWSER_SIMULATION_PLUS_EXPLICIT_ENTERPRISE_PANEL",
    "server_persistence": "RC2_G2_REAL_POSTGRESQL_VALIDATED_IN_ISOLATED_PG16_ON_2026_11_04",
    "postgresql": "G2_ISOLATED_DB_PASS_NOT_PRODUCTION_DEPLOYMENT",
    "workflow_execution": "G2_INTERNAL_WORKER_TESTS_34_OF_34_PASS",
    "approval_execution": "G2_ISOLATED_PG16_APPROVAL_TEST_PASS",
    "mcp_execution": "G3_MCP_STDIO_PLUS_AUTH_HTTP_ADAPTER_35_OF_35_PASS",
    "tenant_isolation": "G3_PG16_MCP_TENANT_TEST_PASS",
    "production_ready": False,
}
router = APIRouter(prefix="/api/v1/version-b", tags=["Version B integration"])

@router.get("/capabilities")
def capabilities():
    return CAPABILITIES.copy()

from .rc2 import router as rc2_router
from .rc4 import router as rc4_router

def install(app):
    app.include_router(rc2_router)
    app.include_router(rc4_router)
    app.include_router(router)
    app.mount("/workbench", StaticFiles(directory=str(ROOT / "site"), html=True), name="version_b_workbench")
