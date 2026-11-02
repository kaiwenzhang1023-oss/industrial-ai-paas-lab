-- DEVELOPMENT BRANCH ONLY: dev-v1-6-backend-pg18. Confirm branch in Neon UI first.
-- Safe to run ONCE. This does NOT create a LOGIN credential or modify production.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$ BEGIN
 IF current_database() <> 'industrial_lab_demo' THEN RAISE EXCEPTION 'Wrong database'; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mapping_v14_readonly' AND NOT rolcanlogin) THEN RAISE EXCEPTION 'Mapping NOLOGIN prerequisite missing'; END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='portfolio_v16_reader') THEN RAISE EXCEPTION 'Reader group already exists: inspect before retry'; END IF;
END $$;
CREATE ROLE portfolio_v16_reader NOLOGIN;
GRANT USAGE ON SCHEMA mes_v13,srm_v14 TO portfolio_v16_reader;
GRANT SELECT ON TABLE mes_v13.work_orders,srm_v14.purchase_requisitions,srm_v14.supply_exceptions TO portfolio_v16_reader;
-- Inherit ONLY the approved Mapping views; no base-table grants.
GRANT mapping_v14_readonly TO portfolio_v16_reader;
COMMIT;
