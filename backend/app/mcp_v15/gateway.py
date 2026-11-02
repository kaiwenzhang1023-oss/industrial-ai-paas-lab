"""M1-02 closed-by-default gateway foundation. No business adapter execution.

Identity must come from a trusted launcher or a verified upstream authentication
boundary. Never accept identity claims from tool arguments.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import uuid
from .security import Identity

TOOL_NAMES = ('mrp.get_run','wms.get_inventory','mes.get_work_order','srm.list_requisitions','mapping.preview_b01')

@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str = '1.0'
    enabled: bool = False
    permission: str = 'read'

class Registry:
    def __init__(self):
        self._tools = {n: ToolSpec(n) for n in TOOL_NAMES}
    def list_tools(self):
        return tuple(self._tools.values())
    def get(self, name):
        return self._tools.get(name)
    def enabled(self, name):
        return bool(self.get(name) and self.get(name).enabled)

class Gateway:
    def __init__(self, registry=None):
        self.registry = registry or Registry()

    def submit(self, conn, identity: Identity, tool: str, arguments: dict, resource_type: str, resource_id: str):
        """Persist RECEIVED -> DENIED; no tool execution. Commit is caller-owned.

        Caller MUST use a DB connection with role mcp_v15_runtime_test and must
        authenticate identity out-of-band. No raw SQL or business adapter access.
        """
        if not isinstance(identity, Identity) or not identity.tenant_id or not identity.principal_id:
            raise ValueError('trusted identity required')
        if not isinstance(arguments, dict):
            raise ValueError('arguments must be a JSON object')
        spec = self.registry.get(tool)
        if spec is None:
            raise ValueError('unknown tool')
        payload = json.dumps(arguments,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        digest = sha256(payload.encode('utf-8')).hexdigest()
        call_id, received_event, denied_event = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute('SELECT mcp_v15.runtime_receive(%s,%s,%s,%s,%s,%s,%s)',
                        (call_id,identity.tenant_id,identity.principal_id,tool,spec.version,digest,received_event))
            # Deliberately fail closed even if grants exist: adapters are NOT enabled.
            cur.execute('SELECT mcp_v15.runtime_advance(%s,%s,%s,%s,%s)',
                        (call_id,'RECEIVED',0,'DENIED',denied_event))
            if cur.fetchone()[0] is not True:
                raise RuntimeError('state transition failed')
        return {'call_id':str(call_id),'status':'DENIED','reason':'TOOL_DISABLED'}
