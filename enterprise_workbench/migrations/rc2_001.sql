-- Apply only to isolated PG16 test database after reviewing migration.
CREATE SCHEMA IF NOT EXISTS version_b_rc2;
CREATE TABLE IF NOT EXISTS version_b_rc2.run_tenants (
 tenant_id text NOT NULL, run_id text NOT NULL, actor_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (tenant_id,run_id), UNIQUE(run_id));
CREATE TABLE IF NOT EXISTS version_b_rc2.reconciliation (
 tenant_id text NOT NULL, run_id text NOT NULL, actor_id text NOT NULL,
 idempotency_key text NOT NULL, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,idempotency_key),
 FOREIGN KEY (tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id));
CREATE TABLE IF NOT EXISTS version_b_rc2.decisions (
 tenant_id text NOT NULL, run_id text NOT NULL, actor_id text NOT NULL,
 idempotency_key text NOT NULL, decision text NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
 reason text NOT NULL, command_id uuid NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,idempotency_key),
 FOREIGN KEY (tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id));
CREATE TABLE IF NOT EXISTS version_b_rc2.outbox (
 command_id uuid PRIMARY KEY, tenant_id text NOT NULL, run_id text NOT NULL,
 payload jsonb NOT NULL, status text NOT NULL DEFAULT 'PENDING'
 CHECK(status IN ('PENDING','CLAIMED','RETRY','DONE','DEAD')),
 attempts integer NOT NULL DEFAULT 0, last_error text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id));
CREATE TABLE IF NOT EXISTS version_b_rc2.audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, tenant_id text NOT NULL,
 actor_id text NOT NULL, action text NOT NULL, ref_id text NOT NULL,
 details jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS rc2_outbox_poll ON version_b_rc2.outbox(status,created_at);
