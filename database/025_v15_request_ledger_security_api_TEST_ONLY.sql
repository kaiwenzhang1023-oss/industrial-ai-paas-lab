-- C4.4: close direct request-ledger table access; use narrow SECURITY DEFINER APIs.
-- TEST DATABASE ONLY. Additive forward migration; never run on production.
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'industrial_lab_v15_test' THEN
  RAISE EXCEPTION 'C4.4 TEST SECURITY DB ONLY';
 END IF;
 IF to_regclass('mcp_v15.request_ledger') IS NULL THEN
  RAISE EXCEPTION 'V15 REQUEST LEDGER BASELINE MISSING';
 END IF;
END $$;

DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcp_v15_ledger_owner_test') THEN
  CREATE ROLE mcp_v15_ledger_owner_test NOLOGIN NOBYPASSRLS;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcp_v15_ledger_operator_test') THEN
  CREATE ROLE mcp_v15_ledger_operator_test NOLOGIN NOBYPASSRLS;
 END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcp_v15_ledger_owner_test'
            AND (rolcanlogin OR rolsuper OR rolbypassrls)) THEN
  RAISE EXCEPTION 'LEDGER OWNER ROLE ATTRIBUTES UNSAFE';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcp_v15_ledger_operator_test'
            AND (rolcanlogin OR rolsuper OR rolbypassrls)) THEN
  RAISE EXCEPTION 'LEDGER OPERATOR ROLE ATTRIBUTES UNSAFE';
 END IF;
END $$;

GRANT USAGE ON SCHEMA mcp_v15 TO mcp_v15_ledger_owner_test, mcp_v15_ledger_operator_test;
-- PostgreSQL requires the new owner to hold CREATE on the containing schema during ALTER OWNER.
GRANT CREATE ON SCHEMA mcp_v15 TO mcp_v15_ledger_owner_test;
GRANT SELECT, INSERT, UPDATE ON mcp_v15.request_ledger TO mcp_v15_ledger_owner_test;
REVOKE ALL ON mcp_v15.request_ledger FROM mcp_v15_runtime_test, mcp_v15_reader_test, PUBLIC;

-- Remove only the exact broad policy created by historical migration 020.
DO $policy$
DECLARE p record;
BEGIN
 SELECT polcmd, polpermissive, polroles,
        pg_get_expr(polqual,polrelid) AS using_expr,
        pg_get_expr(polwithcheck,polrelid) AS check_expr
 INTO p FROM pg_policy
 WHERE polrelid='mcp_v15.request_ledger'::regclass AND polname='ledger_runtime_test';
 IF FOUND THEN
  IF p.polcmd <> '*' OR NOT p.polpermissive
     OR p.polroles <> ARRAY[(SELECT oid FROM pg_roles WHERE rolname='mcp_v15_runtime_test')]
     OR p.using_expr <> 'true' OR p.check_expr <> 'true' THEN
   RAISE EXCEPTION 'ledger_runtime_test policy differs; manual review required';
  END IF;
  DROP POLICY ledger_runtime_test ON mcp_v15.request_ledger;
 END IF;
END $policy$;

-- Table owner is not the function owner. RLS remains active for the NOLOGIN function role.
DO $policy$
DECLARE p record;
BEGIN
 SELECT polcmd, polpermissive, polroles,
        pg_get_expr(polqual,polrelid) AS using_expr,
        pg_get_expr(polwithcheck,polrelid) AS check_expr
 INTO p FROM pg_policy
 WHERE polrelid='mcp_v15.request_ledger'::regclass AND polname='ledger_owner_test';
 IF NOT FOUND THEN
  CREATE POLICY ledger_owner_test ON mcp_v15.request_ledger
   TO mcp_v15_ledger_owner_test USING (true) WITH CHECK (true);
 ELSIF p.polcmd <> '*' OR NOT p.polpermissive
    OR p.polroles <> ARRAY[(SELECT oid FROM pg_roles WHERE rolname='mcp_v15_ledger_owner_test')]
    OR p.using_expr <> 'true' OR p.check_expr <> 'true' THEN
  RAISE EXCEPTION 'ledger_owner_test policy differs; manual review required';
 END IF;
END $policy$;

CREATE OR REPLACE FUNCTION mcp_v15.ledger_claim(
 p_tenant text,p_principal text,p_request_id text,p_tool text,p_hash char(64))
