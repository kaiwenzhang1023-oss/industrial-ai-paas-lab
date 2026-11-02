-- RC2 REVIEW CANDIDATE / NOT APPROVED FOR EXECUTION UNTIL REVIEWED.
-- Source: V16_STAGING_MAPPING.sql; target: Neon development branch dev-v1-6-backend-pg18.
-- Neon branch cannot be securely identified by current_database(); VERIFY branch in console.
-- Do not run on production. No live credentials included.
BEGIN;
-- MANUAL CONFIRMATION ONLY: does not technically verify Neon branch.
SET LOCAL v16.operator_confirmed_dev_branch = 'dev-v1-6-backend-pg18';
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
DO $guard$
BEGIN
 IF current_database() <> 'industrial_lab_demo' THEN
   RAISE EXCEPTION 'Unexpected database: %', current_database();
 END IF;
 IF current_setting('v16.operator_confirmed_dev_branch', true) IS DISTINCT FROM 'dev-v1-6-backend-pg18' THEN
   RAISE EXCEPTION 'Operator branch confirmation missing. This does NOT verify Neon branch.';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='lab_schema_migrations') THEN
   RAISE EXCEPTION 'Missing migration ledger';
 END IF;
 IF EXISTS (SELECT 1 FROM public.lab_schema_migrations WHERE filename='023_v16_mapping_pg18.sql') THEN
   RAISE EXCEPTION 'Already applied: 023_v16_mapping_pg18.sql';
 END IF;
END $guard$;
CREATE SCHEMA IF NOT EXISTS mapping_v14;
CREATE TABLE IF NOT EXISTS mapping_v14.mapping_versions (
 mapping_id text NOT NULL, mapping_version text NOT NULL,
 status text NOT NULL CHECK(status IN ('DRAFT','VALIDATED','PUBLISHED','RETIRED')),
 rules_hash text NOT NULL CHECK(length(rules_hash)=64),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(mapping_id,mapping_version));
CREATE TABLE IF NOT EXISTS mapping_v14.execution_runs (
 execution_id text PRIMARY KEY CHECK(length(execution_id)>0),
 mapping_id text NOT NULL, mapping_version text NOT NULL,
 request_hash text NOT NULL CHECK(length(request_hash)=64),
 request_json jsonb NOT NULL, response_json jsonb NOT NULL,
 result_hash text CHECK(result_hash IS NULL OR length(result_hash)=64),
 status text NOT NULL CHECK(status IN ('VALID','REJECTED')),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(mapping_id,mapping_version) REFERENCES mapping_v14.mapping_versions(mapping_id,mapping_version));
CREATE TABLE IF NOT EXISTS mapping_v14.execution_errors (
 execution_id text NOT NULL REFERENCES mapping_v14.execution_runs(execution_id),
 error_index integer NOT NULL CHECK(error_index>=0), error_json jsonb NOT NULL,
 PRIMARY KEY(execution_id,error_index));
CREATE TABLE IF NOT EXISTS mapping_v14.audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 execution_id text NOT NULL REFERENCES mapping_v14.execution_runs(execution_id),
 action text NOT NULL CHECK(action IN ('EXECUTE','REPLAY')),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE OR REPLACE FUNCTION mapping_v14.deny_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'MAPPING_IMMUTABLE_RECORD'; END $$;
DROP TRIGGER IF EXISTS mapping_versions_immutable ON mapping_v14.mapping_versions;
CREATE TRIGGER mapping_versions_immutable BEFORE UPDATE OR DELETE ON mapping_v14.mapping_versions
 FOR EACH ROW EXECUTE FUNCTION mapping_v14.deny_mutation();
DROP TRIGGER IF EXISTS execution_runs_immutable ON mapping_v14.execution_runs;
CREATE TRIGGER execution_runs_immutable BEFORE UPDATE OR DELETE ON mapping_v14.execution_runs
 FOR EACH ROW EXECUTE FUNCTION mapping_v14.deny_mutation();
DROP TRIGGER IF EXISTS execution_errors_immutable ON mapping_v14.execution_errors;
CREATE TRIGGER execution_errors_immutable BEFORE UPDATE OR DELETE ON mapping_v14.execution_errors
 FOR EACH ROW EXECUTE FUNCTION mapping_v14.deny_mutation();
DROP TRIGGER IF EXISTS audit_events_immutable ON mapping_v14.audit_events;
CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON mapping_v14.audit_events
 FOR EACH ROW EXECUTE FUNCTION mapping_v14.deny_mutation();
CREATE OR REPLACE VIEW mapping_v14.public_executions AS
 SELECT execution_id,mapping_id,mapping_version,status,result_hash,created_at
 FROM mapping_v14.execution_runs;
CREATE OR REPLACE VIEW mapping_v14.public_versions AS
 SELECT mapping_id,mapping_version,status,created_at FROM mapping_v14.mapping_versions;

INSERT INTO public.lab_schema_migrations(filename,applied_at)
VALUES ('023_v16_mapping_pg18.sql', now());
COMMIT;
