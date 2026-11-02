-- Batch B additive schema. Apply ONLY to isolated industrial_lab_v14_test until signed off.
-- No references or write privileges to SRM/MRP/MES/Workflow business tables.
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
-- Database-enforced immutable version metadata and immutable execution evidence.
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
-- Public-facing read-only views; do not grant direct access to base tables.
CREATE OR REPLACE VIEW mapping_v14.public_executions AS
 SELECT execution_id,mapping_id,mapping_version,status,result_hash,created_at
 FROM mapping_v14.execution_runs;
CREATE OR REPLACE VIEW mapping_v14.public_versions AS
 SELECT mapping_id,mapping_version,status,created_at FROM mapping_v14.mapping_versions;
-- Optional dedicated NOLOGIN read-only role. Never grant business table privileges.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mapping_v14_readonly') THEN
   CREATE ROLE mapping_v14_readonly NOLOGIN;
 END IF;
END $$;
REVOKE ALL ON SCHEMA mapping_v14 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA mapping_v14 FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA mapping_v14 FROM PUBLIC;
GRANT USAGE ON SCHEMA mapping_v14 TO mapping_v14_readonly;
GRANT SELECT ON mapping_v14.public_executions,mapping_v14.public_versions TO mapping_v14_readonly;
REVOKE ALL ON mapping_v14.mapping_versions,mapping_v14.execution_runs,
 mapping_v14.execution_errors,mapping_v14.audit_events FROM mapping_v14_readonly;
-- Application DB identity must NOT be the schema owner for read-only access.
-- Bind a login role to mapping_v14_readonly only after explicit security review.
