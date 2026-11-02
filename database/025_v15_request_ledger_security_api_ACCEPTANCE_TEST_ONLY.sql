-- C4.4 live PostgreSQL 16 acceptance. Run only on industrial_lab_v15_test.
DO $$
DECLARE db_name text; ver integer; v_action text; v_response jsonb; req text;
BEGIN
 SELECT current_database(),current_setting('server_version_num')::integer INTO db_name,ver;
 IF db_name <> 'industrial_lab_v15_test' OR ver < 160000 OR ver >= 170000 THEN
  RAISE EXCEPTION 'PG16_TEST_DATABASE_REQUIRED: db=%, version=%',db_name,ver;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcp_v15_ledger_owner_test' AND NOT rolsuper AND NOT rolcanlogin AND NOT rolbypassrls) THEN
  RAISE EXCEPTION 'UNSAFE_LEDGER_OWNER_ROLE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcp_v15_ledger_operator_test' AND NOT rolsuper AND NOT rolcanlogin AND NOT rolbypassrls) THEN
  RAISE EXCEPTION 'UNSAFE_LEDGER_OPERATOR_ROLE';
 END IF;
 IF has_table_privilege('mcp_v15_runtime_test','mcp_v15.request_ledger','SELECT')
    OR has_table_privilege('mcp_v15_runtime_test','mcp_v15.request_ledger','INSERT')
    OR has_table_privilege('mcp_v15_runtime_test','mcp_v15.request_ledger','UPDATE') THEN
  RAISE EXCEPTION 'RUNTIME_HAS_DIRECT_LEDGER_PRIVILEGES';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='mcp_v15' AND tablename='request_ledger' AND 'mcp_v15_runtime_test'=ANY(roles)) THEN
  RAISE EXCEPTION 'RUNTIME_LEDGER_POLICY_STILL_PRESENT';
 END IF;
 IF (SELECT r.rolsuper OR r.rolcanlogin OR r.rolbypassrls FROM pg_roles r WHERE r.rolname='mcp_v15_ledger_owner_test') THEN
  RAISE EXCEPTION 'LEDGER_OWNER_ROLE_ATTRIBUTE_FAILURE';
 END IF;
 req := 'C44-' || replace(gen_random_uuid()::text,'-','');

 -- Function owner must be the dedicated non-login role, not lab/superuser.
 IF (SELECT pg_get_userbyid(p.proowner) FROM pg_proc p
     WHERE p.pronamespace='mcp_v15'::regnamespace AND p.proname='ledger_claim')
     <> 'mcp_v15_ledger_owner_test' THEN
  RAISE EXCEPTION 'LEDGER_FUNCTION_OWNER_MISMATCH';
 END IF;

 SET LOCAL ROLE mcp_v15_runtime_test;
 SELECT action,response_json INTO v_action,v_response
 FROM mcp_v15.ledger_claim('c44-tenant','c44-principal',req,'mrp.get_run',repeat('a',64)::char(64));
 IF v_action <> 'NEW' OR v_response IS NOT NULL THEN RAISE EXCEPTION 'CLAIM_NEW_FAILED'; END IF;
 SELECT action,response_json INTO v_action,v_response
 FROM mcp_v15.ledger_claim('c44-tenant','c44-principal',req,'mrp.get_run',repeat('a',64)::char(64));
 IF v_action <> 'IN_PROGRESS' THEN RAISE EXCEPTION 'CLAIM_DUPLICATE_NOT_BLOCKED'; END IF;
 IF mcp_v15.ledger_finish('c44-tenant','c44-principal',req,'mrp.get_run',repeat('a',64)::char(64),'{"ok":true}'::jsonb) IS NOT TRUE THEN
  RAISE EXCEPTION 'LEDGER_FINISH_FAILED';
 END IF;
 SELECT action,response_json INTO v_action,v_response
 FROM mcp_v15.ledger_claim('c44-tenant','c44-principal',req,'mrp.get_run',repeat('a',64)::char(64));
 IF v_action <> 'DONE' OR v_response <> '{"ok":true}'::jsonb THEN RAISE EXCEPTION 'CACHED_RESULT_FAILED'; END IF;
 BEGIN
  PERFORM * FROM mcp_v15.ledger_claim('c44-tenant','c44-principal',req,'mrp.get_run',repeat('b',64)::char(64));
  RAISE EXCEPTION 'IDEMPOTENCY_CONFLICT_NOT_REJECTED';
 EXCEPTION WHEN unique_violation THEN NULL;
 END;
 BEGIN
  PERFORM 1 FROM mcp_v15.request_ledger LIMIT 1;
  RAISE EXCEPTION 'RUNTIME_DIRECT_READ_NOT_DENIED';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 RESET ROLE;

 SET LOCAL ROLE mcp_v15_ledger_operator_test;
 BEGIN
  PERFORM 1 FROM mcp_v15.request_ledger LIMIT 1;
  RAISE EXCEPTION 'OPERATOR_DIRECT_READ_NOT_DENIED';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 PERFORM 1 FROM mcp_v15.ledger_inspect_stale(300,10);
 RESET ROLE;

 DELETE FROM mcp_v15.request_ledger
 WHERE tenant_id='c44-tenant' AND principal_id='c44-principal' AND request_id=req;
 RAISE NOTICE 'C44_PG16_LEDGER_SECURITY_ACCEPTANCE_PASSED';
END $$;
