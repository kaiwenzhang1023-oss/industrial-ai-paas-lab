-- TEST-ONLY additive runtime recovery, on industrial_lab_v15_test.
BEGIN;
DO $$ BEGIN IF current_database()<>'industrial_lab_v15_test' THEN RAISE EXCEPTION 'V15 TEST DATABASE ONLY'; END IF; END $$;
CREATE OR REPLACE FUNCTION mcp_v15.runtime_stale_running(p_age integer)
RETURNS TABLE(call_id uuid, version integer) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF p_age<1 OR p_age>86400 THEN RAISE EXCEPTION 'invalid age'; END IF;
 RETURN QUERY SELECT s.call_id,s.version FROM mcp_v15.tool_call_state s
 WHERE s.status='RUNNING' AND s.updated_at < clock_timestamp() - make_interval(secs=>p_age)
 ORDER BY s.updated_at LIMIT 100;
END $$;
REVOKE ALL ON FUNCTION mcp_v15.runtime_stale_running(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mcp_v15.runtime_stale_running(integer) TO mcp_v15_runtime_test;
COMMIT;