RETURNS TABLE(action text,response_json jsonb)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,mcp_v15 AS $$
DECLARE inserted_count integer; existing_hash char(64); existing_status text; existing_response jsonb;
BEGIN
 IF p_tenant IS NULL OR length(p_tenant) NOT BETWEEN 1 AND 128
    OR p_principal IS NULL OR length(p_principal) NOT BETWEEN 1 AND 128
    OR p_request_id IS NULL OR length(p_request_id) NOT BETWEEN 1 AND 128
    OR p_tool IS NULL OR length(p_tool) NOT BETWEEN 1 AND 128
    OR p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'INVALID_LEDGER_CLAIM';
 END IF;
 INSERT INTO mcp_v15.request_ledger(tenant_id,principal_id,request_id,tool_id,request_hash,status)
 VALUES(p_tenant,p_principal,p_request_id,p_tool,p_hash,'IN_PROGRESS')
 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted_count = ROW_COUNT;
 IF inserted_count=1 THEN
  RETURN QUERY SELECT 'NEW'::text,NULL::jsonb; RETURN;
 END IF;
 SELECT l.request_hash,l.status,l.response_json
 INTO existing_hash,existing_status,existing_response
 FROM mcp_v15.request_ledger l
 WHERE l.tenant_id=p_tenant AND l.principal_id=p_principal AND l.request_id=p_request_id
 FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'LEDGER_READ_FAILED'; END IF;
 IF existing_hash<>p_hash THEN RAISE EXCEPTION 'REQUEST_ID_CONFLICT' USING ERRCODE='23505'; END IF;
 IF existing_status='DONE' THEN
  RETURN QUERY SELECT 'DONE'::text,existing_response;
 ELSIF existing_status='IN_PROGRESS' THEN
  RETURN QUERY SELECT 'IN_PROGRESS'::text,NULL::jsonb;
 ELSE
  RETURN QUERY SELECT 'UNKNOWN'::text,NULL::jsonb;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION mcp_v15.ledger_finish(
 p_tenant text,p_principal text,p_request_id text,p_tool text,p_hash char(64),p_response jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,mcp_v15 AS $$
DECLARE changed integer;
BEGIN
 IF p_tenant IS NULL OR p_principal IS NULL OR p_request_id IS NULL OR p_tool IS NULL
    OR p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$' OR p_response IS NULL THEN
  RAISE EXCEPTION 'INVALID_LEDGER_FINISH';
 END IF;
 UPDATE mcp_v15.request_ledger
 SET status='DONE',response_json=p_response,updated_at=now()
 WHERE tenant_id=p_tenant AND principal_id=p_principal AND request_id=p_request_id
   AND tool_id=p_tool AND request_hash=p_hash AND status='IN_PROGRESS';
 GET DIAGNOSTICS changed = ROW_COUNT;
 RETURN changed=1;
END $$;

CREATE OR REPLACE FUNCTION mcp_v15.ledger_inspect_stale(p_threshold integer,p_limit integer)
RETURNS TABLE(tenant_id text,principal_id text,request_id text,status text,age_seconds double precision)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,mcp_v15 AS $$
BEGIN
 IF p_threshold IS NULL OR p_limit IS NULL OR p_threshold NOT BETWEEN 1 AND 86400 OR p_limit NOT BETWEEN 1 AND 500 THEN
  RAISE EXCEPTION 'INVALID_RECOVERY_BOUNDS';
 END IF;
 RETURN QUERY SELECT l.tenant_id,l.principal_id,l.request_id,l.status,
  EXTRACT(EPOCH FROM (clock_timestamp()-l.updated_at))::double precision
 FROM mcp_v15.request_ledger l
 WHERE l.status IN ('IN_PROGRESS','UNKNOWN')
   AND l.updated_at < clock_timestamp()-(p_threshold * interval '1 second')
 ORDER BY l.updated_at LIMIT p_limit;
END $$;

ALTER FUNCTION mcp_v15.ledger_claim(text,text,text,text,char(64)) OWNER TO mcp_v15_ledger_owner_test;
ALTER FUNCTION mcp_v15.ledger_finish(text,text,text,text,char(64),jsonb) OWNER TO mcp_v15_ledger_owner_test;
ALTER FUNCTION mcp_v15.ledger_inspect_stale(integer,integer) OWNER TO mcp_v15_ledger_owner_test;
REVOKE CREATE ON SCHEMA mcp_v15 FROM mcp_v15_ledger_owner_test;
REVOKE ALL ON FUNCTION mcp_v15.ledger_claim(text,text,text,text,char(64)) FROM PUBLIC;
REVOKE ALL ON FUNCTION mcp_v15.ledger_finish(text,text,text,text,char(64),jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION mcp_v15.ledger_inspect_stale(integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mcp_v15.ledger_claim(text,text,text,text,char(64)) TO mcp_v15_runtime_test;
GRANT EXECUTE ON FUNCTION mcp_v15.ledger_finish(text,text,text,text,char(64),jsonb) TO mcp_v15_runtime_test;
GRANT EXECUTE ON FUNCTION mcp_v15.ledger_inspect_stale(integer,integer) TO mcp_v15_ledger_operator_test;
GRANT mcp_v15_ledger_operator_test TO CURRENT_USER;
COMMIT;
