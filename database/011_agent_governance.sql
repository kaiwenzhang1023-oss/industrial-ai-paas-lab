BEGIN;
CREATE TABLE IF NOT EXISTS platform.agent_tool_audit (
 audit_id BIGSERIAL PRIMARY KEY,
 workflow_id TEXT NOT NULL REFERENCES platform.workflow_instances(instance_id),
 trace_id TEXT NOT NULL DEFAULT '',
 principal TEXT NOT NULL,
 tool_name TEXT NOT NULL,
 policy_version TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK (outcome IN ('ALLOWED','DENIED','ERROR')),
 reason_code TEXT NOT NULL,
 args_hash TEXT,
 result_hash TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_tool_audit_workflow_idx ON platform.agent_tool_audit(workflow_id,audit_id);
COMMIT;
