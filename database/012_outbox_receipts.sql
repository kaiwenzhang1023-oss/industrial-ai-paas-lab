-- V1.0: idempotent local audit sink, not an external broker delivery.
CREATE TABLE IF NOT EXISTS platform.outbox_delivery_receipts (
    event_id TEXT PRIMARY KEY,
    message_id BIGINT NOT NULL UNIQUE REFERENCES platform.workflow_outbox(message_id),
    topic TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
