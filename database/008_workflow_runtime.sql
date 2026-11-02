-- M3-01 V0.2.1: compatible with M2 schema.sql instance_id PK and approval_tasks FK.
-- Apply to a database already migrated through 007; never rename/drop M2 primary key.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='platform' AND table_name='workflow_instances' AND column_name='instance_id') THEN
  RAISE EXCEPTION 'M2 workflow_instances(instance_id) is required';
 END IF;
END $$;
ALTER TABLE platform.workflow_instances ADD COLUMN IF NOT EXISTS mrp_run_id TEXT;
ALTER TABLE platform.workflow_instances ADD COLUMN IF NOT EXISTS error_code TEXT;
ALTER TABLE platform.workflow_instances ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE platform.workflow_instances ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
-- M2 version default 1 remains unchanged; M3 creates explicitly at version 0.
CREATE TABLE IF NOT EXISTS platform.workflow_inbox (
 event_id TEXT PRIMARY KEY,
 instance_id TEXT NOT NULL REFERENCES platform.workflow_instances(instance_id),
 event_type TEXT NOT NULL, payload_hash TEXT NOT NULL, resulting_version BIGINT NOT NULL,
 processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workflow_inbox_instance_idx ON platform.workflow_inbox(instance_id);
CREATE TABLE IF NOT EXISTS platform.workflow_outbox (
 message_id BIGSERIAL PRIMARY KEY,
 instance_id TEXT NOT NULL REFERENCES platform.workflow_instances(instance_id),
 event_id TEXT NOT NULL REFERENCES platform.workflow_inbox(event_id),
 topic TEXT NOT NULL, payload JSONB NOT NULL,
 status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), delivered_at TIMESTAMPTZ,
 CONSTRAINT workflow_outbox_status CHECK (status IN ('PENDING','DELIVERED')),
 CONSTRAINT workflow_outbox_unique_event_topic UNIQUE(event_id,topic)
);
CREATE INDEX IF NOT EXISTS workflow_outbox_pending_idx ON platform.workflow_outbox(message_id) WHERE status='PENDING';
CREATE TABLE IF NOT EXISTS platform.workflow_audit (
 audit_id BIGSERIAL PRIMARY KEY,
 instance_id TEXT NOT NULL REFERENCES platform.workflow_instances(instance_id),
 event_id TEXT NOT NULL REFERENCES platform.workflow_inbox(event_id),
 from_state TEXT NOT NULL, to_state TEXT NOT NULL, version BIGINT NOT NULL,
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(instance_id,version)
);
COMMIT;
