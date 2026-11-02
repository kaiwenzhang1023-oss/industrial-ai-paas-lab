-- V1.5 TEST SECURITY DB ONLY; additive; no V1.4 business data mutation.
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'industrial_lab_v15_test' THEN RAISE EXCEPTION 'TEST SECURITY DB ONLY'; END IF;
 IF to_regclass('mcp_v15.tool_call_state') IS NULL THEN RAISE EXCEPTION 'MCP BASELINE MISSING'; END IF;
END $$;
CREATE TABLE IF NOT EXISTS mcp_v15.request_ledger (
 tenant_id text NOT NULL, principal_id text NOT NULL, request_id text NOT NULL,
 tool_id text NOT NULL, request_hash char(64) NOT NULL,
 status text NOT NULL CHECK(status IN ('IN_PROGRESS','DONE','UNKNOWN')),
 response_json jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,principal_id,request_id),
 CHECK ((status='DONE') = (response_json IS NOT NULL))
);
REVOKE ALL ON mcp_v15.request_ledger FROM PUBLIC;
ALTER TABLE mcp_v15.request_ledger ENABLE ROW LEVEL SECURITY;
-- Only the narrow runtime role gets INSERT, SELECT and UPDATE for idempotency.
GRANT SELECT, INSERT, UPDATE ON mcp_v15.request_ledger TO mcp_v15_runtime_test;
-- The runtime role is NOLOGIN; this policy permits the trusted runtime to use the
-- idempotency ledger. No other role inherits these permissions.
-- CREATE POLICY has no IF NOT EXISTS in PostgreSQL 16. Fail closed if an
-- existing policy differs: do not silently replace or widen permissions.
DO $policy$
DECLARE existing record;
BEGIN
 SELECT polcmd, polpermissive, polroles, pg_get_expr(polqual, polrelid) AS using_expr,
        pg_get_expr(polwithcheck, polrelid) AS check_expr
 INTO existing
 FROM pg_policy
 WHERE polrelid='mcp_v15.request_ledger'::regclass AND polname='ledger_runtime_test';
 IF NOT FOUND THEN
  CREATE POLICY ledger_runtime_test ON mcp_v15.request_ledger
    TO mcp_v15_runtime_test USING (true) WITH CHECK (true);
 ELSIF existing.polcmd <> '*' OR NOT existing.polpermissive
   OR existing.polroles <> ARRAY[(SELECT oid FROM pg_roles WHERE rolname='mcp_v15_runtime_test')]
   OR existing.using_expr <> 'true' OR existing.check_expr <> 'true' THEN
  RAISE EXCEPTION 'ledger_runtime_test existing policy differs; manual review required';
 END IF;
END $policy$;
CREATE INDEX IF NOT EXISTS idx_v15_ledger_pending ON mcp_v15.request_ledger(updated_at)
 WHERE status='IN_PROGRESS';
COMMIT;
