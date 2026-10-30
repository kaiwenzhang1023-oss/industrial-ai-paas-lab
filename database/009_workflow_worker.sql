-- M3-01 V0.2: lease-based outbox worker. Apply after 008.
ALTER TABLE platform.workflow_outbox ADD COLUMN IF NOT EXISTS lease_owner TEXT;
ALTER TABLE platform.workflow_outbox ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ;
ALTER TABLE platform.workflow_outbox ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE platform.workflow_outbox ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE platform.workflow_outbox ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;
ALTER TABLE platform.workflow_outbox DROP CONSTRAINT IF EXISTS workflow_outbox_status;
ALTER TABLE platform.workflow_outbox ADD CONSTRAINT workflow_outbox_status CHECK (status IN ('PENDING','PROCESSING','DELIVERED','DEAD'));
CREATE INDEX IF NOT EXISTS workflow_outbox_claim_idx ON platform.workflow_outbox(next_attempt_at,message_id) WHERE status IN ('PENDING','PROCESSING');
-- Application-layer callbacks are never executed inside a database transaction.
