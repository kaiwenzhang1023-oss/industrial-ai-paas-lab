-- Version B RC2 G2 additive migration: apply AFTER rc2_001.sql.
-- G1 proof of five original RC2 tables remains unchanged.
ALTER TABLE version_b_rc2.outbox ADD COLUMN IF NOT EXISTS lease_owner text;
ALTER TABLE version_b_rc2.outbox ADD COLUMN IF NOT EXISTS lease_until timestamptz;
ALTER TABLE version_b_rc2.outbox ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS rc2_outbox_lease_poll ON version_b_rc2.outbox(status,next_attempt_at,lease_until,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS rc2_single_terminal_decision ON version_b_rc2.decisions(tenant_id,run_id);
CREATE TABLE IF NOT EXISTS version_b_rc2.workflow_states (
 tenant_id text NOT NULL, run_id text NOT NULL, status text NOT NULL DEFAULT 'WAITING_REVIEW'
 CHECK(status IN ('WAITING_REVIEW','APPROVED_QUEUED','REJECTED','RUNNING','RETRY_PENDING','EXECUTED_INTERNAL','FAILED_TERMINAL')),
 version bigint NOT NULL DEFAULT 0, updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,run_id),
 FOREIGN KEY(tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id));
CREATE TABLE IF NOT EXISTS version_b_rc2.execution_receipts (
 command_id uuid PRIMARY KEY REFERENCES version_b_rc2.outbox(command_id),
 tenant_id text NOT NULL, run_id text NOT NULL, result jsonb NOT NULL,
 processed_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id));
CREATE TABLE IF NOT EXISTS version_b_rc2.run_inputs (
 tenant_id text NOT NULL, run_id text NOT NULL, input_hash text NOT NULL,
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,run_id),
 FOREIGN KEY(tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id));
