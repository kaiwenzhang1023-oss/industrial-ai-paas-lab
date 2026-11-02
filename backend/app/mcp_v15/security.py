"""Fail-closed authorization facade; no tool registry or business adapter enabled."""
from dataclasses import dataclass

TOOLS = {name: False for name in ("mrp.get_run", "wms.get_inventory", "mes.get_work_order", "srm.list_requisitions", "mapping.preview_b01")}

@dataclass(frozen=True)
class Identity:
    tenant_id: str
    principal_id: str

def authorize(conn, identity: Identity, permission: str, resource_type: str, resource_id: str) -> bool:
    if not all((identity.tenant_id, identity.principal_id, permission, resource_type, resource_id)):
        return False
    with conn.cursor() as cur:
        cur.execute("SELECT mcp_v15.is_authorized(%s,%s,%s,%s,%s)", (identity.tenant_id, identity.principal_id, permission, resource_type, resource_id))
        row = cur.fetchone()
    return bool(row and row[0])

def tool_enabled(name: str) -> bool:
    return TOOLS.get(name, False)
