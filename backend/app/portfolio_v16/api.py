"""V1.6 additive public read-only portfolio API. No DDL, no writes, no secret exposure."""
import os
import uuid
from decimal import Decimal
from datetime import date, datetime
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Query
from app.db.repository import connect

router = APIRouter(prefix="/api/v1/portfolio", tags=["V1.6 Portfolio (read only)"])
VERSION = "1.6"
# SQL identifiers and projected columns are hardcoded; never accept SQL from a caller.
SOURCES = {
 "mes/work-orders": ("mes_v13", "work_orders", "work_order_id, product_id, quantity, due_date, status, revision, created_at", "created_at DESC, work_order_id"),
 "srm/requisitions": ("srm_v14", "purchase_requisitions", "pr_id, source_run_id, material_id, quantity, uom, need_date, status, created_at", "created_at DESC, pr_id"),
 "srm/exceptions": ("srm_v14", "supply_exceptions", "exception_id, exception_type, risk_qty, late_days, status", "exception_id"),
 "mapping/versions": ("mapping_v14", "public_versions", "mapping_id, mapping_version, status, created_at", "created_at DESC, mapping_id"),
 "mapping/executions": ("mapping_v14", "public_executions", "execution_id, mapping_id, mapping_version, status, created_at", "created_at DESC, execution_id"),
}

def _error(code, status=503):
 raise HTTPException(status_code=status, detail={"code":code,"message":"Module is not available in this environment"})

def _query(key, limit):
 schema, table, columns, order = SOURCES[key]
 try:
  # A dedicated reader DSN is mandatory for live data. Never silently use DATABASE_URL owner.
  dsn=os.getenv("PORTFOLIO_READONLY_DATABASE_URL")
  if not dsn: _error("READONLY_READER_NOT_CONFIGURED")
  # Never attempt a connection to an unexpected login or a non-Neon endpoint.
  try:
   parts = urlsplit(dsn)
   if parts.scheme not in ("postgresql", "postgres") or parts.username != "portfolio_v16_api_limited":
    _error("DEDICATED_READER_REQUIRED")
   if not parts.hostname or not (parts.hostname == "neon.tech" or parts.hostname.endswith(".neon.tech")):
    _error("NEON_READER_HOST_REQUIRED")
  except ValueError:
   _error("INVALID_READER_DSN")
  with connect(dsn) as conn:
   with conn.cursor() as cur:
    cur.execute("SET TRANSACTION READ ONLY")
    cur.execute("SELECT current_user, session_user, pg_is_in_recovery(), current_setting('transaction_read_only')")
    actual_user, session_user, _, readonly = cur.fetchone()
    # Enforce dedicated least-privilege login, not a superuser/owner with SET ROLE.
    if actual_user in ("neondb_owner", "postgres") or session_user in ("neondb_owner", "postgres"):
     _error("OWNER_CONNECTION_FORBIDDEN")
    if actual_user != "portfolio_v16_api_limited" or session_user != "portfolio_v16_api_limited":
     _error("DEDICATED_READER_REQUIRED")
    if readonly != "on": _error("READ_ONLY_TRANSACTION_REQUIRED")
    # Verify the *login* role itself is unprivileged; group membership alone is insufficient.
    cur.execute("""SELECT r.rolcanlogin, r.rolsuper, r.rolcreatedb,
                          r.rolcreaterole, r.rolreplication, r.rolbypassrls,
                          pg_has_role(r.oid, 'neon_superuser', 'MEMBER'),
                          pg_has_role(r.oid, 'portfolio_v16_reader', 'USAGE')
                   FROM pg_roles r WHERE r.rolname = session_user""")
    identity = cur.fetchone()
    if not identity or not identity[0] or any(identity[1:7]):
     _error("PRIVILEGED_LOGIN_FORBIDDEN")
    if not identity[7]: _error("READER_ROLE_REQUIRED")
    cur.execute("SET LOCAL statement_timeout = '3000ms'")
    cur.execute("SELECT to_regclass(%s)", (f"{schema}.{table}",))
    if cur.fetchone()[0] is None: _error("MODULE_NOT_AVAILABLE")
    cur.execute(f"SELECT {columns} FROM {schema}.{table} ORDER BY {order} LIMIT %s",(limit,))
    names=[c.name for c in cur.description]
    rows=[{k:(v.isoformat() if hasattr(v,'isoformat') else str(v) if v is not None and not isinstance(v,(str,int,float,bool)) else v) for k,v in zip(names,row)} for row in cur.fetchall()]
    conn.rollback()
  return {"version":VERSION,"mode":"LIVE_READONLY","source":"neon_postgresql","data":{"items":rows,"limit":limit,"empty":not bool(rows)},"request_id":uuid.uuid4().hex}
 except HTTPException: raise
 except Exception: _error("READONLY_SOURCE_UNAVAILABLE")

@router.get("/capabilities")
def capabilities():
 # Readiness is deliberately conservative: DB existence alone is not proof of access.
 live=bool(os.getenv("PORTFOLIO_READONLY_DATABASE_URL"))
 return {"version":VERSION,"modules":[{"id":key,"mode":"READER_CONFIGURED_UNVERIFIED" if live else "NOT_CONFIGURED","enabled":live,"limitation":"Live access requires a restricted reader role and migrated schema; actual access verified per request"} for key in SOURCES]+[{"id":"mcp","mode":"EVIDENCE_ONLY","enabled":True,"limitation":"No anonymous gateway invocation"}]}

@router.get("/mes/work-orders")
def mes_orders(limit:int=Query(20,ge=1,le=100)):return _query("mes/work-orders",limit)
@router.get("/srm/requisitions")
def srm_requisitions(limit:int=Query(20,ge=1,le=100)):return _query("srm/requisitions",limit)
@router.get("/srm/exceptions")
def srm_exceptions(limit:int=Query(20,ge=1,le=100)):return _query("srm/exceptions",limit)
@router.get("/mapping/versions")
def mapping_versions(limit:int=Query(20,ge=1,le=100)):return _query("mapping/versions",limit)
@router.get("/mapping/executions")
def mapping_executions(limit:int=Query(20,ge=1,le=100)):return _query("mapping/executions",limit)

@router.get("/mcp/tools")
def mcp_tools():
 return {"version":VERSION,"mode":"EVIDENCE_ONLY","tools":[{"name":n,"resource_type":r} for n,r in [("mrp.get_run","MRP_RUN"),("wms.get_inventory","MATERIAL"),("mes.get_work_order","MES_WORK_ORDER"),("srm.list_requisitions","MRP_RUN"),("mapping.preview_b01","MRP_RUN")]],"live_invocation_enabled":False}

@router.get("/architecture")
def architecture():
 return {"version":VERSION,"components":["MRP","WMS","MES","SRM","Mapping","Workflow","Agent","MCP Gateway"],"boundaries":["public-readonly","trusted-gateway-only","separate-runtime-and-business-db-roles"]}

@router.get("/acceptance")
def acceptance():
 return {"version":VERSION,"evidence":[{"scope":"V1.5 five-tool E2E","environment":"local PostgreSQL 16","status":"USER_REPORTED_PASS","pg18_certified":False}],"deployment_status":"NOT_RELEASED"}
