DO $$ BEGIN IF current_database() <> 'industrial_lab_v15_test' THEN RAISE EXCEPTION 'wrong database'; END IF; END $$;
DROP SCHEMA IF EXISTS mcp_v15 CASCADE;
