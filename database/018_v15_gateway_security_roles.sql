-- V1.5 M1-01 FINAL + M1-02: TEST ONLY; additive, non-destructive.
-- Execute as existing DB owner 'lab' on industrial_lab_v15_test.
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'industrial_lab_v15_test' THEN RAISE EXCEPTION 'TEST DB ONLY'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='mcp_v15') THEN RAISE EXCEPTION '017 baseline missing'; END IF;
END $$;
-- NOLOGIN roles prevent direct authentication; tests use SET ROLE as lab, never production.
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='mcp_v15_reader_test') THEN CREATE ROLE mcp_v15_reader_test NOLOGIN NOBYPASSRLS; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='mcp_v15_runtime_test') THEN CREATE ROLE mcp_v15_runtime_test NOLOGIN NOBYPASSRLS; END IF;
END $$;
GRANT mcp_v15_reader_test, mcp_v15_runtime_test TO CURRENT_USER;
REVOKE ALL ON SCHEMA mcp_v15 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA mcp_v15 FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA mcp_v15 FROM PUBLIC;
GRANT USAGE ON SCHEMA mcp_v15 TO mcp_v15_reader_test, mcp_v15_runtime_test;
-- No direct table permissions for either role; authorization is via narrow definer functions.
CREATE OR REPLACE FUNCTION mcp_v15.authorize_runtime(p_tenant text,p_principal text,p_permission text,p_type text,p_id text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT mcp_v15.is_authorized(p_tenant,p_principal,p_permission,p_type,p_id);
$$;
REVOKE ALL ON FUNCTION mcp_v15.authorize_runtime(text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mcp_v15.authorize_runtime(text,text,text,text,text) TO mcp_v15_runtime_test;
-- State changes are restricted to a dedicated runtime role; no direct DML grants.
CREATE OR REPLACE FUNCTION mcp_v15.runtime_receive(p_call uuid,p_tenant text,p_principal text,p_tool text,p_version text,p_hash char(64),p_event uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF p_tenant IS NULL OR p_principal IS NULL OR p_tool IS NULL OR length(trim(p_tenant))=0 OR length(trim(p_principal))=0 OR length(trim(p_tool))=0 THEN RAISE EXCEPTION 'missing identity/tool'; END IF;
 PERFORM mcp_v15.receive_call(p_call,p_tenant,p_principal,p_tool,p_version,p_hash,p_event);
END $$;
CREATE OR REPLACE FUNCTION mcp_v15.runtime_advance(p_call uuid,p_expected text,p_version integer,p_next text,p_event uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN RETURN mcp_v15.advance_call(p_call,p_expected,p_version,p_next,p_event); END $$;
REVOKE ALL ON FUNCTION mcp_v15.runtime_receive(uuid,text,text,text,text,char(64),uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION mcp_v15.runtime_advance(uuid,text,integer,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mcp_v15.runtime_receive(uuid,text,text,text,text,char(64),uuid) TO mcp_v15_runtime_test;
GRANT EXECUTE ON FUNCTION mcp_v15.runtime_advance(uuid,text,integer,text,uuid) TO mcp_v15_runtime_test;
-- Restrict legacy invoker functions as well, including future default grants.
REVOKE ALL ON FUNCTION mcp_v15.receive_call(uuid,text,text,text,text,char(64),uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION mcp_v15.advance_call(uuid,text,integer,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION mcp_v15.is_authorized(text,text,text,text,text) FROM PUBLIC;
-- RLS is defense-in-depth; ownership and SECURITY DEFINER require careful trust boundary.
ALTER TABLE mcp_v15.principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_v15.principal_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_v15.resource_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_v15.resource_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_v15.tool_call_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_v15.tool_call_audit ENABLE ROW LEVEL SECURITY;
-- No policies for low-privilege roles: deny by default. Owner is intentionally not FORCE-RLS,
-- because narrowly exposed SECURITY DEFINER functions must still access governance data.
COMMIT;
