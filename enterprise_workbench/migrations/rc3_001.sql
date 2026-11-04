-- RC3 additive migration; apply only to isolated test DB after RC2 migrations.
-- No modification to original 8 RC2 tables or to production database data.
CREATE TABLE IF NOT EXISTS version_b_rc2.mcp_call_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id text NOT NULL,
  actor_id text NOT NULL,
  tool_name text NOT NULL CHECK(tool_name IN ('mrp.get_run','workflow.get_command','reconciliation.get')),
  arguments_sha256 text NOT NULL CHECK(length(arguments_sha256)=64),
  request_id text NOT NULL DEFAULT '',
  outcome text NOT NULL CHECK(outcome='READ_SUCCESS'),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rc3_mcp_call_tenant_time
  ON version_b_rc2.mcp_call_audit(tenant_id,created_at DESC);
