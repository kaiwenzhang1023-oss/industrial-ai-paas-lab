BEGIN;
CREATE TABLE IF NOT EXISTS platform.agent_drafts (
 draft_id BIGSERIAL PRIMARY KEY,
 workflow_id TEXT NOT NULL REFERENCES platform.workflow_instances(instance_id),
 mrp_run_id TEXT NOT NULL REFERENCES platform.requirement_runs(run_id),
 workflow_version BIGINT NOT NULL,
 model_id TEXT NOT NULL,
 facts_hash TEXT NOT NULL,
 draft_hash TEXT NOT NULL,
 draft JSONB NOT NULL,
 tool_trace JSONB NOT NULL,
 status TEXT NOT NULL DEFAULT 'WAITING_REVIEW' CHECK(status IN ('WAITING_REVIEW','REJECTED','ACCEPTED')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(workflow_id,workflow_version)
);
CREATE INDEX IF NOT EXISTS agent_drafts_workflow_idx ON platform.agent_drafts(workflow_id);
COMMIT;
